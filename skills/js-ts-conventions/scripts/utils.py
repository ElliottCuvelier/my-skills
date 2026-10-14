"""Shared helpers for the js-ts-conventions scripts. Stdlib only."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_VERSION = "1.0.0"
SKILL_DIR = Path(__file__).resolve().parent.parent
CATALOG_PATH = SKILL_DIR / "preferences.json"
PLUGIN_TEMPLATE = SKILL_DIR / "templates" / "plugin.mjs"

STATE_DIR = ".js-ts-conventions"
MANIFEST_NAME = "manifest.json"
OVERRIDES_NAME = "overrides.json"
PLUGIN_NAMESPACE = "js-ts-conventions"

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", "out", ".turbo", ".cache",
    "coverage", ".nyc_output", "storybook-static", ".svelte-kit", ".vercel",
    ".output", ".nuxt", ".expo", "target", ".venv", "venv", "__pycache__",
    STATE_DIR,
}

SEVERITIES = {"off", "warn", "error"}

# Agent tooling folders hold vendored skills and rule files, not the repo's code.
AGENT_TOOLING_DIRS = (".claude/", ".agents/", ".cursor/", ".codex/", ".opencode/", ".windsurf/")


def is_agent_tooling(path: str) -> bool:
    return path.startswith(AGENT_TOOLING_DIRS)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments plus trailing commas, respecting strings."""
    out: list[str] = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
        elif text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end == -1 else end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
        elif ch == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "}]":
                i += 1
            else:
                out.append(ch)
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def read_jsonc(path: Path) -> Any:
    """Parse a JSON-with-comments file. Returns None when missing or invalid."""
    try:
        return json.loads(strip_jsonc(path.read_text(encoding="utf-8", errors="replace")))
    except (OSError, json.JSONDecodeError):
        return None


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def rel(path: Path, root: Path) -> str:
    try:
        value = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
    return value or "."


def load_catalog() -> dict[str, Any]:
    catalog = read_json(CATALOG_PATH)
    if not isinstance(catalog, dict):
        raise SystemExit(f"Cannot read catalog at {CATALOG_PATH}")
    return catalog


def load_overrides(root: Path) -> dict[str, Any]:
    data = read_jsonc(root / STATE_DIR / OVERRIDES_NAME)
    if not isinstance(data, dict):
        data = {}
    for key in ("disabled", "severity", "exempt", "options", "scope"):
        if not isinstance(data.get(key), dict):
            data[key] = {}
    return data


def git_files(root: Path) -> list[str] | None:
    """Tracked + untracked-not-ignored files, or None outside a git work tree."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root, capture_output=True, timeout=60, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    files = [f for f in result.stdout.decode("utf-8", "replace").split("\0") if f]
    return [f for f in files if not any(part in SKIP_DIRS for part in f.split("/")[:-1])]


def walk_files(root: Path, max_depth: int = 12) -> list[str]:
    found: list[str] = []
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        try:
            children = sorted(current.iterdir())
        except OSError:
            continue
        for child in children:
            if child.is_dir():
                if child.name not in SKIP_DIRS and not child.is_symlink() and depth < max_depth:
                    stack.append((child, depth + 1))
            elif child.is_file():
                found.append(rel(child, root))
    return found


def source_files(root: Path) -> list[str]:
    files = git_files(root)
    if files is None:
        files = walk_files(root)
    return files


def find_up(start: Path, root: Path, relative: str) -> Path | None:
    """Look for `relative` in start and its parents, stopping at root."""
    current = start.resolve()
    stop = root.resolve()
    while True:
        candidate = current / relative
        if candidate.exists():
            return candidate
        if current == stop or current.parent == current:
            return None
        current = current.parent


def package_version(start: Path, root: Path, package: str) -> str | None:
    manifest = find_up(start, root, f"node_modules/{package}/package.json")
    data = read_json(manifest) if manifest else None
    return data.get("version") if isinstance(data, dict) else None


def local_bin(start: Path, root: Path, name: str) -> Path | None:
    return find_up(start, root, f"node_modules/.bin/{name}")


def version_tuple(version: str | None) -> tuple[int, ...]:
    if not version:
        return ()
    return tuple(int(part) for part in re.findall(r"\d+", version)[:3])


def glob_match(path: str, patterns: list[str]) -> bool:
    """Minimal `**` glob match with brace expansion, for heuristics only."""
    return any(fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch("/" + path, pattern)
               for raw in patterns for pattern in expand_braces(raw))


def expand_braces(pattern: str) -> list[str]:
    match = re.search(r"\{([^{}]*)\}", pattern)
    if not match:
        return [pattern]
    head, tail = pattern[: match.start()], pattern[match.end():]
    return [p for option in match.group(1).split(",") for p in expand_braces(head + option + tail)]


def anchor_glob(pattern: str) -> str:
    """Make a repo-relative glob match regardless of the config file location."""
    if pattern.startswith(("**/", "/")):
        return pattern.lstrip("/") if pattern.startswith("/") else pattern
    return "**/" + pattern


def normalize_oxlint_code(code: str) -> str:
    """`typescript(no-explicit-any)` -> `typescript/no-explicit-any`; `eslint(x)` -> `x`."""
    match = re.fullmatch(r"(.+?)\((.+)\)", code or "")
    if not match:
        return code
    scope, rule = match.groups()
    return rule if scope == "eslint" else f"{scope}/{rule}"


def rule_namespace(rule_id: str) -> str | None:
    return rule_id.rsplit("/", 1)[0] if "/" in rule_id else None


# ---------------------------------------------------------------------------
# Effective convention rules
# ---------------------------------------------------------------------------

def applicable_preferences(catalog: dict, overrides: dict, snapshot: dict | None = None) -> list[dict]:
    """Catalog entries left after overrides; `scope: ddd` needs a DDD layout unless forced."""
    disabled = overrides.get("disabled", {})
    forced_scope = overrides.get("scope", {})
    ddd = bool(snapshot and snapshot.get("ddd_layout", {}).get("detected"))
    result = []
    for pref in catalog["preferences"]:
        if pref["id"] in disabled:
            continue
        if pref.get("scope") == "ddd" and not ddd and not forced_scope.get(pref["id"]):
            continue
        result.append(pref)
    return result


def severity_for(pref: dict, catalog: dict, overrides: dict) -> str:
    override = overrides.get("severity", {}).get(pref["id"])
    if override in SEVERITIES:
        return override
    return catalog["levels"].get(pref["level"], "warn")


def file_set(pref: dict, catalog: dict) -> list[str]:
    files = pref.get("files", "all")
    if isinstance(files, list):
        return files
    return catalog["file_sets"].get(files, catalog["file_sets"]["all"])


def convention_rules(catalog: dict, overrides: dict, tool: str, snapshot: dict | None,
                unit: dict | None = None, type_aware: bool = False) -> list[dict]:
    """One entry per (preference, rule) for `tool` ('eslint' | 'oxlint') in one lint unit.

    Globs in `files` are relative to the unit directory.
    """
    unit = unit or {}
    entries: list[dict] = []
    for pref in applicable_preferences(catalog, overrides, snapshot):
        spec = pref.get("enforce", {}).get(tool)
        if not spec:
            continue
        files = file_set(pref, catalog)
        files_kind = pref.get("files") if isinstance(pref.get("files"), str) else "custom"
        alias = None
        if pref.get("requires") == "path_alias":
            scopes = unit.get("alias_scopes") or []
            if not scopes:
                continue
            alias = scopes[0]["alias"]
            if not any(scope["dir"] == "." for scope in scopes):
                files = [f"{scope['dir']}/{glob}" for scope in scopes for glob in files]
                files_kind = "custom"
        severity = severity_for(pref, catalog, overrides)
        if severity == "off":
            continue
        user_options = overrides.get("options", {}).get(pref["id"])
        groups = [(spec.get("rules", {}), False)]
        if type_aware:
            groups.append((spec.get("type_aware_rules", {}), True))
        for rules, is_type_aware in groups:
            for rule_id, options in rules.items():
                options = [dict(o) if isinstance(o, dict) else o for o in options]
                if pref.get("requires") == "path_alias":
                    options = alias_options(options, alias, user_options)
                elif isinstance(user_options, dict) and rule_namespace(rule_id) == PLUGIN_NAMESPACE:
                    options = [{**(options[0] if options else {}), **user_options}]
                entries.append({
                    "pref": pref["id"],
                    "rule": rule_id,
                    "severity": severity,
                    "options": options,
                    "files": files,
                    "files_kind": files_kind,
                    "type_aware": is_type_aware,
                    "autofix": pref.get("autofix", "none"),
                    "ignores": [*catalog["ignores"], *pref.get("ignores", [])],
                    "exempt": unit_relative_globs(overrides.get("exempt", {}).get(pref["id"], []),
                                                  unit.get("dir", ".")),
                })
    return entries


def unit_relative_globs(globs: list[str], unit_dir: str) -> list[str]:
    """Repo-root-relative globs -> unit-relative; `**/` globs apply everywhere."""
    if unit_dir in (".", ""):
        return list(globs)
    prefix = unit_dir.rstrip("/") + "/"
    result = []
    for glob in globs:
        if glob.startswith("**/"):
            result.append(glob)
        elif glob.startswith(prefix):
            result.append(glob[len(prefix):])
    return result


def alias_options(options: list, alias: str | None, user_options: Any) -> list:
    base = dict(options[0]) if options else {}
    if alias:
        base["alias"] = alias
    if isinstance(user_options, dict) and isinstance(user_options.get("max_parent_depth"), int):
        base["maxParentDepth"] = user_options["max_parent_depth"]
    return [base]


def rule_to_pref(entries: list[dict]) -> dict[str, str]:
    return {entry["rule"]: entry["pref"] for entry in entries}


def preference_by_id(catalog: dict) -> dict[str, dict]:
    return {pref["id"]: pref for pref in catalog["preferences"]}
