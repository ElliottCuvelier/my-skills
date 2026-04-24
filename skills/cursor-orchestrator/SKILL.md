---
name: cursor-orchestrator
description: Plan on a frontier model (Opus, GPT-5, Codex) and execute on cheaper model-pinned sub-agents (Composer 2 by default) via a /orchestrate workflow. Use when the user is in Plan Mode and wants to split planning from implementation to save cost, delegate the build to a cheaper model, orchestrate a plan across multiple sub-agents, runs a plan with a specific implementation model, asks "which model for the build?", wants Composer / Haiku / Nano for implementation, or mentions sub-agent model selection, cheap build, model tiers, plan-and-dispatch, or orchestrator pattern. Handles first-use setup (7-question interview covering scope, tiers, verifier, rule, commands), fetches the live model catalog from cursor.com/docs/models-and-pricing, writes an `execution:` block into the plan frontmatter so `/orchestrate` can dispatch each step to an `impl-<tier>` sub-agent. Also triggers on /orchestrate, /update-orchestrator, or when the user asks to install / refresh / reconfigure the orchestrator.
---

# Cursor Orchestrator

Plan on a frontier model. Execute on cheaper sub-agents. Save money without giving up planning quality.

## When to use this skill

Activate when the user:

- Is in **Plan Mode** and mentions splitting planning from implementation, cost, cheap/mini/nano/haiku models, Composer for building, or "delegate the build."
- Types `/orchestrate <plan-path>` or `/update-orchestrator`.
- Asks to install, set up, refresh, or reconfigure the orchestrator.
- Says "run this plan on [cheaper model]" or "use Composer for implementation."

Skip when:

- The plan is tiny (one or two steps) and orchestration overhead exceeds the savings.
- The implementation genuinely needs the same reasoning power as the planner (exploratory, ambiguous, architectural).
- The user has explicitly declined orchestration in this conversation.

## Overview

The skill coordinates three pieces:

1. **You (the planner)** on a frontier model, drafting a Plan Mode markdown plan.
2. **`plan-orchestrator`** — a model-pinned sub-agent that reads a saved plan, parses its `execution:` block, and dispatches each step.
3. **`impl-<tier>`** sub-agents — one per selected tier (`composer`, `fast`, `mini`, `haiku`, `premium`), each hard-pinned to a specific model ID.

The user runs Plan Mode → you help draft the plan → the skill asks which implementation tier → the plan gets saved → the user invokes `/orchestrate <plan-path>` → the orchestrator dispatches each step to the right tier.

> **Native Build button caveat.** Cursor's Build button runs the plan on whatever model the user has picked in the composer. To execute on a _different_ model than the planner, the user must use `/orchestrate` (this skill installs that command).

## Workflow

### 1. First-use detection

At activation, check for the marker file at **both** possible install locations:

- `.cursor/agents/.cursor-orchestrator-installed` (project scope)
- `~/.cursor/agents/.cursor-orchestrator-installed` (user-wide scope)

If **neither** exists, this is a first run. Tell the user briefly:

> "First run — I'll walk you through a 7-question setup so I can generate the right sub-agents. About 30 seconds."

Then run the setup interview below.

If a marker **does** exist, skip to step 3 (plan authoring).

### 2. First-use setup interview

Use the `AskQuestion` tool (not stdin) to ask these seven questions **in sequence**. Full question wording and option labels are in [references/SETUP.md](references/SETUP.md). Summary:

1. **Scope** — `.cursor/agents/` (project), `~/.cursor/agents/` (user-wide), or both?
2. **Tiers to generate** — multi-select across composer, fast, mini, haiku, premium. Default: composer + fast + premium.
3. **Default tier** — which tier is written into the `execution:` block when the user doesn't override per-plan? Default: composer.
4. **Install verifier sub-agent?** — runs a check after each step on the `fast` tier. Default: yes.
5. **Install the Plan Mode rule?** — auto-attaches in Plan Mode to hint toward this skill. Default: yes.
6. **Install slash command wrappers?** — `/orchestrate` and `/update-orchestrator`. Default: yes.
7. **Max Mode status** — do you have Max Mode enabled? Used to warn about silent downgrades for tiers that require it.

Once all seven are answered, run:

```bash
python <skill-path>/scripts/setup.py --answers '<json-of-answers>'
```

Where `<skill-path>` is wherever this skill is installed (look under `.agents/skills/cursor-orchestrator/` first, then `~/.cursor/skills/cursor-orchestrator/`). The script:

- Fetches the latest model catalog from `cursor.com/docs/models-and-pricing` (falls back to a committed snapshot if offline).
- Writes `agents/` and `rules/` files at the chosen scope(s).
- Writes the marker file (JSON) containing the user's answers + SHA hashes of every generated file.
- Prints a JSON report and next-steps — relay the next-steps to the user.

Expected answers JSON shape:

```json
{
  "scope": "project",
  "tiers": ["composer", "fast", "premium"],
  "default_tier": "composer",
  "verifier": true,
  "rule": true,
  "commands": true,
  "max_mode": true
}
```

### 3. Plan authoring flow

Help the user draft a Plan Mode markdown as usual. Keep the plan's todos as focused, independently-executable steps — this is what the orchestrator will dispatch.

**Before finalizing the plan**, ask:

> "Which implementation tier should this plan run on?"

- Show a compact summary of available tiers (read [references/MODEL_CATALOG.md](references/MODEL_CATALOG.md) for current pricing).
- Default is the `default_tier` from the marker file (typically `composer`).
- Also ask: parallelism (sequential | parallel) and whether to verify each step (default: whatever the marker says).

Append an `execution:` block into the plan's YAML frontmatter. See [references/PLAN_FORMAT.md](references/PLAN_FORMAT.md) for the schema. Example:

```yaml
---
name: my-feature-plan
overview: ...
todos:
  - id: step-1
    content: ...
    status: pending
execution:
  implementation_model: composer
  parallelism: sequential
  verify_each_step: true
---
```

### 4. Execution handoff

Tell the user exactly what to run:

> "Save the plan, then run: `/orchestrate .cursor/plans/<filename>.plan.md`
>
> (Native Build will run on your current picker model — `/orchestrate` is what dispatches to `impl-composer` on Composer 2 / the tier you selected.)"

You are done. The `plan-orchestrator` sub-agent takes over from there; the user can re-engage you if something needs re-planning.

## Updating the model catalog

When the user runs `/update-orchestrator`:

1. Fetch the latest pricing page via `python <skill-path>/scripts/update_models.py`.
2. Diff against the cached `references/MODEL_CATALOG.md`.
3. Ask for confirmation before regenerating.
4. Run `python <skill-path>/scripts/generate_agents.py --regenerate --tiers <json>` — files with matching SHAs get updated; user-edited files are preserved with a warning.

If the user passes `--reconfigure`, re-run the 7-question interview first.

## Troubleshooting

See [references/TROUBLESHOOTING.md](references/TROUBLESHOOTING.md) for:

- Silent model downgrades (Max Mode required, admin-blocked, plan limitation).
- Native Build button not using the selected tier.
- Stale model catalog.
- Regenerating after user edits.

## Rules

- **Ask before generating.** Never write files on first-use without completing the 7-question interview — users need to know where their agent files are going.
- **Respect the user's edits.** Never clobber a sub-agent file whose SHA doesn't match the marker.
- **Surface silent downgrades.** If the `plan-orchestrator` reports an implementer ran on a different model than configured, relay that to the user — don't hide it.
- **Plan is source of truth.** All tier selection and todo status lives in the plan file's frontmatter, not just in chat.
- **No code, only coordination.** When this skill is active you are planning and dispatching — sub-agents do the actual edits.
