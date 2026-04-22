# Cheatsheet

One-screen quick reference. Back to [SKILL.md](../SKILL.md).

---

## Task-Start Checklist

Before writing a single line of code:

- [ ] **Search** — `list_issues(filter: { query: "..." })` — is there already an issue?
- [ ] **Draft + confirm** — title, description, team, project (find a fit; leave project-less if none), labels (from `list_issue_labels`), priority, estimate, cycle (from `list_cycles`)
- [ ] **Create** — `save_issue(...)` after user confirms
- [ ] **Check current state** — `get_issue(issueId)` — already In Progress? skip transition
- [ ] **Move state** — `list_issue_statuses` → discover In Progress ID → `save_issue({ id, stateId })`
- [ ] **Surface spec** — create or link a Linear Document if a written spec will be referenced

---

## State Transition Checklist

| Moment | Action |
| --- | --- |
| Task starts | `get_issue` → if Backlog/Todo: `save_issue` → In Progress |
| PR opened | `get_issue` → if not yet In Review: `save_issue` → In Review |
| PR merged | `save_issue` → Done (only if no further work) |
| Blocked | Set `blocked_by` relation; note in Blocker comment |

**Always `get_issue` before transitioning — never regress status.**

---

## Comment Quick Reference

| Type | When | Format |
| --- | --- | --- |
| **Progress** | Material step completed (not every commit) | One sentence |
| **Blocker** | Something preventing motion | What + what's needed to unblock |
| **Finding** | Scope creep, bug, deviation from spec | Deviation template |
| ~~Starting work~~ | Never | Status change says it |

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
- [ ] Health changes (on_track → at_risk → off_track)
- [ ] A batch of sibling issues completes

```
create_project_update({ projectId, health: "at_risk", body: "..." })
// verify tool name at runtime; fallback: save_comment on flagship issue
```

---

## End-of-Plan Offer

After any multi-step plan, close with:

> **Translate to Linear?**
> - **Start working** — create issues, assign, move first to In Progress, begin
> - **Archive for team** — create in Backlog, unassigned
> - **Neither**

See [PLAN-TO-LINEAR.md](PLAN-TO-LINEAR.md) for translation rules.

---

## Top Tool Calls

```
// Find issues
list_issues(filter: { team: { key: { eq: "ENG" } }, query: "keyword" })

// My queue
list_issues(filter: { assignee: { isMe: { eq: true } }, state: { type: { in: ["started","unstarted"] } } })

// Get a specific issue (always re-read; don't use memory)
get_issue(id: "ENG-123")

// Discover team workflow states
list_issue_statuses(filter: { team: { id: { eq: teamId } } })

// Discover labels before using any
list_issue_labels(filter: { team: { id: { eq: teamId } } })

// Discover current cycle
list_cycles(filter: { team: { id: { eq: teamId } }, isActive: { eq: true } })

// Create/update issue (save handles both)
save_issue({ teamId, projectId, title, description, labelIds, priority, estimate, cycleId, stateId, parentId })
save_issue({ id: "ENG-123", stateId: inProgressId })
save_issue({ id: "ENG-123", relations: [{ type: "blocked_by", relatedIssueId: "ENG-456" }] })

// Comment
save_comment({ issueId: "ENG-123", body: "..." })
```

**Note:** Tools appear namespaced in-session (e.g., `mcp__linear__save_issue`). Check the actual tool list for the correct prefix.

---

## Priority Reference

| Value | Label |
| --- | --- |
| 0 | No priority |
| 1 | Urgent |
| 2 | High |
| 3 | Medium |
| 4 | Low |

---

## Estimate / Priority / Cycle Rule

| Situation | Action |
| --- | --- |
| Field is unset on create or existing issue | Set it |
| Field is already set, no change needed | Leave it |
| Field is already set, reality diverges ≥ ~50% | Offer the change to the user first |
