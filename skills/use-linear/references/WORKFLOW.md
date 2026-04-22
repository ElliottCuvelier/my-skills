# Workflow Reference

Full expansion of the parallel-progress protocol from [SKILL.md](../SKILL.md). Read when starting a task or verifying the protocol applies correctly.

---

## The Protocol in Full

### (a) At task start

**1. Search first.**

```
list_issues (
  filter: { team: { key: { eq: "ENG" } }, query: "auth token refresh" },
  first: 10
)
```

If the user provided an issue ID directly, skip the search:

```
get_issue(id: "ENG-123")
```

**2. Draft and confirm before creating.**

If no match is found and the task is non-trivial, build a draft and present it to the user before calling `create_issue`. The draft should include:

- **Title** — action-oriented, ≤60 chars (e.g., "Fix token refresh race condition in AuthService")
- **Description** — what needs to happen and why; acceptance criteria if applicable
- **Team** — resolved via `list_teams`
- **Project** — resolved via `list_projects`; every non-trivial issue belongs to a project
- **Labels** — resolved via `list_issue_labels`; never invented
- **Priority** — 0 (no priority), 1 (urgent), 2 (high), 3 (medium), 4 (low)
- **Estimate** — always set (story points or t-shirt size depending on team convention; check existing issues for scale)
- **Cycle** — always assign if the team uses cycles; resolved via `list_cycles` (pick the active or upcoming cycle)
- **Parent** — if this is a sub-issue of an existing issue, include `parentId`
- **Relations** — if this blocks or is blocked by another issue, include the relation

Wait for the user to confirm before calling `create_issue`.

**3. Move to In Progress.**

```
list_issue_statuses(teamId: "<resolved-team-id>")
// → find the state whose type is "started" or name matches "In Progress" / "In Development" / etc.

update_issue(id: "<issue-id>", stateId: "<in-progress-state-id>")
```

Never hard-code state names or UUIDs. Different teams name their states differently.

**4. Surface or create the spec Document.**

If the task has a written spec or design brief that will be referenced during implementation:

```
// Search for an existing document first
list_documents(filter: { project: { id: { eq: "<project-id>" } } })

// If found, read it
get_document(id: "<doc-id>")

// If not found and a spec exists, create it (confirm first)
create_document(projectId: "<project-id>", title: "Spec: <feature>", content: "...")
```

See [DOCUMENTS.md](DOCUMENTS.md) for document shapes and the read-before-write rule.

---

### (b) While working

**Decompose into sub-issues proactively.**

As soon as you discover a unit of work that is ≥ ~30 min or belongs to a different owner/layer, create it as a sub-issue — don't wait until the parent issue is done:

```
create_issue(
  teamId: "<team-id>",
  projectId: "<project-id>",
  parentId: "<parent-issue-id>",
  title: "Add migration for sessions table",
  description: "...",
  estimate: 2,
  cycleId: "<current-cycle-id>"
)
```

**Set relations when dependencies surface.**

```
update_issue(
  id: "<blocking-issue-id>",
  relations: [{ type: "blocks", relatedIssueId: "<blocked-issue-id>" }]
)
```

Available relation types: `blocks`, `blocked_by`, `related`, `duplicate`.

**Update estimate and priority when scope shifts ≥ ~50%.**

```
update_issue(id: "<issue-id>", estimate: 8, priority: 1)
```

**Post project updates at meaningful checkpoints.**

Checkpoints that warrant a project update:

| Trigger | Example |
| --- | --- |
| Milestone lands | "API endpoints done; starting frontend integration" |
| Blocker discovered | "Blocked on auth team's token format change — ENG-456" |
| Scope / timeline materially shifts | "Discovered we also need to migrate existing sessions — adds ~3 days" |
| Health changes | "Moving from On Track to At Risk due to dependency slip" |
| Batch of sibling issues completes | "Backend sub-issues all merged; entering QA phase" |

```
// Discover the tool name at runtime — it may be create_project_update or similar
// Each update should include: health status, what moved, what's next, decisions needed

create_project_update(
  projectId: "<project-id>",
  health: "at_risk",   // on_track | at_risk | off_track — verify enum values at runtime
  body: "..."
)
```

If `create_project_update` is unavailable, post a summary comment on the project's flagship/parent issue as a fallback. Don't skip the update entirely — stakeholders need signal.

---

### (c) On material deviation

See [DEVIATIONS.md](DEVIATIONS.md) for the full materiality bar and anti-flood rules.

The structured comment template:

```
**Deviation**: <one-line summary — e.g., "Changed API response shape for /auth/refresh">
**Why**: <what new information or constraint made the original plan wrong>
**Impact**: <other issues, API consumers, or scope affected>
**Decision needed**: Yes — <specific question> / No
```

Post via `create_comment(issueId: "<id>", body: "...")`.

If the deviation invalidates a spec Document, update it immediately. A comment alone leaves the Document lying.

---

### (d) At handoff / PR

**1. Move to In Review.**

```
list_issue_statuses(teamId: "<team-id>")
// find the "in_review" or equivalent state

update_issue(id: "<issue-id>", stateId: "<in-review-state-id>")
```

**2. Ensure git artifacts reference the issue.**

Every commit on the branch: `feat(auth): fix token refresh race\n\nLinear: ENG-123`

PR body: append `Linear: ENG-123` at the bottom (or fill the existing slot if the PR template has one). See [GIT.md](GIT.md) for the full append rule and template-preservation examples.

**3. Final summary comment.**

```
create_comment(
  issueId: "<id>",
  body: "PR #42 open for review. What landed: fixed race condition, added retry logic. Deferred: rate-limiting improvement (ENG-456). Follow-up issues created: ENG-457 (add monitoring alert)."
)
```

---

## Worked Example — Feature: Rate Limiter for /api/search

**Scenario:** User says "implement rate limiting on the search endpoint so we don't get hammered". No issue exists.

### Step 1 — Search

```
list_issues(filter: { query: "rate limit search" })
// → no matches
```

### Step 2 — Draft + confirm

Present to user:

```
Proposed issue:
  Title: Add rate limiting to /api/search
  Description: Protect the search endpoint from traffic spikes with a per-user token-bucket limiter.
                Acceptance: 429 returned when limit exceeded; retry-after header included;
                existing tests pass; load test confirms ≥100 rps without false positives.
  Team: ENG
  Project: Infrastructure Hardening Q2
  Labels: [backend, security]
  Priority: 2 (high)
  Estimate: 5 (story points)
  Cycle: Sprint 14
```

User approves → `create_issue(...)` → returns `ENG-789`.

### Step 3 — Move to In Progress

```
list_issue_statuses(teamId: "ENG-team-id")
update_issue(id: "ENG-789", stateId: "<in-progress-id>")
```

### Step 4 — Work begins. Sub-issue discovered.

"Redis is the right limiter backend, but we don't have a Redis module set up." → Sub-issue:

```
create_issue(
  parentId: "ENG-789",
  title: "Add Redis module to infrastructure stack",
  estimate: 3,
  cycleId: "<sprint-14-id>"
)
// → ENG-790
```

Add relation: ENG-789 blocked_by ENG-790.

### Step 5 — Milestone lands → project update

```
create_project_update(
  projectId: "<infra-project-id>",
  health: "on_track",
  body: "Rate limiter sub-task (Redis module, ENG-790) complete and merged.
         ENG-789 now unblocked; implementing token-bucket logic. On track for Sprint 14."
)
```

### Step 6 — Material deviation discovered

While implementing, discover the existing middleware pipeline doesn't support per-route configuration — need to refactor the middleware chain first.

```
create_comment(
  issueId: "ENG-789",
  body: "**Deviation**: Middleware chain refactor required before rate limiter can be injected per-route.
         **Why**: Current pipeline applies middleware globally only; per-route limiter config requires route-level injection.
         **Impact**: Scope grows by ~2 days; ENG-790 milestone already merged so no backtrack needed.
         **Decision needed**: Yes — approve scope extension or descope per-route config to a follow-up issue."
)
```

Project update (health change):

```
create_project_update(
  projectId: "<infra-project-id>",
  health: "at_risk",
  body: "Middleware refactor discovered as a prerequisite. Adds ~2 days. Decision needed from @pm on scope."
)
```

### Step 7 — PR + handoff

```
update_issue(id: "ENG-789", stateId: "<in-review-id>")
create_comment(
  issueId: "ENG-789",
  body: "PR #88 open: https://github.com/org/repo/pull/88
         Landed: token-bucket limiter, Redis module, middleware refactor (scoped minimal), 429 + retry-after.
         Deferred: per-route granular config → ENG-791 created."
)
```

Commit messages on the branch all include `Linear: ENG-789`.

---

## Edge Cases

**Task starts with an existing issue that's still in Backlog.**
Move it to In Progress at step (a.3). Don't assume it's already in the right state.

**Project update tool unavailable at runtime.**
Fall back to a comment on the project's most prominent parent issue. Note in the comment that it's a project-level update.

**User explicitly says "don't create an issue".**
Respect it. Skip issue creation and the state-transition steps. You can still post a comment on an existing issue if one is referenced.

**Work spans multiple issues.**
Move all related issues to In Progress at start. Link them with `related` relations. Reference all IDs in commits and PR body.

**Issue exists but has the wrong project or team.**
`update_issue(id: ..., projectId: ..., teamId: ...)` to correct it before proceeding. Don't silently work against a miscategorised issue.
