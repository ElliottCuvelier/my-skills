# Deviation Handling Reference

When to comment, what to write, and when to escalate to a project update. Back to [SKILL.md](../SKILL.md).

---

## The Materiality Bar

Comment on the issue **only** when the deviation is material. Internal implementation choices that don't affect the contract don't need a comment.

| Qualifies as material | Does NOT qualify |
| --- | --- |
| User-visible behavior changes | Refactoring a function's internal structure |
| API contract change (endpoint shape, request/response schema, status codes) | Renaming an internal variable or helper |
| Scope grows or shrinks | Picking one library over another with equivalent interface |
| New hard blocker discovered | Reordering logic that produces the same result |
| Dependency on another team or external service identified | Minor performance optimization with no observable change |
| Architecture changes that affect other issues or teams | Splitting a large function into smaller ones |

**When in doubt:** ask "if I described this change to the person who wrote the issue, would they need to know to update their expectations?" If yes, it's material.

---

## The Structured Comment Template

One comment per coherent deviation. Post via `create_comment(issueId: "<id>", body: "...")`.

```
**Deviation**: <one-line summary — what changed from the spec>
**Why**: <the new information or constraint that made the original plan wrong or incomplete>
**Impact**: <what else is affected — other issues, API consumers, scope, timeline>
**Decision needed**: Yes — <specific question for whom> / No
```

### Example — API shape change

```
**Deviation**: /auth/refresh now returns { token, expiresAt } instead of { accessToken, ttl }
**Why**: Frontend team's token library requires `expiresAt` as an ISO timestamp; `ttl` in seconds caused parsing issues.
**Impact**: All clients consuming /auth/refresh need to update field names. No other endpoints affected.
**Decision needed**: No — agreed with @frontend-lead in Slack; implementing now.
```

### Example — Scope growth

```
**Deviation**: Rate limiter requires a Redis module that doesn't exist yet (ENG-790 created as sub-issue)
**Why**: Assumed Redis was already provisioned in infrastructure; it isn't.
**Impact**: Adds ~2 days. ENG-789 is now blocked by ENG-790.
**Decision needed**: Yes — @pm: approve scope extension or descope per-route config to follow-up?
```

### Example — Blocker discovered

```
**Deviation**: Cannot migrate sessions table without a maintenance window
**Why**: The sessions table has 40M rows; online migration would lock the table for ~8 minutes under current load.
**Impact**: Requires scheduling a maintenance window; blocks ENG-789 until scheduled.
**Decision needed**: Yes — @infra: what's the earliest maintenance window this week?
```

---

## Anti-Flood Rules

| Rule | Rationale |
| --- | --- |
| One comment per **coherent** deviation, not per commit or per file changed | A flood of comments makes the issue timeline unreadable; batch related changes into one comment |
| Do not comment on every approach considered | If you tried two libraries and picked one, just comment if the chosen approach is a material deviation from spec |
| Do not comment to narrate progress ("working on auth now", "halfway done") | Use project updates for progress; issue comments are for deviations and events |
| Do not comment when the fix is a direct implementation of the spec | If you're doing exactly what the issue says, silence is correct |

---

## When to Update the Document Instead

A comment alone is not enough when the deviation **invalidates part of a spec or design document**. In that case:

1. Post the deviation comment (so the timeline is clear)
2. **Update the Document** to reflect the new truth — don't leave the old spec lying around as a trap for future readers

Use the read-before-write protocol:

```
get_document(id: "<spec-doc-id>")
// Edit the specific section that's now wrong
// Update via runtime-discovered update_document tool
```

If the spec document doesn't exist yet and the deviation implies a significant architectural decision, **create a new Document** (confirm with user first).

---

## When to Escalate to a Project Update

Post a project update (in addition to the issue comment) when the deviation is large enough to affect the project:

| Deviation type | Add project update? |
| --- | --- |
| Internal refactor, no timeline impact | No |
| API shape change, single issue | No (unless other issues depended on that contract) |
| Scope grows by ≥ 2 days | Yes — health may change |
| New hard blocker without a clear resolution timeline | Yes — health changes to at_risk or off_track |
| Other teams or projects are now affected | Yes |
| Milestone that stakeholders expected to land is delayed | Yes |

Project update health states (verify enum values at runtime):
- `on_track` — proceeding as planned
- `at_risk` — a problem exists but can likely be resolved within the current plan
- `off_track` — the current plan is broken; intervention or re-scoping needed

---

## Deviation Comment Checklist

Before posting, verify:

- [ ] Is this actually material (user-visible, API shape, scope, or blocker)?
- [ ] Am I combining all related aspects of this deviation into one comment (not several)?
- [ ] Does the comment include all four fields: Deviation / Why / Impact / Decision needed?
- [ ] If the deviation invalidates a spec Document — have I updated the Document?
- [ ] If project health is affected — have I also posted a project update?
