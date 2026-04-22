# Linear MCP Tools Reference

Intent → tool mapping for the official Linear MCP server. Back to [SKILL.md](../SKILL.md).

> **Runtime-discovery rule:** The tool surface evolves. Before acting, confirm the tool is available in your current session's MCP tool list. If a newer or unified tool exists (e.g., `save_issue` replacing `create_issue`/`update_issue`), prefer the one the server advertises. The names below are correct as of early 2026 — treat them as a stable baseline, not a guarantee.

---

## Confirmed Tools (23)

### Querying

| Intent | Tool | Key filters / params |
| --- | --- | --- |
| Find issues by keyword, team, assignee, status | `list_issues` | `filter.team.key`, `filter.assignee.id`, `filter.state.type`, `query` |
| Find projects | `list_projects` | `filter.team.id`, `filter.state` |
| Find teams in workspace | `list_teams` | — |
| Find workspace members | `list_users` | — |
| Find documents attached to a project | `list_documents` | `filter.project.id` |
| Find active and upcoming cycles | `list_cycles` | `filter.team.id`, `filter.isActive`, `filter.isNext` |
| Find comments on an issue | `list_comments` | `filter.issue.id` |
| Find all labels in a team | `list_issue_labels` | `filter.team.id` — **call this before ever writing a label** |
| Find all workflow states for a team | `list_issue_statuses` | `filter.team.id` — **call this before setting state** |
| Find all project-level labels | `list_project_labels` | `filter.project.id` |

### Reading a single object

| Intent | Tool | Required param |
| --- | --- | --- |
| Read full issue detail (description, relations, sub-issues, state) | `get_issue` | `id` (e.g., `"ENG-123"` or the UUID) |
| Read full project detail | `get_project` | `id` |
| Read team detail | `get_team` | `id` |
| Read user profile | `get_user` | `id` |
| Read a document's full content | `get_document` | `id` |
| Read the definition of a workflow state | `get_issue_status` | `id` |

### Creating

| Intent | Tool | Key params |
| --- | --- | --- |
| Create an issue (or sub-issue) | `create_issue` | `teamId`, `title`, `description`, `projectId`, `parentId` (sub-issue), `labelIds`, `priority`, `estimate`, `cycleId`, `stateId` |
| Create a project | `create_project` | `teamId`, `name`, `description`, `targetDate`, `statusId` |
| Add a comment to an issue | `create_comment` | `issueId`, `body` (Markdown supported) |
| Create a new label for a team | `create_issue_label` | `teamId`, `name`, `color` — **only after `list_issue_labels` confirms gap and user confirms** |

### Updating

| Intent | Tool | Key params |
| --- | --- | --- |
| Update any issue field (state, assignee, estimate, priority, cycle, relations, parent) | `update_issue` | `id`, then any subset of: `stateId`, `assigneeId`, `estimate`, `priority`, `cycleId`, `labelIds`, `parentId`, `relations` |
| Update a project (name, state, target date) | `update_project` | `id`, then any subset of fields |

### Knowledge / Search

| Intent | Tool | Key params |
| --- | --- | --- |
| Search Linear help docs and API reference | `search_documentation` | `query` |

---

## Tentative / Runtime-Verify (2026-era tools)

These tools were announced in Linear's February 2026 changelog. Exact names and parameters are **not confirmed** — verify at runtime against your session's MCP tool list before calling.

| Intent | Likely tool name | Notes |
| --- | --- | --- |
| Create an initiative | `create_initiative` | Groups multiple projects at strategy level |
| Update an initiative | `update_initiative` | — |
| Post an initiative update | `create_initiative_update` | Health state + narrative |
| Post a project update | `create_project_update` | Health (`on_track` / `at_risk` / `off_track`) + body |
| Create a project milestone | `create_project_milestone` | Named gate within a project |
| Update a project milestone | `update_project_milestone` | — |
| Manage project labels | `create_project_label` / `update_project_label` | Separate from issue labels |

If `create_project_update` is unavailable, fall back to a `create_comment` on the project's flagship issue.

---

## Common Call Patterns

### Start-of-task pattern

```
// 1. Discover the team
list_teams() → pick team → teamId

// 2. Discover the project
list_projects(filter: { team: { id: { eq: teamId } } }) → pick project → projectId

// 3. Discover labels
list_issue_labels(filter: { team: { id: { eq: teamId } } }) → pick from existing

// 4. Discover cycles
list_cycles(filter: { team: { id: { eq: teamId } }, isActive: { eq: true } }) → cycleId

// 5. Draft + confirm → create
create_issue({ teamId, projectId, title, description, labelIds, priority, estimate, cycleId })

// 6. Discover states
list_issue_statuses(filter: { team: { id: { eq: teamId } } }) → in-progress state → stateId

// 7. Move to In Progress
update_issue({ id: issueId, stateId: inProgressStateId })
```

### Deviation comment

```
create_comment({
  issueId: "ENG-123",
  body: "**Deviation**: ...\n**Why**: ...\n**Impact**: ...\n**Decision needed**: ..."
})
```

### Project update (runtime-discovered)

```
create_project_update({
  projectId: "<project-id>",
  health: "at_risk",
  body: "Blocker discovered: ... | What's next: ... | Decision needed from: ..."
})
```

### Handoff

```
// 1. Discover In Review state
list_issue_statuses(filter: { team: { id: { eq: teamId } } }) → in-review state

// 2. Move issue
update_issue({ id: issueId, stateId: inReviewStateId })

// 3. Final comment
create_comment({ issueId, body: "PR #N open: <link>. Landed: ... Deferred: ..." })
```

---

## Priority Values

| Value | Meaning |
| --- | --- |
| `0` | No priority |
| `1` | Urgent |
| `2` | High |
| `3` | Medium |
| `4` | Low |

---

## Relation Types

| Type | Meaning |
| --- | --- |
| `blocks` | This issue blocks the related issue |
| `blocked_by` | This issue is blocked by the related issue |
| `related` | Contextually related, no ordering constraint |
| `duplicate` | Duplicate of the related issue |

Pass as `relations: [{ type: "blocks", relatedIssueId: "<id>" }]` in `update_issue`.
