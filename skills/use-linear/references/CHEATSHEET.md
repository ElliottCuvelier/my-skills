# Cheatsheet

One-screen quick reference. Keep this open while working. Back to [SKILL.md](../SKILL.md).

---

## Task-Start Checklist

Before writing a single line of code:

- [ ] **Search** — `list_issues(filter: { query: "..." })` — is there already an issue?
- [ ] **Draft + confirm** — title, description, team, project, labels (from `list_issue_labels`), priority, estimate, cycle (from `list_cycles`)
- [ ] **Create** — `create_issue(...)` after user confirms
- [ ] **Move state** — `list_issue_statuses` → discover In Progress ID → `update_issue({ stateId })`
- [ ] **Surface spec** — create or link a Linear Document if a written spec will be referenced

---

## State Transition Checklist

| Moment | Action |
| --- | --- |
| Task starts | `update_issue` → In Progress (discovered, not hard-coded) |
| PR opened | `update_issue` → In Review (discovered) |
| PR merged | `update_issue` → Done (discovered) — only if no further work |
| Blocked | Set `blocked_by` relation; update priority if urgency changed |

---

## PR / Commit Checklist

- [ ] Every commit on branch has `Linear: ENG-###` in the message
- [ ] PR body has `Linear: ENG-###` appended (or fills an existing template slot — check first)
- [ ] Branch name is **not** changed
- [ ] Final `create_comment` summarizes what landed vs. deferred

---

## Project Update Checklist

Post when (event-driven, not on cadence):

- [ ] A milestone lands
- [ ] A blocker surfaces
- [ ] Scope or timeline materially shifts
- [ ] Project health changes (on_track → at_risk → off_track)
- [ ] A batch of sibling issues completes

```
create_project_update(projectId, health, body)
// health: "on_track" | "at_risk" | "off_track"  (verify enum at runtime)
// body: health state + what moved + what's next + decisions needed
```

---

## Top Tool Calls

```
// Find issues
list_issues(filter: { team: { key: { eq: "ENG" } }, query: "keyword" })

// Get a specific issue
get_issue(id: "ENG-123")

// Discover team workflow states
list_issue_statuses(filter: { team: { id: { eq: teamId } } })

// Discover labels before using any
list_issue_labels(filter: { team: { id: { eq: teamId } } })

// Discover current cycle
list_cycles(filter: { team: { id: { eq: teamId } }, isActive: { eq: true } })

// Create issue (after user confirms draft)
create_issue({ teamId, projectId, title, description,
               labelIds, priority, estimate, cycleId, stateId, parentId })

// Update state / relations / estimate
update_issue({ id, stateId })
update_issue({ id, relations: [{ type: "blocks", relatedIssueId }] })
update_issue({ id, estimate: 5, priority: 2 })

// Deviation comment
create_comment({ issueId, body: "**Deviation**: ...\n**Why**: ...\n**Impact**: ...\n**Decision needed**: ..." })

// Project update (verify tool name at runtime)
create_project_update({ projectId, health: "at_risk", body: "..." })
```

---

## Deviation Materiality — Quick Test

"If I described this change to the issue author, would they need to know to update their expectations?"

```
User-visible behavior changed?   → Comment
API shape / contract changed?    → Comment
Scope grew or shrank?            → Comment + possibly project update
Hard blocker discovered?         → Comment + project update if timeline affected
Internal refactor only?          → No comment needed
Library choice (same interface)? → No comment needed
```

---

## Decision Trees (Compact)

### Need a Linear issue?

```
Linear MCP present + task is non-trivial?
└── Yes → search first → found? use it : draft + confirm + create
```

### Sub-issue or new issue?

```
Direct component of parent? → Sub-issue (parentId)
Blocks the parent?          → New issue + blocks relation
Same area, no order?        → New issue + related relation
Done in <5 min inline?      → No tracking needed
```

### Comment or Document?

```
Moment in timeline (deviation, PR link)?  → Comment
Durable knowledge (spec, ADR, runbook)?   → Document
"What this issue is about"?               → Issue description
```

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

## Relation Types

| Type | Meaning |
| --- | --- |
| `blocks` | This issue blocks the related issue |
| `blocked_by` | This issue is blocked by the related issue |
| `related` | Same area, no ordering constraint |
| `duplicate` | Duplicate of the related issue |
