#!/usr/bin/env python3
"""
Analyze the target codebase and collect signals for agent roster composition.

Pure data collection — no opinions on what agents to generate. The skill body
reads this snapshot alongside references/AGENT_PATTERNS.md and composes the
roster using Claude's reasoning.

Outputs a JSON snapshot to stdout. Exits 0 always; on errors a 'warnings' key
in the output lists what failed. Stdlib only (no pip deps).

Usage:
    python scripts/analyze_codebase.py [--cwd <path>] [--pretty]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import now_iso, sha256_file

# Directories to skip in all recursive scans
SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", "out",
    "target", ".venv", "venv", "__pycache__", ".turbo", ".cache",
    "coverage", ".nyc_output", "storybook-static", ".svelte-kit",
}

MAX_FILES_PER_SIGNAL = 100
MAX_GLOB_DEPTH = 6


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None


def _safe_read_text(path: Path, max_bytes: int = 8192) -> str | None:
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            return f.read(max_bytes)
    except OSError:
        return None


def _walk_limited(root: Path, max_depth: int) -> list[Path]:
    """Walk a directory tree up to max_depth, skipping SKIP_DIRS."""
    result: list[Path] = []
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack and len(result) < MAX_FILES_PER_SIGNAL * 10:
        current, depth = stack.pop()
        try:
            for child in sorted(current.iterdir()):
                if child.is_dir():
                    if child.name in SKIP_DIRS:
                        continue
                    if depth < max_depth:
                        stack.append((child, depth + 1))
                elif child.is_file():
                    result.append(child)
        except (OSError, PermissionError):
            pass
    return result


def _glob_capped(root: Path, pattern: str, max_depth: int = MAX_GLOB_DEPTH) -> list[Path]:
    """Glob pattern under root, capped at MAX_FILES_PER_SIGNAL, skipping SKIP_DIRS."""
    results: list[Path] = []
    all_files = _walk_limited(root, max_depth)
    # Simple pattern matching: support ** and * glob semantics via re
    regex = re.compile(
        "^" + re.escape(pattern)
        .replace(r"\*\*", ".+")
        .replace(r"\*", "[^/]+") + "$"
    )
    for f in all_files:
        rel = str(f.relative_to(root)).replace(os.sep, "/")
        if regex.match(rel):
            results.append(f)
            if len(results) >= MAX_FILES_PER_SIGNAL:
                break
    return results


def collect_manifests(cwd: Path) -> dict[str, Any]:
    """Collect key manifest files and their parsed content."""
    manifests: dict[str, Any] = {}
    candidates = [
        ("package_json", "package.json"),
        ("pyproject_toml", "pyproject.toml"),
        ("cargo_toml", "Cargo.toml"),
        ("go_mod", "go.mod"),
        ("gemfile", "Gemfile"),
        ("nest_cli", "nest-cli.json"),
        ("next_config_js", "next.config.js"),
        ("next_config_ts", "next.config.ts"),
        ("next_config_mjs", "next.config.mjs"),
        ("vite_config", "vite.config.ts"),
        ("vite_config_js", "vite.config.js"),
        ("turbo_json", "turbo.json"),
        ("nx_json", "nx.json"),
        ("pnpm_workspace", "pnpm-workspace.yaml"),
        ("drizzle_config", "drizzle.config.ts"),
        ("drizzle_config_js", "drizzle.config.js"),
        ("prisma_schema", "prisma/schema.prisma"),
    ]
    for key, rel_path in candidates:
        path = cwd / rel_path
        if not path.exists():
            continue
        if path.suffix == ".json":
            parsed = _safe_read_json(path)
            if parsed is not None:
                manifests[key] = {"path": rel_path, "content": parsed}
        else:
            text = _safe_read_text(path, 4096)
            if text:
                manifests[key] = {"path": rel_path, "snippet": text[:2048]}
    return manifests


def detect_package_manager(cwd: Path) -> str:
    """Detect the primary package manager from lock file presence."""
    checks = [
        ("bun.lock", "bun"),
        ("bun.lockb", "bun"),
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("package-lock.json", "npm"),
        ("poetry.lock", "poetry"),
        ("Pipfile.lock", "pipenv"),
        ("Cargo.lock", "cargo"),
        ("go.sum", "go"),
    ]
    for filename, manager in checks:
        if (cwd / filename).exists():
            return manager
    return "unknown"


def detect_languages(cwd: Path, manifests: dict[str, Any]) -> list[str]:
    """Infer primary languages from manifest and file presence."""
    langs: list[str] = []
    if "package_json" in manifests or "next_config_js" in manifests:
        # Determine TypeScript vs JavaScript
        ts_indicators = [
            cwd / "tsconfig.json",
            cwd / "tsconfig.base.json",
        ]
        if any(p.exists() for p in ts_indicators):
            langs.append("typescript")
        else:
            langs.append("javascript")
    if "pyproject_toml" in manifests or (cwd / "requirements.txt").exists():
        langs.append("python")
    if "cargo_toml" in manifests:
        langs.append("rust")
    if "go_mod" in manifests:
        langs.append("go")
    if "gemfile" in manifests:
        langs.append("ruby")
    return langs or ["unknown"]


def detect_frameworks(cwd: Path, manifests: dict[str, Any]) -> list[str]:
    """Detect frontend and backend frameworks."""
    frameworks: list[str] = []

    pkg = (manifests.get("package_json") or {}).get("content", {})
    all_deps = {
        **pkg.get("dependencies", {}),
        **pkg.get("devDependencies", {}),
    }

    if "nest_cli" in manifests or "@nestjs/core" in all_deps:
        frameworks.append("nestjs")
    if "next_config_js" in manifests or "next_config_ts" in manifests or "next" in all_deps:
        frameworks.append("nextjs")
    if "nuxt" in all_deps or (cwd / "nuxt.config.ts").exists() or (cwd / "nuxt.config.js").exists():
        frameworks.append("nuxtjs")
    if "vite_config" in manifests or "vite" in all_deps:
        frameworks.append("vite")
    if "remix" in all_deps or (cwd / "remix.config.js").exists():
        frameworks.append("remix")
    if "react" in all_deps and not frameworks:
        frameworks.append("react")
    if "vue" in all_deps and not frameworks:
        frameworks.append("vue")

    # Python
    pyproject = (manifests.get("pyproject_toml") or {}).get("snippet", "")
    if "fastapi" in pyproject.lower() or (cwd / "main.py").exists():
        # Quick check for FastAPI import
        main_py = _safe_read_text(cwd / "main.py", 1024) or ""
        if "fastapi" in main_py.lower() or "fastapi" in pyproject.lower():
            frameworks.append("fastapi")
    if (cwd / "manage.py").exists() or "django" in pyproject.lower():
        frameworks.append("django")

    return frameworks


def detect_monorepo(cwd: Path, manifests: dict[str, Any]) -> dict[str, Any]:
    """Detect monorepo markers."""
    mono: dict[str, Any] = {"is_monorepo": False, "type": None, "workspace_dirs": []}

    if "turbo_json" in manifests:
        mono["is_monorepo"] = True
        mono["type"] = "turborepo"
    elif "nx_json" in manifests:
        mono["is_monorepo"] = True
        mono["type"] = "nx"
    elif "pnpm_workspace" in manifests:
        mono["is_monorepo"] = True
        mono["type"] = "pnpm-workspaces"
    else:
        pkg = (manifests.get("package_json") or {}).get("content", {})
        if "workspaces" in pkg:
            mono["is_monorepo"] = True
            mono["type"] = "npm-workspaces"

    if mono["is_monorepo"]:
        for candidate in ["apps", "packages", "services", "libs", "modules"]:
            if (cwd / candidate).is_dir():
                mono["workspace_dirs"].append(candidate)

    return mono


def detect_test_runner(manifests: dict[str, Any]) -> str:
    """Detect the primary test runner."""
    pkg = (manifests.get("package_json") or {}).get("content", {})
    all_deps = {
        **pkg.get("dependencies", {}),
        **pkg.get("devDependencies", {}),
    }
    scripts = pkg.get("scripts", {})
    test_script = scripts.get("test", "")

    if "bun" in test_script or "@types/bun" in all_deps:
        return "bun:test"
    if "vitest" in all_deps:
        return "vitest"
    if "jest" in all_deps or "@jest/core" in all_deps:
        return "jest"

    pyproject = (manifests.get("pyproject_toml") or {}).get("snippet", "")
    if "pytest" in pyproject:
        return "pytest"

    cargo_toml = (manifests.get("cargo_toml") or {}).get("snippet", "")
    if cargo_toml:
        return "cargo test"

    go_mod = (manifests.get("go_mod") or {}).get("snippet", "")
    if go_mod:
        return "go test"

    return "unknown"


def detect_orms(cwd: Path, manifests: dict[str, Any]) -> list[str]:
    """Detect ORM / migration tools."""
    orms: list[str] = []
    if "prisma_schema" in manifests or (cwd / "prisma").is_dir():
        orms.append("prisma")
    if "drizzle_config" in manifests or "drizzle_config_js" in manifests:
        orms.append("drizzle")
    pkg = (manifests.get("package_json") or {}).get("content", {})
    all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    if "typeorm" in all_deps:
        orms.append("typeorm")
    if "mongoose" in all_deps:
        orms.append("mongoose")
    if (cwd / "alembic.ini").exists():
        orms.append("alembic")
    for migrations_dir in ["migrations", "db/migrations", "database/migrations"]:
        if (cwd / migrations_dir).is_dir():
            if "alembic" not in orms:
                orms.append("generic-migrations")
            break
    return orms


def detect_architectural_signals(cwd: Path) -> list[dict[str, Any]]:
    """Detect architectural patterns (DDD, CQRS, etc.) via depth-limited globs."""
    signals: list[dict[str, Any]] = []

    checks: list[tuple[str, str, str]] = [
        ("ddd_entities", "**/modules/*/domain/*.entity.ts", "DDD domain entities"),
        ("ddd_modules", "**/modules/*/domain", "DDD module directory structure"),
        ("hexagonal_domain", "**/domain/*.ts", "Hexagonal domain layer"),
        ("cqrs_commands", "**/*.command.ts", "CQRS command handlers"),
        ("cqrs_queries", "**/*.query.ts", "CQRS query handlers"),
        ("cqrs_handlers", "**/*.handler.ts", "CQRS command/query handlers"),
        ("bullmq_processors", "**/*.processor.ts", "BullMQ job processors"),
        ("bullmq_workers", "**/*.worker.ts", "Background workers"),
        ("integration_events", "**/integration-events/*.ts", "Integration events"),
        ("event_files", "**/*.event.ts", "Domain events"),
        ("celery_tasks", "**/tasks/*.py", "Celery/async tasks"),
        ("server_actions", "**/actions/*.ts", "Next.js server actions"),
        ("server_actions_dir", "app/**/actions.ts", "Next.js server actions file"),
        ("api_routes_app", "app/**/route.ts", "Next.js App Router route handlers"),
        ("fastapi_routers", "**/routers/*.py", "FastAPI routers"),
        ("fastapi_schemas", "**/schemas/*.py", "Pydantic schemas"),
    ]

    for signal_id, pattern, description in checks:
        matches = _glob_capped(cwd, pattern, max_depth=MAX_GLOB_DEPTH)
        if matches:
            signals.append({
                "signal": signal_id,
                "description": description,
                "count": len(matches),
                "sample_paths": [
                    str(m.relative_to(cwd)).replace(os.sep, "/")
                    for m in matches[:3]
                ],
            })

    return signals


def detect_mcp_integrations(cwd: Path) -> list[str]:
    """Detect MCP servers configured in .mcp.json."""
    mcp_path = cwd / ".mcp.json"
    if not mcp_path.is_file():
        return []
    data = _safe_read_json(mcp_path)
    if not data:
        return []
    servers = data.get("mcpServers", data.get("servers", {}))
    return list(servers.keys()) if isinstance(servers, dict) else []


def detect_existing_agents(cwd: Path) -> list[dict[str, Any]]:
    """Enumerate existing .claude/agents/*.md files (for registration)."""
    agents_dir = cwd / ".claude" / "agents"
    if not agents_dir.is_dir():
        return []
    existing: list[dict[str, Any]] = []
    for p in sorted(agents_dir.glob("*.md")):
        if p.name.startswith("."):
            continue
        sha = sha256_file(p) or ""
        # Attempt to extract frontmatter name/description
        text = _safe_read_text(p, 1024) or ""
        name_match = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
        desc_match = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
        existing.append({
            "path": str(p.relative_to(cwd)).replace(os.sep, "/"),
            "sha": sha,
            "name": (name_match.group(1).strip() if name_match else p.stem),
            "description_snippet": (
                (desc_match.group(1).strip()[:80] + "…") if desc_match else ""
            ),
        })
    return existing


def compute_fingerprint(cwd: Path, manifests: dict[str, Any]) -> str:
    """SHA256 of sorted (path, sha) pairs for key manifest files."""
    fingerprint_paths = [
        "package.json", "pyproject.toml", "Cargo.toml", "go.mod",
        "prisma/schema.prisma", "nest-cli.json", "turbo.json",
        "pnpm-workspace.yaml", "tsconfig.json", "tsconfig.base.json",
    ]
    parts: list[str] = []
    for rel in sorted(fingerprint_paths):
        p = cwd / rel
        if p.is_file():
            sha = sha256_file(p) or ""
            parts.append(f"{rel}:{sha}")
    combined = "\n".join(parts)
    return "sha256:" + hashlib.sha256(combined.encode()).hexdigest()[:16]


def run(cwd: Path | None = None) -> dict[str, Any]:
    cwd = cwd or Path.cwd()
    warnings: list[str] = []
    snapshot: dict[str, Any] = {
        "analyzed_at": now_iso(),
        "cwd": str(cwd),
        "warnings": warnings,
    }

    try:
        manifests = collect_manifests(cwd)
        snapshot["languages"] = detect_languages(cwd, manifests)
        snapshot["package_manager"] = detect_package_manager(cwd)
        snapshot["frameworks"] = detect_frameworks(cwd, manifests)
        snapshot["test_runner"] = detect_test_runner(manifests)
        snapshot["orms"] = detect_orms(cwd, manifests)
        monorepo = detect_monorepo(cwd, manifests)
        snapshot["monorepo"] = monorepo["is_monorepo"]
        snapshot["monorepo_type"] = monorepo["type"]
        snapshot["workspace_dirs"] = monorepo["workspace_dirs"]
        snapshot["architectural_signals"] = detect_architectural_signals(cwd)
        snapshot["mcp_integrations"] = detect_mcp_integrations(cwd)
        snapshot["existing_agents"] = detect_existing_agents(cwd)
        snapshot["fingerprint"] = compute_fingerprint(cwd, manifests)
        # Summary of manifest keys present (without full content for brevity)
        snapshot["manifests_present"] = list(manifests.keys())
    except Exception as exc:
        warnings.append(f"analysis error: {exc}")

    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=Path, default=None)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    result = run(cwd=args.cwd)
    indent = 2 if args.pretty else None
    json.dump(result, sys.stdout, indent=indent)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
