# Linear MCP Tools Reference

Intent → tool mapping for the official Linear MCP server. Back to [SKILL.md](../SKILL.md).

> **Primary tools:** `save_issue`, `save_comment`, `save_project` — unified upserts that handle both create and update. Prefer these over any older `create_*`/`update_*` variants if both are available.
>
> **MCP namespace:** In-session, tools are prefixed by the MCP server name (e.g., `mcp__linear__save_issue`). Check your session's actual tool list — the prefix varies by client configuration. The names below are the short-form; append the prefix when calling.
>
> **Runtime-discovery rule:** The tool surface evolves. Confirm a tool exists in your session before calling it. If a newer equivalent is available, prefer it.

---

## Primary Tools (use these first)

| Intent | Tool | Key params |
| --- | --- | --- |
| Create or update an issue | `save_issue` | `id` (omit to create), `teamId`, `title`, `description`, `stateId`, `assigneeId`, `projectId`, `parentId`, `labelIds`, `priority`, `estimate`, `cycleId`, `relations` |
| Create or update a project | `save_project` | `id` (omit to create), `teamId`, `name`, `description`, `targetDate`, `statusId` |
| Add or update a comment | `save_comment` | `id` (omit to create), `issueId`, `body` (Markdown) |

---

## Reading Tools (confirmed)

### Querying lists

| Intent | Tool | Key filters / params |
| --- | --- | --- |
| Find issues by keyword, team, assignee, status | `list_issues` | `filter.team.key`, `filter.assignee.id`, `filter.assignee.isMe`, `filter.state.type`, `query` |
| Find projects | `list_projects` | `filter.team.id`, `filter.state` |
| Find teams in workspace | `list_teams` | — |
| Find workspace members | `list_users` | — |
| Find documents attached to a project | `list_documents` | `filter.project.id` |
| Find active and upcoming cycles | `list_cycles` | `filter.team.id`, `filter.isActive`, `filter.isNext` |
| Find comments on an issue | `list_comments` | `filter.issue.id` |
| Find all labels in a team | `list_issue_labels` | `filter.team.id` — **call before writing any label** |
| Find all workflow states for a team | `list_issue_statuses` | `filter.team.id` — **call before setting state** |
| Find all project-level labels | `list_project_labels` | `filter.project.id` |

### Reading a single object

| Intent | Tool | Required param |
| --- | --- | --- |
| Read full issue (description, relations, sub-issues, state) | `get_issue` | `id` — always re-read; never rely on memory |
| Read full project detail | `get_project` | `id` |
| Read team detail | `get_team` | `id` |
| Read user profile | `get_user` | `id` |
| Read a document's full content | `get_document` | `id` |
| Read the definition of a workflow state | `get_issue_status` | `id` |

### Knowledge search

| Intent | Tool | Key params |
| --- | --- | --- |
| Search Linear help docs and API reference | `search_documentation` | `query` |

---

## Creating (legacy / also available)

The `save_*` tools are preferred. If `save_issue` is unavailable, fall back to:

| Intent | Legacy tool |
| --- | --- |
| Create an issue | `create_issue` |
| Update an issue | `update_issue` |
| Create a comment | `create_comment` |
| Create a project | `create_project` |
| Update a project | `update_project` |
| Create a new label for a team | `create_issue_label` — **only after `list_issue_labels` confirms gap and user confirms** |

---

## Tentative / Runtime-Verify (2026-era tools)

Announced in Linear's February 2026 changelog. Verify exact names at runtime before calling.

| Intent | Likely tool name |
| --- | --- |
| Create an initiative | `create_initiative` |
| Update an initiative | `update_initiative` |
| Post an initiative update | `create_initiative_update` |
| Post a project update | `create_project_update` — use `health`: `on_track` / `at_risk` / `off_track` |
| Create a project milestone | `create_project_milestone` |
| Manage project labels | `create_project_label` / `update_project_label` |

Fallback if `create_project_update` is unavailable: `save_comment` on the project's flagship issue.

---

## Common Call Patterns

### Start-of-task (full sequence)

```
list_teams()                          → pick teamId
list_projects({ teamId })             → pick projectId
list_issue_labels({ teamId })         → pick existing labelIds
list_cycles({ teamId, isActive })     → pick cycleId
// Draft → user confirms →
save_issue({ teamId, projectId, title, description, labelIds, priority, estimate, cycleId })
// → returns issueId

get_issue(issueId)                    → read current stateId
// If already In Progress or further, skip. Otherwise:
list_issue_statuses({ teamId })       → find In Progress stateId
save_issue({ id: issueId, stateId: inProgressId })
```

### Create sub-issue

```
save_issue({ teamId, projectId, parentId: parentIssueId, title, estimate, cycleId })
```

### Set a relation

```
save_issue({ id: issueId, relations: [{ type: "blocks", relatedIssueId: "<id>" }] })
```

### Progress / Blocker / Finding comment

```
save_comment({ issueId, body: "Redis module merged (ENG-790). Rate limiter now unblocked." })   // Progress
save_comment({ issueId, body: "**Blocked**: Needs token format from auth team (ENG-456) before proceeding." })   // Blocker
save_comment({ issueId, body: "**Deviation**: ...\n**Why**: ...\n**Impact**: ...\n**Decision needed**: ..." })  // Finding
```

### Handoff

```
get_issue(issueId)                    → check current state; skip if already In Review+
list_issue_statuses({ teamId })       → find In Review stateId
save_issue({ id: issueId, stateId: inReviewId })
save_comment({ issueId, body: "PR #N: <link>. Landed: ... Deferred: ... Follow-ups: ENG-###" })
```

### Queue check ("what's on my plate")

```
list_issues({
  filter: {
    assignee: { isMe: { eq: true } },
    state: { type: { in: ["started", "unstarted"] } }
  }
})
```

### Project update

```
create_project_update({ projectId, health: "at_risk", body: "..." })
// verify tool name at runtime; fallback: save_comment on flagship issue
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

Pass as `relations: [{ type: "blocks", relatedIssueId: "<id>" }]` in `save_issue`.
