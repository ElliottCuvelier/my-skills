# Workflow Reference

Full expansion of the parallel-progress protocol from [SKILL.md](../SKILL.md). Read when starting a task or verifying the protocol applies correctly.

---

## The Protocol in Full

### (a) At task start

**1. Search first — re-read from Linear, never from memory.**

```
list_issues(filter: { team: { key: { eq: "ENG" } }, query: "auth token refresh" }, first: 10)
```

If the user provided an issue ID directly:

```
get_issue(id: "ENG-123")
```

**2. Draft and confirm before creating.**

If no match and the task is non-trivial, build a draft and present it to the user before calling `save_issue`. The draft should include:

- **Title** — action-oriented, ≤60 chars
- **Description** — what needs to happen and why; acceptance criteria if applicable
- **Team** — resolved via `list_teams`
- **Project** — resolved via `list_projects`; search for a scope fit. If genuinely self-isolated, leave project-less.
- **Labels** — resolved via `list_issue_labels`; never invented
- **Priority** — 0 (none), 1 (urgent), 2 (high), 3 (medium), 4 (low)
- **Estimate** — set on create (check existing issues for the team's scale convention)
- **Cycle** — assign to the active cycle if the team uses cycles (`list_cycles`)
- **Parent** — `parentId` if this is a sub-issue
- **Relations** — if this blocks or is blocked by another issue

Wait for the user to confirm before calling `save_issue`.

**3. Move to In Progress — check current state first.**

```
get_issue(issueId)    // read current state
// If stateType is already "started", "completed", or "cancelled" → skip
// If stateType is "unstarted" or "backlog":
list_issue_statuses(filter: { team: { id: { eq: teamId } } })  // find In Progress id
save_issue({ id: issueId, stateId: inProgressId })
```

Never regress. If the user already moved the issue forward, leave it where it is.

**4. Surface or create the spec Document.**

```
list_documents(filter: { project: { id: { eq: projectId } } })
get_document(id: docId)   // if found — read before writing

// If not found and a spec exists, confirm with user then:
create_document(projectId, title: "Spec: <feature>", content: "...")  // runtime-discovered tool
```

See [DOCUMENTS.md](DOCUMENTS.md) for document shapes.

---

### (b) While working

**Decompose into sub-issues proactively.**

```
save_issue({
  teamId,
  projectId,
  parentId: parentIssueId,
  title: "Add migration for sessions table",
  description: "...",
  estimate: 2,
  cycleId: currentCycleId
})
```

**Set relations when dependencies surface.**

```
save_issue({ id: blockingIssueId, relations: [{ type: "blocks", relatedIssueId: blockedIssueId }] })
```

**Update estimate / priority — offer first if already set.**

If the field is unset, set it directly. If already set and reality diverges ≥ ~50%, offer:
> "Estimate is currently 3 points but this looks closer to 8 — update it?"

Then: `save_issue({ id: issueId, estimate: 8 })` on confirmation.

**Post project updates at meaningful checkpoints.**

```
create_project_update({ projectId, health: "at_risk", body: "..." })
// verify tool name at runtime; fallback: save_comment on flagship issue
```

Triggers: milestone lands, blocker discovered, scope/timeline shifts, health changes, sibling-issue batch completes.

**Comments — three types, no narration.**

```
// Progress — material step completed
save_comment({ issueId, body: "Redis module (ENG-790) merged. Rate limiter now unblocked." })

// Blocker — something preventing motion
save_comment({ issueId, body: "**Blocked**: Need token format confirmation from auth team before proceeding. Waiting on ENG-456." })

// Finding / Deviation — scope creep, discovered bug, spec deviation
save_comment({ issueId, body: "**Deviation**: Changed /auth/refresh response shape\n**Why**: Frontend token library requires expiresAt (ISO), not ttl (seconds)\n**Impact**: All /auth/refresh consumers need field-name update\n**Decision needed**: No — agreed with @frontend-lead" })
```

**No "starting work now" comment.** The status transition is the signal.

---

### (c) On material deviation

See [DEVIATIONS.md](DEVIATIONS.md) for the full materiality bar.

Post a Finding comment via `save_comment`:

```
**Deviation**: <one-line>
**Why**: <new information or constraint>
**Impact**: <other issues, API consumers, scope affected>
**Decision needed**: Yes — <specific question> / No
```

If the deviation invalidates a spec Document, update it immediately — a comment alone leaves the Document lying.

---

### (d) At handoff / PR

**1. Check state before transitioning.**

```
get_issue(issueId)
// if already In Review or beyond → skip
list_issue_statuses(filter: { team: { id: { eq: teamId } } })   // find In Review state
save_issue({ id: issueId, stateId: inReviewId })
```

**2. Git artifacts reference the issue.**

Every commit: `feat(auth): fix token refresh race\n\nLinear: ENG-123`

PR body: append `Linear: ENG-123`. See [GIT.md](GIT.md).

**3. Final summary comment.**

```
save_comment({
  issueId,
  body: "PR #42 open for review. Landed: fixed race condition, added retry logic. Deferred: rate-limiting (ENG-456). Follow-ups: ENG-457 (monitoring alert)."
})
```

---

## Worked Example — Rate Limiter for /api/search

**Scenario:** User says "implement rate limiting on the search endpoint." No issue exists.

### Step 1 — Search

```
list_issues(filter: { query: "rate limit search" })   // → no matches
```

### Step 2 — Draft + confirm

```
Proposed issue:
  Title: Add rate limiting to /api/search
  Description: Protect the search endpoint with a per-user token-bucket limiter.
               Acceptance: 429 returned when limit exceeded; retry-after header included;
               existing tests pass; load test confirms ≥100 rps without false positives.
  Team: ENG
  Project: Infrastructure Hardening Q2
  Labels: [backend, security]
  Priority: 2 (high)
  Estimate: 5
  Cycle: Sprint 14
```

User approves → `save_issue(...)` → returns `ENG-789`.

### Step 3 — Move to In Progress (check first)

```
get_issue("ENG-789")    // stateType: "backlog" → proceed
list_issue_statuses(teamId)   // find In Progress
save_issue({ id: "ENG-789", stateId: inProgressId })
```

### Step 4 — Sub-issue + relation discovered

Redis isn't provisioned → sub-issue:

```
save_issue({ parentId: "ENG-789", title: "Add Redis module to infra stack", estimate: 3, cycleId })
// → ENG-790
save_issue({ id: "ENG-789", relations: [{ type: "blocked_by", relatedIssueId: "ENG-790" }] })
```

### Step 5 — Milestone lands → project update

```
create_project_update({
  projectId: infraProjectId,
  health: "on_track",
  body: "Redis module (ENG-790) complete and merged. ENG-789 now unblocked. On track for Sprint 14."
})
```

No comment on the issue — the project update is the signal.

### Step 6 — Material deviation → Finding comment + project update

Middleware chain doesn't support per-route config — needs refactor:

```
save_comment({
  issueId: "ENG-789",
  body: "**Deviation**: Middleware refactor required before per-route rate limiter injection.\n**Why**: Pipeline applies middleware globally only; per-route config requires route-level injection.\n**Impact**: Scope grows ~2 days.\n**Decision needed**: Yes — approve scope extension or descope per-route config to follow-up?"
})

create_project_update({ projectId: infraProjectId, health: "at_risk",
  body: "Middleware refactor prerequisite discovered. Adds ~2 days. Decision needed from @pm on scope." })
```

### Step 7 — PR + handoff

```
get_issue("ENG-789")    // check state before transitioning
save_issue({ id: "ENG-789", stateId: inReviewId })
save_comment({ issueId: "ENG-789", body: "PR #88 open: https://github.com/org/repo/pull/88. Landed: token-bucket, Redis, middleware refactor (minimal scope). Deferred: per-route config → ENG-791." })
```

---

## Edge Cases

**Issue already In Progress when task starts.** `get_issue` shows state type "started" → skip step (a.3) entirely.

**Project update tool unavailable.** `save_comment` on the project's flagship issue as fallback. Note it's a project-level update in the comment.

**User says "don't create an issue."** Respect it. Skip creation and state-transition steps. You can still comment on an existing issue if referenced.

**Work spans multiple issues.** Move all to In Progress. Link them. Reference all IDs in commits and PR body.

**Issue in wrong project.** `save_issue({ id, projectId: correctId })` before starting work — don't operate against a miscategorised issue.
