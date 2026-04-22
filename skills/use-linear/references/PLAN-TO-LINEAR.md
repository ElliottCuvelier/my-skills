# Translating Plans to Linear

How to convert a multi-step plan into Linear issues at the end of planning. Back to [SKILL.md](../SKILL.md).

---

## The Offer

After producing any multi-step plan or structured proposal, close with:

> **Translate to Linear?**
> - **Start working** — I'll create the issues (with sub-issues and `blockedBy` links), assign to you, move the first one to In Progress, and begin.
> - **Archive for team** — I'll create the issues in Backlog under the right project so the team can pick them up. Nothing gets assigned or started.
> - **Neither** — keep the plan local to this conversation.

Present this every time, even for small plans. The user decides; the agent doesn't assume.

---

## Translation Rules

### Structure

| Plan element | Linear object |
| --- | --- |
| Top-level section / distinct deliverable | Issue |
| Piece within a section (same deliverable, shipped together) | Sub-issue (`parentId`) |
| Sequenced step that must land before the next can start | `blockedBy` relation between sibling issues |
| Parallel work in the same area, no ordering constraint | `related` relation |

### Descriptions

- Copy from the plan — short, action-oriented
- Do **not** copy the full rationale or design discussion — that belongs in a Linear Document
- Acceptance criteria if the plan included them

### Assignment and state

| Mode | Assignee | Initial state |
| --- | --- | --- |
| Start working | Authenticated user (API key owner) | First issue → In Progress; rest → Backlog |
| Archive for team | Unassigned | All → Backlog |

### Project and team

- Use `list_projects` to find a project whose scope fits
- If none fits and the work is self-isolated, create issues project-less
- If the plan implies a new project-scale initiative, offer to `save_project` first (confirm separately)
- Always resolve `teamId` via `list_teams` before creating

### Labels, estimates, cycles

- Labels: `list_issue_labels` first; pick existing labels that fit
- Estimate: set on each issue if the team uses estimates
- Cycle: assign to the active cycle (`list_cycles`) if the team uses cycles

### Confirm once, not per issue

Present the full proposed structure (all issues with their sub-issues and relations) for the user to review before calling `save_issue` on any of them. One confirmation covers the batch — don't prompt issue-by-issue.

---

## Worked Example

**Plan produced:**

```
## Phase 1: Database
- Add sessions table migration
- Add index on user_id

## Phase 2: API
- POST /sessions endpoint
- DELETE /sessions/:id endpoint

## Phase 3: Frontend
- Session list component
- Logout flow
```

**Proposed Linear structure (presented to user):**

```
Issue: Implement user sessions feature
  Sub-issue: Add sessions table migration        (Phase 1a)
  Sub-issue: Add index on user_id               (Phase 1b)
  Sub-issue: POST /sessions endpoint            (Phase 2a) — blockedBy Phase 1
  Sub-issue: DELETE /sessions/:id endpoint      (Phase 2b) — blockedBy Phase 1
  Sub-issue: Session list component             (Phase 3a) — blockedBy Phase 2a
  Sub-issue: Logout flow                        (Phase 3b) — blockedBy Phase 2a
```

**On "Start working":**

```
save_issue({ teamId, projectId, title: "Implement user sessions feature", ... })     // → ENG-100 (parent)
save_issue({ parentId: "ENG-100", title: "Add sessions table migration", ... })      // → ENG-101
save_issue({ parentId: "ENG-100", title: "Add index on user_id", ... })              // → ENG-102
save_issue({ parentId: "ENG-100", title: "POST /sessions endpoint", ... })           // → ENG-103
save_issue({ id: "ENG-103", relations: [{ type: "blocked_by", relatedIssueId: "ENG-101" }] })
save_issue({ parentId: "ENG-100", title: "DELETE /sessions/:id endpoint", ... })     // → ENG-104
save_issue({ id: "ENG-104", relations: [{ type: "blocked_by", relatedIssueId: "ENG-101" }] })
save_issue({ parentId: "ENG-100", title: "Session list component", ... })            // → ENG-105
save_issue({ id: "ENG-105", relations: [{ type: "blocked_by", relatedIssueId: "ENG-103" }] })
save_issue({ parentId: "ENG-100", title: "Logout flow", ... })                       // → ENG-106
save_issue({ id: "ENG-106", relations: [{ type: "blocked_by", relatedIssueId: "ENG-103" }] })

// Move first issue to In Progress
get_issue("ENG-101")    // check state
save_issue({ id: "ENG-101", stateId: inProgressId, assigneeId: viewerUserId })
```

---

## Edge Cases

**Plan has only one step.** A single issue with no sub-issues. Still offer — the user may want it in Backlog for the team.

**Plan is already partially in Linear.** Some sections map to existing issues. For those, skip `save_issue` and just add the new sub-issues or relations under the existing issue.

**Plan implies a new project.** Offer `save_project` as part of the structure confirmation — don't create it silently. The user may have an existing project it should live under.

**"Archive" and then "Start working" later.** When the user eventually picks up an archived issue, follow the normal protocol — `get_issue`, move to In Progress, proceed. The archive step is complete; no re-creation needed.

**User wants to translate only part of the plan.** Let them say which sections. Translate only those.
