#!/usr/bin/env python3
"""
Render the cursor-orchestrator templates into sub-agent and rule files at
the target scope(s). Idempotent: existing files whose SHA matches the stored
marker hash are overwritten; user-edited files (hash mismatch) are left alone
and reported as warnings.

Usage:
    # Generate from scratch using answers and tier data from stdin
    python scripts/generate_agents.py --answers <json> --tiers <json>

    # Regenerate using the existing marker (for /update-orchestrator)
    python scripts/generate_agents.py --regenerate --tiers <json>

The --tiers JSON is the "tiers" subtree produced by update_models.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (CURRENT_VERSION, MARKER_FILENAME, SKILL_ROOT,
                   TIER_DESCRIPTIONS, load_marker, now_iso, render_template,
                   resolve_target_roots, save_marker, sha256_file, sha256_text,
                   validate_answers)

TEMPLATE_DIR = SKILL_ROOT / "templates"


def _read_template(name: str) -> str:
    path = TEMPLATE_DIR / name
    if not path.is_file():
        raise RuntimeError(f"Missing template: {path}")
    return path.read_text(encoding="utf-8")


def _tier_label(tier_entry: dict[str, Any]) -> str:
    name = tier_entry.get("name", "")
    model_id = tier_entry.get("model_id", "")
    if name and model_id and name.lower() != model_id.lower():
        return f"{name} ({model_id})"
    return name or model_id


def _plan_file_list(
    answers: dict[str, Any],
    tiers: dict[str, dict[str, Any]],
    root: Path,
) -> list[tuple[Path, str]]:
    """Return the list of (target_path, rendered_content) tuples to write under `root`."""
    files: list[tuple[Path, str]] = []
    agents_dir = root / "agents"
    rules_dir = root / "rules"

    orchestrator_tmpl = _read_template("orchestrator.md.tmpl")
    files.append((agents_dir / "plan-orchestrator.md", orchestrator_tmpl))

    implementer_tmpl = _read_template("implementer.md.tmpl")
    for tier_name in answers["tiers"]:
        entry = tiers.get(tier_name)
        if entry is None:
            raise RuntimeError(
                f"Tier {tier_name!r} was selected but is missing from the model catalog. "
                "Run update_models.py or pick a different tier."
            )
        variables = {
            "tier_name": tier_name,
            "model_id": entry["model_id"],
            "model_label": _tier_label(entry),
            "tier_description": TIER_DESCRIPTIONS.get(tier_name, ""),
        }
        rendered = render_template(implementer_tmpl, variables)
        files.append((agents_dir / f"impl-{tier_name}.md", rendered))

    if answers["verifier"]:
        verifier_tmpl = _read_template("verifier.md.tmpl")
        files.append((agents_dir / "verifier.md", verifier_tmpl))

    if answers["commands"]:
        orchestrate_cmd_tmpl = _read_template("orchestrate-cmd.md.tmpl")
        update_cmd_tmpl = _read_template("update-cmd.md.tmpl")
        files.append((agents_dir / "orchestrate.md", orchestrate_cmd_tmpl))
        files.append((agents_dir / "update-orchestrator.md", update_cmd_tmpl))

    if answers["rule"]:
        rule_tmpl = _read_template("plan-mode-rule.md.tmpl")
        files.append((rules_dir / "cursor-orchestrator-plan-mode.mdc", rule_tmpl))

    return files


def generate(
    answers: dict[str, Any],
    tiers: dict[str, dict[str, Any]],
    *,
    skill_root: Path,
    catalog_fetched_at: str | None = None,
    existing_marker: dict[str, Any] | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """
    Write all files for the given answers/tiers. Returns a report dict with
    keys: written, skipped_user_edited, removed, errors.
    """
    validate_answers(answers)

    report: dict[str, list[str]] = {
        "written": [],
        "skipped_user_edited": [],
        "removed": [],
        "errors": [],
    }
    file_hashes: dict[str, str] = {}

    target_roots = resolve_target_roots(answers["scope"], cwd=cwd)

    previously_tracked: dict[str, str] = {}
    if existing_marker is not None:
        previously_tracked = existing_marker.get("file_hashes", {}) or {}

    planned_paths: set[str] = set()

    for root in target_roots:
        for target_path, content in _plan_file_list(answers, tiers, root):
            target_path.parent.mkdir(parents=True, exist_ok=True)
            rel_key = str(target_path)
            planned_paths.add(rel_key)

            current_hash = sha256_file(target_path)
            previous_hash = previously_tracked.get(rel_key)

            if current_hash is not None and previous_hash is not None and current_hash != previous_hash:
                report["skipped_user_edited"].append(rel_key)
                file_hashes[rel_key] = current_hash
                continue

            try:
                target_path.write_text(content, encoding="utf-8")
            except OSError as exc:
                report["errors"].append(f"{rel_key}: {exc}")
                continue

            new_hash = sha256_text(content)
            file_hashes[rel_key] = new_hash
            report["written"].append(rel_key)

        marker_path = root / "agents" / MARKER_FILENAME
        marker_data = _build_marker(
            answers=answers,
            file_hashes={k: v for k, v in file_hashes.items() if k.startswith(str(root))},
            catalog_fetched_at=catalog_fetched_at,
            existing=existing_marker,
        )
        save_marker(marker_path, marker_data)
        report["written"].append(str(marker_path))

    for rel_key, _old_hash in previously_tracked.items():
        if rel_key in planned_paths:
            continue
        p = Path(rel_key)
        if not p.is_file():
            continue
        current_hash = sha256_file(p)
        if current_hash == _old_hash:
            try:
                p.unlink()
                report["removed"].append(rel_key)
            except OSError as exc:
                report["errors"].append(f"unlink {rel_key}: {exc}")
        else:
            report["skipped_user_edited"].append(rel_key)

    return report


def _build_marker(
    *,
    answers: dict[str, Any],
    file_hashes: dict[str, str],
    catalog_fetched_at: str | None,
    existing: dict[str, Any] | None,
) -> dict[str, Any]:
    previous_installed_at = (existing or {}).get("installed_at")
    return {
        "version": CURRENT_VERSION,
        "installed_at": previous_installed_at or now_iso(),
        "last_regenerated_at": now_iso(),
        "catalog_fetched_at": catalog_fetched_at or now_iso(),
        "scope": answers["scope"],
        "tiers": list(answers["tiers"]),
        "default_tier": answers["default_tier"],
        "verifier_enabled": bool(answers["verifier"]),
        "rule_enabled": bool(answers["rule"]),
        "commands_enabled": bool(answers["commands"]),
        "max_mode": bool(answers["max_mode"]),
        "file_hashes": file_hashes,
    }


def _load_json_arg(raw: str | None, path: Path | None, *, what: str) -> Any:
    if raw and path:
        raise ValueError(f"Provide either --{what} or --{what}-file, not both.")
    if raw:
        return json.loads(raw)
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answers", type=str, default=None,
                        help="JSON string of setup interview answers.")
    parser.add_argument("--answers-file", type=Path, default=None,
                        help="Path to a file containing the answers JSON.")
    parser.add_argument("--tiers", type=str, default=None,
                        help="JSON string of the tiers subtree from update_models.py.")
    parser.add_argument("--tiers-file", type=Path, default=None,
                        help="Path to a file containing the tiers JSON.")
    parser.add_argument("--catalog-fetched-at", type=str, default=None,
                        help="ISO timestamp of the catalog fetch (from update_models output).")
    parser.add_argument("--regenerate", action="store_true",
                        help="Load answers from the existing marker and regenerate.")
    parser.add_argument("--skill-root", type=Path, default=SKILL_ROOT,
                        help="Path to the cursor-orchestrator skill root.")
    parser.add_argument("--cwd", type=Path, default=None,
                        help="Target working directory (for project-scoped writes).")
    args = parser.parse_args()

    try:
        tiers = _load_json_arg(args.tiers, args.tiers_file, what="tiers")
        if tiers is None:
            raise ValueError("Missing --tiers or --tiers-file.")

        if args.regenerate:
            marker = _find_first_marker(args.cwd)
            if marker is None:
                raise RuntimeError(
                    "No existing marker found — run setup.py for first-use setup first."
                )
            answers = {
                "scope": marker["scope"],
                "tiers": marker["tiers"],
                "default_tier": marker["default_tier"],
                "verifier": marker["verifier_enabled"],
                "rule": marker["rule_enabled"],
                "commands": marker["commands_enabled"],
                "max_mode": marker["max_mode"],
            }
            existing = marker
        else:
            answers = _load_json_arg(args.answers, args.answers_file, what="answers")
            if answers is None:
                raise ValueError("Missing --answers or --answers-file (required unless --regenerate).")
            existing = _find_first_marker(args.cwd)

        report = generate(
            answers=answers,
            tiers=tiers,
            skill_root=args.skill_root,
            catalog_fetched_at=args.catalog_fetched_at,
            existing_marker=existing,
            cwd=args.cwd,
        )
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _find_first_marker(cwd: Path | None) -> dict[str, Any] | None:
    cwd = cwd or Path.cwd()
    for candidate in (
        cwd / ".cursor" / "agents" / MARKER_FILENAME,
        Path.home() / ".cursor" / "agents" / MARKER_FILENAME,
    ):
        data = load_marker(candidate)
        if data is not None:
            return data
    return None


if __name__ == "__main__":
    raise SystemExit(main())
