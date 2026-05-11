---
name: claude-orchestrator
description: Plan on Opus/Sonnet and execute on cheaper model-pinned sub-agents via a /claude-orchestrate workflow. Use when the user is in Plan Mode and wants to split planning from implementation to save cost, delegate the build to a cheaper model, orchestrate a plan across multiple sub-agents, assign plan steps to specific models, build this plan on haiku, dispatch to sonnet, use cheaper Claude for implementation, generate project-specific Claude Code sub-agents, install project agents, set up the orchestrator, or mentions sub-agent model selection, cheap build, plan-and-dispatch, or orchestrator pattern. Handles first-use setup (7-question interview + codebase analysis + adaptive roster proposal), generates project-specific sub-agents tailored to the actual codebase using AGENT_PATTERNS.md, detects and integrates ByteRover memory (Recall→Work→Curate→Report loop in every agent), writes an `execution:` block into the plan so `/claude-orchestrate` can dispatch each step to the right sub-agent. Also triggers on /claude-orchestrate, /claude-orchestrate-resume, /update-claude-orchestrator, or when the user asks to install, refresh, or reconfigure the orchestrator.
---

# Claude Orchestrator

Plan on a frontier model. Execute on cheaper sub-agents. Build a project-specific roster that gets smarter with every plan run.

## When to use this skill

Activate when the user:

- Is in **Plan Mode** and mentions splitting planning from implementation, cost, cheap/mini/haiku models, delegating the build, or "run this plan on haiku/sonnet."
- Types `/claude-orchestrate <plan-path>`, `/claude-orchestrate-resume <plan-path>`, or `/update-claude-orchestrator`.
- Asks to install, set up, refresh, or reconfigure the orchestrator.
- Says "generate project agents," "set up Claude Code sub-agents," or "adapt the orchestrator to this codebase."

Skip when:

- The plan is one or two steps and orchestration overhead isn't worth it.
- The task is genuinely exploratory/architectural and needs the planner's reasoning level throughout.
- The user has explicitly declined orchestration in this conversation.

## Overview

The skill coordinates three pieces:

1. **You (the planner)** on Opus/Sonnet, drafting a Plan Mode markdown plan.
2. **`plan-orchestrator`** — a sub-agent (`model: inherit`) that reads a saved plan, parses its `execution:` block, and dispatches each step.
3. **`impl-<tier>`** sub-agents + project-specific agents — each pinned to a Claude tier (`haiku`, `sonnet`, `opus`, or `inherit`), with project agents scoped to specific directories and patterns in the codebase.

The user runs Plan Mode → you draft the plan → first-use sets up the roster → the plan gets saved → the user invokes `/claude-orchestrate <plan-path>` → the orchestrator dispatches each step to the right agent.

## Workflow

### 1. First-use detection

At activation, check for the marker file at **both** possible install locations:

- `.claude/agents/.claude-orchestrator-installed` (project scope)
- `~/.claude/agents/.claude-orchestrator-installed` (user-wide scope)

If **neither** exists, this is a first run. Tell the user:

> "First run — I'll walk through a quick setup: 7 questions about tiers and scope, then I'll analyze the codebase to propose project-specific agents. About a minute."

Then run the setup interview below.

If a marker **does** exist, skip to step 7 (plan authoring flow).

### 2. Setup interview

Use `AskUserQuestion` to ask these seven questions in sequence. Full question wording, options, and defaults are in [references/SETUP.md](references/SETUP.md). Summary:

1. **Scope** — `.claude/agents/` (project), `~/.claude/agents/` (user-wide), or both? Default: `project`
2. **Tiers to install** — multi-select: `haiku`, `sonnet`, `opus`, `inherit`. Default: `haiku`, `sonnet`, `inherit`
3. **Default tier** — single-select filtered to Q2 choices. Default: `sonnet`
4. **Install verifier sub-agent?** — runs after each step on `haiku`. Default: `yes`
5. **Install memory-curator agent?** — terminal consolidation pass; recommended when ByteRover enabled. Default: `yes`
6. **Install slash commands?** — `/claude-orchestrate`, `/claude-orchestrate-resume`, `/update-claude-orchestrator`. Default: `yes`
7. **ByteRover handling** — options reflect detection result:
   - If `brv` found on PATH: "Already installed — enable the memory loop (recommended)"
   - If not found: "Install now (`npm install -g byterover-cli`)" / "Skip — omit the memory loop"
7.5. **Hooks to install** — offered after Q7; options adapt to ByteRover status:
   - If ByteRover enabled: multi-select `taskids` (SubagentStop taskId collector) / `pending` (Stop review surfacer) / `tests` (PostToolUse scoped test runner). Default: all three.
   - If ByteRover disabled: single choice — `tests` (scoped test runner) or skip. Default: `tests`.

### 3. Codebase analysis

After the 7 questions, run:

```bash
python <skill-path>/scripts/analyze_codebase.py --format json
```

Where `<skill-path>` is the installed skill directory (check `.claude/skills/claude-orchestrator/` first, then `~/.claude/skills/claude-orchestrator/`).

This collects signals — manifests, frameworks, ORMs, test runners, architectural patterns (DDD entities, CQRS handlers, BullMQ processors, etc.), existing `.claude/agents/`, and ByteRover subtrees — into a JSON snapshot. **No opinions, pure data collection.**

### 4. Roster composition

Read the snapshot together with [references/AGENT_PATTERNS.md](references/AGENT_PATTERNS.md). The patterns file is a **signal → agent recipe** library — a table that maps detected signals to suggested agents (name, role, model, scope_hint, byterover_scope, curate_when).

Compose a **project-specific roster** by reasoning over the snapshot and recipe table:

- Include recipe agents only when their signal threshold is met (e.g., `ddd_entities` ≥ 3, `bullmq_processors` ≥ 1).
- Skip recipes for signals absent from the snapshot.
- Don't duplicate existing agents from `existing_agents` in the snapshot — register them instead.
- Cap at ~8 project-specific agents. Beyond that, the roster becomes unwieldy.
- Prefix names with a project slug (e.g., `wi-be-domain-modeler`). Confirm the prefix in Q8.
- For frameworks not in the recipe table, propose baseline-only (no project agents).

The baseline agents (`impl-haiku`, `impl-sonnet`, etc., `verifier`, `memory-curator`) are **always written alongside** the project roster as a fallback.

Build a proposed roster list. Each entry must have:

```json
{
  "name": "<project-slug>-<agent-name>",
  "description": "<imperative trigger phrase with keywords for auto-delegation>",
  "model": "haiku|sonnet|opus|inherit",
  "role": "writer|verifier|scaffolder",
  "readonly": false,
  "scope_hint": "<glob pattern for agent routing>",
  "byterover_scope": "<scope under .brv/context-tree/>",
  "curate_when": "<one-line trigger>",
  "when_invoked": "<what the agent does>",
  "conventions": "<project-specific conventions from snapshot: package manager, test runner, etc.>"
}
```

### 5. ByteRover detection

Run:

```bash
python <skill-path>/scripts/detect_byterover.py
```

This checks for `brv` on PATH, the ByteRover skill file, and any `.brv/context-tree/` subtrees. Returns a JSON dict with `installed`, `cli_version`, `skill_present`, `context_tree_present`, and `subtrees_detected`.

If Q7 was "install now," tell the user to run:

```
npm install -g byterover-cli
brv providers connect byterover
brv status
```

Then ask the user to confirm when done, and re-run `detect_byterover.py`.

If Q7 was "skip" or install failed, set `byterover_enabled: false` in the answers.

### 6. Q8 — Roster confirmation

Present the proposed roster via `AskUserQuestion`:

> "Here's the proposed agent roster based on codebase analysis. Accept all, or let me know what to change."

Show each agent: name, model, scope_hint, and one-line purpose. Provide options:
- **Accept all** — generate everything as proposed.
- **Edit** — user describes changes; re-compose and ask again.
- **Baseline only** — skip project-specific agents; generate `impl-*`, verifier, memory-curator only.

If there are conflicts with existing agents (same name already in `.claude/agents/`), surface them: "Agent `foo.md` already exists. Keep existing / rename new / skip new."

### 7. Generate files

Build the final answers payload and call setup.py:

```bash
python <skill-path>/scripts/setup.py \
  --answers '<json>' \
  --project-agents '<roster-json>' \
  --byterover-info '<detect-byterover-output>' \
  --codebase-snapshot '<analyze-output>'
```

Expected answers JSON shape:

```json
{
  "scope": "project",
  "tiers": ["haiku", "sonnet", "inherit"],
  "default_tier": "sonnet",
  "verifier": true,
  "memory_curator": true,
  "commands": true,
  "byterover_enabled": true,
  "hooks": ["taskids", "pending", "tests"]
}
```

The script validates answers, renders all templates, writes files to `.claude/agents/` and `.claude/commands/`, registers pre-existing agents in the marker, and prints a JSON report with `next_steps`. Relay the `next_steps` to the user verbatim.

### 8. Plan authoring flow

Help the user draft a Plan Mode markdown as usual. Keep todos as focused, independently-executable steps — the orchestrator dispatches each one.

**Before finalizing the plan**, ask:

> "Which implementation tier should this plan run on? And should I parallelize non-overlapping steps?"

- Show the tier options from the marker's `tiers_installed` and their Claude model labels.
- Default is `default_tier` from the marker.
- Ask: parallelism (`sequential` | `parallel`) and whether to verify each step.

Append an `execution:` block to the plan's YAML frontmatter. For project-agent routing, suggest adding `agent:` or `files:` fields to individual todos where relevant. See [references/PLAN_FORMAT.md](references/PLAN_FORMAT.md) for the full schema.

Example:

```yaml
---
name: add-payment-module
overview: Implement Stripe payment processing
todos:
  - id: domain-entities
    content: Create Payment entity and PaymentStatus VO
    status: pending
    files: [modules/payments/domain/]
  - id: command-handlers
    content: Add CreatePaymentCommand and handler
    status: pending
    files: [modules/payments/application/]
execution:
  implementation_model: sonnet
  parallelism: sequential
  verify_each_step: true
  prefer_project_agents: true
---
```

### 9. Execution handoff

Tell the user exactly what to run:

> "Save the plan at `~/.claude/plans/<name>.md`, then run:
> `/claude-orchestrate ~/.claude/plans/<name>.md`
>
> The plan-orchestrator will dispatch each step. You can resume an interrupted run with `/claude-orchestrate-resume ~/.claude/plans/<name>.md`."

You are done. The `plan-orchestrator` sub-agent takes over from there.

## Updating the orchestrator

When the user runs `/update-claude-orchestrator`:

1. Re-run `analyze_codebase.py` and `detect_byterover.py`.
2. Compare new codebase fingerprint against the marker's stored fingerprint.
3. If different, show the diff (new signals, new ByteRover subtrees, new existing agents) and propose updated/additional project agents.
4. If `byterover.enabled` flipped (e.g., user installed `brv` since first run), offer to regenerate agents with the loop included.
5. Run `generate_agents.py --regenerate` (SHA-protected — user-edited files are preserved with a warning).
6. Report: regenerated / skipped (user-edited) / newly registered.

If the user passes `--reconfigure`, re-run the full 7-question interview first.

## Troubleshooting

See [references/TROUBLESHOOTING.md](references/TROUBLESHOOTING.md) for:

- ByteRover loop not firing (agent ignores `## Memory` section).
- `brv curate` hanging (check `--detach` was NOT used).
- Pre-existing agent conflicts.
- User-edited file preserved on regenerate.
- Codebase fingerprint false-positive (build artifact changes).
- Plan file at `~/.claude/plans/` cross-project confusion.

## Rules

- **Ask before generating.** Never write files on first-use without completing the 7-question interview and Q8 roster confirmation. Users need to know where their agent files are going.
- **Respect the user's edits.** Never clobber a sub-agent file whose SHA doesn't match the marker. Warn loudly: "File modified since last generation; will not overwrite — delete to regenerate."
- **No built-in profiles.** The roster is always composed fresh from the codebase snapshot + AGENT_PATTERNS.md. Never ship hardcoded "NestJS profile" or "Next.js profile" agent sets.
- **ByteRover is binary.** If the user declined ByteRover (Q7 = skip), generated agents have **no** memory loop — not even a commented-out block. A later `/update-claude-orchestrator` run will offer to regenerate when `brv` is detected.
- **Plan is source of truth.** All tier selection and todo status lives in the plan file's frontmatter, not in chat.
- **No code, only coordination.** When this skill is active you are planning and dispatching — sub-agents do the actual edits.
- **Never auto-approve ByteRover curates.** Collect `taskId`s from sub-agents and surface them in the final report for the user to approve or reject manually with `brv review approve <taskId>` / `brv review reject <taskId>`.

## Reference Documentation

| Document | Purpose |
|----------|---------|
| [references/SETUP.md](references/SETUP.md) | Full Q1–Q7 question wording, options, defaults, and answers payload schema |
| [references/PLAN_FORMAT.md](references/PLAN_FORMAT.md) | `execution:` block schema, per-todo `agent:` and `model_override:` semantics |
| [references/MODEL_TIERS.md](references/MODEL_TIERS.md) | The 4 Claude Code model values and when to use each |
| [references/AGENT_PATTERNS.md](references/AGENT_PATTERNS.md) | Signal → agent recipe library (the skill's composition intelligence) |
| [references/BYTEROVER_LOOP.md](references/BYTEROVER_LOOP.md) | Canonical Recall → Work → Curate → Report loop fragment |
| [references/BYTEROVER_SCOPES.md](references/BYTEROVER_SCOPES.md) | ByteRover scope namespace conventions |
| [references/TROUBLESHOOTING.md](references/TROUBLESHOOTING.md) | Common issues and fallback paths |
