# ByteRover Scope Conventions

## Context tree layout

```
.brv/context-tree/
├── architecture/               # Codebase-shaped knowledge (existing convention)
│   ├── <module-name>/          # Per-module — filled by domain/specialist agents
│   │   ├── domain_model/       # Entities, VOs, aggregate rules
│   │   ├── patterns/           # Reusable patterns for this module
│   │   └── integrations/       # External system mappings
│   └── patterns/               # Cross-cutting patterns (applies to many modules)
│
├── orchestration/              # Orchestrator-specific knowledge
│   ├── plans/                  # Plan-level decisions (themed, NOT per-plan-slug)
│   ├── roster/                 # The project's agent set and rationale
│   ├── tiers/                  # Tier-selection learnings
│   │                           # ("haiku fails on this type of work because...")
│   └── failures/               # Downgrade events, escalations, root causes
│
└── process/                    # Cross-plan orchestrator-loop knowledge
    ├── verification/           # Patterns where verifier repeatedly flags issues
    └── false-completion/       # Patterns where a step appears done but isn't
```

## Three rules

1. **Codebase-shaped, not agent-name-shaped.**
   - Use `architecture/auth/` not `agents/impl-haiku/`.
   - Curates describe architectural knowledge, not implementation provenance.
   - Don't write "this code was produced by impl-haiku" — that's implementation metadata, not knowledge.

2. **No per-plan-slug subtrees.**
   - `plans/<slug>/` accumulates forever and `brv search --scope plans/` becomes useless.
   - Instead, use stable themed paths under `orchestration/plans/` and let ByteRover's auto-categorization group related plan decisions together.

3. **Per-module scopes use discovered module names.**
   - `analyze_codebase.py` detects module directory names at first-run.
   - Agent generation writes the discovered module names into `{{AGENT_SCOPE_FLAG}}`.
   - If no module name is known yet (greenfield), omit `--scope` from `brv search`.

## Per-agent scope assignment examples

| Agent | Scope hint | ByteRover scope |
|-------|------------|----------------|
| `domain-modeler` | `modules/*/domain/` | `architecture/<module-name>/domain_model/` |
| `hexagon-verifier` | `modules/*/` | `architecture/patterns/` |
| `prisma-migrator` | `prisma/` | `architecture/patterns/` |
| `worker-builder` | `**/*.processor.ts` | `architecture/<module>/integrations/` |
| `test-runner` | `test/` or `**/*.spec.ts` | (no scope — test patterns are cross-cutting) |
| `impl-haiku/sonnet/opus` | (no scope) | (no scope — generic; curates go wherever relevant) |
| `memory-curator` | (no scope) | `orchestration/plans/` (for plan-level curates) |
| orchestrating session | (no scope) | `orchestration/plans/` + `orchestration/tiers/` + `orchestration/failures/` |

## ByteRover search cost

| Command | Cost | When to use |
|---------|------|-------------|
| `brv search` | Free (BM25) | Always — every sub-agent, every step |
| `brv query` | LLM call | Orchestrator only, at most 1-2 per plan, only when `search` returns thin results |
| `brv curate` | LLM call | When something genuinely new was learned |
| `brv review pending` | Free | Orchestrator at plan end |
