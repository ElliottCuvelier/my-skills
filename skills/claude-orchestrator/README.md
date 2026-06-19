# Claude Orchestrator

Plan on a frontier model. Execute on cheaper sub-agents. Build a project-specific roster that gets smarter with every plan run.

## What it does

- **Adaptive first-run setup** — analyzes the codebase and proposes a tailored set of sub-agents based on detected frameworks, ORMs, architectural patterns, and existing agents. No built-in profiles.
- **ByteRover memory integration** — if ByteRover is installed, every generated agent gets a Recall→Work→Curate→Report loop so the project accumulates institutional knowledge across plan runs.
- **Claude Code model tiers** — `haiku` (cheap, fast), `sonnet` (balanced), `opus` (premium), `inherit` (same as orchestrator). Fixed enum; no scraping required.
- **SHA-protected idempotent regeneration** — user-edited agent files are never clobbered on `/update-claude-orchestrator`.
- **Slash commands** — `/claude-orchestrate`, `/claude-orchestrate-resume`, `/update-claude-orchestrator`.

## Installation

This skill is distributed via `skills-lock.json`. In a target repo:

1. Add to the repo's `skills-lock.json`:
   ```json
   {
     "claude-orchestrator": {
       "source": "<github-user>/<repo>",
       "sourceType": "github"
     }
   }
   ```
2. Run the skills installer CLI to copy the skill to `.claude/skills/claude-orchestrator/`.
3. In Claude Code, trigger the skill by mentioning orchestration, plan dispatch, sub-agent setup, or typing `/claude-orchestrate`.

## File layout (installed)

```
<target-repo>/
├── .claude/
│   ├── skills/claude-orchestrator/   ← the installed skill (read-only source)
│   ├── agents/
│   │   ├── .claude-orchestrator-installed  ← marker file (JSON, tracks versions + SHAs)
│   │   ├── impl-haiku.md
│   │   ├── impl-sonnet.md
│   │   ├── impl-inherit.md
│   │   ├── verifier.md
│   │   ├── memory-curator.md
│   │   └── <project-slug>-<agent-name>.md  ← project-specific agents (varies per repo)
│   └── commands/
│       ├── claude-orchestrate.md
│       ├── claude-orchestrate-resume.md
│       └── update-claude-orchestrator.md
└── .brv/context-tree/                 ← ByteRover memory (grows over time)
```

Plan files are user-wide, not per-repo:

```
~/.claude/plans/<project-prefix>-<plan-name>.md
```

## Source layout (this repo)

```
skills/claude-orchestrator/
├── SKILL.md                          ← entry point; Claude reads this when triggered
├── README.md                         ← this file
├── references/
│   ├── SETUP.md                      ← Q1–Q7 interview wording + answers payload schema
│   ├── PLAN_FORMAT.md                ← execution: block schema
│   ├── ORCHESTRATION.md              ← dispatch playbook the orchestrating session follows
│   ├── MODEL_TIERS.md                ← 4 model values + use-case guidance
│   ├── AGENT_PATTERNS.md             ← signal → agent recipe library
│   ├── BYTEROVER_LOOP.md             ← canonical Recall→Work→Curate→Report fragment
│   ├── BYTEROVER_SCOPES.md           ← .brv/context-tree/ namespace conventions
│   └── TROUBLESHOOTING.md
├── scripts/
│   ├── utils.py                      ← SHA, render, marker I/O helpers
│   ├── analyze_codebase.py           ← signal collector (stdlib-only, JSON output)
│   ├── detect_byterover.py           ← brv CLI + skill + context-tree detection
│   ├── generate_agents.py            ← renders templates → .claude/agents/ + commands/
│   └── setup.py                      ← first-run entry point
└── templates/
    ├── impl-baseline.md.tmpl
    ├── project-agent.md.tmpl
    ├── verifier.md.tmpl
    ├── memory-curator.md.tmpl
    ├── orchestrate-cmd.md.tmpl
    ├── orchestrate-resume-cmd.md.tmpl
    ├── update-cmd.md.tmpl
    └── byterover_loop_fragment.md.tmpl
```

## Quick usage

1. **Set up** — trigger the skill in any conversation. It detects no marker, runs the 7-question interview, analyzes the codebase, proposes a roster, and generates files.

2. **Draft a plan** — in Plan Mode, write a plan as usual. The skill helps append an `execution:` block with the chosen tier and parallelism.

3. **Execute** — `/claude-orchestrate ~/.claude/plans/<name>.md`

4. **Resume** — `/claude-orchestrate-resume ~/.claude/plans/<name>.md`

5. **Update roster** — `/update-claude-orchestrator` after adding a new framework, changing the tech stack, or installing ByteRover.

## Anti-patterns

- **Don't edit generated agent files expecting them to persist** — SHA mismatch means they won't be updated on regenerate. If you want permanent changes, either keep the edits and accept that regenerate will skip, or upstream the change to the template.
- **Don't store plan files in the repo** — `~/.claude/plans/` is user-wide and not project-local. Committing plans to the repo won't make them available cross-machine via git.
- **Don't use `brv review approve` in a sub-agent** — pending taskIds must be surfaced to the user by the orchestrator for manual approval.
- **Don't call `brv query` in a sub-agent** — it costs an LLM call. Sub-agents use `brv search` (free BM25) only. The orchestrator may use `brv query` sparingly (0–1 per plan).

## Non-goals

- No model catalog scraping (the Anthropic model enum is fixed: `haiku`, `sonnet`, `opus`, `inherit`).
- No built-in profile library. The roster is always composed fresh from the codebase.
- No automatic `brv review approve` — always surfaces to user.
- No automatic `brv vc push` — cloud sync is user-driven.
- No cross-project plan resume.
- No sub-agent → sub-agent dispatch (only the orchestrating session dispatches; sub-agents always return to it).
- No cost-savings guarantees — sub-agents may downgrade silently; the verifier catches it.

## Limitations

- **Codebase analysis depth** — the analyzer caps at 100 files per signal type and depth-6 globs. Very deep or unusual project structures may not be fully detected.
- **Recipe library coverage** — `references/AGENT_PATTERNS.md` covers NestJS/DDD/hexagonal, Next.js App Router, FastAPI/Python, and common cross-cutting patterns. Unknown frameworks get a baseline-only roster.
- **ByteRover requirement** — the memory loop requires `brv` on PATH. Without it, agents are stateless across plan runs.
- **Plan files are user-wide** — `~/.claude/plans/` is shared across projects. Use project-prefixed filenames to avoid confusion.
