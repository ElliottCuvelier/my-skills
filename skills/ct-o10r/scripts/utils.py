"""
Shared helpers for the ct-o10r (claudeteam-orchestrator) scripts.

Stdlib only (no external deps). Used by generate_agents.py, setup.py,
analyze_codebase.py, and detect_byterover.py.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent
MARKER_FILENAME = ".ct-o10r-installed"
CURRENT_VERSION = "0.1.1"

VALID_TIERS = ("haiku", "sonnet", "opus", "inherit")
VALID_SCOPES = ("project", "user", "both")
# Team-native hooks. "tests" installs the TaskCreated files-sidecar + the
# TaskCompleted test gate (a pair); "taskids" installs the TeammateIdle
# ByteRover-taskId backstop collector.
VALID_HOOKS = ("taskids", "tests")

TIER_DESCRIPTIONS: dict[str, str] = {
    "haiku": "Fastest and cheapest Claude tier — good for straightforward edits, "
             "bulk changes, and high-volume grunt work.",
    "sonnet": "Best price/performance balance — the default for most implementation "
              "work.",
    "opus": "Most capable Claude tier — escape hatch when an implementation step "
            "needs full reasoning power.",
    "inherit": "Runs on the same model as the team lead — useful when you want "
               "a teammate to have the same capability as the planner.",
}

TIER_MODEL_LABELS: dict[str, str] = {
    "haiku": "Claude Haiku",
    "sonnet": "Claude Sonnet",
    "opus": "Claude Opus",
    "inherit": "Inherit (same as team lead)",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^\w\s.-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return sha256_text(path.read_text(encoding="utf-8"))


def render_template(template_text: str, variables: dict[str, str]) -> str:
    """
    Simple ${var} substitution. We roll our own (instead of string.Template)
    because the template body contains markdown where $ could otherwise be
    misinterpreted. Only ${name} style is treated as a placeholder.
    """
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            raise KeyError(f"Template variable ${{{key}}} was not provided")
        return variables[key]

    return re.sub(r"\$\{(\w+)\}", repl, template_text)


def resolve_target_roots(scope: str, cwd: Path | None = None) -> list[Path]:
    """
    Return the list of .claude base directories where agents/ and commands/ should
    be written.

    - "project" → <cwd>/.claude
    - "user"    → ~/.claude
    - "both"    → both of the above
    """
    cwd = cwd or Path.cwd()
    if scope == "project":
        return [cwd / ".claude"]
    if scope == "user":
        return [Path.home() / ".claude"]
    if scope == "both":
        return [cwd / ".claude", Path.home() / ".claude"]
    raise ValueError(f"Unknown scope: {scope!r}. Expected one of {VALID_SCOPES}.")


def validate_answers(answers: dict[str, Any]) -> None:
    """Validate the setup interview answers. Raises ValueError on bad input."""
    required: dict[str, type] = {
        "scope": str,
        "tiers": list,
        "default_tier": str,
        "verifier": bool,
        "memory_curator": bool,
        "commands": bool,
        "byterover_enabled": bool,
    }
    for key, typ in required.items():
        if key not in answers:
            raise ValueError(f"Missing required answer: {key!r}")
        if not isinstance(answers[key], typ):
            raise ValueError(
                f"Answer {key!r} must be {typ.__name__}, got {type(answers[key]).__name__}"
            )

    # hooks is optional — default to empty list for backward compatibility
    answers.setdefault("hooks", [])
    if not isinstance(answers["hooks"], list):
        raise ValueError("Answer 'hooks' must be a list")
    bad_hooks = [h for h in answers["hooks"] if h not in VALID_HOOKS]
    if bad_hooks:
        raise ValueError(f"Invalid hook(s): {bad_hooks!r}. Valid: {list(VALID_HOOKS)}.")

    if answers["scope"] not in VALID_SCOPES:
        raise ValueError(
            f"Invalid scope {answers['scope']!r}. Expected one of {VALID_SCOPES}."
        )

    bad_tiers = [t for t in answers["tiers"] if t not in VALID_TIERS]
    if bad_tiers:
        raise ValueError(
            f"Invalid tier(s): {bad_tiers}. Valid tiers: {list(VALID_TIERS)}."
        )

    if not answers["tiers"]:
        raise ValueError("At least one tier must be selected.")

    if answers["default_tier"] not in answers["tiers"]:
        raise ValueError(
            f"default_tier {answers['default_tier']!r} must be one of the selected "
            f"tiers: {answers['tiers']}."
        )


def load_marker(marker_path: Path) -> dict[str, Any] | None:
    if not marker_path.is_file():
        return None
    try:
        return json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_marker(marker_path: Path, data: dict[str, Any]) -> None:
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def find_marker_paths(cwd: Path | None = None) -> list[Path]:
    """Return marker paths for all possible install locations, in precedence order."""
    cwd = cwd or Path.cwd()
    return [
        cwd / ".claude" / "agents" / MARKER_FILENAME,
        Path.home() / ".claude" / "agents" / MARKER_FILENAME,
    ]


def find_skill_dir(cwd: Path | None = None) -> Path:
    """
    Locate the installed skill directory. Searches:
      1. <cwd>/.claude/skills/ct-o10r/
      2. ~/.claude/skills/ct-o10r/
    Returns the first hit, or raises RuntimeError if not found.
    """
    cwd = cwd or Path.cwd()
    candidates = [
        cwd / ".claude" / "skills" / "ct-o10r",
        Path.home() / ".claude" / "skills" / "ct-o10r",
    ]
    for c in candidates:
        if (c / "scripts" / "setup.py").is_file():
            return c
    raise RuntimeError(
        "ct-o10r skill not found. "
        "Add it to your skills-lock.json and run the installer."
    )
