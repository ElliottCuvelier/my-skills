"""
Run convention rules through the repo's own linter, isolated from the repo's rules.

ESLint: a temp flat config imports the repo's config, keeps its parser/ignores/
plugins, drops its `rules`, and adds the convention rules (skipping rules whose
plugin namespace the repo never registers). oxlint: a temp config with only the
convention rules and the custom plugin. Both report JSON that is mapped back to
catalog preference ids.

Library module for audit.py / enforce.py. Stdlib only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from utils import (
    PLUGIN_NAMESPACE, PLUGIN_TEMPLATE, anchor_glob, normalize_oxlint_code, rel,
    rule_namespace, version_tuple,
)

OXLINT_CATEGORIES = ("correctness", "suspicious", "pedantic", "perf", "style", "restriction", "nursery")
OXLINT_NPX = ["npx", "--yes", "oxlint@1"]
JS_DEFAULT_FILES = ["**/*.js", "**/*.mjs", "**/*.cjs"]
ESLINT_SUPPRESSIONS_MIN = (9, 24, 0)


def _severity(entry: dict) -> list:
    return [entry["severity"], *entry["options"]]


def _unit_relative(dirs: list[str], unit_dir: str) -> list[str]:
    prefix = "" if unit_dir == "." else unit_dir + "/"
    return [d[len(prefix):] if prefix and d.startswith(prefix) else d for d in dirs]


def _run(cmd: list[str], cwd: Path, timeout: int, env: dict | None = None) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                              env={**os.environ, **(env or {})})
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s: {' '.join(cmd[:3])}"
    return proc.returncode, proc.stdout, proc.stderr


def _json_payload(text: str, opener: str) -> Any:
    start = text.find(opener)
    if start == -1:
        return None
    try:
        return json.loads(text[start:])
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# oxlint
# ---------------------------------------------------------------------------

def oxlint_config(entries: list[dict], catalog: dict, plugin_path: str, *, anchored: bool,
                  decorator_metadata: bool, ignore_patterns: list[str] | None = None,
                  legacy: dict[str, list[str]] | None = None, isolate: bool = False) -> dict:
    """Conventions oxlint config. `anchored` prefixes globs with `**/` (temp configs).

    `isolate` switches every category off so only convention rules run. Only for temp
    audit configs: in a config the repo extends, it would disable the repo's
    default rules too.
    """
    fix = anchor_glob if anchored else (lambda glob: glob)
    scopes = {rule_namespace(e["rule"]) for e in entries} - {None, PLUGIN_NAMESPACE}
    overrides: list[dict] = []
    for entry in entries:
        overrides.append({"files": [fix(g) for g in entry["files"]], "rules": {entry["rule"]: _severity(entry)}})
    if decorator_metadata and any(e["rule"] == "typescript/consistent-type-imports" for e in entries):
        overrides.append({"files": catalog["decorator_metadata_files"],
                          "rules": {"typescript/consistent-type-imports": "off"}})
    for entry in entries:
        if entry["exempt"]:
            overrides.append({"files": [fix(g) for g in entry["exempt"]], "rules": {entry["rule"]: "off"}})
    for rule, files in sorted((legacy or {}).items()):
        if files:
            overrides.append({"files": sorted(files), "rules": {rule: "off"}})
    if entries:
        overrides.append({"files": catalog["ignores"], "rules": {e["rule"]: "off" for e in entries}})
    for entry in entries:
        extra = [glob for glob in entry.get("ignores", []) if glob not in catalog["ignores"]]
        if extra:
            overrides.append({"files": extra, "rules": {entry["rule"]: "off"}})
    config: dict[str, Any] = {
        "plugins": sorted(scopes | {"typescript"}),
        "jsPlugins": [plugin_path],
        "overrides": overrides,
    }
    if isolate:
        config["categories"] = {category: "off" for category in OXLINT_CATEGORIES}
    if ignore_patterns:
        config["ignorePatterns"] = [fix(p.rstrip("/") + ("/**" if p.endswith("/") else "")) for p in ignore_patterns]
    return config


def oxlint_command(unit: dict) -> tuple[list[str], str]:
    if unit.get("binary"):
        return [unit["binary"]], "oxlint"
    if shutil.which("npx"):
        return list(OXLINT_NPX), "oxlint (npx stand-in)"
    return [], "none"


def parse_oxlint(payload: Any, unit_root: Path, root: Path, convention_ids: set[str]) -> list[dict]:
    violations = []
    for diag in (payload or {}).get("diagnostics", []):
        rule = normalize_oxlint_code(diag.get("code", ""))
        if rule not in convention_ids:
            continue
        span = (diag.get("labels") or [{}])[0].get("span", {})
        violations.append({
            "rule": rule,
            "file": rel(unit_root / diag.get("filename", ""), root),
            "line": span.get("line", 0),
            "column": span.get("column", 0),
            "message": diag.get("message", ""),
            "severity": "error" if diag.get("severity") == "error" else "warn",
        })
    return violations


def run_oxlint(root: Path, unit: dict, entries: list[dict], catalog: dict, *, timeout: int,
               fix: bool = False, type_aware: bool = False) -> dict:
    unit_root = root / unit["dir"]
    command, engine = oxlint_command(unit)
    result: dict[str, Any] = {"engine": engine, "violations": [], "skipped": [], "errors": []}
    if not command:
        result["errors"].append("No oxlint binary and no npx on PATH.")
        return result
    with tempfile.TemporaryDirectory(prefix="js-ts-conventions-") as tmp:
        plugin = Path(tmp) / "plugin.mjs"
        shutil.copyfile(PLUGIN_TEMPLATE, plugin)
        config = oxlint_config(entries, catalog, str(plugin), anchored=True, isolate=True,
                               decorator_metadata=bool(unit.get("decorator_metadata")),
                               ignore_patterns=unit.get("ignore_patterns"))
        config_path = Path(tmp) / "oxlintrc.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        cmd = [*command, "-c", str(config_path), "--disable-nested-config", "-f", "json"]
        if type_aware:
            cmd.append("--type-aware")
        if fix:
            cmd.append("--fix")
        for nested in _unit_relative(unit.get("nested_units", []), unit["dir"]):
            cmd += ["--ignore-pattern", f"{nested}/**"]
        cmd.append(".")
        code, out, err = _run(cmd, unit_root, timeout)
    payload = _json_payload(out, "{")
    if payload is None:
        result["errors"].append(f"oxlint exited {code}: {(err or out).strip()[:600]}")
        return result
    result["version"] = unit.get("version")
    result["files_linted"] = payload.get("number_of_files")
    result["violations"] = parse_oxlint(payload, unit_root, root, {e["rule"] for e in entries})
    return result


# ---------------------------------------------------------------------------
# ESLint
# ---------------------------------------------------------------------------

ESLINT_WRAPPER = """\
import {{ writeFileSync }} from "node:fs";
import plugin from {plugin};

const ENTRIES = {entries};
const IGNORES = {ignores};
const DEFAULT_TS = {default_ts};
const JS_DEFAULT = {js_default};
const DECORATOR_METADATA = {decorator_metadata};

const loaded = (await import({config})).default;
const base = [await loaded].flat(Infinity).filter(Boolean);
const registered = new Set(base.flatMap((c) => Object.keys(c?.plugins ?? {{}})));
const typeAware = base.some((c) => {{
  const options = c?.languageOptions?.parserOptions;
  return Boolean(options?.project || options?.projectService);
}});
const parserConfigs = base.filter((c) => c?.languageOptions?.parser);
let tsFiles = parserConfigs.length ? DEFAULT_TS : [];
if (parserConfigs.length && parserConfigs.every((c) => Array.isArray(c.files) && c.files.every((f) => typeof f === "string"))) {{
  tsFiles = [...new Set(parserConfigs.flatMap((c) => c.files))];
}}
const isTsGlob = (glob) => /\\.[cm]?tsx?(?:\\}}|$)|\\{{[^}}]*ts/.test(glob);

const used = [];
const skipped = [];
for (const entry of ENTRIES) {{
  const slash = entry.rule.lastIndexOf("/");
  const namespace = slash === -1 ? undefined : entry.rule.slice(0, slash);
  if (namespace && namespace !== "{namespace}" && !registered.has(namespace)) {{
    skipped.push({{ rule: entry.rule, reason: `plugin ${{namespace}} is not registered in the repo config` }});
    continue;
  }}
  if (entry.type_aware && !typeAware) {{
    skipped.push({{ rule: entry.rule, reason: "type-aware linting (parserOptions.projectService) is not configured" }});
    continue;
  }}
  let files = entry.files_kind === "ts" ? tsFiles
    : entry.files_kind === "all" ? [...tsFiles, ...JS_DEFAULT]
    : entry.files.filter((glob) => tsFiles.length || !isTsGlob(glob));
  if (!files.length) {{
    skipped.push({{ rule: entry.rule, reason: "no TypeScript parser configured for these files" }});
    continue;
  }}
  used.push({{ ...entry, files }});
}}
writeFileSync({sidecar}, JSON.stringify({{ registered: [...registered], typeAware, tsFiles, skipped }}));

const conventions = [];
if (!registered.has("{namespace}")) conventions.push({{ name: "{namespace}/plugin", plugins: {{ "{namespace}": plugin }} }});
if (DECORATOR_METADATA && tsFiles.length) {{
  conventions.push({{ name: "{namespace}/decorators", files: tsFiles,
    languageOptions: {{ parserOptions: {{ emitDecoratorMetadata: true, experimentalDecorators: true }} }} }});
}}
for (const entry of used) {{
  conventions.push({{ files: entry.files, ignores: entry.ignores ?? IGNORES, rules: {{ [entry.rule]: [entry.severity, ...entry.options] }} }});
  if (entry.exempt.length) conventions.push({{ files: entry.exempt, rules: {{ [entry.rule]: "off" }} }});
}}

// Keep the repo's parser, plugins and ignores; drop its rules so only convention rules run.
export default [...base.map(({{ rules, ...rest }}) => rest), ...conventions];
"""


def eslint_wrapper(config_path: Path, entries: list[dict], catalog: dict, plugin_path: Path,
                   sidecar: Path, decorator_metadata: bool) -> str:
    def js(value: Any) -> str:
        return json.dumps(value)

    return ESLINT_WRAPPER.format(
        plugin=js(plugin_path.as_uri()),
        config=js(config_path.resolve().as_uri()),
        entries=js(entries),
        ignores=js(catalog["ignores"]),
        default_ts=js(catalog["file_sets"]["ts"]),
        js_default=js(JS_DEFAULT_FILES),
        decorator_metadata=js(decorator_metadata),
        sidecar=js(str(sidecar)),
        namespace=PLUGIN_NAMESPACE,
    )


def parse_eslint(payload: Any, root: Path, convention_ids: set[str]) -> tuple[list[dict], list[dict]]:
    violations, fatal = [], []
    for file_result in payload or []:
        path = Path(file_result.get("filePath", ""))
        for message in file_result.get("messages", []):
            if message.get("fatal"):
                fatal.append({"file": rel(path, root), "message": message.get("message", "")[:200]})
                continue
            if message.get("ruleId") not in convention_ids:
                continue
            violations.append({
                "rule": message["ruleId"],
                "file": rel(path, root),
                "line": message.get("line", 0),
                "column": message.get("column", 0),
                "message": message.get("message", ""),
                "severity": "error" if message.get("severity") == 2 else "warn",
            })
    return violations, fatal


def run_eslint(root: Path, unit: dict, entries: list[dict], catalog: dict, *, timeout: int,
               fix: bool = False) -> dict:
    unit_root = root / unit["dir"]
    result: dict[str, Any] = {"engine": "eslint", "version": unit.get("version"),
                              "violations": [], "skipped": [], "errors": []}
    if unit.get("format") != "flat":
        result["errors"].append("Legacy .eslintrc config: migrate to flat config first.")
        return result
    if not unit.get("binary"):
        result["errors"].append("ESLint is not installed here (run the package manager install first).")
        return result
    with tempfile.TemporaryDirectory(prefix="js-ts-conventions-") as tmp:
        plugin = Path(tmp) / "plugin.mjs"
        shutil.copyfile(PLUGIN_TEMPLATE, plugin)
        sidecar = Path(tmp) / "sidecar.json"
        wrapper = Path(tmp) / "eslint.audit.config.mjs"
        wrapper.write_text(eslint_wrapper(root / unit["config"], entries, catalog, plugin, sidecar,
                                          bool(unit.get("decorator_metadata"))), encoding="utf-8")
        cmd = [unit["binary"], "--config", str(wrapper), "-f", "json", "--no-warn-ignored"]
        if eslint_supports_suppressions(unit.get("version")):
            # The audit counts frozen violations too: point ESLint at an empty suppressions file.
            empty = Path(tmp) / "no-suppressions.json"
            empty.write_text("{}", encoding="utf-8")
            cmd += ["--suppressions-location", str(empty)]
        if fix:
            cmd.append("--fix")
        for nested in _unit_relative(unit.get("nested_units", []), unit["dir"]):
            cmd += ["--ignore-pattern", f"{nested}/**"]
        cmd.append(".")
        code, out, err = _run(cmd, unit_root, timeout, env={"ESLINT_USE_FLAT_CONFIG": "true"})
        side = json.loads(sidecar.read_text()) if sidecar.exists() else {}
    payload = _json_payload(out, "[")
    if payload is None:
        result["errors"].append(f"eslint exited {code}: {(err or out).strip()[:600]}")
        return result
    violations, fatal = parse_eslint(payload, root, {e["rule"] for e in entries})
    result.update({
        "violations": violations,
        "parse_errors": fatal[:20],
        "parse_error_count": len(fatal),
        "files_linted": len(payload),
        "skipped": side.get("skipped", []),
        "registered_plugins": side.get("registered", []),
        "type_aware": side.get("typeAware", False),
    })
    return result


def eslint_supports_suppressions(version: str | None) -> bool:
    return version_tuple(version) >= ESLINT_SUPPRESSIONS_MIN


def run_unit(root: Path, unit: dict, entries: list[dict], catalog: dict, *, timeout: int = 600,
             fix: bool = False) -> dict:
    if unit["tool"] == "eslint":
        result = run_eslint(root, unit, entries, catalog, timeout=timeout, fix=fix)
        if result["errors"] and not result["violations"] and not fix:
            # Fall back to oxlint so the audit still measures the custom and typescript rules.
            fallback = dict(unit, binary=None, tool="oxlint")
            ox = run_oxlint(root, fallback, oxlint_entries_for(entries, catalog), catalog, timeout=timeout)
            if not ox["errors"]:
                ox["fallback_reason"] = result["errors"][0]
                return ox
        return result
    type_aware = bool(unit.get("type_aware_available")) and any(e["type_aware"] for e in entries)
    return run_oxlint(root, unit, entries, catalog, timeout=timeout, fix=fix, type_aware=type_aware)


def oxlint_entries_for(eslint_entries: list[dict], catalog: dict) -> list[dict]:
    """Translate ESLint entries to oxlint rule ids via the catalog (for the stand-in engine)."""
    by_pref: dict[str, dict] = {p["id"]: p for p in catalog["preferences"]}
    translated, seen = [], set()
    for entry in eslint_entries:
        spec = by_pref[entry["pref"]].get("enforce", {}).get("oxlint", {})
        for rule_id, options in spec.get("rules", {}).items():
            if (entry["pref"], rule_id) in seen:
                continue
            seen.add((entry["pref"], rule_id))
            translated.append({**entry, "rule": rule_id,
                               "options": entry["options"] if rule_id.startswith(PLUGIN_NAMESPACE) else options,
                               "type_aware": False})
    return translated
