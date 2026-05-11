# Workflow Reference

Full expansion of the parallel-progress protocol from [SKILL.md](../SKILL.md). Read when starting a task or verifying the protocol applies correctly.

---

## The Protocol in Full

### (a) At task start

**0. Session start (before any `list_*`).**

1. Read `.agents/use-linear/context.yaml` if it exists (see [CONTEXT.md](CONTEXT.md)).
2. Git hints — two read-only shell calls:
   ```bash
   git branch --show-current
   git log -n 20 --pretty=%B | grep -Eo '\b[A-Z][A-Z0-9]*-[0-9]+\b' | head -5
   ```

**1. Resolve the issue — re-read from Linear, never from memory.**

If the user provided an issue ID directly:

```
get_issue({ id: "ENG-123" })
```

Otherwise prefer, in order: IDs from git branch or recent commit `Linear:` trailers; then a single narrow MCP search:

```
list_issues({ assignee: "me", state: "started", limit: 15 })
```

Only broaden (keywords / team) if still no candidate.

**2. Draft and confirm before creating.**

If no match and the task is non-trivial, build a draft and present it to the user before calling `save_issue`. The draft should include:

- **Title** — action-oriented, ≤60 chars
- **Description** — what needs to happen and why; acceptance criteria if applicable
- **Team** — from `context.yaml` `team`; else `list_teams` once
- **Project** — from context.yaml `projects`; else `list_projects` just-in-time for a scope fit. If genuinely self-isolated, leave project-less.
- **Labels** — from context `labels`; else `list_issue_labels` once before save; never invented
- **Priority** — 0 (none), 1 (urgent), 2 (high), 3 (normal), 4 (low)
- **Estimate** — set on create (check existing issues for the team's scale convention)
- **Cycle** — assign to the active cycle if the team uses cycles (`list_cycles({ teamId, type: "current" })` just-in-time)
- **Parent** — `parentId` if this is a sub-issue
- **Relations** — if this blocks or is blocked by another issue (`blockedBy`, `blocks`)

Wait for the user to confirm before calling `save_issue`.

**3. Move to In Progress — check current state first.**

```
get_issue({ id: issueId })
// Read the state from the returned object. If already "started", "completed", or "cancelled" → skip.
// If "unstarted" or "backlog":
// Prefer context.yaml.states.in_progress if set.
list_issue_statuses({ team })  // only if state name unknown from context.yaml
save_issue({ id: issueId, state: "In Progress" })
```

Never regress. If the user already moved the issue forward, leave it where it is.

**4. Surface or create the spec Document.**

```
list_documents({ projectId })
get_document({ id: docId })   // if found — read before writing

// If not found and a spec exists, confirm with user then:
create_document({ project: projectId, title: "Spec: <feature>", content: "..." })
```

See [DOCUMENTS.md](DOCUMENTS.md) for document shapes.

---

### (b) While working

**Decompose into sub-issues proactively.**

```
save_issue({
  team,
  project,
  parentId: parentIssueId,
  title: "Add migration for sessions table",
  description: "...",
  estimate: 2,
  cycle: currentCycleId
})
```

**Set relations when dependencies surface.**

```
save_issue({ id: blockedIssueId, blockedBy: [blockingIssueId] })
```

**Update estimate / priority — offer first if already set.**

If the field is unset, set it directly. If already set and reality diverges ≥ ~50%, offer:

> "Estimate is currently 3 points but this looks closer to 8 — update it?"

Then: `save_issue({ id: issueId, estimate: 8 })` on confirmation.

**Post project updates at meaningful checkpoints.**

```
save_status_update({ project: projectId, health: "atRisk", body: "..." })
// For initiative updates: save_status_update({ initiative: initiativeId, type: "initiative", health: "onTrack", body: "..." })
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
get_issue({ id: issueId })
// if already In Review or beyond → skip
list_issue_statuses({ team })   // find In Review state
save_issue({ id: issueId, state: "In Review" })
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

### Step 1 — Bootstrap, then search if needed

```
git branch --show-current && git log -n 20 --pretty=%B | grep -Eo '\b[A-Z][A-Z0-9]*-[0-9]+\b' | head -5   // git hints
list_issues({ assignee: "me", state: "started", limit: 15 })   // check if already tracked → no matches
list_issues({ query: "rate limit search", limit: 10 })   // keyword search → no matches
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

User approves → `save_issue({ team: "ENG", project: "...", title: "...", ... })` → returns `ENG-789`.

### Step 3 — Move to In Progress (check first)

```
get_issue({ id: "ENG-789" })    // state is backlog → proceed
// Prefer context.yaml.states.in_progress for ENG; else:
list_issue_statuses({ team: "ENG" })   // find In Progress
save_issue({ id: "ENG-789", state: "In Progress" })
```

### Step 4 — Sub-issue + relation discovered

Redis isn't provisioned → sub-issue:

```
save_issue({ team: "ENG", project: "...", parentId: "ENG-789", title: "Add Redis module to infra stack", estimate: 3, cycle: "Sprint 14" })
// → ENG-790
save_issue({ id: "ENG-789", blockedBy: ["ENG-790"] })
```

### Step 5 — Milestone lands → project update

```
save_status_update({
  project: "Infrastructure Hardening Q2",
  health: "onTrack",
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

save_status_update({
  project: "Infrastructure Hardening Q2",
  health: "atRisk",
  body: "Middleware refactor prerequisite discovered. Adds ~2 days. Decision needed from @pm on scope."
})
```

### Step 7 — PR + handoff

```
get_issue({ id: "ENG-789" })    // check state before transitioning
save_issue({ id: "ENG-789", state: "In Review" })
save_comment({ issueId: "ENG-789", body: "PR #88 open: https://github.com/org/repo/pull/88. Landed: token-bucket, Redis, middleware refactor (minimal scope). Deferred: per-route config → ENG-791." })
```

---

## Edge Cases

**Issue already In Progress when task starts.** `get_issue` shows the state name or type as "started" → skip step (a.3) entirely.

**Project update tool unavailable.** `save_comment` on the project's flagship issue as fallback. Note it's a project-level update in the comment.

**User says "don't create an issue."** Respect it. Skip creation and state-transition steps. You can still comment on an existing issue if referenced.

**Work spans multiple issues.** Move all to In Progress. Link them. Reference all IDs in commits and PR body.

**Issue in wrong project.** `save_issue({ id, project: correctProject })` before starting work — don't operate against a miscategorised issue.
