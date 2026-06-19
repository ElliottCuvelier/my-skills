# Orchestration Playbook

This is the playbook the **current session** follows to execute a saved plan. It is read when the user runs `/claude-orchestrate` or `/claude-orchestrate-resume`, or asks in-session to build/execute/resume a plan.

> **You — this session — are the orchestrator.**
> You coordinate sub-agents; you do **not** write code yourself, and you do **not** spawn a separate orchestrator agent. Dispatch each step to a model-pinned sub-agent (`impl-*`, a project agent, the `verifier`, or the `memory-curator`) and write results back to the plan file. Running in the same session you planned in keeps all of your planning context available while you dispatch.

The main session is normally allowed to edit files — **while orchestrating, you must not.** Every file change goes through a dispatched sub-agent. The only writes you make directly are todo-status updates to the plan file itself.

---

## Step 0 — Load the roster from the install marker

Read the install marker to learn which agents exist and how to route. Look in this order and use the first one found:

1. `.claude/agents/.claude-orchestrator-installed` (project scope)
2. `~/.claude/agents/.claude-orchestrator-installed` (user-wide scope)

The marker is JSON. Read these fields:

- `tiers_installed` — the tiers that have an `impl-<tier>` agent on disk (e.g. `["haiku", "sonnet", "inherit"]`).
- `default_tier` — the fallback tier when a plan omits `implementation_model`.
- `verifier_enabled` — whether `agents/verifier.md` exists.
- `memory_curator_enabled` — whether `agents/memory-curator.md` exists.
- `byterover.enabled` — whether the ByteRover memory loop is active.
- `project_agents` — list of `{name, model, scope_hint, role, byterover_scope, ...}` for scope-matched routing.

**If no marker is found:** the orchestrator isn't installed here. Tell the user to run first-use setup (trigger the `claude-orchestrator` skill), or — if `agents/impl-*.md` files clearly exist — fall back to whatever `impl-*` agents are on disk and ask the user which tier to use.

---

## Routing

The set of agents available to dispatch:

- **Implementation agents** — `impl-<tier>` for each tier in `tiers_installed`.
- **Project agents** — each entry in `project_agents`, matched to work by its `scope_hint` glob.
- **Verifier / memory-curator** — present only if `verifier_enabled` / `memory_curator_enabled`.
- Any agent named directly in a todo's `agent:` field, if that agent file exists on disk.

**Routing priority for each todo:**

1. If the todo has an `agent:` field → use that agent directly.
2. Else if `prefer_project_agents: true` AND a `project_agents[].scope_hint` matches a path in the todo's `files:` → use that project agent.
3. Else fall back to `impl-<model_override>` if the todo sets `model_override`, otherwise `impl-<implementation_model>` (the plan's `execution.implementation_model`, defaulting to `default_tier`).

If a routed tier has no `impl-<tier>` file installed, tell the user and ask which installed tier to use instead.

---

## Step 1 — Read and validate the plan

Read the plan file from the path provided. Parse its YAML frontmatter:

- `todos` — the list of steps (each with `id`, `content`, `status`, and optional `files`, `agent`, `depends_on`, `model_override`).
- `execution:` block — fields:
  - `implementation_model`: `haiku | sonnet | opus | inherit` (defaults to the marker's `default_tier`)
  - `parallelism`: `sequential | parallel` (default: `sequential`)
  - `verify_each_step`: bool (default: `true` if `verifier_enabled`, else `false`)
  - `curate_on_completion`: bool (default: `true` if `memory_curator_enabled` and ByteRover enabled, else `false`)
  - `prefer_project_agents`: bool (default: `true`)
  - `max_retries_per_step`: int (default: `0`)

If no `execution:` block exists, ask the user which tier to use (list available agents from Step 0) and whether to run sequentially or in parallel, then write the block to the plan file before proceeding.

Before the dispatch loop, capture the merge-base for end-of-plan consolidation: run `git log --format="%H" -1 HEAD` and remember the SHA.

---

## Step 2 — ByteRover pre-flight

Only if `byterover.enabled` is true. Otherwise skip memory pre-flight and pending-review surfacing entirely.

```bash
brv search "<plan topic keywords>" --scope "architecture/" --format json --limit 10
```

If the search returns relevant prior decisions, surface them inline before dispatching. You (the orchestrating session) may use at most one `brv query` call if `search` is thin and synthesis is genuinely needed — sub-agents are never allowed to call `brv query`.

After ALL todos are done, surface the pending taskIds accumulated from sub-agents (see Step 5).

---

## Step 3 — Dispatch loop

For each todo in `todos` with `status: pending` (skip `completed`, `cancelled`):

**Route the todo:** follow the routing priority above.

**Build the dispatch prompt.** Give the implementer a focused prompt containing:

- The step content.
- Relevant file paths from `files:` (if specified).
- Success criteria: "This step is complete when [specific condition]".
- Any depends-on context: "This step follows [todo-id] which [brief outcome]".

**Parallelism.** If `parallelism: parallel` AND the current todo has no `depends_on` entries AND its `files:` don't overlap with other in-flight todos → dispatch alongside other non-conflicting todos in a single message. Otherwise dispatch sequentially.

**Update status.** Before dispatching: set `status: in_progress` in the plan file. On success: set `status: completed`. On failure: set `status: failed`, then pause and ask the user: skip / retry (up to `max_retries_per_step` times) / abort.

**Collect memory reviews.** Parse each sub-agent's return for `Pending review: <taskId>` lines in its `## Memory` section. Accumulate these into a `pending_taskIds` list — do NOT surface them between todos.

**Verify (if enabled).** If `verify_each_step: true` AND `verifier_enabled` → dispatch `verifier` after each completed step, providing the step content and the implementer's report (files changed, commands run). On an `INCOMPLETE:` or failing verdict, retry the step up to `max_retries_per_step` times (default `0` → fail immediately).

---

## Step 4 — End-of-plan consolidation

After all todos are done:

1. If `curate_on_completion: true` AND `memory_curator_enabled` → dispatch `memory-curator` once with:
   - The plan path.
   - The merge-base commit captured in Step 1.
   - The list of `pending_taskIds` already collected.

2. Collect any additional `Pending review: <taskId>` lines from the curator's return.

3. Run your own curate (only if ByteRover enabled):

   ```bash
   brv curate "Plan <plan-name>: ran <N> todos on impl-<tier>. [Summary of what was accomplished.] [Any downgrades or failures noted.]" \
     -f <plan-file-path>
   ```

   Curate to scope `orchestration/plans/`.

---

## Step 5 — Final report

Print a structured summary. This report is the **authoritative surface** for pending ByteRover reviews — surface every accumulated taskId here regardless of any session hook.

```
## Plan complete: <plan-name>

### Results
| todo | status | agent | notes |
|------|--------|-------|-------|
| <id> | completed | impl-sonnet | ... |
| <id> | failed | impl-haiku | ... |

### Verifier summary
<pass/fail counts, any CONCERN: items>

### Downgrades detected
<any DOWNGRADE: reports from sub-agents — flag explicitly>

### Pending memory review
<Only if there are taskIds>

N curates from this plan need your approval:

1. `<taskId-1>` — <scope/path.md> (from `<agent>` on todo `<id>`)
   Summary: "<curate summary>"
   - Approve: `brv review approve <taskId-1>`
   - Reject:  `brv review reject <taskId-1>`

2. ...

### Suggested follow-ups
<anything the implementers flagged as out-of-scope follow-ups>
```

Where you can, run the whole plan within a single uninterrupted turn so the session's Stop hook surfaces pending reviews exactly once. Genuine user-decision pauses (missing `execution:` block, a skip/retry/abort prompt) are unavoidable — that's fine, because `brv review approve/reject` is idempotent and this final report is the source of truth either way.

---

## Rules

- **Dispatch, don't implement.** You coordinate — you never make file edits yourself (other than todo-status updates to the plan file).
- **Don't spawn a separate orchestrator.** You are the orchestrator. Dispatch `impl-*` / project / `verifier` / `memory-curator` sub-agents directly.
- **Respect user-edited state.** Skip todos already `completed` unless the user asks for a re-run.
- **Fail gracefully.** On step failure, pause and ask skip / retry / abort. Do not cascade failures silently.
- **Surface downgrades.** If an implementer reports its model was overridden (capacity-limited, model not available), flag it in the final summary.
- **Plan is source of truth.** All status updates go into the plan file's frontmatter, not just chat.
- **Never auto-approve memory reviews.** Collect taskIds and surface them to the user at the end. Never run `brv review approve` yourself.
