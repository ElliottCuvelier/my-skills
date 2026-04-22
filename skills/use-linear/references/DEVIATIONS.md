# Comment Types and Deviation Handling

When to comment, what type to use, and when to escalate to a project update. Back to [SKILL.md](../SKILL.md).

---

## The Three Comment Types

Use `save_comment` for exactly three situations. Everything else is silence.

| Type | When | Format |
| --- | --- | --- |
| **Progress** | A material step completed — not every commit, only meaningful milestones | One sentence: what completed and what it unblocks |
| **Blocker** | Something preventing forward motion that the user or team should know about | What's blocking + what's needed to unblock |
| **Finding** | Something the user or team should know: scope creep, discovered bug, design gap, deviation from spec | Short paragraph; use the structured template for deviations |

**No other comment types.** Specifically:
- No "starting work now" comment — the status transition is the signal
- No file-by-file narration of what was done
- No recap that duplicates what the status change already communicated
- No "I'm done here" without substance — the PR + final summary comment covers it

---

## The Materiality Bar for Findings / Deviations

Post a Finding comment only when:

| Qualifies | Does NOT qualify |
| --- | --- |
| User-visible behavior changes | Refactoring internal structure with same external behavior |
| API contract change (endpoint shape, request/response schema, status codes) | Renaming an internal variable or helper |
| Scope grows or shrinks | Picking one library over another with equivalent interface |
| New hard blocker discovered | Reordering logic that produces the same result |
| Dependency on another team or external service identified | Minor performance optimization, no observable change |
| Architecture change affecting other issues or teams | Splitting a large function into smaller ones |

**When in doubt:** "If I described this to the person who wrote the issue, would they need to update their expectations?" If yes — it's material.

---

## The Structured Deviation Template

For material deviations, use this shape as a Finding comment:

```
**Deviation**: <one-line summary — what changed from the spec>
**Why**: <new information or constraint that made the original plan wrong>
**Impact**: <what else is affected — other issues, API consumers, scope, timeline>
**Decision needed**: Yes — <specific question for whom> / No
```

### Example — API shape change

```
**Deviation**: /auth/refresh now returns { token, expiresAt } instead of { accessToken, ttl }
**Why**: Frontend token library requires expiresAt as ISO timestamp; ttl in seconds caused parsing issues.
**Impact**: All clients consuming /auth/refresh need field-name update. No other endpoints affected.
**Decision needed**: No — agreed with @frontend-lead.
```

### Example — Scope growth

```
**Deviation**: Rate limiter requires Redis module that doesn't exist yet (ENG-790 created as sub-issue)
**Why**: Assumed Redis was already provisioned; it isn't.
**Impact**: Adds ~2 days. ENG-789 now blocked by ENG-790.
**Decision needed**: Yes — @pm: approve scope extension or descope per-route config to follow-up?
```

### Example — Blocker (use Blocker type, not Deviation template)

```
**Blocked**: Cannot migrate sessions table without a maintenance window.
Need ~8 min window under current load. Waiting on @infra to schedule.
```

---

## Anti-Flood Rules

- One comment per **coherent** deviation — not per commit, not per file changed
- Don't comment on every approach considered — only on the chosen one if it's a material deviation from spec
- Don't comment to narrate progress detail — use a Progress comment for milestones only
- Don't add a comment when the status change already communicates the event

---

## When to Update the Document Instead

A comment alone is not enough when a deviation **invalidates part of a spec or design Document**:

1. Post the Finding comment (so the timeline is clear)
2. **Update the Document** to reflect the new truth

Read-before-write:

```
get_document(id: specDocId)
// edit the specific section that changed
// save via runtime-discovered update_document tool
```

If no spec Document exists and the deviation implies a significant architectural decision, create one (confirm with user first). See [DOCUMENTS.md](DOCUMENTS.md).

---

## When to Escalate to a Project Update

Post a project update (in addition to the issue comment) when the deviation affects the project:

| Situation | Add project update? |
| --- | --- |
| Internal refactor, no timeline impact | No |
| API shape change, one issue, no timeline impact | No |
| Scope grows by ≥ 2 days | Yes — health may change |
| Hard blocker with unclear resolution timeline | Yes — health → `at_risk` or `off_track` |
| Other teams or projects now affected | Yes |
| Milestone stakeholders expected is delayed | Yes |

Health states (verify enum at runtime): `on_track` / `at_risk` / `off_track`.

---

## Comment Checklist

- [ ] Is this actually material (user-visible, API shape, scope, or blocker)?
- [ ] Am I combining all related aspects into one comment?
- [ ] Is this a Progress, Blocker, or Finding — and using the right format?
- [ ] If a spec Document is invalidated — have I updated the Document too?
- [ ] If project health is affected — have I also posted a project update?
- [ ] Am I avoiding narration of what was done file-by-file?
