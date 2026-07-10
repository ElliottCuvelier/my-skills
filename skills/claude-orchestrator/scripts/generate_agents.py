#!/usr/bin/env python3
"""
Render the claude-orchestrator templates into sub-agent and command files at
the target scope(s). Idempotent: existing files whose SHA matches the stored
marker hash are overwritten; user-edited files (hash mismatch) are left alone
and reported as warnings; pre-existing untracked files are registered and
never touched.

Usage:
    # Generate from scratch using answers JSON
    python scripts/generate_agents.py --answers <json>

    # Regenerate using the existing marker (for /update-claude-orchestrator)
    python scripts/generate_agents.py --regenerate [--answers <json>]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (
    CURRENT_VERSION,
    MARKER_FILENAME,
    SKILL_ROOT,
    TIER_DESCRIPTIONS,
    TIER_MODEL_LABELS,
    VALID_HOOKS,
    VALID_TIERS,
    load_marker,
    now_iso,
    render_template,
    resolve_target_roots,
    save_marker,
    sha256_file,
    sha256_text,
    validate_answers,
)

TEMPLATE_DIR = SKILL_ROOT / "templates"


def _read_template(name: str) -> str:
    path = TEMPLATE_DIR / name
    if not path.is_file():
        raise RuntimeError(f"Missing template: {path}")
    return path.read_text(encoding="utf-8")


def _plan_file_list(
    answers: dict[str, Any],
    project_agents: list[dict[str, Any]],
    byterover_info: dict[str, Any],
    byterover_loop_fragment: str,
    root: Path,
) -> list[tuple[Path, str]]:
    """Return (target_path, rendered_content) pairs to write under `root`."""
    files: list[tuple[Path, str]] = []
    agents_dir = root / "agents"
    commands_dir = root / "commands"

    byterover_enabled = byterover_info.get("enabled", False)

    # impl-* baseline agents
    impl_tmpl = _read_template("impl-baseline.md.tmpl")
    for tier in answers["tiers"]:
        impl_vars = {
            "tier_name": tier,
            "model_label": TIER_MODEL_LABELS.get(tier, tier),
            "tier_description": TIER_DESCRIPTIONS.get(tier, ""),
            "byterover_loop": _build_agent_byterover_loop(
                byterover_enabled,
                "",  # no specific scope for generic baseline impl agents
                "a non-trivial pattern, reusable convention, or architecture decision is discovered",
                byterover_loop_fragment,
            ),
        }
        files.append((
            agents_dir / f"impl-{tier}.md",
            render_template(impl_tmpl, impl_vars),
        ))

    # project-specific agents (PR2+)
    if project_agents:
        project_tmpl = _read_template("project-agent.md.tmpl")
        for pa in project_agents:
            pa_vars = {
                "agent_name": pa["name"],
                "agent_description": pa.get("description", f"Specialist agent for {pa['name']}"),
                "agent_model": pa.get("model", "sonnet"),
                "agent_readonly": "true" if pa.get("readonly", False) else "false",
                "agent_role": pa.get("role", "writer"),
                "when_invoked": pa.get("when_invoked", f"Handle {pa['name']}-related tasks."),
                "conventions": pa.get("conventions", ""),
                "return_format": pa.get(
                    "return_format",
                    "status | files_changed | commands_run | blockers",
                ),
                "byterover_loop": _build_agent_byterover_loop(
                    byterover_enabled,
                    pa.get("byterover_scope", ""),
                    pa.get("curate_when", "a non-trivial pattern or decision is discovered"),
                    byterover_loop_fragment,
                ),
            }
            files.append((
                agents_dir / f"{pa['name']}.md",
                render_template(project_tmpl, pa_vars),
            ))

    # verifier
    if answers["verifier"]:
        verifier_tmpl = _read_template("verifier.md.tmpl")
        files.append((agents_dir / "verifier.md", verifier_tmpl))

    # memory-curator
    if answers["memory_curator"]:
        curator_tmpl = _read_template("memory-curator.md.tmpl")
        files.append((agents_dir / "memory-curator.md", curator_tmpl))

    # slash commands
    if answers["commands"]:
        for cmd_tmpl_name, cmd_filename in [
            ("orchestrate-cmd.md.tmpl", "claude-orchestrate.md"),
            ("orchestrate-resume-cmd.md.tmpl", "claude-orchestrate-resume.md"),
            ("update-cmd.md.tmpl", "update-claude-orchestrator.md"),
        ]:
            tmpl = _read_template(cmd_tmpl_name)
            files.append((commands_dir / cmd_filename, tmpl))

    return files


def _build_agent_byterover_loop(
    byterover_enabled: bool,
    scope: str,
    curate_when: str,
    loop_fragment: str,
) -> str:
    """Return the fully-substituted ByteRover loop for a project agent."""
    if not byterover_enabled or not loop_fragment:
        return ""
    # {{AGENT_SCOPE_FLAG}} becomes "--scope \"<scope>\" " when scope is set, else ""
    scope_flag = f'--scope "{scope}" ' if scope else ""
    return (
        loop_fragment
        .replace("{{AGENT_SCOPE_FLAG}}", scope_flag)
        .replace("{{CURATE_WHEN}}", curate_when)
    )


def _scan_existing_agents(agents_dir: Path, tracked: set[str]) -> list[dict[str, Any]]:
    """Find .md files in agents_dir that are not in the tracked set."""
    existing = []
    if not agents_dir.is_dir():
        return existing
    for p in sorted(agents_dir.glob("*.md")):
        key = str(p)
        if key not in tracked and p.name != MARKER_FILENAME:
            sha = sha256_file(p) or ""
            existing.append({"path": key, "sha": sha, "registered_at": now_iso()})
    return existing


def generate(
    answers: dict[str, Any],
    *,
    skill_root: Path,
    project_agents: list[dict[str, Any]] | None = None,
    byterover_info: dict[str, Any] | None = None,
    codebase_snapshot: dict[str, Any] | None = None,
    existing_marker: dict[str, Any] | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """
    Write all files for the given answers. Returns a report dict with keys:
    written, skipped_user_edited, removed, errors.
    """
    validate_answers(answers)

    project_agents = project_agents or []
    byterover_info = byterover_info or {"enabled": False}
    codebase_snapshot = codebase_snapshot or {}

    # Load ByteRover loop fragment if enabled
    byterover_loop_fragment = ""
    if byterover_info.get("enabled", False):
        loop_path = skill_root / "templates" / "byterover_loop_fragment.md.tmpl"
        if loop_path.is_file():
            byterover_loop_fragment = loop_path.read_text(encoding="utf-8")

    report: dict[str, list[str]] = {
        "written": [],
        "skipped_user_edited": [],
        "removed": [],
        "errors": [],
    }
    file_hashes: dict[str, str] = {}

    target_roots = resolve_target_roots(answers["scope"], cwd=cwd)

    previously_tracked: dict[str, str] = {}
    previous_registered: list[dict[str, Any]] = []
    if existing_marker is not None:
        previously_tracked = existing_marker.get("file_hashes", {}) or {}
        previous_registered = existing_marker.get("registered_existing_agents", []) or []

    planned_paths: set[str] = set()
    all_registered_existing: list[dict[str, Any]] = list(previous_registered)

    for root in target_roots:
        planned = _plan_file_list(
            answers,
            project_agents,
            byterover_info,
            byterover_loop_fragment,
            root,
        )

        for target_path, content in planned:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            rel_key = str(target_path)
            planned_paths.add(rel_key)

            current_hash = sha256_file(target_path)
            previous_hash = previously_tracked.get(rel_key)

            if (
                current_hash is not None
                and previous_hash is not None
                and current_hash != previous_hash
            ):
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

        # Register pre-existing agents not generated by us
        already_registered_keys = {e["path"] for e in all_registered_existing}
        new_existing = _scan_existing_agents(
            root / "agents",
            planned_paths | already_registered_keys,
        )
        for entry in new_existing:
            if entry["path"] not in already_registered_keys:
                all_registered_existing.append(entry)
                already_registered_keys.add(entry["path"])

        # Install hooks and merge settings.local.json (always called — handles cleanup too)
        hooks_settings: dict[str, Any] = _install_hooks(
            hooks_to_install=answers.get("hooks", []),
            root=root,
            skill_root=skill_root,
            existing_marker=existing_marker,
            file_hashes=file_hashes,
            report=report,
        )
        # _install_hooks records its files only in file_hashes; mark them planned
        # so the stale-file cleanup below doesn't delete them.
        planned_paths.update(file_hashes.keys())

        marker_path = root / "agents" / MARKER_FILENAME
        marker_data = _build_marker(
            answers=answers,
            file_hashes={k: v for k, v in file_hashes.items()
                         if k.startswith(str(root))},
            byterover_info=byterover_info,
            codebase_snapshot=codebase_snapshot,
            project_agents=project_agents,
            registered_existing=all_registered_existing,
            existing=existing_marker,
            hooks_installed=answers.get("hooks", []),
            hooks_settings=hooks_settings,
        )
        save_marker(marker_path, marker_data)
        report["written"].append(str(marker_path))

    # Remove previously-tracked files that are no longer in the plan
    for rel_key, old_hash in previously_tracked.items():
        if rel_key in planned_paths:
            continue
        p = Path(rel_key)
        if not p.is_file():
            continue
        if sha256_file(p) == old_hash:
            try:
                p.unlink()
                report["removed"].append(rel_key)
            except OSError as exc:
                report["errors"].append(f"unlink {rel_key}: {exc}")
        else:
            report["skipped_user_edited"].append(rel_key)

    return report


# Maps hook id → (template filename, generated script filename, event, matcher|None, timeout ms)
_HOOK_SPEC: dict[str, tuple[str, str, str, str | None, int]] = {
    "taskids": ("hooks/collect-taskids.py.tmpl", "collect-taskids.py", "SubagentStop", None, 5_000),
    "pending": ("hooks/surface-pending.py.tmpl", "surface-pending.py", "Stop", None, 5_000),
    "tests":   ("hooks/run-scoped-tests.py.tmpl", "run-scoped-tests.py", "PostToolUse", "Write|Edit|MultiEdit", 120_000),
}


def _install_hooks(
    hooks_to_install: list[str],
    root: Path,
    skill_root: Path,
    existing_marker: dict[str, Any] | None,
    file_hashes: dict[str, str],
    report: dict[str, list[str]],
) -> dict[str, Any]:
    """
    Write hook scripts to root/hooks/ and merge entries into settings.local.json.

    Mutates file_hashes and report in place (consistent with the agent-writing loop).
    Returns the hooks_settings dict to store in the marker.
    """
    hooks_dir = root / "hooks"
    previously_tracked: dict[str, str] = (existing_marker or {}).get("file_hashes", {})
    hooks_settings: dict[str, Any] = {}

    if not hooks_to_install:
        # No hooks to install, but we still need to clean up stale settings entries
        stale = (existing_marker or {}).get("hooks_settings", {})
        if stale:
            _merge_settings(root, {}, existing_marker, report)
        return {}

    hooks_dir.mkdir(parents=True, exist_ok=True)

    # --- Part A: write hook scripts ---
    for hook_id in hooks_to_install:
        if hook_id not in _HOOK_SPEC:
            continue
        tmpl_name, script_name, event, matcher, timeout_ms = _HOOK_SPEC[hook_id]

        tmpl_path = skill_root / "templates" / tmpl_name
        if not tmpl_path.is_file():
            report["errors"].append(f"Missing hook template: {tmpl_path}")
            continue

        content = tmpl_path.read_text(encoding="utf-8")
        dest = hooks_dir / script_name
        rel_key = str(dest)

        current_hash = sha256_file(dest)
        previous_hash = previously_tracked.get(rel_key)
        if current_hash is not None and previous_hash is not None and current_hash != previous_hash:
            report["skipped_user_edited"].append(rel_key)
            file_hashes[rel_key] = current_hash
        else:
            try:
                dest.write_text(content, encoding="utf-8")
            except OSError as exc:
                report["errors"].append(f"{rel_key}: {exc}")
                continue
            file_hashes[rel_key] = sha256_text(content)
            report["written"].append(rel_key)

        # --- Part B: build settings entry for this hook ---
        command = f'python3 "{dest}"'
        hook_entry: dict[str, Any] = {
            "type": "command",
            "command": command,
            "timeout": timeout_ms,
        }
        outer: dict[str, Any] = {"hooks": [hook_entry]}
        if matcher:
            outer["matcher"] = matcher

        if event not in hooks_settings:
            hooks_settings[event] = []
        hooks_settings[event].append(outer)

    # --- Part C: merge into settings.local.json ---
    if hooks_settings:
        _merge_settings(root, hooks_settings, existing_marker, report)

    return hooks_settings


def _merge_settings(
    root: Path,
    new_hooks_settings: dict[str, Any],
    existing_marker: dict[str, Any] | None,
    report: dict[str, list[str]],
) -> None:
    """Read settings.local.json, remove stale hook entries, add new ones, write back."""
    settings_path = root / "settings.local.json"

    # Load existing settings
    settings: dict[str, Any] = {}
    if settings_path.is_file():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            report["errors"].append(
                f"settings.local.json could not be parsed ({exc}); hooks not merged."
            )
            return

    hooks_section: dict[str, list[dict]] = settings.setdefault("hooks", {})

    # Remove stale entries from previous install (identified by command string)
    stale_settings = (existing_marker or {}).get("hooks_settings", {})
    for event, entries in stale_settings.items():
        if event not in hooks_section:
            continue
        stale_commands = {
            h["command"]
            for outer in entries
            for h in outer.get("hooks", [])
            if "command" in h
        }
        hooks_section[event] = [
            outer for outer in hooks_section[event]
            if not any(
                h.get("command") in stale_commands
                for h in outer.get("hooks", [])
            )
        ]
        if not hooks_section[event]:
            del hooks_section[event]

    # Add new entries (guard against duplicate commands from manual installs)
    for event, new_entries in new_hooks_settings.items():
        existing_entries = hooks_section.setdefault(event, [])
        existing_commands = {
            h["command"]
            for outer in existing_entries
            for h in outer.get("hooks", [])
            if "command" in h
        }
        for outer in new_entries:
            has_dup = any(
                h.get("command") in existing_commands
                for h in outer.get("hooks", [])
            )
            if not has_dup:
                existing_entries.append(outer)

    # Atomic write
    tmp = settings_path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(str(tmp), str(settings_path))
    except OSError as exc:
        report["errors"].append(f"settings.local.json write failed: {exc}")
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _build_marker(
    *,
    answers: dict[str, Any],
    file_hashes: dict[str, str],
    byterover_info: dict[str, Any],
    codebase_snapshot: dict[str, Any],
    project_agents: list[dict[str, Any]],
    registered_existing: list[dict[str, Any]],
    existing: dict[str, Any] | None,
    hooks_installed: list[str] | None = None,
    hooks_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous_installed_at = (existing or {}).get("installed_at")
    return {
        "version": CURRENT_VERSION,
        "installed_at": previous_installed_at or now_iso(),
        "last_regenerated_at": now_iso(),
        "scope": answers["scope"],
        "tiers_installed": list(answers["tiers"]),
        "default_tier": answers["default_tier"],
        "verifier_enabled": bool(answers["verifier"]),
        "memory_curator_enabled": bool(answers["memory_curator"]),
        "commands_enabled": bool(answers["commands"]),
        "hooks_installed": list(hooks_installed or []),
        "hooks_settings": hooks_settings or {},
        "byterover": byterover_info,
        "codebase_snapshot": codebase_snapshot,
        "project_agents": project_agents,
        "file_hashes": file_hashes,
        "registered_existing_agents": registered_existing,
    }


def _load_json_arg(raw: str | None, path: Path | None, *, what: str) -> Any:
    if raw and path:
        raise ValueError(f"Provide either --{what} or --{what}-file, not both.")
    if raw:
        return json.loads(raw)
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _find_first_marker(cwd: Path | None) -> dict[str, Any] | None:
    cwd = cwd or Path.cwd()
    for candidate in (
        cwd / ".claude" / "agents" / MARKER_FILENAME,
        Path.home() / ".claude" / "agents" / MARKER_FILENAME,
    ):
        data = load_marker(candidate)
        if data is not None:
            return data
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answers", type=str, default=None)
    parser.add_argument("--answers-file", type=Path, default=None)
    parser.add_argument("--project-agents", type=str, default=None,
                        help="JSON array of project-specific agent dicts.")
    parser.add_argument("--byterover-info", type=str, default=None,
                        help="JSON from detect_byterover.py output.")
    parser.add_argument("--codebase-snapshot", type=str, default=None,
                        help="JSON from analyze_codebase.py output.")
    parser.add_argument("--regenerate", action="store_true",
                        help="Load answers from the existing marker and regenerate.")
    parser.add_argument("--skill-root", type=Path, default=SKILL_ROOT)
    parser.add_argument("--cwd", type=Path, default=None)
    args = parser.parse_args()

    try:
        byterover_info = json.loads(args.byterover_info) if args.byterover_info else {}
        codebase_snapshot = json.loads(args.codebase_snapshot) if args.codebase_snapshot else {}
        project_agents = json.loads(args.project_agents) if args.project_agents else []

        if args.regenerate:
            marker = _find_first_marker(args.cwd)
            if marker is None:
                raise RuntimeError(
                    "No existing marker found — run setup.py for first-use setup first."
                )
            answers = {
                "scope": marker["scope"],
                "tiers": marker["tiers_installed"],
                "default_tier": marker["default_tier"],
                "verifier": marker["verifier_enabled"],
                "memory_curator": marker["memory_curator_enabled"],
                "commands": marker["commands_enabled"],
                "byterover_enabled": marker.get("byterover", {}).get("enabled", False),
                "hooks": marker.get("hooks_installed", []),
            }
            # Use stored project_agents if not overridden
            if not project_agents:
                project_agents = marker.get("project_agents", [])
            if not byterover_info:
                byterover_info = marker.get("byterover", {})
            if not codebase_snapshot:
                codebase_snapshot = marker.get("codebase_snapshot", {})
            existing = marker
        else:
            answers = _load_json_arg(args.answers, args.answers_file, what="answers")
            if answers is None:
                raise ValueError(
                    "Missing --answers or --answers-file (required unless --regenerate)."
                )
            existing = _find_first_marker(args.cwd)

        report = generate(
            answers=answers,
            skill_root=args.skill_root,
            project_agents=project_agents,
            byterover_info=byterover_info,
            codebase_snapshot=codebase_snapshot,
            existing_marker=existing,
            cwd=args.cwd,
        )
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
