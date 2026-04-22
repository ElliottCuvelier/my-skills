---
name: use-linear
description: 'Use Linear (via the official Linear MCP server at mcp.linear.app) as the project-management spine for all non-trivial work — track every task as a Linear issue, update issue state in parallel with coding, post project updates at meaningful checkpoints, comment on deviations from spec, and lean on sub-issues, relations, labels, cycles, projects, initiatives, and documents. Proactively apply whenever Linear MCP tools are detected in the available tool list — do not wait for the user to name "Linear" explicitly. Also triggers whenever the user mentions: Linear, linear.app, an issue ID like ENG-123 or ABC-4567, ticket, sub-issue, parent issue, blocks/blocked-by, Linear cycle, Linear project, Linear initiative, Linear document, RFC, ADR, runbook, PR or commit linkage to a tracker, project management, issue tracking, progress updates, or produces a multi-step plan. Triggers on: linear, linear.app, ENG-###, issue tracker, ticket, sub-issue, parent issue, blocks, blocked-by, linear cycle, linear project, linear initiative, linear document, RFC, ADR, runbook, project update, plan, translate to linear. Use when starting a non-trivial task (search-then-create an issue), while working (move state, post project updates, comment on material deviations), at handoff (embed issue ID in commits/PR, final summary comment), and at the end of any multi-step plan (offer to translate to Linear). Skip only for trivial one-line or single-word fixes where issue overhead exceeds the work itself.'
---

# Linear as Project-Management Spine

The official Linear MCP server is your project-management co-pilot. Use it in parallel with all non-trivial work — not as a post-hoc changelog.

## Compatibility

| Requirement | Details |
| --- | --- |
| MCP server | Varies by installation (official: `https://mcp.linear.app/mcp`; community servers also available) |
| Auth | OAuth 2.1 (interactive flow in Claude Code) or `Authorization: Bearer <token>` header — the token is bound to a Linear user; the authenticated user is the default assignee |
| Supported clients | Claude Code, Claude Desktop, Cursor, Windsurf, VS Code, Zed, and any MCP-compatible client |
| Primary tools | `save_issue`, `save_comment`, `save_project` (unified upsert); `list_*` / `get_*` for reading |
| Tool surface | Check the session's actual tool list — prefix varies by server (e.g., `mcp__linear-wi__save_issue` or `mcp__linear__save_issue`) |

## When to Use (and When NOT to)

| Use | Skip |
| --- | --- |
| Linear MCP tools are present in the session | No Linear MCP in the session |
| Non-trivial task (>1 file, >15 min, or user-visible) | One-line fix, typo, whitespace change |
| Multi-step or multi-issue work | Throwaway script or prototype explicitly not meant to be tracked |
| Work that will produce a PR or commit | Exploratory "what does this code do?" question |
| After producing any multi-step plan | Cadence-based update when nothing material happened |

## Core Principles

1. **Issue is the contract.** Every non-trivial task has a Linear issue. The issue's description is the spec of record — not a Slack message, not a comment, not a README section.

2. **Linear updates run in parallel with code, not after.** State transitions, sub-issue creation, and comments happen as they occur. Batching them to the end defeats the purpose.

3. **Discover, don't invent.** Call `list_issue_labels`, `list_issue_statuses`, `list_projects`, `list_teams`, and `list_cycles` before assuming names or IDs exist. Never hard-code status names or label strings from memory.

4. **Documents for durable knowledge; comments for timeline events.** Specs, RFCs, ADRs, runbooks → Linear Documents. Progress milestones, blockers, findings, and deviations → issue comments. Don't bury durable content in comments where it's impossible to find later.

5. **Project fit, not project force.** If an issue is orphan, search for a project whose scope matches and attach it. If the work is genuinely self-isolated, leave it project-less. Never silently invent or force-assign a project.

6. **Confirm before creating.** `save_issue` (new), `save_project` (new), `create_issue_label`, and `create_document` all require presenting a draft and waiting for explicit user confirmation. The agent is not a PM; it assists the PM.

## The Parallel-Progress Protocol

Follow this protocol for every non-trivial task. It runs in parallel with coding — not sequentially before or after.

### (a) At task start — before writing code

1. **Find an existing issue.** Call `list_issues` filtered by keywords/team. If the user named an ID (e.g., `ENG-123`), call `get_issue` directly — re-read from Linear, never rely on memory.
2. **If no match and task is non-trivial:** draft an issue — title, description, team (`list_teams`), project (`list_projects`), labels (`list_issue_labels`), priority, estimate, cycle (`list_cycles`), parent or relations if applicable. **Present the draft to the user. Wait for confirmation.** Then call `save_issue`.
3. **Move to In Progress.** First, call `get_issue` to read the current state. If it's already at or past In Progress, skip the transition — never regress status. If it's still in Backlog/Todo, discover the In Progress state via `list_issue_statuses` and call `save_issue`. Never hard-code status names or UUIDs.
4. **Capture durable spec.** If the task has a written spec or design that will be referenced repeatedly, create a Linear Document (`create_document`) or update the issue description. Do not bury specs in comments.

### (b) While working — continuously

- **Sub-issues.** When a subtask is ≥ ~30 min or belongs to a different layer/person, create it as a sub-issue via `save_issue` with `parentId`. Decompose proactively.
- **Relations.** The moment a dependency surfaces, set it: `blocks`, `blocked_by`, or `related` via `save_issue`. Don't let blockers sit silent.
- **Estimate / priority.** If a field is **unset**, set it. If already set and reality diverges ≥ ~50%, **offer the update to the user** — don't silently overwrite.
- **Post project updates.** At meaningful checkpoints, call `save_status_update` on the parent project. Checkpoints: a milestone lands, a blocker is discovered, scope or timeline materially shifts, a batch of sibling issues completes, or health changes (`onTrack` → `atRisk` → `offTrack`). Each update names the health state, what moved, what's next, decisions needed. Not on cadence — events only. See [references/WORKFLOW.md](references/WORKFLOW.md).
- **Comments — three types only.** Use `save_comment` for exactly three things:
  - **Progress**: a material step completed (not every commit). One sentence.
  - **Blocker**: something preventing forward motion. State what + what's needed to unblock.
  - **Finding**: something the user or team should know (scope creep, discovered bug, design gap, deviation from spec).
  - **No "starting work now" comment** — the status transition is the signal.

### (c) On material deviation

Material = user-visible behavior change, API/contract shift, scope change, or newly discovered blocker. Internal refactors don't qualify.

Post a **Finding** comment via `save_comment` using this structure:

```
**Deviation**: <one-line summary>
**Why**: <why the original plan didn't work or what new info changed things>
**Impact**: <scope, API surface, or other issues affected>
**Decision needed**: <yes/no — what from whom>
```

If the deviation invalidates a spec Document, **update the Document** so future readers see truth. One comment per coherent deviation, not per commit. See [references/DEVIATIONS.md](references/DEVIATIONS.md).

### (d) At handoff / PR

1. **Check current state first.** `get_issue` — if already In Review or beyond, don't regress it.
2. Move to In Review via `save_issue` (discovered state ID).
3. Ensure the issue ID appears in every commit message and in the PR body (see [references/GIT.md](references/GIT.md)). Branch names are **not** touched.
4. Post a final `save_comment` linking the PR and summarizing: what landed, what was deferred, any follow-up issue IDs created.

## Translating Plans to Linear

After producing any multi-step plan or structured proposal, close with this offer:

> **Translate to Linear?**
> - **Start working** — create the issues (with sub-issues and `blockedBy` links), assign to you, move the first one to In Progress, and begin.
> - **Archive for team** — create the issues in Backlog under the right project, unassigned, so the team can pick them up.
> - **Neither** — keep the plan local to this conversation.

**Translation rules (if Start working or Archive is chosen):**

- One top-level issue per plan section or distinct deliverable
- Sub-issues for pieces within a section (same deliverable, shipped together)
- `blockedBy` links for sequencing between sibling issues (different deliverables, ordered)
- Descriptions from the plan — short, not the full rationale
- Assign to the authenticated user only on "Start working"; leave unassigned for "Archive"
- Move only the first issue to In Progress on "Start working"; rest stay Backlog

See [references/PLAN-TO-LINEAR.md](references/PLAN-TO-LINEAR.md) for worked examples and edge cases.

## Reading Linear — Re-read, Don't Recall

Linear state changes constantly. Before reporting or acting on issue status, assignee, comment count, or project membership, **always re-read from Linear** — never quote from memory or prior conversation context.

```
get_issue(id: "ENG-123")     // current state, not cached state
list_issues({ assignee: "me", state: "started" })    // started work
list_issues({ assignee: "me", state: "unstarted" })  // todo / backlog assigned to me
// for "what's on my plate" queries
```

Memory entries about Linear can be hours or days stale — they're context, not ground truth.

## Quick Decision Trees

### Do I need a Linear issue for this task?

```
Is Linear MCP present in the session?
├── No  → Skip Linear entirely
└── Yes → Is this a trivial one-line / typo fix?
           ├── Yes → Skip, or add a passing comment on an existing issue
           └── No  → Search for an existing issue first
                      ├── Found → Use it (update state, add sub-issues as needed)
                      └── Not found → Draft + confirm + save_issue
```

### Sub-issue vs. new related issue vs. inline todo?

```
Is this work a direct component of the parent task?
├── Yes, same deliverable → Sub-issue (save_issue with parentId)
│
Is this a dependency that must land first?
├── Yes → New issue + blockedBy relation
│
Is this a parallel concern in the same area?
├── Yes → New issue + related relation
│
Can it be done in <5 min as part of the current diff?
└── Yes → Inline, no separate tracking needed
```

### Which comment type?

```
Material step completed (not every commit)?   → Progress comment (1 sentence)
Something blocking forward motion?            → Blocker comment (what + needed to unblock)
Scope creep / bug / design gap / deviation?   → Finding comment (structured Deviation template)
"Starting work now" / "working on auth"?      → None — status transition says it
Durable spec or design decision?              → Linear Document, not a comment
```

### Cycle vs. Project vs. Initiative?

```
Quarter/half-level strategic grouping of multiple projects?
└── Yes → Initiative

Multi-issue deliverable with a ship date?
└── Yes → Project (search for a fit; if none, leave project-less or ask)

Time-boxed sprint-style commitment?
└── Yes → Cycle (assign on create if team uses cycles; discover via list_cycles)

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
| Sub-issue (`parentId`) | ≥2 distinct units of work, different owners/layers, or each needs independent tracking | `save_issue` with `parentId` |
| Relation `blocks` / `blocked_by` | Strict ordering matters; A cannot start before B lands | `save_issue` (relations field) |
| Relation `related` | Same area, navigational only — no ordering constraint | `save_issue` (relations field) |
| Label | Recurring cross-cutting attribute (bug, tech-debt, area, security) | **`list_issue_labels` first**; `create_issue_label` only with user confirmation |
| Priority | Set on create; if already set and needs changing, offer the change | `save_issue` |
| Estimate | Set on create if unset; if already set and diverges ≥ ~50%, offer the change | `save_issue` |
| Cycle | Assign on create if team uses cycles and field is unset; offer change if already set | `list_cycles` → `save_issue` |
| Project | If orphan, search for a fit; don't force; if self-isolated, leave project-less | `list_projects` / `save_project` (confirm first) |
| Initiative | Quarter/half-scale strategic grouping; read-mostly; create only on explicit ask | `list_initiatives` / `save_initiative` (confirm first) |
| **Project Update** | While project is in progress — at milestone, blocker, scope shift, health change. Not on cadence. | `save_status_update` (pass `project` name/ID; `health`: `onTrack`/`atRisk`/`offTrack`) |
| Project milestone | Split a long project into explicit gates | `save_milestone` (pass `project` name/ID, `name`; confirm first) |
| Document | Durable knowledge: spec, RFC, ADR, runbook, onboarding | `list_documents` → `get_document` → update existing or create; never fork |
| Comment | Progress milestone, blocker, or finding (deviation) tied to one issue's timeline | `save_comment` |

## Git Coupling

Include the issue ID in commit messages and the PR body. Do **not** change branch names.

**Commit message:**
```
<type>(<scope>): <subject>

Linear: ENG-###
```

**PR body:** Append `Linear: ENG-###` at the end. If an existing PR template has a "Linear:", "Ticket:", or "Issue:" field, fill that slot instead — don't duplicate. A PR touching multiple issues lists all IDs: `Linear: ENG-123, ENG-124`.

Full templates and examples in [references/GIT.md](references/GIT.md).

## Tool Discovery

The primary tools are `save_issue` (create or update), `save_comment`, and `save_project`. Additional write tools — `save_status_update`, `save_milestone`, `save_initiative`, `create_document`, `update_document` — follow the same `save_*` / `create_*` pattern. In-session, tools are namespaced by whatever name the MCP server was configured with — check the actual tool list for the correct prefix (e.g., `mcp__linear__save_issue` if named "linear", `mcp__linear-wi__save_issue` if named "linear-wi").

## Anti-Patterns (CRITICAL)

| Anti-pattern | Problem | Fix |
| --- | --- | --- |
| **Inventing labels** | `create_issue_label` without listing first fragments the team's taxonomy | Always `list_issue_labels`; `create_issue_label` only with user confirmation |
| **Orphan issues** | Issue created without team | Resolve team before `save_issue`; project is optional if no fit exists |
| **Stuck in Backlog** | Forgetting to move state at start or handoff | Protocol (a.3) and (d.2) are non-optional; but check current state first |
| **Status regression** | Moving an issue backwards (In Review → In Progress) because protocol says to | Always `get_issue` first; skip the transition if already at or past target |
| **Comment flood** | One comment per commit, per file, or per thought | Three types only: Progress, Blocker, Finding. No narration. |
| **"Starting work now" comment** | Narrating a status change that already communicates itself | Status transition is the signal — no comment needed |
| **Spec buried in comments** | Full spec posted as a comment, silently invalidated later | Create a Linear Document; link from the issue |
| **Hard-coded status / label names** | Assuming "In Progress" or "Bug" from memory | Runtime: `list_issue_statuses`, `list_issue_labels` |
| **Silent deviations** | Changing user-visible behavior or API without a comment | Finding comment with Deviation template per protocol (c) |
| **Branch-name mandates** | Forcing `ENG-123-foo` branch naming | Issue ID goes in commits + PR only; branch naming is out of scope |
| **Silently overwriting set fields** | Changing estimate/priority/cycle that user already set | Offer the change; don't silently overwrite |
| **Creating without confirmation** | Calling `save_issue` (new), `save_project` (new), or `create_document` autonomously | Draft → present → wait for confirmation |
| **Silent projects** | All issues complete but no project updates — stakeholders have no signal | Post project updates at real checkpoints; don't wait for completion |
| **Stale-memory answers** | Quoting issue state or assignee from memory without re-reading | Always `get_issue` before reporting or acting on Linear state |

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
| [references/TOOLS.md](references/TOOLS.md) | Intent → tool cheatsheet (`save_*` primary; full list; MCP prefix note) | Looking up which tool to call for a given action |
| [references/PLAN-TO-LINEAR.md](references/PLAN-TO-LINEAR.md) | End-of-plan offer; section → issue translation rules; worked examples | Translating a plan into Linear issues |
| [references/HIERARCHY.md](references/HIERARCHY.md) | Initiative / Project / Issue / Sub-issue / Doc / Cycle model; promotion rules | Designing issue structure or deciding what level something belongs at |
| [references/DEVIATIONS.md](references/DEVIATIONS.md) | Three comment types; materiality bar; structured template; anti-flood rules | Deciding whether and how to comment |
| [references/GIT.md](references/GIT.md) | Commit and PR templates with issue ID; PR-template-append rule; non-rule on branches | Wiring up git artifacts to the Linear issue |
| [references/DOCUMENTS.md](references/DOCUMENTS.md) | Comment vs Document decision; four document shapes (Spec, RFC, ADR, Runbook) | Creating or updating a Linear Document |
| [references/CHEATSHEET.md](references/CHEATSHEET.md) | One-screen quick reference: task-start checklist, state transitions, top tool calls | Day-to-day reference while executing |

## Sources

- [Linear MCP documentation](https://linear.app/docs/mcp) — official server, auth, and client setup
- [Linear changelog: MCP for product management (2026-02)](https://linear.app/changelog/2026-02-05-linear-mcp-for-product-management) — initiative/milestone/project-update tooling
- [Linear API reference](https://developers.linear.app/docs/graphql/working-with-the-graphql-api) — GraphQL API underlying the MCP tools; useful for understanding field names and relationships
