---
name: ct-o10r
description: Run a saved plan as a Claude Code agent team — a team lead spawns model-pinned teammates that own file-disjoint lanes, share a native task list, and message each other, via a /ct-orchestrate workflow. The agent-teams ("claudeteam-orchestrator") variant of claude-orchestrator. Instead of one-shot sub-agent dispatch it forms a persistent team for parallel, collaborative, cross-layer execution (multi-module features, parallel review, competing-hypothesis debugging). Use when the user wants to orchestrate a plan with an agent team, spawn teammates for a plan, run a plan in parallel across lanes, build a cross-layer feature with a team, or mentions agent teams, teammates, claudeteam, ct-o10r, or team orchestration. Handles first-use setup (interview + codebase analysis + teammate-role roster from AGENT_PATTERNS.md), generates project-specific teammate roles, detects and integrates ByteRover memory (Recall→Work→Curate→Report loop in every teammate), installs team-native quality-gate hooks (TaskCompleted test gate, TaskCreated files-sidecar, TeammateIdle taskId backstop), and writes a `team:` block into the plan so /ct-orchestrate can spawn the team and seed the shared task list. Requires CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1. Agent teams cost ~7x a single session — this is for parallelism and collaboration, not cost savings. Also triggers on /ct-orchestrate, /ct-orchestrate-resume, /update-ct-orchestrator, and on asking to run, build, execute, or resume a saved plan as a team.
---

# ct-o10r (claudeteam-orchestrator)

Run a saved plan as a Claude Code **agent team**: a lead spawns model-pinned teammates that own file-disjoint lanes, share a native task list, and message each other. The agent-teams variant of `claude-orchestrator`.

## When to use this skill

Activate when the user:

- Wants to run / build / execute / resume a saved plan **as an agent team**, "spawn teammates for this plan," or run a plan "in parallel across lanes."
- Types `/ct-orchestrate <plan>`, `/ct-orchestrate-resume <plan>`, or `/update-ct-orchestrator`.
- Mentions Claude Code **agent teams**, **teammates**, **claudeteam**, **ct-o10r**, or team orchestration of a build.
- Asks to install, set up, refresh, or reconfigure ct-o10r.

Skip when:

- Agent teams aren't enabled and the user won't set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` — a team can't form; point them at `claude-orchestrator` or a single session.
- The plan is sequential, single-file, or 1–2 steps — the ~7× team cost isn't worth it.
- The user wants to **minimize** token cost — agent teams cost more, not less. Use `claude-orchestrator` (cheap one-shot dispatch) instead.

## What this is (and isn't)

ct-o10r is for **parallel, collaborative, cross-layer execution** — multi-module features, parallel review/research, cross-layer changes where teammates own different files and coordinate via a shared task list and a mailbox. It is **not** a cost-saver: each teammate is a full Claude instance (~7× a single session). Per-lane model-pinning is supported (put cheap lanes on `haiku`), but the headline is wall-clock speed + collaboration quality, not tokens. For cheap one-shot execution, use `claude-orchestrator`.

## Overview

Two pieces:

1. **You — the planner, then the team LEAD** (on Opus/Sonnet). You draft a Plan Mode plan, then run it as a team: read the plan, partition todos into file-disjoint lanes, spawn one teammate per lane, seed a shared task list, and coordinate. You never edit files while leading — teammates do.
2. **Teammates + a shared task list + a mailbox.** Each teammate is a full Claude Code instance spawned from a model-pinned role (`impl-<tier>` or a project role) and owns one file lane. They claim assigned tasks, message each other, and gate completion through hooks.

The native task list, file-lock claiming, and dependency unblocking handle status tracking and ordering — ct-o10r delegates to them rather than hand-rolling.

Flow: Plan Mode → you draft the plan → first-use sets up roles + hooks → the plan gets a `team:` block and is saved → the user runs `/ct-orchestrate <plan>` → **this session** becomes the lead, spawns the team, and runs it.

## Workflow

### 0. Enable check

Agent teams require `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, read at **startup**. On activation, if it's not set (check the env / `settings.json` `env`), tell the user and offer to add it (restart required). Setup can proceed without it; `/ct-orchestrate` cannot run until it's set.

### 1. First-use detection

Check for the marker at **both** locations:

- `.claude/agents/.ct-o10r-installed` (project scope)
- `~/.claude/agents/.ct-o10r-installed` (user scope)

If **neither** exists, this is a first run. Tell the user:

> "First run — a quick setup: a few questions about models and scope, then I'll analyze the codebase to propose teammate roles. About a minute."

Then run the setup interview. If a marker **exists**, skip to step 8 (plan authoring).

### 2. Setup interview

Use `AskUserQuestion` for the questions in [references/SETUP.md](references/SETUP.md). Summary: scope; which tiers to install as teammate-role baselines; default teammate model (default `sonnet`); install a reviewer-teammate role? (y/n); memory-curator? (y/n); slash commands? (y/n); ByteRover; hooks (`tests` gate, `taskids` backstop).

### 3. Codebase analysis

```bash
python <skill-path>/scripts/analyze_codebase.py
```

`<skill-path>` is the installed skill dir (`.claude/skills/ct-o10r/`, else `~/.claude/skills/ct-o10r/`). Outputs a JSON snapshot to stdout (add `--pretty` for human-readable). Collects manifests, frameworks, ORMs, test runner, architectural patterns, existing agents, and ByteRover subtrees — **pure data collection**.

### 4. Roster composition

Read the snapshot together with [references/AGENT_PATTERNS.md](references/AGENT_PATTERNS.md) (the signal → teammate-role recipe library). Compose a project roster — each role is reused as an agent-team teammate type that owns the matching files (`scope_hint`) as its lane:

- Include recipes only when their signal threshold is met; skip absent signals; don't duplicate existing agents (register them).
- Cap at ~8 project roles; prefix names with a project slug (confirm in Q8).
- Baselines (`impl-*`, `verifier`, `memory-curator`) are **always** written alongside the project roster.

Each roster entry:

```json
{
  "name": "<project-slug>-<role-name>",
  "description": "<imperative trigger phrase>",
  "model": "haiku|sonnet|opus|inherit",
  "role": "writer|verifier|scaffolder",
  "readonly": false,
  "scope_hint": "<glob for the lane this role owns>",
  "byterover_scope": "<scope under .brv/context-tree/>",
  "curate_when": "<one-line trigger>",
  "when_invoked": "<what the teammate does>",
  "conventions": "<project conventions: package manager, test runner, etc.>"
}
```

### 5. ByteRover detection

```bash
python <skill-path>/scripts/detect_byterover.py
```

Checks for `brv` on PATH, the ByteRover skill file, and `.brv/context-tree/` subtrees. If Q7 was "install now," have the user run `! npm install -g byterover-cli && brv providers connect byterover && brv status`, confirm, then re-run detection. If skipped/failed, set `byterover_enabled: false`.

### 6. Q8 — roster confirmation

Present the proposed teammate-role roster via `AskUserQuestion` (each role: name, model, scope_hint, one-line purpose). Options: **Accept all** / **Edit** / **Baseline only**. Surface any name conflicts with existing `.claude/agents/*.md`.

### 7. Generate files

```bash
python <skill-path>/scripts/setup.py \
  --answers '<json>' \
  --project-agents '<roster-json>' \
  --byterover-info '<detect-byterover-output>' \
  --codebase-snapshot '<analyze-output>'
```

Validates answers, renders teammate-role files to `.claude/agents/`, command wrappers to `.claude/commands/`, hook scripts to `.claude/hooks/` + `settings.local.json`, registers pre-existing agents, and prints a JSON report with `next_steps`. Relay `next_steps` verbatim (including the enable-flag + restart reminder).

### 8. Plan authoring flow

Help the user draft a Plan Mode plan with focused, independently-executable todos. **Add `files:` to each todo** — this drives lane partitioning (the most load-bearing field). Group todos that touch the same files into one lane; serialize true ordering with `depends_on`.

**Before finalizing**, ask:

> "Default teammate model for this plan? Verification: the `TaskCompleted` test gate (`hook`), a reviewer teammate (`review`), or none?"

Append a `team:` block to the plan frontmatter. See [references/PLAN_FORMAT.md](references/PLAN_FORMAT.md). Example:

```yaml
---
name: add-payment-module
overview: Implement Stripe payment processing
todos:
  - id: domain
    content: Create Payment entity and PaymentStatus VO
    files: [modules/payments/domain/]
  - id: webhooks
    content: Add Stripe webhook handler (independent of domain internals)
    files: [modules/payments/webhooks/]
team:
  team_size: 2
  default_teammate_model: sonnet
  lead_mode: delegate
  verify: hook
---
```

### 9. Run the plan

Tell the user:

> "Save the plan at `~/.claude/plans/<name>.md`, make sure `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set (and you've restarted), then run:
> `/ct-orchestrate ~/.claude/plans/<name>.md`
>
> I'll become the team lead, spawn a teammate per lane, and coordinate. Resume an interrupted run with `/ct-orchestrate-resume ~/.claude/plans/<name>.md`."

## Running a plan as a team

When the user runs `/ct-orchestrate` or `/ct-orchestrate-resume`, **or** asks in-session to run/build/execute/resume a saved plan as a team, **you (this session) are the team LEAD**:

1. Read the playbook at [references/TEAM_ORCHESTRATION.md](references/TEAM_ORCHESTRATION.md) and follow it.
2. Verify the enable flag, load the marker, partition lanes, spawn one teammate per lane (pinned to the right model), seed the shared task list from the todos, coordinate, verify (gate / reviewer), consolidate ByteRover memory, shut teammates down, and print the final report.

You never edit files while leading — every change goes through a teammate. **One team per session; no nested teams.** This works even without slash commands — the natural-language request alone triggers it.

## Updating ct-o10r

When the user runs `/update-ct-orchestrator`:

1. Re-run `analyze_codebase.py` and `detect_byterover.py`.
2. Compare the new fingerprint against the marker's stored fingerprint; if different, show the diff and propose updated/additional teammate roles.
3. If `byterover.enabled` flipped, offer to regenerate with/without the loop.
4. Run `generate_agents.py --regenerate` (SHA-protected — user-edited files preserved with a warning).
5. Report: regenerated / skipped / newly registered.

`--reconfigure` re-runs the full setup interview first.

## Troubleshooting

See [references/TROUBLESHOOTING.md](references/TROUBLESHOOTING.md): enable flag missing, resume respawn, file conflicts, task-status lag, permission storms, cost, ByteRover loop not firing, `brv` not found, and more.

## Rules

- **Ask before generating.** Never write files on first-use without completing the interview and Q8 roster confirmation.
- **Respect the user's edits.** Never clobber a role file whose SHA doesn't match the marker. Warn: "File modified since last generation; will not overwrite — delete to regenerate."
- **No built-in profiles.** The roster is always composed fresh from the codebase snapshot + AGENT_PATTERNS.md.
- **ByteRover is binary.** If the user declined ByteRover, teammate roles have **no** memory loop. A later `/update-ct-orchestrator` offers to regenerate when `brv` is detected.
- **Coordinate, don't implement.** While leading you spawn teammates and seed tasks — you never edit files yourself.
- **One team per session; no nested teams.** Teammates never spawn teammates; the ct-o10r orchestrator role is never a teammate role.
- **Assign, don't open-claim, for file safety.** File-disjoint lanes + assignment + dependencies; native locking guards task-claim, not source writes.
- **Never auto-approve ByteRover curates.** Collect `BRV-REVIEW` taskIds (mailbox + backstop) and surface them in the final report for manual `brv review approve/reject`.
- **It's not a cost-saver.** Agent teams cost ~7×; use ct-o10r for parallelism and collaboration, not to save tokens.

## Reference Documentation

| Document | Purpose |
|----------|---------|
| [references/AGENT_TEAMS.md](references/AGENT_TEAMS.md) | The agent-team model: enable flag, lead/teammate/task-list/mailbox, spawn, delegate mode, display modes, limits |
| [references/TEAM_ORCHESTRATION.md](references/TEAM_ORCHESTRATION.md) | The lead playbook this session follows when running a plan as a team |
| [references/PLAN_FORMAT.md](references/PLAN_FORMAT.md) | The `team:` block schema and per-todo field semantics |
| [references/SETUP.md](references/SETUP.md) | Full setup interview wording, options, defaults, and answers payload schema |
| [references/MODEL_TIERS.md](references/MODEL_TIERS.md) | The 4 Claude model values and per-teammate model pinning |
| [references/AGENT_PATTERNS.md](references/AGENT_PATTERNS.md) | Signal → teammate-role recipe library (the roster composition intelligence) |
| [references/BYTEROVER_LOOP.md](references/BYTEROVER_LOOP.md) | Canonical Recall → Work → Curate → Report loop fragment |
| [references/BYTEROVER_SCOPES.md](references/BYTEROVER_SCOPES.md) | ByteRover scope namespace conventions |
| [references/TROUBLESHOOTING.md](references/TROUBLESHOOTING.md) | Common issues and fallback paths |
