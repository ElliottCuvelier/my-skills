# Agent Teams (the model ct-o10r builds on)

ct-o10r runs a saved plan as a Claude Code **agent team**. This is the quick reference for that team model. Full mechanics: [Claude Code docs → agent teams](https://code.claude.com/docs/en/agent-teams).

## Enable (required)

Agent teams are **experimental and off by default**. Set:

```json
// settings.json
{ "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }
```

The flag is read at **startup** — add it, then **restart** Claude Code. Without it, no team forms and `/ct-orchestrate` cannot run.

## The model

| Component | Role |
|-----------|------|
| **Lead** | The main session running the plan. Spawns teammates, seeds tasks, coordinates. Fixed for the session — can't be transferred or promoted. |
| **Teammates** | Separate full Claude Code instances, each with its own context window. Own a file lane and do the edits. |
| **Task list** | Shared list at `~/.claude/tasks/<team-name>/`. Tasks have status (pending / in_progress / completed) + dependencies; claiming uses file locks. Persists across resume. |
| **Mailbox** | Teammates and the lead message each other by name; delivery is automatic; idle teammates notify the lead. |

`<team-name>` = `session-` + the first 8 chars of the session id.

## What's native (so ct-o10r doesn't hand-roll it)

- **Status tracking** — the task list owns it (so there's no per-todo `status:` in the plan).
- **Dependency ordering** — a task with unresolved `depends_on` can't be claimed until they complete; dependents auto-unblock.
- **Parallelism** — emergent from file-disjoint lanes running on different teammates.
- **Claim races** — file-locked. (This does **not** lock source-file writes — see Gotchas.)

## Teammates from role definitions

The lead spawns a teammate by referencing a subagent definition as the teammate **type** (`subagent_type`). The definition's `model` and `tools` are honored, and its body is appended to the teammate's system prompt. ct-o10r's generated `impl-<tier>` and project roles are exactly these definitions; `SendMessage` and the task tools are always available to a teammate even under a restrictive `tools` allowlist.

**Caveat:** a definition's `skills` and `mcpServers` frontmatter are **not** applied to a teammate — teammates load skills/MCP from project/user settings like any session. Restate skill-dependent procedures in the spawn prompt.

## Per-teammate model

Teammates do **not** inherit the lead's `/model`. The lead sets each teammate's model at spawn (ct-o10r uses the lane's `roster[].model` / `default_teammate_model`), or you set a Default teammate model in `/config`.

## Delegate mode

Shift+Tab (or `team.lead_mode: delegate`) restricts the lead to coordination-only tools so it can't drift into implementing. Trade-off: the lead then can't run Bash / `brv curate`, so ByteRover consolidation is delegated to a teammate (`curate_via: teammate`).

## Display modes

- **in-process** (default) — teammates render in the main terminal; ↑/↓ select a teammate, Enter views/messages it, Ctrl+T toggles the task list.
- **split-panes** — one pane per teammate; needs tmux or iTerm2. Enable with `teammateMode: "auto"` (settings) or `--teammate-mode auto`.

## Hooks (quality gates) — see [TEAM_ORCHESTRATION.md](TEAM_ORCHESTRATION.md)

| Event | ct-o10r use | Exit 2 effect |
|-------|-------------|---------------|
| `TaskCreated` | record each task's `Files: [...]` into the sidecar | rolls back task creation |
| `TaskCompleted` | run scoped tests; gate completion | keeps task `in_progress` + sends feedback |
| `TeammateIdle` | scrape transcript for ByteRover taskIds (backstop) | would prevent idle (not used) |

There is no teammate `Stop` hook — the lead's final report is the surface for pending reviews.

## Shutdown & cleanup

Ask the lead to "ask the `<name>` teammate to shut down." Team config (`~/.claude/teams/<team-name>/`) is removed on session exit; the task list persists (governed by `cleanupPeriodDays`).

## Gotchas

- **File locks guard task-claim, not source writes** — two teammates editing the same file corrupt it. ct-o10r enforces file-disjoint lanes + assignment.
- **No in-process resume** — `/resume` doesn't restore teammates; respawn them (the task list persists; reset orphaned `in_progress` tasks).
- **Status can lag** — a teammate may forget to mark a task complete, blocking dependents; the lead nudges or reopens.
- **One team per session; no nested teams** — teammates can't spawn teammates.
- **Permissions fixed at spawn** — set them before spawning to avoid a prompt storm.
- **~7× token cost** — each teammate is a full instance; keep teams to 3–5 and prefer cheap models.
