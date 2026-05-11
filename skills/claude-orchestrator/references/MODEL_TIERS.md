# Claude Model Tiers

Claude Code agent frontmatter accepts exactly four values for `model:`. These are the only valid tiers for claude-orchestrator.

| Tier | `model:` value | Characteristics | Best for |
|------|---------------|-----------------|---------|
| **haiku** | `haiku` | Fastest, cheapest. Lower reasoning depth. | Bulk edits, renaming, simple refactors, lint fixes, boilerplate generation. Tests show it handles ≤5-file scoped changes well. |
| **sonnet** | `sonnet` | Best price/performance balance. Default tier. | Most implementation work — features, API integration, moderate refactors. Handles context-dependent changes confidently. |
| **opus** | `opus` | Most capable. Highest cost. | Complex architectural changes, ambiguous specs, multi-system refactors, anything that keeps failing on sonnet. |
| **inherit** | `inherit` | Runs on whatever model the parent session uses. No model pinning. | Orchestrator-level agents, plan authoring, anything where the user's chosen model should flow through. |

## Choosing a default tier

Set `default_tier` in the interview based on your typical work:

- **Daily implementation (PRs, tickets)** → `sonnet` (recommended default)
- **Large-scale refactors or ambiguous specs** → `opus`
- **Bulk low-risk changes (imports, formatting, typo fixes)** → `haiku`

## Tier selection in plan files

The `execution.implementation_model` field in a plan's YAML frontmatter accepts any of the four values above.

Per-todo overrides use `model_override: haiku | sonnet | opus` (not `inherit` for per-todo overrides, since the per-todo override is explicit).

## Cost discipline

- `brv query` (LLM call inside ByteRover) is reserved for the orchestrator only. Sub-agents use `brv search` (free, BM25).
- Dispatch cheap work to `haiku`, only escalate to `sonnet` or `opus` when the verifier catches failures repeatedly.
- The verifier always runs on `haiku` — fast and cheap enough to run between every step.
