# ct-o10r (claudeteam-orchestrator)

Run a saved plan as a Claude Code **agent team**: a lead spawns model-pinned teammates that own file-disjoint lanes, share a native task list, and message each other. The agent-teams sibling of `claude-orchestrator`.

> **Not a cost-saver.** Agent teams cost ~7× a single session. ct-o10r is for parallel, collaborative, cross-layer execution — not to save tokens. For cheap one-shot dispatch, use `claude-orchestrator`.

## Requirements

Agent teams are experimental and off by default. Enable, then **restart** Claude Code:

```json
// settings.json
{ "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }
```

## What it does

- **Adaptive first-run setup** — analyzes the codebase and proposes a tailored set of **teammate roles** (no built-in profiles).
- **Native-lean orchestration** — plan todos seed the **native shared task list**; the lead partitions them into file-disjoint lanes, spawns one teammate per lane, and lets native dependency-unblocking + file-lock claiming handle ordering and parallelism.
- **Team-native quality gates** — `TaskCompleted` runs scoped tests and blocks completion (exit 2) on failure; `TaskCreated` records each task's files into a sidecar the gate reads; `TeammateIdle` backstops ByteRover taskId collection.
- **ByteRover memory** — each teammate gets a Recall→Work→Curate→Report loop and messages the lead a `BRV-REVIEW` note per curate; the lead surfaces pending reviews in its final report.
- **Per-lane model pinning** — `haiku` / `sonnet` / `opus` / `inherit`.
- **SHA-protected regeneration** + slash commands `/ct-orchestrate`, `/ct-orchestrate-resume`, `/update-ct-orchestrator`.

## Installation

Distributed via `skills-lock.json`:

```json
{ "ct-o10r": { "source": "<github-user>/<repo>", "sourceType": "github" } }
```

Run the skills installer to copy the skill to `.claude/skills/ct-o10r/`. Trigger it by mentioning agent teams, team orchestration, or typing `/ct-orchestrate`.

## File layout (installed)

```
<target-repo>/
├── .claude/
│   ├── skills/ct-o10r/            ← the installed skill (read-only source)
│   ├── agents/
│   │   ├── .ct-o10r-installed     ← marker (JSON: versions, SHAs, roster, hooks)
│   │   ├── impl-haiku.md / impl-sonnet.md / impl-inherit.md   ← teammate roles
│   │   ├── verifier.md            ← reviewer teammate role (if installed)
│   │   ├── memory-curator.md
│   │   └── <project-slug>-<role>.md   ← project teammate roles
│   ├── commands/
│   │   └── ct-orchestrate.md / ct-orchestrate-resume.md / update-ct-orchestrator.md
│   ├── hooks/
│   │   └── taskcreated-files-sidecar.py / run-task-tests.py / collect-taskids.py
│   └── settings.local.json        ← TaskCreated / TaskCompleted / TeammateIdle hooks
├── .brv/context-tree/             ← ByteRover memory (grows over time)
└── ~/.claude/
    ├── plans/<project-prefix>-<name>.md    ← plan files (user-wide)
    ├── tasks/<team-name>/                  ← native shared task list (per run, persists)
    └── ct-o10r/<team-name>/                ← runtime state (files-sidecar, brv backstop)
```

`<team-name>` = `session-` + the first 8 chars of the session id.

## Source layout (this repo)

```
skills/ct-o10r/
├── SKILL.md                          ← entry point
├── README.md                         ← this file
├── references/
│   ├── AGENT_TEAMS.md                ← the agent-team model + enable flag + limits
│   ├── TEAM_ORCHESTRATION.md         ← the lead playbook
│   ├── PLAN_FORMAT.md                ← the team: block schema
│   ├── SETUP.md                      ← setup interview + answers payload
│   ├── MODEL_TIERS.md                ← 4 model values + per-teammate pinning
│   ├── AGENT_PATTERNS.md             ← signal → teammate-role recipes
│   ├── BYTEROVER_LOOP.md / BYTEROVER_SCOPES.md
│   └── TROUBLESHOOTING.md
├── scripts/
│   ├── utils.py / analyze_codebase.py / detect_byterover.py
│   └── generate_agents.py / setup.py
└── templates/
    ├── teammate-role.md.tmpl
    ├── project-agent.md.tmpl / verifier.md.tmpl / memory-curator.md.tmpl
    ├── orchestrate-cmd.md.tmpl / orchestrate-resume-cmd.md.tmpl / update-cmd.md.tmpl
    ├── byterover_loop_fragment.md.tmpl
    └── hooks/
        ├── taskcreated-files-sidecar.py.tmpl   (TaskCreated)
        ├── run-task-tests.py.tmpl              (TaskCompleted gate)
        └── collect-taskids.py.tmpl             (TeammateIdle backstop)
```

## Quick usage

1. **Enable** agent teams (above) and restart.
2. **Set up** — trigger the skill; it runs the interview, analyzes the codebase, proposes a teammate-role roster, and generates files + hooks.
3. **Draft a plan** — in Plan Mode, write todos with `files:` (the lane key); the skill appends a `team:` block.
4. **Run** — `/ct-orchestrate ~/.claude/plans/<name>.md` → the lead spawns a teammate per lane.
5. **Resume** — `/ct-orchestrate-resume ~/.claude/plans/<name>.md` (respawns teammates; task list persists).
6. **Update roster** — `/update-ct-orchestrator` after a stack change or installing ByteRover.

## How it differs from claude-orchestrator

| | claude-orchestrator | ct-o10r |
|---|---|---|
| Engine | same-session one-shot sub-agent dispatch | persistent agent team (lead + teammates) |
| Status | hand-tracked in the plan file | native shared task list |
| Parallelism | manual files-overlap detection | file-disjoint lanes + native claiming |
| Workers | report back to the orchestrator only | message each other; share the task list |
| Verification | verifier sub-agent per step | TaskCompleted test gate (+ optional reviewer teammate) |
| Pitch | cheap execution | parallel / collaborative execution (~7× cost) |
| Requires | — | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` |

## Anti-patterns

- **Don't use a team for sequential or single-file work** — the ~7× cost isn't worth it; use `claude-orchestrator` or a single session.
- **Don't split one file across two teammates** — concurrent writes corrupt it. One file → one lane.
- **Don't edit generated role files expecting them to persist** — SHA mismatch skips them on regenerate; upstream changes to the template instead.
- **Don't call `brv query` or `brv review approve` in a teammate** — `brv query` is the lead's (costly); approvals are the user's.

## Limitations

- **Experimental** — agent teams are an experimental Claude Code feature; behavior and the underlying spawn/task tools may change. The playbook is written as coordination acts, not against a stable tool API.
- **No in-process resume** — `/resume` doesn't restore teammates (the task list persists; respawn them and heal orphaned tasks).
- **One team per session; no nested teams** — teammates can't spawn teammates.
- **File safety is by construction** — native locks guard task-claim, not source writes; ct-o10r relies on file-disjoint lanes.
- **~7× token cost** — not for cost-sensitive work.
- **ByteRover requirement** — the memory loop needs `brv` on PATH; without it, teammates are stateless across runs.
