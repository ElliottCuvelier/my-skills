# Team Orchestration Playbook

This is the playbook the **team lead** follows to run a saved plan as a Claude Code agent team. It is read when the user runs `/ct-orchestrate` or `/ct-orchestrate-resume`, or asks in-session to run/resume a plan as a team.

> **You — this session — are the team LEAD.**
> You coordinate teammates; you do **not** edit files yourself. There is exactly **one team per session**, the lead is **fixed** for the session's lifetime, and **teammates cannot spawn teammates** (no nested teams). You spawn one teammate per file-disjoint lane, seed a shared task list, and let the native **task list + file-lock claiming + mailbox** do the status tracking, ordering, and parallelism that a single-session orchestrator would hand-roll.

Agent teams are **experimental** and cost **~7× a single session** (each teammate is a full Claude instance). Use this for plans whose work splits into independent file lanes (cross-layer features, parallel modules, parallel review). For a one- or two-step plan, just build it directly.

---

## Step 0 — Preflight & enable gate

1. **Enable gate.** A team only forms when `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set. It is read at **startup**, so it must live in `settings.json` `env` (or the shell) with the session **restarted** — exporting it mid-session does nothing. If it is unset, **stop** and tell the user:
   > Add `"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"` to settings.json `env`, restart Claude Code, then re-run `/ct-orchestrate`.
   Do **not** fall back to one-shot sub-agents — that is a different skill (`claude-orchestrator`).
2. **Load the marker** (`.claude/agents/.ct-o10r-installed`, else `~/.claude/agents/...`). Read: `tiers_installed` (which `impl-<tier>` roles exist), `default_tier` (the default teammate model), `verifier_enabled` (reviewer role available), `memory_curator_enabled`, `byterover.enabled`, `project_agents` (specialist roles + `scope_hint`), and `codebase_snapshot.test_runner` (the TaskCompleted gate needs it). No marker → the skill isn't installed here; trigger first-use setup.
3. **Compute the team name:** `session-` + the first 8 chars of the session id. ct-o10r runtime state lives under `~/.claude/ct-o10r/<team-name>/` (the files-sidecar and ByteRover backstop); the native task list is under `~/.claude/tasks/<team-name>/`.

---

## Step 0R — Resume

After `/ct-orchestrate-resume` (or `/resume` then a re-run): the session id is unchanged, so `<team-name>` is the same and the native task list at `~/.claude/tasks/<team-name>/` **persists** — but in-process teammates are **gone**.

1. Read the task list; treat **it**, not the plan's todos, as the source of truth for what's done.
2. **Heal orphans:** reset every task that is `in_progress` with no live owner back to pending/unassigned (its teammate died with the previous session — otherwise its dependents never unblock).
3. Recompute lanes from the still-open tasks, respawn the needed teammates (Step 3), and re-assign only the open tasks (Step 4 over the open set). Skip `completed` tasks.

---

## Step 1 — Read the plan and derive lanes

Parse the frontmatter: `todos` (each `id`, `content`, optional `files`, `depends_on`, `agent`, `model_override`) and the `team:` block (see [PLAN_FORMAT.md](PLAN_FORMAT.md)). If there's no `team:` block, ask the user for a default teammate model + verification strategy and write one before proceeding.

**Derive the lanes — the native-lean core:**

- **Partition todos into file-disjoint lanes.** A lane is a maximal group of todos whose `files:` don't overlap any other lane's `files:`. Each lane = one teammate's exclusive ownership.
- **One model per lane.** Split a lane if a todo's `model_override` (or its `agent:` role's model) disagrees with the lane's model.
- **A cross-cutting todo** (files overlap several lanes) becomes its own lane that `depends_on` the lanes it must follow — a serialization point, not a conflict.
- **Cap 3–5 teammates** (~≤6 tasks each). More lanes than 5 → give some teammates two lanes; fewer → one teammate per lane.
- If `team.roster` is explicit, use it and validate that its lanes are file-disjoint.

Capture the **git baseline**: `git rev-parse HEAD` (the diff base for end-of-run consolidation).

---

## Step 2 — ByteRover pre-flight (before delegate mode)

Only if `byterover.enabled`. While the lead still has full tool access, run once:

```bash
brv search "<plan topic keywords>" --scope "architecture/" --format json --limit 10
```

Surface relevant prior decisions inline. The lead may spend **≤1 `brv query`** if search is thin; teammates only ever `brv search`.

---

## Step 3 — Delegate mode, then spawn the team

1. **Engage delegate mode** (Shift+Tab) so the lead is restricted to coordination tools and won't drift into implementing. (It also can't run `brv curate` while delegated → consolidation is delegated to a teammate in Step 7. Set `team.lead_mode: default` to skip this and let the lead curate directly.)
2. **Set permissions first.** Teammates inherit the lead's permission mode **at spawn** and it is fixed thereafter. Allow-list the test runner, `git`, `brv`, and edits **now** so N teammates don't each trigger a prompt.
3. **Spawn one teammate per lane.** Reference the lane's role definition as the teammate type (`impl-<model>` or a `project_agents` role) and state the model explicitly. Teammates do **not** see your conversation — put everything in the spawn prompt:
   > Spawn a teammate named `<lane>` using role `impl-sonnet` on Sonnet. Mission: `<lane goal>`. **You own only `<glob>` — never edit outside it; message me first if a task needs an out-of-lane change.** Work the tasks I assign you in dependency order; mark each complete only after its scoped tests pass; after any `brv curate`, message me `BRV-REVIEW <taskId> <scope>`. Follow the ByteRover loop. **Do not spawn or coordinate other teammates.**
   - **Spawn mechanism:** with the flag on, spawning is the Agent/Task tool invoked with the role as its `subagent_type` (the role's body is appended to the teammate's system prompt; its `model`/`tools` are honored), or the equivalent natural-language "spawn a teammate using `<role>`…". The contract is the same either way.
   - **skills/MCP caveat:** a role's `skills`/`mcpServers` frontmatter is **not** applied to a teammate (teammates load skills/MCP from project/user settings). If a role relied on a skill, restate the procedure in the spawn prompt.
   - For a `plan_approval` lane, add: "work in read-only plan mode and submit a plan for my approval before editing," and remember `team.plan_approval_criteria`.

---

## Step 4 — Seed the shared task list (assign, don't open-claim)

Create one task per todo. Each task's **description must be self-contained** (teammates don't share your context) and include a machine-parseable file line for the gate:

```
<full step text>
Files: [<path>, <path>]
Success: <success criteria>
Protocol: mark complete only when scoped tests pass; after curating, message the lead BRV-REVIEW <taskId>.
```

- **Dependencies:** map `depends_on` → native task dependencies. The system auto-unblocks dependents when a prerequisite completes — never hand-order.
- **Assignment is a correctness requirement, not a preference.** **Assign every task to its lane's single owner.** Native file-locking serializes only task-**claim** races — it does **not** lock source files. Two teammates editing the same file corrupt it. File safety comes from assignment + dependencies; **self-claim is only for intra-lane "what's next" ordering.** Cross-lane parallelism is preserved because lanes are file-disjoint.
- The `Files:` line is read by the `TaskCreated` hook into `~/.claude/ct-o10r/<team-name>/scoped-files.json` so the `TaskCompleted` gate can scope tests to the right files.

---

## Step 5 — Coordinate and steer

Let the native machinery run; watch the task list (Ctrl+T) and the mailbox.

- Answer teammate questions; **deny out-of-lane edit requests by default** — if genuinely needed, re-partition or add a dependency to serialize.
- Reassign a stuck task; escalate a task the gate keeps bouncing (`max_bounces`) by reassigning or spawning a higher-tier teammate for that lane.
- **Wait for teammates to finish before consolidating** — don't race ahead of in-flight lanes (and don't start implementing yourself).
- **Status lag:** if a teammate goes idle leaving a task `in_progress`, ping it to mark complete, or reopen/reassign so dependents unblock.

---

## Step 6 — Verification (per `team.verify`)

- **`hook`** (default, recommended): the `TaskCompleted` gate runs scoped tests on each task's files and **exit-2 bounces** failures back to the same teammate (task stays `in_progress`, failure text delivered as feedback). The lead intervenes only after `max_bounces`.
- **`review`:** also spawn a read-only **reviewer teammate** (role `verifier`) that claims a review task per implementation task and messages the lead / reopens the task on `INCOMPLETE:` / `CONCERN:`. Use when semantic judgment (not just tests) matters.
- **`none`:** no automated verification.
- **`plan_approval` lanes:** approve or reject-with-feedback each teammate's submitted plan against `team.plan_approval_criteria` before it implements.

---

## Step 7 — End-of-run ByteRover consolidation

Only if `byterover.enabled` and `curate_on_completion`. When every task is `completed`:

1. **Assemble pending taskIds**, deduped, from two channels: the `BRV-REVIEW` mailbox notes you collected in-context (primary), and the backstop file `~/.claude/ct-o10r/<team-name>/brv-pending.txt` (written by the `TeammateIdle` hook).
2. **Consolidate (≤3 curates).** Default `curate_via: teammate` (lead stays delegated): spawn the **memory-curator** teammate with a single task that `depends_on` all others (native runs it last); pass the plan path, the **baseline SHA from Step 1**, and the collected taskIds in its task description. It runs `git diff --stat <baseline>..HEAD`, writes ≤3 curates to `architecture/`…/`orchestration/plans/`, and messages back its `BRV-REVIEW` ids. `curate_via: lead` (only if not delegated): the lead runs the consolidation `brv curate` itself, to scope `orchestration/plans/`.

---

## Step 8 — Graceful shutdown

Ask each teammate to shut down by name (roughly in parallel). A teammate may approve (graceful) or reject with a reason (e.g. mid-write) — surface refusals. **Don't block the report on shutdown** — team dirs auto-clean on session exit; explicit shutdown just frees resources/cost sooner.

---

## Step 9 — Final report (the authoritative surface)

There is **no teammate `Stop` hook** — the lead's report is the single surface for pending reviews. Source status from the **native task list**:

```
## Plan complete: <plan-name>   (team <team-name>, N teammates)

### Results
| task | status | teammate (model) | notes |
|------|--------|------------------|-------|
| auth-domain   | completed | auth  (sonnet) | tests green |
| auth-endpoint | completed | auth  (sonnet) | 1 gate bounce, fixed |
| notif-mailer  | completed | notif (haiku)  | — |

### Verification
gate bounces: <n> (all resolved) | reviewer concerns: <list or none>

### Downgrades detected
<DOWNGRADE: notes a teammate reported, or none>

### Pending memory review   (deduped: mailbox ∪ idle backstop)
1. <taskId> — <scope> (from teammate <name>)
   approve: brv review approve <taskId>    reject: brv review reject <taskId>

### Cost note
Team run ≈ 7× a single session. Teammates: N on <models>.

### Suggested follow-ups
<out-of-lane items teammates flagged>
```

---

## Rules

- **Coordinate, don't implement.** The lead never edits files. Every change goes through a teammate.
- **One team per session; the lead is fixed; no nested teams.** Teammates never spawn teammates, and the ct-o10r orchestrator role is never a teammate role.
- **Assign, don't open-claim, for file safety.** File-disjoint lanes + assignment + dependencies. Native locking guards task-claim, not source writes.
- **Self-contained tasks.** Teammates don't share the lead's conversation — put everything in the task description and spawn prompt.
- **Never auto-approve memory reviews.** Surface taskIds in the report; the user runs `brv review approve/reject`.
- **Surface downgrades and the cost note every run.**
