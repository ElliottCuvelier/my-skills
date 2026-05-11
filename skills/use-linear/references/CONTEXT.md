# Local Linear context file (YAML)

Back to [SKILL.md](../SKILL.md).

## Purpose

`.agents/use-linear/context.yaml` is **gitignored**. It holds stable defaults (team, usual projects, label names, workflow state display names) so the agent does not need repeated `list_teams` / `list_projects` / `list_issue_labels` / `list_issue_statuses` / `list_cycles` calls at every task start.

**Live issue state** still comes from `get_issue` / MCP — never treat this file as ground truth for status.

## Location

Create the file at the **repository root**:

```
.agents/use-linear/context.yaml
```

If missing, copy the template below and edit values for your workspace.

## Schema (all keys optional except you should set `team` if you use a single default team)

| Key           | Type            | Meaning                                                                                                                                            |
| ------------- | --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `team`        | string          | Default team **key** (e.g. `ENG`) used when drafting issues and resolving team defaults                                                            |
| `projects`    | list of strings | Active project **names** you usually attach work to (for drafts; still confirm fit per task)                                                       |
| `labels`      | list of strings | Label **names** that already exist on that team — never invent labels not listed here without `list_issue_labels` + user confirm                   |
| `uses_cycles` | boolean         | If `true`, agent should assign cycle on create when unset (resolve cycle via `list_cycles({ teamId, type: "current" })` just-in-time)              |
| `states`      | map             | Optional hints: `in_progress`, `in_review`, `done` → display names your team uses (still verify with `list_issue_statuses` before write if unsure) |

Use **flow-style** lists (`[a, b]`) and a single nested map for `states` to avoid YAML indentation mistakes.

## Copy-paste template

```yaml
team: ENG
projects: [Infrastructure Hardening Q2, Platform Reliability]
labels: [backend, frontend, bug, security, tech-debt]
uses_cycles: true
states:
  in_progress: In Progress
  in_review: In Review
  done: Done
```

## Conflict with Linear

If `context.yaml` disagrees with `get_issue` or other MCP reads, **trust Linear** (MCP). Update `context.yaml` when your team renames projects, labels, or states.

## Related

- Session start: see the **Session Start** section in [SKILL.md](../SKILL.md) and [CHEATSHEET.md](CHEATSHEET.md).
- Protocol: [WORKFLOW.md](WORKFLOW.md) step (a).
