#!/usr/bin/env python3
"""
Detect ByteRover installation status for claude-orchestrator.

Checks (in order of decreasing reliability):
  1. brv CLI on PATH (most reliable — this is the canonical install)
  2. ~/.claude/skills/byterover/SKILL.md present (skill installed globally)
  3. <cwd>/.claude/skills/byterover/SKILL.md present (skill installed locally)
  4. <cwd>/.brv/context-tree/ present (context tree initialized)

Outputs JSON to stdout. Exits 0 always (detection failure is not fatal).

Usage:
    python scripts/detect_byterover.py [--cwd <path>]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import now_iso


def _run(cmd: list[str], timeout: float = 5.0) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 1, ""


def detect(cwd: Path | None = None) -> dict:
    cwd = cwd or Path.cwd()

    result: dict = {
        "detected_at": now_iso(),
        "installed": False,
        "cli_version": None,
        "skill_present": False,
        "skill_path": None,
        "context_tree_present": False,
        "subtrees_detected": [],
        "recommendation": None,
    }

    # 1. CLI on PATH
    rc, output = _run(["brv", "--version"])
    if rc == 0:
        result["installed"] = True
        # Extract version from "byterover-cli/1.x.y" or just the output
        version_line = output.strip().split("\n")[0]
        result["cli_version"] = version_line or "unknown"

    # 2. Skill file presence
    skill_candidates = [
        Path.home() / ".claude" / "skills" / "byterover" / "SKILL.md",
        cwd / ".claude" / "skills" / "byterover" / "SKILL.md",
    ]
    for candidate in skill_candidates:
        if candidate.is_file():
            result["skill_present"] = True
            result["skill_path"] = str(candidate)
            break

    # 3. Context tree presence
    context_tree = cwd / ".brv" / "context-tree"
    if context_tree.is_dir():
        result["context_tree_present"] = True
        # Enumerate top-level subtrees (depth 2 from context-tree/)
        subtrees: list[str] = []
        try:
            for top in sorted(context_tree.iterdir()):
                if top.is_dir():
                    subtrees.append(top.name + "/")
                    for sub in sorted(top.iterdir()):
                        if sub.is_dir():
                            subtrees.append(top.name + "/" + sub.name + "/")
        except OSError:
            pass
        result["subtrees_detected"] = subtrees

    # 4. Recommendation if not installed
    if not result["installed"] and not result["skill_present"] and not result["context_tree_present"]:
        result["recommendation"] = (
            "ByteRover is not installed. To enable the Recall → Work → Curate loop:\n"
            "  npm install -g byterover-cli\n"
            "  brv providers connect byterover   # free, no API key\n"
            "  brv status                         # verify\n"
            "\n"
            "You can also skip and the generated agents will omit the memory loop."
        )

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=Path, default=None)
    args = parser.parse_args()

    result = detect(cwd=args.cwd)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
