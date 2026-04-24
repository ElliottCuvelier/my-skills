#!/usr/bin/env python3
"""
First-use setup entry point for cursor-orchestrator.

The agent conducts the 7-question interview via AskQuestion and then calls
this script with the answers as JSON:

    python scripts/setup.py --answers '{"scope": "project", "tiers": [...], ...}'

This script:
  1. Validates the answers payload.
  2. Calls update_models.run() to fetch the latest pricing page.
  3. Calls generate_agents.generate() to write the sub-agent / rule files.
  4. Prints a human-readable summary plus a JSON block on stdout for the agent
     to parse and relay back to the user.

Exits 0 on success, 1 on error (with JSON error on stderr).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_agents
import update_models
from utils import SKILL_ROOT, validate_answers


def _load_answers(raw: str | None, path: Path | None) -> dict[str, Any]:
    if raw and path:
        raise ValueError("Provide either --answers or --answers-file, not both.")
    if raw:
        return json.loads(raw)
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    raise ValueError("Missing --answers or --answers-file.")


def run(answers: dict[str, Any], *, no_fetch: bool, skill_root: Path, cwd: Path | None) -> dict[str, Any]:
    validate_answers(answers)

    catalog = update_models.run(no_fetch=no_fetch, skill_root=skill_root)
    tiers = catalog["tiers"]

    missing = [t for t in answers["tiers"] if t not in tiers]
    if missing:
        raise RuntimeError(
            f"Selected tier(s) {missing} are not available in the current catalog. "
            "Either remove them from the answers or pick alternatives."
        )

    report = generate_agents.generate(
        answers=answers,
        tiers=tiers,
        skill_root=skill_root,
        catalog_fetched_at=catalog["fetched_at"],
        existing_marker=None,
        cwd=cwd,
    )

    return {
        "ok": True,
        "catalog": {
            "fetched_at": catalog["fetched_at"],
            "source": catalog["source"],
            "stale": catalog["stale"],
            "tier_count": len(tiers),
        },
        "tiers_selected": answers["tiers"],
        "default_tier": answers["default_tier"],
        "scope": answers["scope"],
        "report": report,
        "next_steps": _next_steps(answers),
    }


def _next_steps(answers: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    steps.append(
        "In Plan Mode on your frontier model, draft a plan as usual. "
        "The skill will ask which implementation tier to use and write an "
        "`execution:` block into the plan frontmatter."
    )
    if answers["commands"]:
        steps.append(
            "To execute a saved plan: `/orchestrate .cursor/plans/<plan>.plan.md`"
        )
        steps.append(
            "To refresh the model catalog and regenerate agents: `/update-orchestrator`"
        )
    else:
        steps.append(
            "Slash command wrappers are disabled. Invoke the orchestrator "
            "directly with `/plan-orchestrator <plan-path>`."
        )
    steps.append(
        "Native Build button still runs on the picker model — use `/orchestrate` "
        "(or `/plan-orchestrator`) to execute on the tier you selected."
    )
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answers", type=str, default=None,
                        help="JSON string of setup interview answers.")
    parser.add_argument("--answers-file", type=Path, default=None,
                        help="Path to a file containing the answers JSON.")
    parser.add_argument("--no-fetch", action="store_true",
                        help="Skip the network fetch and load from fallback.")
    parser.add_argument("--skill-root", type=Path, default=SKILL_ROOT,
                        help="Path to the cursor-orchestrator skill root.")
    parser.add_argument("--cwd", type=Path, default=None,
                        help="Target project root (default: current working directory).")
    args = parser.parse_args()

    try:
        answers = _load_answers(args.answers, args.answers_file)
        result = run(
            answers=answers,
            no_fetch=args.no_fetch,
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
