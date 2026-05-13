# Linear Hierarchy Reference

How Linear's objects relate to each other, when to use each level, and when to promote. Back to [SKILL.md](../SKILL.md).

---

## The Full Model

```
Workspace
└── Team  (owns issues, projects, labels, cycles, workflow states)
    │
    ├── Initiative  (strategy-level grouping; quarter / half-year scope)
    │   └── Project  (multi-issue deliverable with a ship date)
    │       ├── Project Updates  (health posts: onTrack / atRisk / offTrack)
    │       ├── Project Milestones  (named progress gates)
    │       └── Issue  (unit of tracked work)
    │           ├── Sub-issue  (Issue with parentId set — same fields, same API)
    │           │   └── Sub-sub-issue  (avoid more than 2 levels deep)
    │           ├── Comments  (timeline events: deviations, progress notes, PR links)
    │           └── Relations  (blocks / blocked_by / related / duplicate)
    │
    ├── Cycle  (time-boxed sprint; orthogonal to project hierarchy)
    │   └── Issues are assigned to cycles; they still belong to a project
    │
    └── Document  (durable knowledge; attached to a Project or Issue)
```

---

## Level-by-Level Guide

### Workspace

One Linear workspace per organization. You do not create workspaces via MCP. Discover teams with `list_teams`.

### Team

The primary ownership boundary. Issues, labels, cycles, and workflow states are all scoped to a team. Always resolve `teamId` before creating anything.

### Initiative

- **Scope:** Multi-project; quarter/half-year strategic bet.
- **Name:** Descriptive of the strategic theme (e.g., `Platform Observability`, `User Sessions`). No `Wave X`, `Phase Y`, or coded prefixes.
- **Create when:** Multiple projects share a strategic theme and stakeholders need a single place to track progress across all of them.
- **Skip when:** You have a single project or the grouping is just for convenience. Projects can stand alone.
- **MCP:** `list_initiatives`, `get_initiative`, `save_initiative` (confirm before creating). See [TOOLS.md](TOOLS.md).

### Project

- **Scope:** Multi-issue deliverable with a defined end state and usually a ship date.
- **Name:** Descriptive of scope (e.g., `Infrastructure Hardening Q2`, `Platform Reliability`). Do not prefix with `Wave`, `Phase`, or coded identifiers — use plain language.
- **Create when:** Work spans ≥ 3 issues and has a shared deliverable.
- **If an issue is orphan:** call `list_projects` and find one whose scope matches the work. If a clear fit exists, attach it. If the work is genuinely self-isolated (one-off fix, no initiative), leave it project-less — don't force-assign a bad-fit project.
- **MCP:** `list_projects`, `save_project` (confirm first).

### Milestone

- **Scope:** A named progress gate within a project; marks a meaningful ship checkpoint.
- **Naming:** Use an `M<N>` prefix for ordering clarity, followed by a short descriptive name: `M1 Foundation`, `M2 Public Beta`, `M3 GA`. The `M<N>` prefix is the only coded identifier permitted at the project level — it directly serves readability rather than retroactive grouping.
- **Create when:** A project spans multiple meaningful checkpoints that stakeholders need to track independently.
- **MCP:** `save_milestone` (pass `project` name/ID, `name`; confirm before creating).

### Issue

- **Scope:** A single unit of trackable work. The fundamental object.
- **A good issue has:** action-oriented title, acceptance criteria in description, estimate, priority, cycle assignment, correct state, and at least one label.
- **MCP:** `save_issue` (create or update), `get_issue`, `list_issues`.

### Sub-issue (Issue with `parentId`)

- **Scope:** A component of a parent issue; tracked independently.
- **Create when:**
  - Subtask is ≥ ~30 min and benefits from independent tracking
  - Subtask is owned by a different team member or layer
  - Subtask can be merged separately (e.g., a database migration before the feature)
  - Parent issue would otherwise be impossible to mark Done until all components are shipped
- **Skip when:**
  - Work is <15 min and inline to the parent PR
  - It would only exist for a few hours (just do it and don't track it)
- **Depth:** Aim for max 2 levels (issue → sub-issue). A sub-sub-issue that has sub-sub-sub-issues is a sign the parent issue is too large and should be promoted to a project.
- **MCP:** Same as Issue — `save_issue` with `parentId`.

### Document

- **Scope:** Durable knowledge attached to a project or issue.
- **Not a comment.** A comment is ephemeral and timeline-ordered. A document is searchable, updateable, and authoritative.
- **MCP:** `list_documents`, `get_document`, `create_document`, `update_document`.
- See [DOCUMENTS.md](DOCUMENTS.md) for shapes and the read-before-write protocol.

### Cycle

- **Scope:** Time-boxed sprint-style commitment. Orthogonal to project hierarchy — an issue belongs to a project AND a cycle.
- **Assign on create** if the team uses cycles. Discover via `list_cycles({ teamId, type: "current" })` or `type: "next"`.
- **Do not invent cycles.** Only assign to existing cycles.

### Project Update

- **Scope:** A health post on a Project; visible to all stakeholders.
- **Post at:** milestone landings, blocker discoveries, health changes, scope/timeline shifts, sibling-issue batch completions.
- **Do not post on cadence.** Event-driven only.
- **MCP:** `save_status_update` (pass `project` name/ID, `health`: `onTrack`/`atRisk`/`offTrack`, `body`).

### Comment

- **Scope:** Ephemeral timeline entry on an issue.
- **Use for:** deviation notes, PR links, status summaries, questions that need answers.
- **Do not use for:** durable specs, decision records, runbooks — those belong in Documents.

---

## Promotion Rules

### Sub-issue → Issue

Promote (set `parentId` to null, or create standalone) when:
- The subtask grows beyond ~40% of the parent's original scope
- It becomes relevant to a different project or team
- It needs its own cycle assignment separate from the parent

### Issue → Project

Create a new project (confirm first) when:
- Work expands to ≥ 3 issues with a shared deliverable
- A "quick fix" snowballs into a multi-sprint effort
- A stakeholder needs to track progress at a higher level than individual issues

### Project → Initiative

Create an initiative (confirm first) when:
- Multiple projects are interconnected and share a strategic goal
- A roadmap item spans teams and needs a single narrative

---

## Common Mistakes

| Mistake | Symptom | Fix |
| --- | --- | --- |
| Issue in wrong project | Issue completed but project doesn't reflect it | `save_issue({ id, project: correctProject })` before starting |
| Sub-issue nesting > 2 levels | Impossible to navigate; hard to assign | Flatten: promote inner sub-issues to top-level issues with relations |
| Cycle omitted on create | Issue floats with no sprint ownership | Always `list_cycles` and assign on create when team uses cycles |
| Project missing target date | Project update health has no timeline context | Set `targetDate` on `save_project` |
| Initiative created for a single project | Over-engineering; nobody maintains it | Projects can stand alone; initiatives are for multi-project themes |
| Wave / Phase / Group prefix on titles | "Wave 2 Auth", "Phase 3 Deploy" — becomes stale; obscures meaning | Use plain descriptive titles; Linear's canonical IDs are auto-assigned |
| Coding labels as temporary groupings | `wave-1`, `sprint-3` labels fragment taxonomy and expire | Labels are durable taxonomy only: type (`feature`, `bug`, …) or service/domain (`api`, `web-client`, …) |
