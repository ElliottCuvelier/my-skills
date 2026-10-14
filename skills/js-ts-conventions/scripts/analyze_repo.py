#!/usr/bin/env python3
"""
Collect the repo signals js-ts-conventions needs. Pure data collection, no opinions.

Finds lint units (each directory with its own oxlint/ESLint config), installed
linter versions, tsconfig strictness and path aliases, DDD folder layout,
frameworks, scripts, and the skill's own state (.js-ts-conventions/).

Prints a JSON snapshot to stdout. Exits 0 always; problems go to `warnings`.
Stdlib only.

Usage:
    python3 scripts/analyze_repo.py [--root <path>] [--pretty]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (  # noqa: E402
    MANIFEST_NAME, OVERRIDES_NAME, SKILL_VERSION, STATE_DIR, find_up, is_agent_tooling, local_bin,
    now_iso, package_version, read_json, read_jsonc, rel, source_files,
)

OXLINT_CONFIGS = (".oxlintrc.json", ".oxlintrc.jsonc", "oxlint.config.ts", "oxlint.config.mts",
                  "oxlint.config.js", "oxlint.config.mjs")
ESLINT_FLAT = tuple(f"eslint.config.{ext}" for ext in ("js", "mjs", "cjs", "ts", "mts", "cts"))
ESLINT_LEGACY = (".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yaml",
                 ".eslintrc.yml")
BIOME_CONFIGS = ("biome.json", "biome.jsonc")
PRETTIER_CONFIGS = (".prettierrc", ".prettierrc.json", ".prettierrc.js", ".prettierrc.cjs",
                    ".prettierrc.mjs", ".prettierrc.yaml", ".prettierrc.yml", "prettier.config.js",
                    "prettier.config.cjs", "prettier.config.mjs", "prettier.config.ts")
SOURCE_EXTENSIONS = ("d.ts", "ts", "tsx", "mts", "cts", "js", "jsx", "mjs", "cjs")
STRICT_FLAGS = ("strict", "noUncheckedIndexedAccess", "noImplicitOverride", "noImplicitReturns",
                "noFallthroughCasesInSwitch", "exactOptionalPropertyTypes", "verbatimModuleSyntax",
                "experimentalDecorators", "emitDecoratorMetadata")
FRAMEWORK_PACKAGES = {
    "next": "next", "react": "react", "@nestjs/core": "nestjs", "payload": "payload",
    "express": "express", "fastify": "fastify", "hono": "hono", "vue": "vue", "svelte": "svelte",
    "@angular/core": "angular", "@prisma/client": "prisma", "typeorm": "typeorm",
    "drizzle-orm": "drizzle", "zod": "zod", "@remix-run/react": "remix", "astro": "astro",
}
ALIAS_KEYS = ("@/*", "~/*", "#/*", "@src/*", "src/*")
STYLE_KEYWORDS = re.compile(r"camelCase|PascalCase|kebab-case|\bnull\b|import type|naming", re.I)


def config_dirs(files: list[str]) -> dict[str, list[str]]:
    """Map each directory to the config-ish filenames it contains."""
    wanted = set(OXLINT_CONFIGS + ESLINT_FLAT + ESLINT_LEGACY + BIOME_CONFIGS + PRETTIER_CONFIGS
                 + ("tsconfig.json", "package.json"))
    result: dict[str, list[str]] = {}
    for path in files:
        name = path.rsplit("/", 1)[-1]
        if name in wanted:
            directory = path.rsplit("/", 1)[0] if "/" in path else "."
            result.setdefault(directory, []).append(name)
    return result


def scripts_using(package_json: dict | None, tool: str) -> dict[str, str]:
    scripts = (package_json or {}).get("scripts") or {}
    return {name: cmd for name, cmd in scripts.items()
            if isinstance(cmd, str) and re.search(rf"\b{tool}\b", cmd)}


def oxlint_unit(root: Path, directory: str, filename: str) -> dict[str, Any]:
    unit_dir = root / directory
    config_path = unit_dir / filename
    unit: dict[str, Any] = {
        "dir": directory,
        "tool": "oxlint",
        "config": rel(config_path, root),
        "format": "json" if filename.endswith((".json", ".jsonc")) else "js",
        "binary": None,
        "version": package_version(unit_dir, root, "oxlint"),
        "type_aware_available": package_version(unit_dir, root, "oxlint-tsgolint") is not None,
    }
    binary = local_bin(unit_dir, root, "oxlint")
    unit["binary"] = str(binary) if binary else None
    if unit["format"] == "json":
        data = read_jsonc(config_path) or {}
        extends = data.get("extends") or []
        unit.update({
            "plugins": data.get("plugins"),
            "js_plugins": data.get("jsPlugins") or [],
            "ignore_patterns": data.get("ignorePatterns") or [],
            "extends": extends,
            "rules": data.get("rules") or {},
            "overrides": [o for o in data.get("overrides") or [] if isinstance(o, dict)],
            "has_conventions_extends": any(STATE_DIR in str(entry) for entry in extends),
        })
    package_json = read_json(unit_dir / "package.json")
    unit["scripts"] = scripts_using(package_json, "oxlint")
    return unit


def eslint_unit(root: Path, directory: str, filename: str, legacy: bool) -> dict[str, Any]:
    unit_dir = root / directory
    binary = local_bin(unit_dir, root, "eslint")
    config_path = unit_dir / filename
    text = ""
    try:
        text = config_path.read_text(encoding="utf-8", errors="replace")[:20000]
    except OSError:
        pass
    imports = re.findall(r"""(?:from|import\()\s*["']([^"']+)["']""", text)
    return {
        "dir": directory,
        "tool": "eslint",
        "config": rel(config_path, root),
        "format": "legacy" if legacy else "flat",
        "binary": str(binary) if binary else None,
        "version": package_version(unit_dir, root, "eslint"),
        "typescript_eslint_version": package_version(unit_dir, root, "typescript-eslint")
        or package_version(unit_dir, root, "@typescript-eslint/eslint-plugin"),
        "config_imports": [i for i in imports if not i.startswith("node:")],
        "has_conventions_import": STATE_DIR in text or "withConventions" in text,
        "scripts": scripts_using(read_json(unit_dir / "package.json"), "eslint"),
    }


def find_lint_units(root: Path, dirs: dict[str, list[str]], warnings: list[str]) -> list[dict]:
    units: list[dict] = []
    oxlint_dirs = sorted(d for d, names in dirs.items() if any(n in OXLINT_CONFIGS for n in names))
    for directory in oxlint_dirs:
        # oxlint loads nested configs itself, so a config under another oxlint dir is not a new unit.
        parent = next((o for o in oxlint_dirs if o != directory and (o == "." or directory.startswith(o + "/"))), None)
        filename = next(n for n in OXLINT_CONFIGS if n in dirs[directory])
        if parent is not None:
            host = next(u for u in units if u["tool"] == "oxlint" and u["dir"] == parent)
            host.setdefault("nested_configs", []).append(f"{directory}/{filename}")
            continue
        units.append(oxlint_unit(root, directory, filename))
    for directory, names in sorted(dirs.items()):
        flat = next((n for n in ESLINT_FLAT if n in names), None)
        legacy = next((n for n in ESLINT_LEGACY if n in names), None)
        if flat:
            units.append(eslint_unit(root, directory, flat, legacy=False))
        elif legacy:
            units.append(eslint_unit(root, directory, legacy, legacy=True))
            warnings.append(f"{directory}: legacy .eslintrc config; enforce supports flat config only "
                            "(migrate with `npx @eslint/migrate-config`).")
    for unit in units:
        prefix = "" if unit["dir"] == "." else unit["dir"] + "/"
        unit["nested_units"] = sorted(
            u["dir"] for u in units
            if u is not unit and u["tool"] == unit["tool"] and u["dir"] != "."
            and (unit["dir"] == "." or u["dir"].startswith(prefix))
        )
    return units


def resolve_extends(spec: str, config_dir: Path, root: Path) -> Path | None:
    if spec.startswith("."):
        candidate = (config_dir / spec).resolve()
        for option in (candidate, candidate.with_suffix(".json") if candidate.suffix != ".json" else candidate,
                       candidate / "tsconfig.json"):
            if option.is_file():
                return option
        return None
    for suffix in ("", ".json", "/tsconfig.json"):
        found = find_up(config_dir, root, f"node_modules/{spec}{suffix}")
        if found and found.is_file():
            return found
    package_dir = find_up(config_dir, root, f"node_modules/{spec}")
    if package_dir and package_dir.is_dir():
        manifest = read_json(package_dir / "package.json") or {}
        target = manifest.get("tsconfig")
        if isinstance(target, str) and (package_dir / target).is_file():
            return package_dir / target
    return None


def effective_tsconfig(path: Path, root: Path, warnings: list[str], seen: set | None = None) -> dict:
    seen = seen or set()
    if path in seen:
        return {}
    seen.add(path)
    data = read_jsonc(path)
    if not isinstance(data, dict):
        warnings.append(f"{rel(path, root)}: unreadable tsconfig")
        return {}
    merged: dict[str, Any] = {}
    extends = data.get("extends")
    for spec in ([extends] if isinstance(extends, str) else extends or []):
        target = resolve_extends(spec, path.parent, root)
        if target is None:
            warnings.append(f"{rel(path, root)}: cannot resolve extends `{spec}` (dependencies installed?)")
            continue
        merged.update(effective_tsconfig(target, root, warnings, seen))
    merged.update(data.get("compilerOptions") or {})
    return merged


def analyze_tsconfigs(root: Path, dirs: dict[str, list[str]], warnings: list[str]) -> list[dict]:
    configs = []
    for directory, names in sorted(dirs.items()):
        if "tsconfig.json" not in names:
            continue
        path = root / directory / "tsconfig.json"
        options = effective_tsconfig(path, root, warnings)
        paths = options.get("paths") or {}
        alias = next((key[:-1] for key in ALIAS_KEYS if key in paths), None)
        configs.append({
            "path": rel(path, root),
            "dir": directory,
            "flags": {flag: options.get(flag) for flag in STRICT_FLAGS},
            "path_aliases": sorted(paths.keys())[:20],
            "alias": alias,
        })
    return configs


def nearest_tsconfig(directory: str, tsconfigs: list[dict]) -> dict | None:
    candidates = [t for t in tsconfigs if t["dir"] == "." or directory == t["dir"]
                  or directory.startswith(t["dir"] + "/")]
    return max(candidates, key=lambda t: len(t["dir"]), default=None)


def alias_scopes(unit: dict, tsconfigs: list[dict]) -> list[dict]:
    """Directories (relative to the unit) whose nearest tsconfig defines a path alias."""
    prefix = "" if unit["dir"] == "." else unit["dir"] + "/"
    own = nearest_tsconfig(unit["dir"], tsconfigs)
    if own and own["alias"]:
        return [{"dir": ".", "alias": own["alias"]}]
    return [
        {"dir": t["dir"][len(prefix):] if prefix else t["dir"], "alias": t["alias"]}
        for t in tsconfigs
        if t["alias"] and t["dir"] != "." and (prefix == "" or t["dir"].startswith(prefix))
    ]


def ddd_layout(files: list[str]) -> dict:
    layer_dirs: dict[str, set[str]] = {}
    for path in files:
        parts = path.split("/")[:-1]
        for index, part in enumerate(parts):
            if part in ("domain", "application", "infrastructure"):
                parent = "/".join(parts[:index]) or "."
                layer_dirs.setdefault(parent, set()).add(part)
    modules = sorted(p for p, layers in layer_dirs.items() if "domain" in layers and len(layers) >= 2)
    return {"detected": bool(modules), "module_count": len(modules), "modules": modules[:20]}


def frameworks(root: Path, package_dirs: list[str]) -> list[str]:
    found: set[str] = set()
    for directory in package_dirs:
        manifest = read_json(root / directory / "package.json") or {}
        deps = {**(manifest.get("dependencies") or {}), **(manifest.get("devDependencies") or {})}
        found.update(name for pkg, name in FRAMEWORK_PACKAGES.items() if pkg in deps)
    return sorted(found)


def file_counts(files: list[str]) -> dict[str, int]:
    counts = {ext: 0 for ext in SOURCE_EXTENSIONS}
    for path in files:
        for ext in SOURCE_EXTENSIONS:
            if path.endswith("." + ext):
                counts[ext] += 1
                break
    return counts


def existing_style_rules(root: Path, files: list[str]) -> list[str]:
    candidates = [f for f in files if f.startswith((".cursor/rules/", ".claude/rules/"))
                  or f in ("CLAUDE.md", "AGENTS.md", ".cursorrules")]
    hits = []
    for path in candidates:
        try:
            text = (root / path).read_text(encoding="utf-8", errors="replace")[:30000]
        except OSError:
            continue
        if len(STYLE_KEYWORDS.findall(text)) >= 3 and "js-ts-conventions" not in path:
            hits.append(path)
    return hits[:10]


def tooling(root: Path, dirs: dict[str, list[str]], files: list[str]) -> dict:
    root_pkg = read_json(root / "package.json") or {}
    return {
        "package_manager": next((pm for lock, pm in (("pnpm-lock.yaml", "pnpm"), ("bun.lock", "bun"),
                                                       ("bun.lockb", "bun"), ("yarn.lock", "yarn"),
                                                       ("package-lock.json", "npm"))
                                 if (root / lock).exists()), None),
        "workspaces": root_pkg.get("workspaces") or ((root / "pnpm-workspace.yaml").exists() or None),
        "turbo": (root / "turbo.json").exists(),
        "prettier": sorted(f"{d}/{n}" if d != "." else n for d, names in dirs.items()
                           for n in names if n in PRETTIER_CONFIGS)[:10],
        "biome": sorted(f"{d}/{n}" if d != "." else n for d, names in dirs.items()
                        for n in names if n in BIOME_CONFIGS)[:10],
        "git_hooks": [hook for hook, present in (
            ("husky", (root / ".husky").is_dir()),
            ("lefthook", (root / "lefthook.yml").exists() or (root / "lefthook.yaml").exists()),
            ("lint-staged", "lint-staged" in root_pkg or any(f.startswith(".lintstagedrc") for f in files)),
        ) if present],
        "ci": [f for f in files if f.startswith(".github/workflows/")
               or f in (".gitlab-ci.yml", "bitbucket-pipelines.yml", "azure-pipelines.yml")][:10],
    }


def conventions_state(root: Path) -> dict:
    state_dir = root / STATE_DIR
    manifest = read_json(state_dir / MANIFEST_NAME)
    return {
        "installed": isinstance(manifest, dict),
        "manifest": manifest if isinstance(manifest, dict) else None,
        "overrides_present": (state_dir / OVERRIDES_NAME).exists(),
        "report_present": (state_dir / "REPORT.md").exists(),
        "plan_present": (state_dir / "PLAN.md").exists(),
    }


def analyze(root: Path) -> dict:
    warnings: list[str] = []
    files = source_files(root)
    code_files = [f for f in files if not is_agent_tooling(f)]
    dirs = config_dirs(code_files)
    units = find_lint_units(root, dirs, warnings)
    tsconfigs = analyze_tsconfigs(root, dirs, warnings)
    for unit in units:
        unit["alias_scopes"] = alias_scopes(unit, tsconfigs)
        unit["decorator_metadata"] = any(
            t["flags"].get("emitDecoratorMetadata") for t in tsconfigs
            if unit["dir"] == "." or t["dir"] == unit["dir"] or t["dir"].startswith(unit["dir"] + "/")
        )
    package_dirs = sorted(d for d, names in dirs.items() if "package.json" in names)
    shared = [d for d in package_dirs if re.search(r"(eslint|oxlint|lint)-config", d)
              or re.search(r"(eslint|oxlint)-config", str((read_json(root / d / "package.json") or {}).get("name", "")))]
    snapshot = {
        "skill_version": SKILL_VERSION,
        "generated_at": now_iso(),
        "root": str(root.resolve()),
        "lint_units": units,
        "shared_config_packages": shared,
        "tsconfigs": tsconfigs,
        "decorator_metadata": any(t["flags"].get("emitDecoratorMetadata") for t in tsconfigs),
        "ddd_layout": ddd_layout(code_files),
        "frameworks": frameworks(root, package_dirs),
        "packages": package_dirs[:50],
        "file_counts": file_counts(code_files),
        "tooling": tooling(root, dirs, files),
        "existing_style_rules": existing_style_rules(root, files),
        "conventions_state": conventions_state(root),
        "warnings": warnings,
    }
    if not units:
        warnings.append("No oxlint or ESLint config found; audit will use `npx oxlint` as a stand-in engine.")
    if snapshot["tooling"]["biome"]:
        warnings.append("Biome config found; js-ts-conventions v1 enforces through oxlint/ESLint only.")
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".", help="Repository root (default: cwd)")
    parser.add_argument("--pretty", action="store_true", help="Indent JSON output")
    args = parser.parse_args()
    snapshot = analyze(Path(args.root).resolve())
    print(json.dumps(snapshot, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
