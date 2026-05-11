# Linear MCP Tools Reference

Intent → tool mapping for the official Linear MCP server. Back to [SKILL.md](../SKILL.md).

> **Primary tools:** `save_issue`, `save_comment`, `save_project` — unified upserts that handle both create and update. Prefer these over any older `create_*`/`update_*` variants if both are available.
>
> **MCP namespace:** In-session, tools are prefixed by the MCP server name — check the session's actual tool list for the correct prefix (e.g., `mcp__linear-wi__save_issue` or `mcp__linear__save_issue`). The names below are the short-form; append the prefix when calling.
>
> **Parameter style:** All tools use flat scalar params — no nested `filter` object. Reference fields (team, project, state, cycle, assignee, labels) accept either a **name or ID**.

---

## Primary Tools (use these first)

| Intent                     | Tool           | Key params                                                                                                                                                                                                                       |
| -------------------------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Create or update an issue  | `save_issue`   | `id` (omit to create), `team`, `title`, `description`, `state`, `assignee`, `project`, `parentId`, `labels`, `priority`, `estimate`, `cycle`, `milestone`, `dueDate`, `blockedBy`, `blocks`, `relatedTo`, `duplicateOf`, `links` |
| Create or update a project | `save_project` | `id` (omit to create), `name`, `addTeams`/`setTeams`, `description`, `state`, `priority`, `startDate`, `targetDate`, `summary`                                                                                                   |
| Add or update a comment    | `save_comment` | `id` (omit to create), `issueId`, `body` (Markdown), `parentId` (for replies)                                                                                                                                                    |

---

## Reading Tools

### Querying lists

| Intent                                             | Tool                  | Key params                                                                                                                                                                               |
| -------------------------------------------------- | --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Find issues by keyword, team, assignee, status     | `list_issues`         | `team`, `assignee` ("me" for self, "null" for unassigned), `state`, `query`, `project`, `label`, `cycle`, `parentId`, `priority`, `createdAt`, `updatedAt`, `limit` (max 250), `orderBy` |
| Find projects                                      | `list_projects`       | `team`, `state`, `query`, `label`, `initiative`, `member`, `limit`                                                                                                                       |
| Find teams in workspace                            | `list_teams`          | —                                                                                                                                                                                        |
| Find workspace members                             | `list_users`          | —                                                                                                                                                                                        |
| Find documents attached to a project or initiative | `list_documents`      | `projectId`, `initiativeId`, `query`, `creatorId`, `limit`                                                                                                                               |
| Find active / upcoming cycles                      | `list_cycles`         | `teamId` (required), `type`: `current` \| `previous` \| `next`                                                                                                                           |
| Find comments on an issue                          | `list_comments`       | `issueId` or nested filters                                                                                                                                                              |
| Find all labels in a team                          | `list_issue_labels`   | `team`, `name` — **call before writing any label**                                                                                                                                       |
| Find all workflow states for a team                | `list_issue_statuses` | `team` (required) — **call before setting state**                                                                                                                                        |
| Find project-level labels                          | `list_project_labels` | `projectId`                                                                                                                                                                              |
| Find milestones for a project                      | `list_milestones`     | `project` (required — name, ID, or slug)                                                                                                                                                 |
| Find initiatives in workspace                      | `list_initiatives`    | `owner`, `status`, `query`, `parentInitiative`, `limit`                                                                                                                                  |

### Reading a single object

| Intent                                                      | Tool                 | Required param                                                                                                          |
| ----------------------------------------------------------- | -------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Read full issue (description, relations, sub-issues, state) | `get_issue`          | `id` — always re-read; never rely on memory. Pass `includeRelations: true` to include blocking/related/duplicate links. |
| Read full project detail                                    | `get_project`        | `id`                                                                                                                    |
| Read team detail                                            | `get_team`           | `id`                                                                                                                    |
| Read user profile                                           | `get_user`           | `id`                                                                                                                    |
| Read a document's full content                              | `get_document`       | `id`                                                                                                                    |
| Read the definition of a workflow state                     | `get_issue_status`   | `id`                                                                                                                    |
| Read a milestone                                            | `get_milestone`      | `id`                                                                                                                    |
| Read an initiative                                          | `get_initiative`     | `id`                                                                                                                    |
| List project / initiative status updates                    | `get_status_updates` | `project` or `initiative` (name/ID); pass `type: "initiative"` for initiatives                                          |

### Knowledge search

| Intent                                    | Tool                   | Key params |
| ----------------------------------------- | ---------------------- | ---------- |
| Search Linear help docs and API reference | `search_documentation` | `query`    |

---

## Write Tools (beyond the primary `save_*`)

| Intent                             | Tool                   | Key params                                                                         |
| ---------------------------------- | ---------------------- | ---------------------------------------------------------------------------------- |
| Post a project status update       | `save_status_update`   | `project` (name/ID), `health` (`onTrack`/`atRisk`/`offTrack`), `body` (Markdown)   |
| Post an initiative status update   | `save_status_update`   | `initiative` (name/ID), `type: "initiative"`, `health`, `body`                     |
| Create or update a milestone       | `save_milestone`       | `project` (required), `name` (required when creating), `targetDate`, `description` |
| Create or update an initiative     | `save_initiative`      | `name` (required when creating), `description`, `owner`, `status`, `targetDate`    |
| Create a new document              | `create_document`      | `title` (required), `project` or `issue` (name/ID), `content` (Markdown)           |
| Update an existing document        | `update_document`      | `id` (required), `title`, `content`                                                |
| Create a new label for a team      | `create_issue_label`   | — **only after `list_issue_labels` confirms gap and user confirms**                |
| Delete a comment                   | `delete_comment`       | `id`                                                                               |
| Delete a status update             | `delete_status_update` | `id`                                                                               |
| Add an attachment/link to an issue | `create_attachment`    | `issueId`, `url`, `title`                                                          |
| Read an attachment                 | `get_attachment`       | `id`                                                                               |
| Delete an attachment               | `delete_attachment`    | `id`                                                                               |
| Extract images from content        | `extract_images`       | `url`                                                                              |

---

## Common Call Patterns

### Start-of-task (full sequence)

Use **Session Start** from [SKILL.md](../SKILL.md): read `.agents/use-linear/context.yaml`, capture git hints, then `list_issues({ assignee: "me", state: "started" })`; call the `list_*` tools below **only to fill gaps** before `save_issue`.

```
list_teams()                              → only if team unknown from context.yaml
list_projects({ team })                   → only if project unknown from context.yaml
list_issue_labels({ team })               → only if labels unknown from context.yaml
list_cycles({ teamId, type: "current" })  → only if cycle unknown from context.yaml
// Draft → user confirms →
save_issue({ team, project, title, description, labels, priority, estimate, cycle })
// → returns issueId

get_issue(issueId)                        → read current state
// If already In Progress or further, skip. Otherwise:
list_issue_statuses({ team })             → only if In Progress name unknown from context.yaml
save_issue({ id: issueId, state: "In Progress" })
```

### Create sub-issue

```
save_issue({ team, project, parentId: parentIssueId, title, estimate, cycle })
```

### Set relations

```
save_issue({ id: issueId, blockedBy: ["ENG-456"] })          // this issue is blocked by ENG-456
save_issue({ id: issueId, blocks: ["ENG-789"] })             // this issue blocks ENG-789
save_issue({ id: issueId, relatedTo: ["ENG-100"] })          // contextually related
// Remove a relation:
save_issue({ id: issueId, removeBlockedBy: ["ENG-456"] })
```

### Progress / Blocker / Finding comment

```
save_comment({ issueId, body: "Redis module merged (ENG-790). Rate limiter now unblocked." })   // Progress
save_comment({ issueId, body: "**Blocked**: Needs token format from auth team (ENG-456) before proceeding." })   // Blocker
save_comment({ issueId, body: "**Deviation**: ...\n**Why**: ...\n**Impact**: ...\n**Decision needed**: ..." })  // Finding
```

### Project status update

```
save_status_update({ project: "Infrastructure Hardening Q2", health: "atRisk", body: "..." })
save_status_update({ initiative: "Platform Reliability", type: "initiative", health: "onTrack", body: "..." })
```

### Handoff

```
get_issue(issueId)                    → check current state; skip if already In Review+
list_issue_statuses({ team })         → find In Review state
save_issue({ id: issueId, state: "In Review" })
save_comment({ issueId, body: "PR #N: <link>. Landed: ... Deferred: ... Follow-ups: ENG-###" })
```

### Queue check ("what's on my plate")

```
list_issues({ assignee: "me", state: "started" })    // in progress
list_issues({ assignee: "me", state: "unstarted" })  // todo / backlog assigned to me
```

---

## Priority Values

| Value | Meaning (issues) | Meaning (projects) |
| ----- | ---------------- | ------------------ |
| `0`   | No priority      | No priority        |
| `1`   | Urgent           | Urgent             |
| `2`   | High             | High               |
| `3`   | Normal           | Medium             |
| `4`   | Low              | Low                |

---

## Relation Fields on `save_issue`

| Field         | Meaning                                         | Remove with       |
| ------------- | ----------------------------------------------- | ----------------- |
| `blocks`      | This issue blocks the listed issues             | `removeBlocks`    |
| `blockedBy`   | This issue is blocked by the listed issues      | `removeBlockedBy` |
| `relatedTo`   | Contextually related, no ordering constraint    | `removeRelatedTo` |
| `duplicateOf` | Duplicate of a single issue (string, not array) | pass `null`       |

All fields are append-only by default — existing relations are never removed unless you use the corresponding `remove*` field.
