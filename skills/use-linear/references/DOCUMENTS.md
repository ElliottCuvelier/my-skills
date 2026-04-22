# Linear Documents Reference

When to create a Document vs. a comment, and how to write each type. Back to [SKILL.md](../SKILL.md).

---

## Comment vs. Document

```
Is this information useful only at a specific moment in the issue's timeline?
└── Yes → Comment (deviation note, PR link, status update, question)

Is this information something a future person would search for?
└── Yes → Document (spec, RFC, ADR, runbook, onboarding)

Is this the authoritative "what this issue is about"?
└── Yes → Issue description (update it, don't comment it)

Is this a durable design decision or architectural note?
└── Yes → Document (even if it started as a comment, elevate it)
```

**Rule of thumb:** If you'd be annoyed to have to scroll through 40 comments to find it six months from now, it's a Document.

---

## Read-Before-Write Protocol

Never create a new Document without checking whether one already exists. Forking creates two conflicting sources of truth.

```
// 1. Search for existing documents on the project
list_documents({ projectId: "<project-id>" })

// 2. If a relevant document exists, read it
get_document({ id: "<doc-id>" })

// 3a. If found and stale → update it
update_document({ id: "<doc-id>", content: "..." })
// 3b. If not found → draft + confirm with user → create it
create_document({ project: "<project-name-or-id>", title: "Spec: <feature>", content: "..." })
```

---

## Document Types

### Spec

The canonical description of what is being built — acceptance criteria, constraints, non-goals.

```markdown
# Spec: <Feature Name>

## Status
Draft | Review | Approved | Superseded

## Problem
<What gap or pain this feature addresses>

## Solution
<High-level description of the approach>

## Acceptance Criteria
- [ ] <observable, testable criterion>
- [ ] <observable, testable criterion>

## Non-goals
- <what this explicitly does not cover>

## Open Questions
- <question> — @assignee
```

### RFC (Request for Comments)

A design proposal that needs team input before a decision is made.

```markdown
# RFC: <Proposal Title>

## Status
Proposed | Accepted | Rejected | Superseded by <link>

## Summary
<1–2 sentence TL;DR>

## Motivation
<Why this change is needed>

## Design
<Technical details — diagrams, data models, API shapes>

## Alternatives Considered
<What else was considered and why it was rejected>

## Questions for Review
1. <specific question>
2. <specific question>
```

### ADR (Architecture Decision Record)

A record of a decision already made — immutable after approval.

```markdown
# ADR-### <Title>

## Status
Proposed | Accepted | Deprecated | Superseded by ADR-###

## Context
<The situation and forces that led to this decision>

## Decision
<What was decided, in one or two sentences>

## Rationale
<Why this option over the alternatives>

## Consequences
<Trade-offs, follow-on work required, risks accepted>
```

### Runbook

Step-by-step operational guide for a specific scenario (incident response, deployment, rollback, etc.).

```markdown
# Runbook: <Scenario Name>

## When to Use
<What conditions trigger this runbook>

## Prerequisites
- <access / credentials / tools needed>

## Steps
1. <action>
2. <action>
3. <action>

## Verification
<How to confirm success>

## Rollback
<How to undo if something goes wrong>

## Escalation
<Who to contact if this runbook doesn't resolve the issue>
```

---

## When to Create Each Type

| Situation | Document type |
| --- | --- |
| Starting a significant feature that will take ≥1 week | Spec |
| Proposing a change that affects other teams or architecture | RFC |
| Recording a major technical decision for posterity | ADR |
| Writing operational procedures for the team | Runbook |
| Something else durable (onboarding, glossary, FAQ) | Use the closest template as a starting point |

---

## Linking Documents to Issues

After creating a document:
- Reference it in the issue description: "See [Spec: Rate Limiter](linear://doc/...)".
- Mention it in the initial deviation comment if the deviation invalidates part of the spec.
- Update it (not just comment) when the spec changes.

---

## Document Maintenance

| Situation | Action |
| --- | --- |
| A deviation invalidates part of a spec | Update the spec section; note the change date in the document |
| An RFC is accepted | Update status to "Accepted"; link the implementing issue |
| An ADR is superseded | Update status to "Superseded by ADR-###"; keep the old record |
| A runbook step no longer works | Update or add a "Deprecated step" note; create a follow-up issue if a full rewrite is needed |

Never delete Documents, even if superseded — they form a historical record. Mark them as "Superseded" or "Deprecated" instead.
