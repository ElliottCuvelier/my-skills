# Claude Model Tiers

Claude Code agent frontmatter accepts exactly four values for `model:`. These are the only valid tiers for ct-o10r teammate roles.

| Tier | `model:` value | Characteristics | Best for |
|------|---------------|-----------------|---------|
| **haiku** | `haiku` | Fastest, cheapest. Lower reasoning depth. | Bulk edits, renaming, simple refactors, lint fixes, boilerplate generation. Tests show it handles ≤5-file scoped changes well. |
| **sonnet** | `sonnet` | Best price/performance balance. Default tier. | Most implementation work — features, API integration, moderate refactors. Handles context-dependent changes confidently. |
| **opus** | `opus` | Most capable. Highest cost. | Complex architectural changes, ambiguous specs, multi-system refactors, anything that keeps failing on sonnet. |
| **inherit** | `inherit` | Runs on whatever model the lead session uses. No model pinning. | Teammates that should match the lead's capability; lanes needing planning-tier reasoning. |

## Choosing a default teammate model

Set the default teammate model in the interview based on your typical work:

- **Daily implementation (PRs, tickets)** → `sonnet` (recommended default)
- **Large-scale refactors or ambiguous specs** → `opus`
- **Bulk low-risk changes (imports, formatting, typo fixes)** → `haiku`

## Model selection in plan files

The `team.default_teammate_model` field in a plan's `team:` block accepts any of the four values above; per-lane `roster[].model` and per-todo `model_override:` override it.

A lane runs on a single model — if a todo's `model_override` disagrees with its lane, the lead splits the lane so each teammate has one model.

## Cost discipline

Agent teams cost ~7× a single session (each teammate is a full Claude instance), so model choice matters more, not less:

- `brv query` (LLM call inside ByteRover) is reserved for the **lead** only. Teammates use `brv search` (free, BM25).
- Default teammates to `sonnet` (Anthropic's recommendation for team coordination); put cheap bulk lanes on `haiku`; reserve `opus` for one hard lane, not the whole team.
- Prefer the `TaskCompleted` test gate (`verify: hook`) over a reviewer teammate when tests suffice — it adds no teammate and no token cost. The optional reviewer teammate runs on `haiku`.
