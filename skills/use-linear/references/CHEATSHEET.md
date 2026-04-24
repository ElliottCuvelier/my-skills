# Cheatsheet

One-screen quick reference. Back to [SKILL.md](../SKILL.md).

---

## Session bootstrap (once per task, before `list_*`)

From **repo root**:

```bash
python skills/use-linear/scripts/bootstrap.py
```

Read `.agents/use-linear/context.yaml` if present ([CONTEXT.md](CONTEXT.md)). Parse pipe rows under `## issues`, `## states`, `## projects`, `## cycles`, `## git`. Use `list_teams` / `list_projects` / `list_issue_labels` / `list_issue_statuses` / `list_cycles` **only just-in-time** before a `save_*` when something is missing from context + snapshot.

---

## Task-Start Checklist

Before writing a single line of code:

- [ ] **Bootstrap** — `context.yaml` + `python skills/use-linear/scripts/bootstrap.py` (if script prints `# bootstrap: …`, fall back to MCP discovery)
- [ ] **Resolve issue** — user ID / git hints / `## issues` started row → `get_issue`; else narrow `list_issues({ assignee: "me", state: "started" })`
- [ ] **Draft + confirm** — title, description, team, project, labels, priority, estimate, cycle (prefer context + snapshot; `list_*` only to fill gaps)
- [ ] **Create** — `save_issue(...)` after user confirms
- [ ] **Check current state** — `get_issue({ id })` — already In Progress? skip transition
- [ ] **Move state** — `list_issue_statuses({ team })` → discover In Progress name → `save_issue({ id, state: "In Progress" })`
- [ ] **Surface spec** — create or link a Linear Document if a written spec will be referenced

---

## State Transition Checklist

| Moment      | Action                                                                   |
| ----------- | ------------------------------------------------------------------------ |
| Task starts | `get_issue` → if Backlog/Todo: `save_issue({ state: "In Progress" })`    |
| PR opened   | `get_issue` → if not yet In Review: `save_issue({ state: "In Review" })` |
| PR merged   | `save_issue({ state: "Done" })` (only if no further work)                |
| Blocked     | Set `blockedBy` relation; note in Blocker comment                        |

**Always `get_issue` before transitioning — never regress status.**

---

## Comment Quick Reference

| Type              | When                                       | Format                          |
| ----------------- | ------------------------------------------ | ------------------------------- |
| **Progress**      | Material step completed (not every commit) | One sentence                    |
| **Blocker**       | Something preventing motion                | What + what's needed to unblock |
| **Finding**       | Scope creep, bug, deviation from spec      | Deviation template              |
| ~~Starting work~~ | Never                                      | Status change says it           |

```
// Progress
save_comment({ issueId, body: "Redis module merged. Rate limiter now unblocked." })

// Blocker
save_comment({ issueId, body: "**Blocked**: Need auth team token format before proceeding." })

// Finding / Deviation
save_comment({ issueId, body: "**Deviation**: ...\n**Why**: ...\n**Impact**: ...\n**Decision needed**: ..." })
```

---

## PR / Commit Checklist

- [ ] Every commit on branch has `Linear: ENG-###` in the message
- [ ] PR body has `Linear: ENG-###` appended (or fills existing template slot — check first)
- [ ] Multiple issues: `Linear: ENG-123, ENG-124`
- [ ] Branch name is **not** changed
- [ ] Final `save_comment` summarizes landed vs. deferred + follow-up issue IDs

---

## Project Update Checklist

Post when (event-driven, not on cadence):

- [ ] A milestone lands
- [ ] A blocker surfaces
- [ ] Scope or timeline materially shifts
- [ ] Health changes (`onTrack` → `atRisk` → `offTrack`)
- [ ] A batch of sibling issues completes

```
save_status_update({ project: "Project Name", health: "atRisk", body: "..." })
// Initiative updates: save_status_update({ initiative: "Init Name", type: "initiative", health: "onTrack", body: "..." })
```

---

## End-of-Plan Offer

After any multi-step plan, close with:

> **Translate to Linear?**
>
> - **Start working** — create issues, assign, move first to In Progress, begin
> - **Archive for team** — create in Backlog, unassigned
> - **Neither**

See [PLAN-TO-LINEAR.md](PLAN-TO-LINEAR.md) for translation rules.

---

## Top Tool Calls

```
// Find issues by keyword
list_issues({ team: "ENG", query: "keyword" })

// My queue
list_issues({ assignee: "me", state: "started" })
list_issues({ assignee: "me", state: "unstarted" })

// Get a specific issue (always re-read; don't use memory)
get_issue({ id: "ENG-123" })
get_issue({ id: "ENG-123", includeRelations: true })  // include blocking/related links

// Discover team workflow states
list_issue_statuses({ team: "ENG" })

// Discover labels before using any
list_issue_labels({ team: "ENG" })

// Discover current cycle
list_cycles({ teamId: "<id>", type: "current" })

// Create/update issue (save handles both)
save_issue({ team: "ENG", project: "...", title: "...", description: "...", labels: ["backend"], priority: 2, estimate: 5, cycle: "Sprint 14" })
save_issue({ id: "ENG-123", state: "In Progress" })
save_issue({ id: "ENG-123", blockedBy: ["ENG-456"] })      // blocked by
save_issue({ id: "ENG-123", blocks: ["ENG-789"] })          // this blocks another
save_issue({ id: "ENG-123", removeBlockedBy: ["ENG-456"] }) // remove a blocker

// Comment
save_comment({ issueId: "ENG-123", body: "..." })
```

**Note:** Tools appear namespaced in-session by the server's configured name — check the actual tool list for the correct prefix (e.g., `mcp__linear__save_issue` if the server is named "linear").

---

## Priority Reference

| Value | Issues      | Projects    |
| ----- | ----------- | ----------- |
| 0     | No priority | No priority |
| 1     | Urgent      | Urgent      |
| 2     | High        | High        |
| 3     | Normal      | Medium      |
| 4     | Low         | Low         |

---

## Estimate / Priority / Cycle Rule

| Situation                                     | Action                             |
| --------------------------------------------- | ---------------------------------- |
| Field is unset on create or existing issue    | Set it                             |
| Field is already set, no change needed        | Leave it                           |
| Field is already set, reality diverges ≥ ~50% | Offer the change to the user first |
