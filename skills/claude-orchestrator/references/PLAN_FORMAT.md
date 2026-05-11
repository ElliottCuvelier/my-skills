# Plan File Format

Claude Code plan files live at `~/.claude/plans/<name>.md`. The claude-orchestrator
skill extends the standard plan frontmatter with an `execution:` block and two optional
per-todo fields.

## Full schema

```yaml
---
name: <string>               # display name for the plan
overview: <string>           # one-sentence description of the goal

todos:
  - id: <string>             # unique identifier, e.g. "step-1" or "add-auth"
    content: <string>        # what to do — be specific and independently executable
    status: pending | in_progress | completed | failed | cancelled
    
    # Optional per-todo fields (claude-orchestrator extensions):
    depends_on: [<todo-id>, ...]     # declare ordering dependency
    files: [<path>, ...]             # files this step touches (for parallel safety + routing)
    agent: <agent-name>              # pin a specific generated agent for this step
    model_override: haiku | sonnet | opus   # override the plan-level implementation_model

execution:
  implementation_model: haiku | sonnet | opus | inherit   # REQUIRED — default tier
  parallelism: sequential | parallel                       # default: sequential
  verify_each_step: true | false                           # default: true if verifier installed
  curate_on_completion: true | false                       # default: true if memory-curator installed
  prefer_project_agents: true | false                      # default: true
  max_retries_per_step: <int>                              # default: 0
  stop_on_first_failure: true | false                      # default: true
---
```

## Field reference

### `execution.implementation_model`

The Claude model tier all steps default to. See [MODEL_TIERS.md](MODEL_TIERS.md).

### `execution.parallelism`

- `sequential` — dispatch one todo at a time, wait for each to complete.
- `parallel` — dispatch non-conflicting todos in a single message. Two todos conflict if:
  - One lists the other in `depends_on`, OR
  - Their `files:` lists overlap (any common path).

### `execution.prefer_project_agents`

When `true` (default), the orchestrator routes todos to project-specific agents when a `scope_hint` match exists. Set to `false` to always use the baseline `impl-*` agents.

### `execution.curate_on_completion`

When `true` and `memory-curator` is installed, the orchestrator dispatches it exactly once after all todos finish. It consolidates cross-cutting knowledge (max 3 curates per plan).

### Per-todo `agent:`

Pins a specific agent for that step. The named agent must exist at `<project>/.claude/agents/<name>.md`. Takes precedence over scope-hint routing.

### Per-todo `model_override:`

Overrides `implementation_model` for a single step. Useful for escalating one expensive step to `opus` while running the rest on `haiku`.

## Minimal example

```yaml
---
name: add-password-reset
overview: Add password reset via email token to the auth module
todos:
  - id: domain
    content: Add ResetToken value object and domain event to the auth module
    status: pending
    files: [apps/api/src/modules/auth/domain/]
    agent: domain-modeler
  - id: endpoint
    content: Add POST /auth/reset-password endpoint (validate token, update hash)
    status: pending
    depends_on: [domain]
    files: [apps/api/src/modules/auth/]
  - id: tests
    content: Add integration tests covering the reset flow end-to-end
    status: pending
    depends_on: [endpoint]
    files: [apps/api/test/auth/]
execution:
  implementation_model: sonnet
  parallelism: sequential
  verify_each_step: true
  curate_on_completion: true
---
```

## Status lifecycle

```
pending → in_progress → completed
                     ↘ failed → (retry) → completed | failed
```

- `cancelled` — manually set by the user to skip a step permanently.
- The orchestrator never marks a todo `cancelled` on its own.

## Plan file location

Plans live at `~/.claude/plans/` (user-wide, not project-local). To disambiguate across projects, use a project-slug prefix in the filename: `wi-be-add-payment-module.md`.
