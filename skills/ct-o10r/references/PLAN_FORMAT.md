# Plan File Format

Claude Code plan files live at `~/.claude/plans/<name>.md`. The ct-o10r skill extends the standard plan frontmatter with a `team:` block and re-points a few per-todo fields. Plan todos **seed** the agent team's shared task list; once a run starts, the native task list at `~/.claude/tasks/<team-name>/` owns live status — so there is **no per-todo `status:` field** here.

## Full schema

```yaml
---
name: <string>               # display name for the plan
overview: <string>           # one-sentence description of the goal

todos:
  - id: <string>             # unique identifier, e.g. "domain" or "add-auth"
    content: <string>        # what to do — specific and independently executable

    # Optional per-todo fields:
    files: [<path>, ...]             # the files this step OWNS — drives lane partitioning + test scoping
    depends_on: [<todo-id>, ...]     # ordering dependency (becomes a native task dependency)
    agent: <role-name>               # pin a teammate role (impl-<tier> or a project role)
    model_override: haiku | sonnet | opus   # force this step's lane onto a specific model

team:
  team_size: <int>                 # 3–5; or omit and let the lead derive lanes from files:
  roster:                          # OPTIONAL explicit lanes; else derived from todos' files:/agent:
    - name: <string>               # teammate name (referenceable in prompts)
      role: <role-name>            # subagent definition reused as the teammate role
      model: haiku | sonnet | opus | inherit
      files: [<path>, ...]         # this teammate's EXCLUSIVE lane
      plan_approval: true | false  # require this teammate to plan before implementing
  default_teammate_model: haiku | sonnet | opus | inherit   # default teammate model (default: sonnet)
  lead_mode: delegate | default    # delegate = coordination-only (recommended); default = lead may also act
  verify: hook | review | none     # hook = TaskCompleted test gate (default); review = reviewer teammate
  plan_approval: true | false      # default for lanes that don't set their own (default: false)
  plan_approval_criteria: <string> # how the lead auto-approves/rejects submitted plans
  curate_on_completion: true | false   # consolidate ByteRover memory at the end (default: true if available)
  curate_via: teammate | lead      # teammate = curator teammate (default); lead = lead curates (needs lead_mode: default)
  prefer_project_agents: true | false  # use project role bodies vs generic impl roles (default: true)
  max_bounces: <int>               # times the TaskCompleted gate may bounce a task before the lead escalates (default: 2)
  on_task_failure: reopen | ask    # what to do when a task can't pass (default: reopen)
  display_mode: in-process | split-panes   # UI hint (split-panes needs tmux/iTerm2)
---
```

## How a plan becomes a team

1. The lead **partitions todos into file-disjoint lanes** by their `files:`. Each lane → one teammate that **exclusively owns** those files.
2. Each todo becomes one **task** on the shared list, assigned to its lane's teammate, with `depends_on` mapped to native task dependencies.
3. Teammates work their assigned tasks in dependency order; the native list tracks status; the `TaskCompleted` gate runs scoped tests per task.

This is why `files:` is the most load-bearing field: it determines lanes, teammate assignment, and test scoping. Two todos that must touch the same files belong to the **same lane** (one teammate) or must be serialized with `depends_on` — never split across teammates (concurrent writes corrupt files; see [TEAM_ORCHESTRATION.md](TEAM_ORCHESTRATION.md) Step 4).

## Field reference

### Per-todo `files:`
The step's file-ownership lane. Drives (a) lane partitioning, (b) which teammate owns the task, and (c) the `Files: [...]` line the lead writes into the task description, which the `TaskCompleted` test gate reads. Be precise — overly broad globs merge lanes and reduce parallelism.

### Per-todo `depends_on:`
Becomes a native task dependency. A task with unresolved dependencies can't be claimed until they complete; the system unblocks it automatically.

### Per-todo `agent:` / `model_override:`
`agent:` pins a teammate role (must exist at `.claude/agents/<role>.md`). `model_override:` forces the step's lane onto a specific model; if it disagrees with the rest of its lane, the lead splits the lane.

### `team.default_teammate_model`
The model teammates run on when a lane/role doesn't pin one. Default `sonnet` (Anthropic's recommendation for team coordination); use `haiku` for cheap bulk lanes, reserve `opus` for one hard lane.

### `team.verify`
`hook` (default) gates each task on scoped tests via the `TaskCompleted` hook — no extra teammate, no extra cost. `review` additionally spawns a read-only reviewer teammate for semantic checks. `none` disables automated verification.

### `team.lead_mode` / `team.curate_via`
`delegate` (recommended) restricts the lead to coordination tools so it can't drift into implementing — but then it can't run `brv curate`, so set `curate_via: teammate` (the default). Use `lead_mode: default` + `curate_via: lead` only if you want the lead to curate directly.

## Minimal example

```yaml
---
name: add-password-reset
overview: Add password reset via email token to the auth module
todos:
  - id: domain
    content: Add ResetToken value object and domain event to the auth module
    files: [apps/api/src/modules/auth/domain/]
    agent: domain-modeler
  - id: endpoint
    content: Add POST /auth/reset-password (validate token, update hash)
    depends_on: [domain]
    files: [apps/api/src/modules/auth/application/, apps/api/src/modules/auth/http/]
  - id: mailer
    content: Add reset-email template + sender (independent of auth internals)
    files: [apps/api/src/modules/notifications/]
  - id: tests
    content: Integration tests covering the reset flow end-to-end
    depends_on: [endpoint]
    files: [apps/api/test/auth/]
team:
  team_size: 2
  default_teammate_model: sonnet
  lead_mode: delegate
  verify: hook
  curate_on_completion: true
  curate_via: teammate
---
```

The lead derives **lane A** = `domain → endpoint → tests` (auth files, serial via deps, one Sonnet teammate; `domain` uses the `domain-modeler` role) and **lane B** = `mailer` (notifications files, a second teammate that runs fully in parallel). `tests` auto-unblocks when `endpoint` completes. No `status:` anywhere — the native task list owns it.

## Plan file location

Plans live at `~/.claude/plans/` (user-wide, not project-local). To disambiguate across projects, use a project-slug prefix in the filename: `wi-be-add-password-reset.md`.
