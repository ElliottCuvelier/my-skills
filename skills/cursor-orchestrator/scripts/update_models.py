#!/usr/bin/env python3
"""
Fetch cursor.com/docs/models-and-pricing, parse the pricing table, categorize
models into tiers, write references/MODEL_CATALOG.md, and emit JSON on stdout
so setup.py / generate_agents.py can consume the tier mapping.

Stdlib only. Exits 0 on success. On fetch failure, loads the committed
references/MODEL_CATALOG.md.fallback snapshot and emits that instead with
"stale": true in the JSON so callers can warn the user.

Usage:
    python scripts/update_models.py [--no-fetch] [--skill-root PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (SKILL_ROOT, TIER_DESCRIPTIONS, derive_model_id, fetch_url,
                   now_iso)

MODELS_URL_PRIMARY = "https://cursor.com/docs/models-and-pricing.md"
MODELS_URL_FALLBACK = "https://cursor.com/docs/models-and-pricing"


def parse_pricing_table(markdown: str) -> list[dict[str, Any]]:
    """
    Parse the pricing table from the models-and-pricing page. Looks for the
    header row containing "Model", "Provider", "Input", and "Output", then
    consumes subsequent table rows until a non-table line appears.
    """
    models: list[dict[str, Any]] = []
    lines = markdown.splitlines()
    in_table = False
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table:
                break
            continue

        cells = _split_row(stripped)

        if not in_table:
            if _looks_like_header(cells):
                in_table = True
            continue

        if _is_separator_row(stripped):
            continue

        if len(cells) < 6:
            continue

        name = _strip_link(cells[0])
        provider = cells[1]
        input_price = _parse_price(cells[2])
        cache_write = _parse_price(cells[3])
        cache_read = _parse_price(cells[4])
        output_price = _parse_price(cells[5])
        notes = cells[6] if len(cells) > 6 else ""

        if not name or provider.lower() == "provider":
            continue

        models.append({
            "name": name,
            "model_id": derive_model_id(name),
            "provider": provider,
            "input_price": input_price,
            "cache_write": cache_write,
            "cache_read": cache_read,
            "output_price": output_price,
            "notes": notes,
        })

    return models


def _split_row(row: str) -> list[str]:
    cells = row.strip().strip("|").split("|")
    return [c.strip() for c in cells]


def _looks_like_header(cells: list[str]) -> bool:
    joined = " ".join(c.lower() for c in cells)
    return "model" in joined and "provider" in joined and "input" in joined and "output" in joined


def _is_separator_row(row: str) -> bool:
    return bool(re.match(r"^\|\s*[-:]+", row))


def _strip_link(cell: str) -> str:
    m = re.match(r"\[([^\]]+)\]\([^)]+\)\s*$", cell)
    if m:
        return m.group(1).strip()
    return cell.strip()


def _parse_price(cell: str) -> float | None:
    m = re.search(r"\$?([\d.]+)", cell)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def categorize_into_tiers(models: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Pick one model per tier from the full catalog. Returns a mapping tier → entry."""
    tiers: dict[str, dict[str, Any]] = {}

    composers = [m for m in models if m["provider"].strip().lower() == "cursor" and m["name"].startswith("Composer")]
    if composers:
        latest = max(composers, key=_composer_version)
        tiers["composer"] = _build_tier_entry(latest, "composer")

    tiers["fast"] = {
        "name": "Cursor fast tier",
        "model_id": "fast",
        "provider": "Cursor",
        "input_price": None,
        "output_price": None,
        "description": TIER_DESCRIPTIONS["fast"],
    }

    openai_small = [
        m for m in models
        if m["provider"].strip().lower() == "openai"
        and re.search(r"\b(nano|mini)\b", m["name"].lower())
        and m["output_price"] is not None
    ]
    if openai_small:
        cheapest = min(openai_small, key=lambda m: m["output_price"] or float("inf"))
        tiers["mini"] = _build_tier_entry(cheapest, "mini")

    haikus = [
        m for m in models
        if m["provider"].strip().lower() == "anthropic" and "haiku" in m["name"].lower()
        and m["output_price"] is not None
    ]
    if haikus:
        cheapest = min(haikus, key=lambda m: m["output_price"] or float("inf"))
        tiers["haiku"] = _build_tier_entry(cheapest, "haiku")

    tiers["premium"] = {
        "name": "Inherit from parent",
        "model_id": "inherit",
        "provider": "any",
        "input_price": None,
        "output_price": None,
        "description": TIER_DESCRIPTIONS["premium"],
    }

    return tiers


def _composer_version(model: dict[str, Any]) -> float:
    match = re.search(r"Composer\s+([\d.]+)", model["name"])
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


def _build_tier_entry(model: dict[str, Any], tier_key: str) -> dict[str, Any]:
    return {
        "name": model["name"],
        "model_id": model["model_id"],
        "provider": model["provider"],
        "input_price": model["input_price"],
        "output_price": model["output_price"],
        "description": TIER_DESCRIPTIONS[tier_key],
    }


def fetch_catalog(no_fetch: bool, skill_root: Path) -> tuple[str, str, bool]:
    """
    Return (markdown_body, source_url, stale). If no_fetch is True or the
    network fetch fails, fall back to the committed snapshot and mark stale.
    """
    fallback_path = skill_root / "references" / "MODEL_CATALOG.md.fallback"

    def _load_fallback(reason: str) -> tuple[str, str, bool]:
        if not fallback_path.is_file():
            raise RuntimeError(
                f"Offline fallback not found at {fallback_path}. Original reason: {reason}"
            )
        return fallback_path.read_text(encoding="utf-8"), f"file://{fallback_path}", True

    if no_fetch:
        return _load_fallback("--no-fetch was passed")

    for url in (MODELS_URL_PRIMARY, MODELS_URL_FALLBACK):
        try:
            body = fetch_url(url)
            return body, url, False
        except Exception:
            continue

    return _load_fallback("both remote URLs failed")


def write_catalog_markdown(
    out_path: Path,
    models: list[dict[str, Any]],
    tiers: dict[str, dict[str, Any]],
    source: str,
    stale: bool,
) -> None:
    lines: list[str] = []
    lines.append("# Model Catalog")
    lines.append("")
    lines.append(f"Fetched at: {now_iso()}")
    lines.append(f"Source: {source}")
    if stale:
        lines.append("")
        lines.append("> Fetch failed — this catalog was loaded from the committed offline fallback and may be out of date.")
    lines.append("")
    lines.append("## Selected tiers")
    lines.append("")
    lines.append("| Tier | Model | Provider | Input $/Mtok | Output $/Mtok | Notes |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for tier_name in ("composer", "fast", "mini", "haiku", "premium"):
        entry = tiers.get(tier_name)
        if entry is None:
            lines.append(f"| `{tier_name}` | _(not available in current catalog)_ | — | — | — | — |")
            continue
        input_p = f"${entry['input_price']}" if entry.get("input_price") is not None else "—"
        output_p = f"${entry['output_price']}" if entry.get("output_price") is not None else "—"
        lines.append(
            f"| `{tier_name}` | {entry['name']} | {entry['provider']} | {input_p} | {output_p} | {entry['description']} |"
        )
    lines.append("")
    lines.append("## Full catalog")
    lines.append("")
    lines.append("| Model | Provider | Input | Cache write | Cache read | Output | Notes |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for m in models:
        def _fmt(p: float | None) -> str:
            return f"${p}" if p is not None else "—"
        lines.append(
            f"| {m['name']} | {m['provider']} | {_fmt(m['input_price'])} | {_fmt(m['cache_write'])} | {_fmt(m['cache_read'])} | {_fmt(m['output_price'])} | {m['notes']} |"
        )
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def run(no_fetch: bool, skill_root: Path) -> dict[str, Any]:
    markdown, source, stale = fetch_catalog(no_fetch=no_fetch, skill_root=skill_root)
    models = parse_pricing_table(markdown)
    if not models:
        raise RuntimeError(
            "Could not parse any models from the pricing page. The page format may have changed."
        )
    tiers = categorize_into_tiers(models)

    catalog_md = skill_root / "references" / "MODEL_CATALOG.md"
    write_catalog_markdown(catalog_md, models, tiers, source, stale)

    return {
        "fetched_at": now_iso(),
        "source": source,
        "stale": stale,
        "all_models": models,
        "tiers": tiers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip the network fetch and load from the committed fallback snapshot.",
    )
    parser.add_argument(
        "--skill-root",
        type=Path,
        default=SKILL_ROOT,
        help="Path to the cursor-orchestrator skill root (default: auto-detected).",
    )
    args = parser.parse_args()

    try:
        result = run(no_fetch=args.no_fetch, skill_root=args.skill_root)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
