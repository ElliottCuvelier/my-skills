---
name: use-linear
description: Use Linear (via the official Linear MCP server at mcp.linear.app) as the project-management spine for all non-trivial work — track every task as a Linear issue, update issue state in parallel with coding, post project updates at meaningful checkpoints, comment on deviations from spec, and lean on sub-issues, relations, labels, cycles, projects, initiatives, and documents. Proactively apply whenever Linear MCP tools are detected in the available tool list — do not wait for the user to name "Linear" explicitly. Also triggers whenever the user mentions: Linear, linear.app, an issue ID like ENG-123 or ABC-4567, ticket, sub-issue, parent issue, blocks/blocked-by, Linear cycle, Linear project, Linear initiative, Linear document, RFC, ADR, runbook, PR or commit linkage to a tracker, project management, issue tracking, or progress updates. Triggers on: linear, linear.app, ENG-###, issue tracker, ticket, sub-issue, parent issue, blocks, blocked-by, linear cycle, linear project, linear initiative, linear document, RFC, ADR, runbook, project update. Use when starting a non-trivial task (search-then-create an issue), while working (move state, post project updates, comment on material deviations), and at handoff (embed issue ID in commits/PR, final summary comment). Skip only for trivial one-line or single-word fixes where issue overhead exceeds the work itself.
---

# Linear as Project-Management Spine

The official Linear MCP server is your project-management co-pilot. Use it in parallel with all non-trivial work — not as a post-hoc changelog.

## Compatibility

| Requirement | Details |
| --- | --- |
| MCP server | `https://mcp.linear.app/mcp` (official Linear server) |
| Auth | OAuth 2.1 (interactive flow in Claude Code) or `Authorization: Bearer <token>` header |
| Supported clients | Claude Code, Claude Desktop, Cursor, Windsurf, VS Code, Zed, and any MCP-compatible client |
| Tool surface | Evolves — discover available tools at runtime rather than relying solely on names in this skill |

## When to Use (and When NOT to)

| Use | Skip |
| --- | --- |
| Linear MCP tools are present in the session | No Linear MCP in the session |
| Non-trivial task (>1 file, >15 min, or user-visible) | One-line fix, typo, whitespace change |
| Multi-step or multi-issue work | Throwaway script or prototype explicitly not meant to be tracked |
| Work that will produce a PR or commit | Exploratory "what does this code do?" question |
| Project needs a progress update (milestone, blocker, scope shift) | Cadence-based update when nothing material happened |

## Core Principles

1. **Issue is the contract.** Every non-trivial task has a Linear issue. The issue's description is the spec of record — not a Slack message, not a comment, not a README section.

2. **Linear updates run in parallel with code, not after.** State transitions, sub-issue creation, and deviation comments happen as they occur. Batching them to the end defeats the purpose.

3. **Discover, don't invent.** Call `list_issue_labels`, `list_issue_statuses`, `list_projects`, `list_teams`, and `list_cycles` before assuming names or IDs exist. Never hard-code status names or label strings from memory.

4. **Documents for durable knowledge; comments for timeline events.** Specs, RFCs, ADRs, runbooks → Linear Documents. Progress notes and deviations → issue comments. Don't bury durable content in comments where it's impossible to find later.

5. **Never orphan.** An issue created without a team is broken. An issue without a project (on a team that uses projects) is noise. Resolve team + project before calling `create_issue`.

6. **Confirm before creating.** `create_issue`, `create_project`, `create_issue_label`, and `create_document` all require presenting a draft and waiting for explicit user confirmation. The agent is not a PM; it assists the PM.

## The Parallel-Progress Protocol

Follow this protocol for every non-trivial task. It runs in parallel with coding — not sequentially before or after.

### (a) At task start — before writing code

1. **Find an existing issue.** Call `list_issues` filtered by keywords/assignee/team. If the user named an ID (e.g., `ENG-123`), call `get_issue` directly.
2. **If no match and task is non-trivial:** draft an issue — title, description, team (`list_teams`), project (`list_projects`), labels (`list_issue_labels`), priority, estimate, cycle (`list_cycles`), parent or relations if applicable. **Present the draft to the user. Wait for confirmation.** Then call `create_issue`.
3. **Move to In Progress.** Discover the team's in-progress status via `list_issue_statuses`. Call `update_issue`. Never hard-code status names or UUIDs.
4. **Capture durable spec.** If the task has a written spec or design that will be referenced repeatedly, create a Linear Document (runtime-discovered create tool) or update the issue description. Do not bury specs in comments.

### (b) While working — continuously

- **Sub-issues.** When a subtask is ≥ ~30 min or belongs to a different layer/person, create it as a sub-issue via `create_issue` with `parentId`. Decompose proactively — don't wait until the work is done.
- **Relations.** The moment a dependency surfaces, set it: `blocks`, `blocked-by`, or `related` on `update_issue`. Don't let blockers sit silent.
- **Update estimate / priority.** If reality diverges ≥ ~50% from original, call `update_issue` to reflect current understanding.
- **Post project updates.** At meaningful checkpoints, call the runtime-discovered `create_project_update` on the parent project (fallback: summary comment on the project's flagship issue). Meaningful checkpoints: a milestone lands, a blocker is discovered, scope or timeline materially shifts, a batch of sibling issues completes, or project health changes (on-track → at-risk → off-track). Each update should name the health state, what moved, what's next, and any decisions needed. Do **not** post on cadence — only on events. See [references/WORKFLOW.md](references/WORKFLOW.md) for a worked example.

### (c) On material deviation — not internal refactors

Material = user-visible behavior change, API/contract shift, scope change, or newly discovered blocker. Internal refactors and implementation choices that don't affect the contract do **not** qualify.

Post **one** structured comment per coherent deviation via `create_comment`:

```
**Deviation**: <one-line summary>
**Why**: <why the original plan didn't work or what new info changed things>
**Impact**: <scope, API surface, or other issues affected>
**Decision needed**: <yes/no — what from whom>
```

If the deviation invalidates part of a spec Document, **update the Document** so future readers see truth. A comment alone is not enough.

One comment per deviation, not per commit. See [references/DEVIATIONS.md](references/DEVIATIONS.md) for the materiality bar, anti-flood rules, and examples.

### (d) At handoff / PR

1. `update_issue` → team's "In Review"-equivalent status (discover via `list_issue_statuses`).
2. Ensure the issue ID appears in every commit message and in the PR body (see [references/GIT.md](references/GIT.md)). Branch names are **not** touched.
3. Post a final `create_comment` linking the PR and summarizing: what landed, what was deferred, any follow-up issue IDs created.

## Quick Decision Trees

### Do I need a Linear issue for this task?

```
Is Linear MCP present in the session?
├── No  → Skip Linear entirely
└── Yes → Is this a trivial one-line / typo fix?
           ├── Yes → Skip, or add a passing comment on an existing issue
           └── No  → Search for an existing issue first
                      ├── Found → Use it (update state, add sub-issues as needed)
                      └── Not found → Draft + confirm + create_issue
```

### Sub-issue vs. new related issue vs. inline todo?

```
Is this work a direct component of the parent task?
├── Yes, same deliverable → Sub-issue (create_issue with parentId)
│
Is this a dependency that must land first?
├── Yes → New issue + blocks relation on the parent
│
Is this a parallel concern in the same area?
├── Yes → New issue + related relation
│
Can it be done in <5 min as part of the current diff?
└── Yes → Inline, no separate tracking needed
```

### Comment vs. Document vs. issue description update?

```
Is this durable knowledge (spec, RFC, ADR, design decision)?
└── Yes → Linear Document (create or update; never fork)

Is this tied to a specific moment in the issue timeline (deviation, status note)?
└── Yes → Comment on the issue

Is this the "what this issue is trying to achieve" definition?
└── Yes → Update the issue description directly
```

### Cycle vs. Project vs. Initiative?

```
Quarter/half-level strategic grouping of multiple projects?
└── Yes → Initiative

Multi-issue deliverable with a ship date?
└── Yes → Project (every non-trivial issue should belong to one)

Time-boxed sprint-style commitment?
└── Yes → Cycle (assign on create; don't invent cycles, discover via list_cycles)

Single unit of work?
└── Yes → Issue (with sub-issues for decomposition)
```

## Linear Hierarchy at a Glance

```
Initiative
└── Project  (has Project Updates, Milestones)
    └── Issue  (has Comments, Documents, Labels, Priority, Estimate, Cycle assignment)
        └── Sub-issue  (same fields as Issue; parentId links to parent)

Cycle  (orthogonal to the hierarchy; issues are assigned to cycles)
Document  (attached to a Project or Issue; durable knowledge, not timeline events)
```

Full model with promotion rules in [references/HIERARCHY.md](references/HIERARCHY.md).

## Feature Heuristics

| Linear feature | Use when | How to discover |
| --- | --- | --- |
| Sub-issue (`parentId`) | ≥2 distinct units of work, different owners/layers, or each needs independent tracking | `create_issue` with `parentId` |
| Relation `blocks` / `blocked-by` | Strict ordering matters; A cannot start before B lands | `update_issue` (relations field) |
| Relation `related` | Same area, navigational only — no ordering constraint | `update_issue` (relations field) |
| Label | Recurring cross-cutting attribute (bug, tech-debt, area, security) | **`list_issue_labels` first**; `create_issue_label` only with user confirmation |
| Priority | Set on create; re-set when user expedites or scope grows materially | `create_issue` / `update_issue` |
| **Estimate** | **Always set on create** if the team uses estimates (check existing issues) | field on `create_issue` |
| **Cycle** | **Always assign on create** if the team uses cycles | `list_cycles` → assign in `create_issue` |
| Project | Every non-trivial issue belongs to one | `list_projects` / `create_project` (confirm first) |
| Initiative | Quarter/half-scale strategic grouping; read-mostly; create only on explicit ask | runtime-discovered tools |
| **Project Update** | **While the project is in progress** — at milestone, blocker, scope shift, health change, or sibling-issue batch completion. Not on cadence. | runtime-discovered `create_project_update`; fallback to comment on flagship issue |
| Project milestone | Split a long project into explicit gates | runtime-discovered (2026-era) |
| Document | Durable knowledge: spec, RFC, ADR, runbook, onboarding | `list_documents` → `get_document` → update existing or create; never fork |
| Comment | Ephemeral progress note or material deviation tied to one issue's timeline | `create_comment` |

## Git Coupling

Include the issue ID in commit messages and the PR body. Do **not** change branch names.

**Commit message:**
```
<type>(<scope>): <subject>

Linear: ENG-###
```

**PR body:** Append `Linear: ENG-###` at the end. If an existing PR template has a "Linear:", "Ticket:", or "Issue:" field, fill that slot instead — don't duplicate. Do not rewrite or reorder the rest of the template.

Full templates and examples in [references/GIT.md](references/GIT.md).

## Tool Discovery

Linear's MCP tool surface evolves; do not treat the tool names in this skill as an exhaustive or frozen list. Before acting, consult the actually-available tools in your session — the Linear MCP server advertises them. If a newer or unified tool (e.g., a `save_issue` that replaces `create_issue`/`update_issue`) is present, prefer it. For 2026-era tools (initiatives, initiative updates, project milestones, project updates, project labels), verify the exact name at runtime before calling.

## Anti-Patterns (CRITICAL)

| Anti-pattern | Problem | Fix |
| --- | --- | --- |
| **Inventing labels** | `create_issue_label` without listing first fragments the team's taxonomy | Always `list_issue_labels`; `create_issue_label` only with user confirmation |
| **Orphan issues** | Issue created without team, or without project on a team that uses projects | Resolve team + project first; attach `parentId` if decomposing a parent |
| **Stuck in Backlog** | Forgetting to move state to In Progress at start, or In Review at handoff | Protocol steps (a.3) and (d.1) are non-optional |
| **Comment flood** | One comment per commit, per file, or per thought | One comment per coherent material deviation; promote durable content to Document |
| **Spec buried in comments** | Full spec or design posted as a comment, then silently invalidated later | Create a Linear Document; link from the issue |
| **Hard-coded status / label names** | Assuming "In Progress" or "Bug" from memory | Runtime: `list_issue_statuses`, `list_issue_labels`, `list_projects` |
| **Silent deviations** | Changing user-visible behavior or API without a comment | Structured deviation comment per protocol (c) |
| **Branch-name mandates** | Forcing `ENG-123-foo` branch naming | Issue ID goes in commits + PR only; branch naming is out of scope |
| **Ignoring blockers** | Starting work that's actually blocked by another issue | Check relations; set `blocked-by` immediately on discovery |
| **Creating without confirmation** | Calling `create_issue`, `create_project`, or `create_document` autonomously | Draft → present → wait for explicit user confirmation |
| **Silent projects** | All issues complete but the project has no updates — stakeholders have no signal | Post project updates at real checkpoints; don't wait for project completion |
| **Cadence-based project updates** | Posting "weekly update" regardless of whether anything moved | Event-driven only: milestone, blocker, health change, scope shift |

## Non-Goals

- Does **not** dictate git branch naming conventions.
- Does **not** replace project-specific PM conventions, custom workflows, or team automations — augments them.
- Does **not** perform bulk migrations, backfills, or mass-label operations without explicit user instruction.
- Does **not** auto-close, auto-cancel, or archive issues without confirmation.
- Does **not** mirror Linear state into the repo (no local `issues/` markdown shadow).
- Does **not** post status updates or project updates on a cadence — only on real events.
- Does **not** replace human scope or priority decisions — surfaces them via deviation comments.

## Reference Documentation

| File | Purpose | Read when |
| --- | --- | --- |
| [references/WORKFLOW.md](references/WORKFLOW.md) | Protocol expanded with a full worked example, edge-case handling | Starting work or verifying the protocol applies correctly |
| [references/TOOLS.md](references/TOOLS.md) | Intent → tool cheatsheet (all 23 confirmed tools + tentative 2026-era tools) | Looking up which tool to call for a given action |
| [references/HIERARCHY.md](references/HIERARCHY.md) | Initiative / Project / Issue / Sub-issue / Doc / Cycle model; promotion rules | Designing issue structure or deciding what level something belongs at |
| [references/DEVIATIONS.md](references/DEVIATIONS.md) | Materiality bar, structured comment template, anti-flood rules, Document escalation | Deciding whether and how to comment a deviation |
| [references/GIT.md](references/GIT.md) | Commit and PR templates with issue ID; PR-template-append rule; non-rule on branches | Wiring up git artifacts to the Linear issue |
| [references/DOCUMENTS.md](references/DOCUMENTS.md) | Comment vs Document decision; four document shapes (Spec, RFC, ADR, Runbook) | Creating or updating a Linear Document |
| [references/CHEATSHEET.md](references/CHEATSHEET.md) | One-screen quick reference: task-start checklist, state transitions, top tool calls | Day-to-day reference while executing |

## Sources

- [Linear MCP documentation](https://linear.app/docs/mcp) — official server, auth, and client setup
- [Linear changelog: MCP for product management (2026-02)](https://linear.app/changelog/2026-02-05-linear-mcp-for-product-management) — initiative/milestone/project-update tooling
- [Linear API reference](https://developers.linear.app/docs/graphql/working-with-the-graphql-api) — GraphQL API underlying the MCP tools; useful for understanding field names and relationships
