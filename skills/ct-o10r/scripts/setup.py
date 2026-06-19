#!/usr/bin/env python3
"""
First-use setup entry point for ct-o10r (claudeteam-orchestrator).

The skill conducts the interview (via AskUserQuestion) and calls this script
with the answers as JSON:

    python scripts/setup.py --answers '{"scope": "project", "tiers": [...], ...}'
                            [--project-agents '[{"name": "domain-modeler", ...}]']
                            [--byterover-info '{"enabled": true, ...}']
                            [--codebase-snapshot '{"fingerprint": "...", ...}']

This script:
  1. Validates the answers payload.
  2. Calls generate_agents.generate() to write the sub-agent / command files.
  3. Prints a JSON report on stdout for the skill to parse and relay to the user.

Exits 0 on success, 1 on error (JSON error on stderr).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_agents
from utils import SKILL_ROOT, find_marker_paths, load_marker, validate_answers


def _load_json_arg(raw: str | None, path: Path | None, *, what: str) -> Any:
    if raw and path:
        raise ValueError(f"Provide either --{what} or --{what}-file, not both.")
    if raw:
        return json.loads(raw)
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def run(
    answers: dict[str, Any],
    *,
    project_agents: list[dict[str, Any]],
    byterover_info: dict[str, Any],
    codebase_snapshot: dict[str, Any],
    skill_root: Path,
    cwd: Path | None,
) -> dict[str, Any]:
    validate_answers(answers)

    # Load any existing marker so SHA protection and hook cleanup work correctly
    cwd_actual = cwd or Path.cwd()
    existing_marker = None
    for mpath in find_marker_paths(cwd_actual):
        existing_marker = load_marker(mpath)
        if existing_marker:
            break

    report = generate_agents.generate(
        answers=answers,
        skill_root=skill_root,
        project_agents=project_agents,
        byterover_info=byterover_info,
        codebase_snapshot=codebase_snapshot,
        existing_marker=existing_marker,
        cwd=cwd,
    )

    return {
        "ok": True,
        "scope": answers["scope"],
        "tiers_installed": answers["tiers"],
        "default_tier": answers["default_tier"],
        "byterover_enabled": answers["byterover_enabled"],
        "project_agents_count": len(project_agents),
        "report": report,
        "next_steps": _next_steps(answers),
    }


def _next_steps(answers: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    steps.append(
        'Enable agent teams: add "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" to your '
        'settings.json "env" block and RESTART Claude Code (the flag is read at '
        "startup). Without it, no team forms and /ct-orchestrate cannot run."
    )
    steps.append(
        "In Plan Mode on Opus/Sonnet, draft a plan as usual. The skill will ask for a "
        "default teammate model and verification strategy before finalizing, then "
        "write a `team:` block into the plan frontmatter."
    )
    if answers["commands"]:
        steps.append(
            "To run a saved plan as a team: "
            "`/ct-orchestrate ~/.claude/plans/<plan>.md`"
        )
        steps.append(
            "To resume an interrupted run (respawns teammates; the task list persists): "
            "`/ct-orchestrate-resume ~/.claude/plans/<plan>.md`"
        )
        steps.append(
            "To re-analyze the codebase and refresh teammate roles: "
            "`/update-ct-orchestrator`"
        )
    else:
        steps.append(
            "Slash commands are disabled. To run a plan, in a session where this skill "
            "is active say e.g. 'orchestrate ~/.claude/plans/<plan>.md as a team' — the "
            "lead reads references/TEAM_ORCHESTRATION.md and coordinates teammates."
        )
    steps.append(
        'Tip: teammates render in-process by default. For split panes (one per '
        'teammate) set teammateMode to "auto" in settings and use tmux or iTerm2.'
    )
    if answers["byterover_enabled"]:
        steps.append(
            "ByteRover is enabled. Each teammate recalls prior context and curates "
            "learnings into .brv/context-tree/, messaging the lead a `BRV-REVIEW` note "
            "per curate. The lead surfaces all pending curates in its final report for "
            "your approval."
        )
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answers", type=str, default=None)
    parser.add_argument("--answers-file", type=Path, default=None)
    parser.add_argument("--project-agents", type=str, default=None,
                        help="JSON array of project-specific agent dicts (from roster composition).")
    parser.add_argument("--byterover-info", type=str, default=None,
                        help="JSON output from detect_byterover.py.")
    parser.add_argument("--codebase-snapshot", type=str, default=None,
                        help="JSON output from analyze_codebase.py.")
    parser.add_argument("--skill-root", type=Path, default=SKILL_ROOT)
    parser.add_argument("--cwd", type=Path, default=None,
                        help="Target project root (default: current working directory).")
    args = parser.parse_args()

    try:
        answers = _load_json_arg(args.answers, args.answers_file, what="answers")
        if answers is None:
            raise ValueError("Missing --answers or --answers-file.")

        project_agents = json.loads(args.project_agents) if args.project_agents else []
        byterover_info = json.loads(args.byterover_info) if args.byterover_info else {"enabled": False}
        codebase_snapshot = json.loads(args.codebase_snapshot) if args.codebase_snapshot else {}

        result = run(
            answers=answers,
            project_agents=project_agents,
            byterover_info=byterover_info,
            codebase_snapshot=codebase_snapshot,
            skill_root=args.skill_root,
            cwd=args.cwd,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
