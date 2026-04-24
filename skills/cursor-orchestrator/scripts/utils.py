"""
Shared helpers for the cursor-orchestrator scripts.

Stdlib only (no external deps). Used by update_models.py, generate_agents.py,
and setup.py.
"""

from __future__ import annotations

import hashlib
import json
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent
MARKER_FILENAME = ".cursor-orchestrator-installed"
CURRENT_VERSION = "0.1.0"

VALID_TIERS = ("composer", "fast", "mini", "haiku", "premium")
VALID_SCOPES = ("project", "user", "both")

TIER_DESCRIPTIONS: dict[str, str] = {
    "composer": "Best price/performance default for most implementation work.",
    "fast": "Cheapest Cursor tier — good for trivial edits and high-volume grunt work.",
    "mini": "Cheapest OpenAI model — fine for straightforward tasks.",
    "haiku": "Cheapest Anthropic model — fine for straightforward tasks.",
    "premium": "Runs on the same model as the orchestrator — escape hatch when an implementation step needs full reasoning power.",
}

CANONICAL_MODEL_IDS: dict[str, str] = {
    "Composer 1": "composer-1",
    "Composer 1.5": "composer-1.5",
    "Composer 2": "composer-2",
    "Composer 3": "composer-3",
    "Claude 4 Sonnet": "claude-4-sonnet",
    "Claude 4 Sonnet 1M": "claude-4-sonnet-1m",
    "Claude 4.5 Sonnet": "claude-sonnet-4-5",
    "Claude 4.6 Sonnet": "claude-sonnet-4-6",
    "Claude 4.5 Haiku": "claude-haiku-4-5",
    "Claude 4.5 Opus": "claude-opus-4-5",
    "Claude 4.6 Opus": "claude-opus-4-6",
    "Claude 4.7 Opus": "claude-opus-4-7",
    "GPT-5": "gpt-5",
    "GPT-5 Fast": "gpt-5-fast",
    "GPT-5 Mini": "gpt-5-mini",
    "GPT-5-Codex": "gpt-5-codex",
    "GPT-5.1 Codex": "gpt-5.1-codex",
    "GPT-5.1 Codex Max": "gpt-5.1-codex-max",
    "GPT-5.1 Codex Mini": "gpt-5.1-codex-mini",
    "GPT-5.2": "gpt-5.2",
    "GPT-5.2 Codex": "gpt-5.2-codex",
    "GPT-5.3 Codex": "gpt-5.3-codex",
    "GPT-5.4": "gpt-5.4",
    "GPT-5.4 Mini": "gpt-5.4-mini",
    "GPT-5.4 Nano": "gpt-5.4-nano",
    "Gemini 2.5 Flash": "gemini-2.5-flash",
    "Gemini 3 Flash": "gemini-3-flash",
    "Gemini 3 Pro": "gemini-3-pro",
    "Gemini 3.1 Pro": "gemini-3.1-pro",
    "Grok 4.20": "grok-4.20",
    "Kimi K2.5": "kimi-k2.5",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(name: str) -> str:
    """Fallback for converting a display name to a model-id slug."""
    s = name.lower()
    s = re.sub(r"[^\w\s.-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def derive_model_id(name: str) -> str:
    if name in CANONICAL_MODEL_IDS:
        return CANONICAL_MODEL_IDS[name]
    return slugify(name)


def fetch_url(url: str, timeout: float = 15.0) -> str:
    """
    Fetch a URL and return the response body as a UTF-8 string.

    Uses a realistic User-Agent since cursor.com may block default urllib.
    Raises urllib.error.URLError on failure.
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "cursor-orchestrator/{ver} (https://cursor.com/docs/skills)"
            ).format(ver=CURRENT_VERSION),
            "Accept": "text/markdown, text/html;q=0.9, */*;q=0.5",
        },
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read().decode("utf-8", errors="replace")


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
    Return the list of directories where agents/ and rules/ should be written.

    - "project" → <cwd>/.cursor
    - "user"    → ~/.cursor
    - "both"    → both of the above
    """
    cwd = cwd or Path.cwd()
    if scope == "project":
        return [cwd / ".cursor"]
    if scope == "user":
        return [Path.home() / ".cursor"]
    if scope == "both":
        return [cwd / ".cursor", Path.home() / ".cursor"]
    raise ValueError(f"Unknown scope: {scope!r}. Expected one of {VALID_SCOPES}.")


def validate_answers(answers: dict[str, Any]) -> None:
    """
    Validate the setup interview answers. Raises ValueError on bad input.
    """
    required = {
        "scope": str,
        "tiers": list,
        "default_tier": str,
        "verifier": bool,
        "rule": bool,
        "commands": bool,
        "max_mode": bool,
    }
    for key, typ in required.items():
        if key not in answers:
            raise ValueError(f"Missing required answer: {key!r}")
        if not isinstance(answers[key], typ):
            raise ValueError(
                f"Answer {key!r} must be {typ.__name__}, got {type(answers[key]).__name__}"
            )

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
            f"default_tier {answers['default_tier']!r} must be one of the selected tiers: {answers['tiers']}."
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
        cwd / ".cursor" / "agents" / MARKER_FILENAME,
        Path.home() / ".cursor" / "agents" / MARKER_FILENAME,
    ]
