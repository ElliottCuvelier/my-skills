#!/usr/bin/env python3
"""
Audit a repo against the js-ts-conventions catalog.

Runs every lint-enforced preference through the repo's own linter (oxlint or
ESLint flat config, isolated from the repo's rules), checks tsconfig strictness
and repo-config conflicts, gathers signals for the agent-reviewed preferences,
and writes:

    <out>/audit.json   machine-readable results (input for PLAN.md and enforce)
    <out>/REPORT.md    human report; the agent fills the "Agent review" section

Nothing outside <out> is modified unless --fix is passed.

Usage:
    python3 scripts/audit.py [--root .] [--out .js-ts-conventions] [--tsc-impact] [--timeout 600]
    python3 scripts/audit.py --fix [--only type-imports]   # apply autofixes for convention rules only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze_repo import alias_scopes, analyze  # noqa: E402
from lint_engine import oxlint_entries_for, run_unit  # noqa: E402
from utils import (  # noqa: E402
    PLUGIN_NAMESPACE, SKILL_VERSION, STATE_DIR, applicable_preferences, glob_match, convention_rules, is_agent_tooling,
    load_catalog, load_overrides, local_bin, now_iso, preference_by_id, rel, source_files, write_json,
)

SEVERITY_RANK = {"off": 0, "allow": 0, "0": 0, "warn": 1, "1": 1, "error": 2, "deny": 2, "2": 2}
REDUNDANT = {
    "unicorn/no-null": "no-null",
    "unicorn/filename-case": "filename-case",
    "@typescript-eslint/naming-convention": "naming",
}
TS_EXTENSIONS = (".ts", ".tsx", ".mts", ".cts")
SIGNALS = {
    "result-type": [("files using `Result.ok(`/`Result.err(`", r"\bResult\.(?:ok|err)\("),
                    ("`static create(` factories", r"\bstatic\s+create\s*\(")],
    "value-object-structure": [("classes extending `ValueObject`", r"extends\s+ValueObject\b"),
                               ("private constructors", r"private\s+constructor\s*\(")],
    "zod-at-boundaries": [("files declaring `z.object(` schemas", r"\bz\.object\("),
                          ("files using `z.infer`", r"\bz\.infer<"),
                          ("hand-written `*Dto` interfaces", r"\binterface\s+\w+Dto\b")],
    "iso-standards": [("`toLocaleDateString(`/`toLocaleString(` calls", r"\.toLocale(?:Date)?String\("),
                      ("`.datetime()` validators", r"\.datetime\(\)")],
    "jsdoc-public-api": [("exported functions/classes", r"^export\s+(?:default\s+)?(?:async\s+)?(?:function|class|abstract\s+class)\b")],
}


def severity_rank(value: Any) -> int:
    if isinstance(value, list):
        value = value[0] if value else "off"
    return SEVERITY_RANK.get(str(value).lower(), 0)


# ---------------------------------------------------------------------------
# Config checks
# ---------------------------------------------------------------------------

def tsconfig_gaps(snapshot: dict, catalog: dict, overrides: dict) -> list[dict]:
    pref = preference_by_id(catalog).get("strict-compiler")
    if not pref or pref["id"] in overrides.get("disabled", {}):
        return []
    required = pref["enforce"]["tsconfig"]
    gaps = []
    for tsconfig in snapshot["tsconfigs"]:
        if any(part.startswith(".") and part != "." for part in tsconfig["dir"].split("/")):
            continue
        missing = [flag for flag, value in required.items() if tsconfig["flags"].get(flag) != value]
        if missing:
            gaps.append({"tsconfig": tsconfig["path"], "missing": missing})
    return gaps


def tsc_impact(root: Path, gaps: list[dict], timeout: int) -> None:
    """Count the extra type errors each missing flag would surface (best effort)."""
    for gap in gaps:
        path = root / gap["tsconfig"]
        tsc = local_bin(path.parent, root, "tsc")
        if not tsc:
            gap["impact_error"] = "tsc not installed"
            continue

        def count(extra: list[str]) -> int | None:
            try:
                proc = subprocess.run([str(tsc), "-p", str(path), "--noEmit", "--pretty", "false", *extra],
                                      cwd=path.parent, capture_output=True, text=True, timeout=timeout)
            except (OSError, subprocess.SubprocessError):
                return None
            return len(re.findall(r"error TS\d+", proc.stdout + proc.stderr))

        baseline = count([])
        if baseline is None:
            gap["impact_error"] = "tsc timed out or failed"
            continue
        gap["baseline_errors"] = baseline
        gap["impact"] = {}
        for flag in gap["missing"]:
            with_flag = count([f"--{flag}", "true"])
            gap["impact"][flag] = None if with_flag is None else max(with_flag - baseline, 0)


def eslint_effective_rules(root: Path, unit: dict, files: list[str], timeout: int) -> dict | None:
    if not unit.get("binary") or unit.get("format") != "flat":
        return None
    prefix = "" if unit["dir"] == "." else unit["dir"] + "/"
    nested = tuple(n + "/" for n in unit.get("nested_units", []))
    sample = next((f for f in files if f.startswith(prefix) and f.endswith(TS_EXTENSIONS)
                   and not f.endswith(".d.ts") and not f.startswith(nested)), None)
    if not sample:
        return None
    try:
        proc = subprocess.run([unit["binary"], "--print-config", sample[len(prefix):]], cwd=root / unit["dir"],
                              capture_output=True, text=True, timeout=timeout,
                              env={**os.environ, "ESLINT_USE_FLAT_CONFIG": "true"})
        data = json.loads(proc.stdout[proc.stdout.find("{"):])
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return {"sample": sample, "rules": data.get("rules", {})}


def config_conflicts(root: Path, snapshot: dict, catalog: dict, overrides: dict, files: list[str],
                     timeout: int) -> list[dict]:
    """Repo settings that disagree with the conventions.

    kind "weaker": the repo setting wins over the conventions (oxlint: the repo's own
    `overrides`; ESLint: a block after the wrapper). "shadowed": the conventions win once
    wired (oxlint top-level `rules`; ESLint settings in an unwired config), so the setting
    only misleads readers. "redundant": a stock rule the conventions replace.
    """
    conflicts = []
    for unit in snapshot["lint_units"]:
        entries = convention_rules(catalog, overrides, unit["tool"], snapshot, unit, type_aware=True)
        wanted = {e["rule"]: e for e in entries}
        if unit["tool"] == "oxlint":
            sources = [(unit["config"], unit.get("rules") or {}, "shadowed")]
            for override in unit.get("overrides") or []:
                globs = ", ".join(override.get("files") or [])
                sources.append((f"{unit['config']} overrides [{globs}]", override.get("rules") or {}, "weaker"))
        else:
            effective = eslint_effective_rules(root, unit, files, timeout)
            if not effective:
                continue
            wired = any(rule.startswith(PLUGIN_NAMESPACE + "/") for rule in effective["rules"])
            sources = [(f"{unit['config']} (effective for {effective['sample']})", effective["rules"],
                        "weaker" if wired else "shadowed")]
        for where, repo_rules, kind in sources:
            for rule, value in repo_rules.items():
                if rule in wanted and severity_rank(value) < severity_rank(wanted[rule]["severity"]):
                    conflicts.append({"unit": unit["dir"], "where": where, "rule": rule, "pref": wanted[rule]["pref"],
                                      "repo": value if not isinstance(value, list) else value[0],
                                      "conventions": wanted[rule]["severity"], "kind": kind})
                elif rule in REDUNDANT and severity_rank(value) > 0:
                    conflicts.append({"unit": unit["dir"], "where": where, "rule": rule, "pref": REDUNDANT[rule],
                                      "kind": "redundant"})
    return conflicts


# ---------------------------------------------------------------------------
# Signals for agent-reviewed preferences
# ---------------------------------------------------------------------------

def gather_signals(root: Path, files: list[str], pref_ids: set[str]) -> dict[str, list[dict]]:
    wanted = {pid: patterns for pid, patterns in SIGNALS.items() if pid in pref_ids}
    if not wanted:
        return {}
    compiled = {pid: [(label, re.compile(rx, re.M)) for label, rx in patterns] for pid, patterns in wanted.items()}
    counts: dict[str, Counter] = {pid: Counter() for pid in wanted}
    jsdoc_documented = 0
    ts_files = [f for f in files if f.endswith(TS_EXTENSIONS) and not f.endswith(".d.ts")][:4000]
    for path in ts_files:
        try:
            text = (root / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pid, patterns in compiled.items():
            for label, rx in patterns:
                hits = rx.findall(text)
                if hits:
                    # "files ..." signals count files; the others count occurrences.
                    counts[pid][label] += 1 if label.startswith("files ") else len(hits)
        if "jsdoc-public-api" in wanted:
            jsdoc_documented += len(re.findall(r"\*/\s*\n\s*export\s+(?:default\s+)?(?:async\s+)?(?:function|class|abstract\s+class)\b", text))
    result = {pid: [{"label": label, "count": counts[pid][label]} for label, _ in patterns]
              for pid, patterns in wanted.items()}
    if "jsdoc-public-api" in result:
        result["jsdoc-public-api"].append({"label": "of those preceded by a JSDoc block", "count": jsdoc_documented})
    return result


def heuristic_counts(root: Path, files: list[str], pref: dict) -> dict | None:
    pattern = pref.get("heuristic")
    if not pattern:
        return None
    rx = re.compile(pattern, re.M)
    total, per_file = 0, Counter()
    for path in [f for f in files if f.endswith(TS_EXTENSIONS + (".js", ".jsx", ".mjs", ".cjs"))][:4000]:
        try:
            hits = len(rx.findall((root / path).read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
        if hits:
            per_file[path] = hits
            total += hits
    return {"violations": total, "files": len(per_file), "top_files": per_file.most_common(5)}


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def area_of(path: str) -> str:
    parts = path.split("/")
    return "/".join(parts[: min(3, len(parts) - 1)]) or "."


def aggregate(catalog: dict, overrides: dict, snapshot: dict, unit_results: list[dict],
              root: Path, files: list[str], gaps: list[dict]) -> list[dict]:
    applicable = {p["id"] for p in applicable_preferences(catalog, overrides, snapshot)}
    any_alias = any(u.get("alias_scopes") for u in snapshot["lint_units"]) or any(
        t["alias"] for t in snapshot["tsconfigs"])
    by_pref: dict[str, list[dict]] = defaultdict(list)
    measured: dict[str, set[str]] = defaultdict(set)
    # pref -> reason -> (rules, units)
    skipped: dict[str, dict[str, tuple[set, set]]] = defaultdict(dict)
    for unit_result in unit_results:
        rule_pref = {e["rule"]: e["pref"] for e in unit_result["entries"]}
        for violation in unit_result["violations"]:
            by_pref[rule_pref[violation["rule"]]].append(violation)
        ran = {e["rule"] for e in unit_result["entries"]} - {s["rule"] for s in unit_result.get("skipped", [])}
        if not unit_result.get("errors"):
            for rule in ran:
                measured[rule_pref[rule]].add(f"{unit_result['engine']} ({unit_result['dir']})")
        for skip in unit_result.get("skipped", []):
            rules, units = skipped[rule_pref.get(skip["rule"], "?")].setdefault(skip["reason"], (set(), set()))
            rules.add(skip["rule"])
            units.add(unit_result["dir"])

    results = []
    for pref in catalog["preferences"]:
        pid = pref["id"]
        entry: dict[str, Any] = {"id": pid, "title": pref["title"], "level": pref["level"],
                                 "section": pref["section"], "autofix": pref.get("autofix", "none")}
        lintable = bool(pref["enforce"].get("eslint") or pref["enforce"].get("oxlint"))
        if pid not in applicable:
            reason = ("disabled in overrides: " + str(overrides["disabled"][pid])) if pid in overrides["disabled"] \
                else "no DDD layout (domain/application/infrastructure folders) detected"
            entry.update(status="n/a", reason=reason)
        elif pref.get("requires") == "path_alias" and not any_alias:
            entry.update(status="n/a", reason="no tsconfig path alias (`@/*`) defined")
        elif pid == "strict-compiler":
            if not snapshot["tsconfigs"]:
                entry.update(status="n/a", reason="no tsconfig.json (plain JavaScript)")
            elif gaps:
                entry.update(status="config")
            else:
                entry.update(status="pass", violations=0, files=0, measured_by=["tsconfig"])
        elif not lintable:
            entry.update(status="review", review=pref.get("review", ""))
        elif measured.get(pid):
            violations = sorted(by_pref.get(pid, []), key=lambda v: (v["file"], v["line"]))
            per_file = Counter(v["file"] for v in violations)
            entry.update(
                status="fail" if violations else "pass",
                violations=len(violations),
                files=len(per_file),
                top_files=per_file.most_common(5),
                by_area=Counter(area_of(v["file"]) for v in violations).most_common(10),
                samples=[{k: v[k] for k in ("file", "line", "message")} for v in violations[:3]],
                measured_by=sorted(measured[pid]),
                per_file=dict(per_file),
            )
            if pref.get("boundary_hints") and violations:
                entry["boundary_candidates"] = [
                    {"glob": glob, "violations": sum(n for f, n in per_file.items() if glob_match(f, [glob]))}
                    for glob in pref["boundary_hints"]
                ]
                entry["boundary_candidates"] = [c for c in entry["boundary_candidates"] if c["violations"]]
        else:
            heuristic = heuristic_counts(root, files, pref)
            entry.update(status="unmeasured", heuristic=heuristic)
        if skipped.get(pid):
            entry["skipped"] = [
                f"{', '.join(f'`{r}`' for r in sorted(rules))} in {', '.join(f'`{u}`' for u in sorted(units))}: {reason}"
                for reason, (rules, units) in skipped[pid].items()
            ]
        results.append(entry)
    return results


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

STATUS_ICON = {"pass": "✅", "fail": "❌", "review": "🔍", "config": "⚙️", "n/a": "➖", "unmeasured": "❔"}


def fix_label(entry: dict) -> str:
    return {"full": "auto", "partial": "partly auto"}.get(entry.get("autofix"), "manual")


def render_report(audit: dict) -> str:
    prefs = audit["preferences"]
    failing = [p for p in prefs if p["status"] == "fail"]
    total = sum(p["violations"] for p in failing)
    file_total = len({f for p in failing for f in p.get("per_file", {})})
    autofix = sum(p["violations"] for p in failing if p["autofix"] == "full")
    gaps = audit["tsconfig_gaps"]
    lines = [
        f"# js-ts-conventions audit: {audit['repo']}",
        "",
        f"{audit['generated_at'][:10]} · catalog v{audit['catalog_version']} · skill {audit['skill_version']}",
        "Engines: " + (" · ".join(f"{u['engine']} {u.get('version') or ''} (`{u['dir']}`)".replace("  ", " ")
                                  for u in audit["units"]) or "none"),
        "",
        "## Summary",
        "",
        f"**{total} violations** across **{len(failing)} preferences** in **{file_total} files**. "
        f"{autofix} are autofixable. {sum(len(g['missing']) for g in gaps)} tsconfig flags are missing.",
        "",
        "| | Preference | Level | Violations | Files | Fix |",
        "|---|---|---|---:|---:|---|",
    ]
    order = {"fail": 0, "config": 1, "unmeasured": 2, "review": 3, "pass": 4, "n/a": 5}
    for p in sorted(prefs, key=lambda p: (order[p["status"]], p["level"] != "must", -p.get("violations", 0))):
        icon = STATUS_ICON[p["status"]]
        if p["status"] == "fail":
            cells = [str(p["violations"]), str(p["files"]), fix_label(p)]
        elif p["status"] == "pass":
            cells = ["0", "0", ""]
        elif p["status"] == "config":
            cells = [f"{sum(len(g['missing']) for g in gaps)} flags", str(len(gaps)) + " tsconfigs", "config"]
        elif p["status"] == "unmeasured":
            h = p.get("heuristic") or {}
            cells = [f"~{h.get('violations', '?')} (grep)", f"~{h.get('files', '?')}", fix_label(p)]
        elif p["status"] == "review":
            cells = ["agent review", "", ""]
        else:
            cells = [p.get("reason", ""), "", ""]
        lines.append(f"| {icon} | {p['title']} (`{p['id']}`) | {p['level']} | " + " | ".join(cells) + " |")

    lines += ["", "## Config discrepancies", ""]
    config_lines = []
    for gap in gaps:
        impact = ""
        if gap.get("impact"):
            impact = " · new type errors if enabled: " + ", ".join(
                f"`{flag}` +{n if n is not None else '?'}" for flag, n in gap["impact"].items())
        config_lines.append(f"- `{gap['tsconfig']}`: missing " + ", ".join(f"`{m}`" for m in gap["missing"]) + impact)
    for c in audit["conflicts"]:
        if c["kind"] == "weaker":
            config_lines.append(f"- `{c['where']}` sets `{c['rule']}` to `{c['repo']}` and wins over the conventions "
                                f"(`{c['conventions']}`, `{c['pref']}`). Remove it, or record the exception in overrides.json.")
        elif c["kind"] == "shadowed":
            config_lines.append(f"- `{c['where']}` sets `{c['rule']}` to `{c['repo']}`; the conventions override it once "
                                f"wired (`{c['conventions']}`, `{c['pref']}`). Remove the setting so the config doesn't mislead.")
        else:
            config_lines.append(f"- `{c['where']}`: `{c['rule']}` is redundant once `{c['pref']}` is enforced.")
    for path in audit["existing_style_rules"]:
        config_lines.append(f"- `{path}` already states style rules; reconcile it with the generated convention rules.")
    for warning in audit["warnings"]:
        config_lines.append(f"- {warning}")
    lines += config_lines or ["None."]

    lines += ["", "## Violations by preference", ""]
    for p in [p for p in prefs if p["status"] == "fail"]:
        lines += [f"### ❌ {p['title']}: {p['violations']} in {p['files']} files ({p['level']}, {fix_label(p)})", ""]
        lines.append("Top files: " + ", ".join(f"`{f}` ({n})" for f, n in p["top_files"]))
        lines.append("")
        lines += [f"- `{s['file']}:{s['line']}` {s['message']}" for s in p["samples"]]
        if p.get("boundary_candidates"):
            lines += ["", "Boundary candidates (exempt in `overrides.json` if these are real boundaries): "
                      + ", ".join(f"`{c['glob']}` ({c['violations']})" for c in p["boundary_candidates"])]
        if p.get("skipped"):
            lines += ["", "Not run: " + "; ".join(p["skipped"])]
        lines.append("")
    if not failing:
        lines += ["No lint violations.", ""]

    unmeasured = [p for p in prefs if p["status"] == "unmeasured"]
    skipped_only = [p for p in prefs if p["status"] in ("pass",) and p.get("skipped")]
    if unmeasured or skipped_only:
        lines += ["## Not measured", ""]
        for p in unmeasured:
            h = p.get("heuristic")
            detail = f"grep estimate ~{h['violations']} in {h['files']} files" if h else "no estimate"
            lines.append(f"- `{p['id']}`: no linter could run ({detail}). " + "; ".join(p.get("skipped", [])))
        for p in skipped_only:
            lines.append(f"- `{p['id']}`: " + "; ".join(p["skipped"]))
        lines.append("")

    reviews = [p for p in prefs if p["status"] == "review"]
    if reviews:
        lines += ["## Agent review", "",
                  "_Filled in by the agent after sampling the code. Replace each `Findings` line._", ""]
        for p in reviews:
            lines += [f"### 🔍 {p['title']} ({p['level']})", ""]
            for signal in audit["signals"].get(p["id"], []):
                lines.append(f"- Signal: {signal['count']} {signal['label']}")
            lines += [f"- Check: {p.get('review', '')}", "- Findings: _pending_", ""]

    not_applicable = [p for p in prefs if p["status"] == "n/a"]
    if not_applicable:
        lines += ["## Not applicable", ""]
        lines += [f"- `{p['id']}`: {p['reason']}" for p in not_applicable]
        lines.append("")
    lines += ["---", "Next: write `PLAN.md` from this report (see the skill's `references/AUDIT.md`), "
              "then run enforce."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def audit_units(root: Path, snapshot: dict, catalog: dict, overrides: dict, timeout: int,
                fix: bool = False, only: set[str] | None = None) -> list[dict]:
    units = list(snapshot["lint_units"])
    if not units:
        virtual = {"dir": ".", "tool": "oxlint", "config": None, "binary": None, "nested_units": [],
                   "decorator_metadata": snapshot["decorator_metadata"], "ignore_patterns": []}
        virtual["alias_scopes"] = alias_scopes(virtual, snapshot["tsconfigs"])
        units = [virtual]
    results = []
    for unit in units:
        type_aware = unit["tool"] == "eslint" or bool(unit.get("type_aware_available"))
        entries = convention_rules(catalog, overrides, unit["tool"], snapshot, unit, type_aware=type_aware)
        if fix:
            entries = [e for e in entries if (e["pref"] in only if only else e["autofix"] == "full")]
        if not entries:
            continue
        print(f"→ {unit['tool']} on `{unit['dir']}` ({len(entries)} convention rules)…", file=sys.stderr)
        result = run_unit(root, unit, entries, catalog, timeout=timeout, fix=fix)
        result["dir"] = unit["dir"]
        result["entries"] = oxlint_entries_for(entries, catalog) if result.get("fallback_reason") else entries
        results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".", help="Repository root (default: cwd)")
    parser.add_argument("--out", help=f"Output directory (default: <root>/{STATE_DIR})")
    parser.add_argument("--timeout", type=int, default=600, help="Seconds per linter run")
    parser.add_argument("--tsc-impact", action="store_true", help="Count type errors each missing tsconfig flag adds")
    parser.add_argument("--fix", action="store_true", help="Apply autofixes for convention rules only, then exit")
    parser.add_argument("--only", nargs="*", help="With --fix: preference ids to fix (default: all autofixable)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.out).resolve() if args.out else root / STATE_DIR
    catalog = load_catalog()
    overrides = load_overrides(root)
    snapshot = analyze(root)

    if args.fix:
        results = audit_units(root, snapshot, catalog, overrides, args.timeout, fix=True,
                              only=set(args.only) if args.only else None)
        for r in results:
            status = "; ".join(r["errors"]) if r["errors"] else f"{len(r['violations'])} left unfixed"
            print(f"{r['engine']} `{r['dir']}`: fixes applied · {status}")
        print("Re-run audit.py to refresh REPORT.md.")
        return 0

    files = [f for f in source_files(root) if not is_agent_tooling(f)]
    unit_results = audit_units(root, snapshot, catalog, overrides, args.timeout)
    gaps = tsconfig_gaps(snapshot, catalog, overrides)
    if args.tsc_impact and gaps:
        print("→ measuring tsconfig flag impact with tsc…", file=sys.stderr)
        tsc_impact(root, gaps, args.timeout)
    prefs = aggregate(catalog, overrides, snapshot, unit_results, root, files, gaps)
    review_ids = {p["id"] for p in prefs if p["status"] == "review"}
    warnings = list(snapshot["warnings"])
    for r in unit_results:
        warnings += [f"`{r['dir']}`: {e}" for e in r.get("errors", [])]
        if r.get("fallback_reason"):
            warnings.append(f"`{r['dir']}`: measured with oxlint instead of ESLint ({r['fallback_reason']}).")
        if r.get("parse_error_count"):
            warnings.append(f"`{r['dir']}`: {r['parse_error_count']} files failed to parse with the repo's ESLint config.")
    audit = {
        "skill_version": SKILL_VERSION,
        "catalog_version": catalog["catalog_version"],
        "generated_at": now_iso(),
        "repo": root.name,
        "root": str(root),
        "units": [{k: r.get(k) for k in ("dir", "engine", "version", "files_linted", "type_aware",
                                          "registered_plugins", "errors", "fallback_reason")}
                  for r in unit_results],
        "preferences": prefs,
        "tsconfig_gaps": gaps,
        "conflicts": config_conflicts(root, snapshot, catalog, overrides, files, args.timeout),
        "signals": gather_signals(root, files, review_ids),
        "existing_style_rules": snapshot["existing_style_rules"],
        "warnings": warnings,
        "snapshot": snapshot,
    }
    write_json(out / "audit.json", audit)
    (out / "REPORT.md").write_text(render_report(audit), encoding="utf-8")
    failing = [p for p in prefs if p["status"] == "fail"]
    print(f"{sum(p['violations'] for p in failing)} violations across {len(failing)} preferences · "
          f"{len(gaps)} tsconfigs with missing flags · {len(review_ids)} preferences need agent review")
    print(f"Wrote {rel(out / 'REPORT.md', root)} and {rel(out / 'audit.json', root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
