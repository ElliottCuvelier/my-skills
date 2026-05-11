# Agent Patterns Reference

This is the skill's **signal → agent recipe** library. When `analyze_codebase.py`
detects a signal, Claude reads this table to decide which agents to propose.

This is **guidance, not hardcoded composition**. Claude reasons over the snapshot
and this table to produce a tailored roster for the actual codebase, combining
recipes as appropriate (e.g., NestJS + Prisma + BullMQ → combine 3-4 recipes).

## How to read this table

| Column | Meaning |
|--------|---------|
| Signal | The `analyze_codebase.py` signal key that triggers this recipe |
| Agent | Suggested agent name (project-prefixed recommended, e.g., `<project>-domain-modeler`) |
| Role | `writer`, `verifier` (read-only), or `scaffolder` |
| Model | Recommended default model tier |
| Scope hint | Directory glob for agent routing (matches todos' `files:` list) |
| ByteRover scope | Subtree under `.brv/context-tree/` for this agent's curates |
| Curate when | Concise trigger for curating — also fills `{{CURATE_WHEN}}` in the loop fragment |
| When invoked | One-line description of what this agent does |

---

## NestJS / DDD / Hexagonal

| Signal | Agent | Role | Model | Scope hint | ByteRover scope | Curate when | When invoked |
|--------|-------|------|-------|------------|----------------|-------------|-------------|
| `ddd_entities` (≥ 3) | `domain-modeler` | writer | sonnet | `modules/*/domain/` | `architecture/<module>/domain_model/` | a new entity, VO, or domain invariant is introduced | Write entities, VOs, and domain events; enforces rich-domain (no anemic models) |
| `ddd_entities` (≥ 3) + `hexagonal_domain` | `hexagon-verifier` | verifier | haiku | `modules/*/` | `architecture/patterns/` | a new layer-violation pattern is observed | Check import direction (domain → nothing), naming conventions, layer boundaries; reports `VERIFIED:` / `VIOLATION:` |
| `cqrs_handlers` (≥ 2) | `command-handler-scaffolder` | scaffolder | sonnet | `modules/*/application/` | `architecture/patterns/` | a new CQRS scaffolding pattern is established | Generate command/query/handler/result triplets following project conventions |
| `bullmq_processors` (≥ 1) | `worker-builder` | writer | sonnet | `**/*.processor.ts` | `architecture/<module>/integrations/` | a new job-queue pattern or retry policy is introduced | Create BullMQ processor classes + queue registration + error handling |
| `integration_events` (≥ 1) | `integration-event-handler` | writer | sonnet | `**/integration-events/` | `architecture/<module>/integrations/` | a new integration event schema or handler pattern is established | Implement Standard Webhooks integration event handlers with proper idempotency |
| `prisma_schema` present | `prisma-migrator` | writer | sonnet | `prisma/` | `architecture/patterns/` | a schema migration pattern or convention is introduced | Run `prisma migrate dev`, validate schema diffs, handle enum additions safely |

## Next.js App Router

| Signal | Agent | Role | Model | Scope hint | ByteRover scope | Curate when | When invoked |
|--------|-------|------|-------|------------|----------------|-------------|-------------|
| `server_actions` or `api_routes_app` | `server-action-builder` | writer | sonnet | `app/**/` | `architecture/patterns/` | a new server action pattern or data mutation strategy is established | Write Next.js server actions with proper `use server`, validation, and error handling |
| `server_actions` or `api_routes_app` | `rsc-boundary-verifier` | verifier | haiku | `app/**/` | `architecture/patterns/` | a new server/client boundary violation pattern is observed | Verify RSC vs client component boundary correctness; check for `use client` / `use server` errors |

## FastAPI / Python

| Signal | Agent | Role | Model | Scope hint | ByteRover scope | Curate when | When invoked |
|--------|-------|------|-------|------------|----------------|-------------|-------------|
| `fastapi_routers` (≥ 1) | `route-handler-builder` | writer | sonnet | `**/routers/` | `architecture/patterns/` | a new endpoint pattern, dependency injection pattern, or auth approach is introduced | Add FastAPI route handlers with proper dependencies, request/response models, and error handling |
| `fastapi_schemas` (≥ 1) | `pydantic-modeler` | writer | sonnet | `**/schemas/` | `architecture/patterns/` | a new Pydantic model validation pattern is introduced | Define Pydantic v2 models with proper field validation, discriminated unions, and serializers |
| `alembic` in ORMs | `alembic-migrator` | writer | sonnet | `alembic/` or `migrations/` | `architecture/patterns/` | a new migration pattern is introduced | Generate and apply Alembic migrations; handle enum and constraint changes safely |

## Cross-cutting (any project)

| Signal | Agent | Role | Model | Scope hint | ByteRover scope | Curate when | When invoked |
|--------|-------|------|-------|------------|----------------|-------------|-------------|
| Any test runner detected | `test-runner` | verifier | haiku | `test/` or `**/*.spec.ts` | (no scope) | a new test helper pattern or test convention is established | Run the project's test suite scoped to changed files; return root-cause summary on failure |
| `linear-wi` in MCP integrations | `linear-issue-syncer` | writer | haiku | (no scope) | (no scope) | a new Linear workflow convention is discovered | Sync plan completion to Linear: add `Linear: ENG-###` trailers to git commits, update issue status |
| Auth/webhook/secrets paths detected (files named `auth.*`, `webhook.*`, `jwt.*`, `secret.*`) | `security-reviewer` | verifier | sonnet | (path-based) | `architecture/patterns/` | a new security pattern or anti-pattern is observed | Review webhook auth, JWT handling, OAuth flows, and secret exposure; reports `PASS:` / `RISK:` / `CRITICAL:` |
| Monorepo (`is_monorepo: true`) | `workspace-scaffolder` | scaffolder | sonnet | (workspace root) | `architecture/patterns/` | a new monorepo configuration pattern is introduced | Add new workspace packages or apps; update root configs (turbo, nx, pnpm workspace) |
| `drizzle` in ORMs | `drizzle-migrator` | writer | sonnet | `**/*.schema.ts` | `architecture/patterns/` | a new Drizzle schema convention is introduced | Apply Drizzle schema changes with `drizzle-kit generate` + `drizzle-kit migrate` |

## Baseline (always generated, regardless of signals)

These are always written alongside the project-specific roster as fallback for
todos that don't match any project agent's scope_hint.

| Agent | Model | Purpose |
|-------|-------|---------|
| `impl-haiku` | haiku | Generic cheap implementer — bulk changes, typo fixes, simple refactors |
| `impl-sonnet` | sonnet | Generic balanced implementer — default for most implementation work |
| `impl-opus` | opus | Generic premium implementer — complex logic, escape hatch |
| `impl-inherit` | inherit | Same model as orchestrator — for steps needing full planning-tier reasoning |
| `verifier` | haiku | Read-only verification after each step |
| `memory-curator` | inherit | End-of-plan consolidation pass |

## Roster composition guidelines

When composing a roster, apply these rules:

1. **Include signals ≥ threshold.** Only add recipe agents when the signal count is high enough to indicate a real pattern (e.g., `ddd_entities` ≥ 3; `bullmq_processors` ≥ 1).
2. **Avoid redundancy.** If the project already has agents (from `existing_agents` in the snapshot), don't propose duplicates. Register existing agents; propose complementary ones.
3. **Cap at ~8 project-specific agents.** Beyond that, the roster becomes unwieldy. Focus on the highest-frequency work patterns.
4. **Name with project prefix.** Proposed agent names should include a project slug prefix (e.g., `wi-be-domain-modeler`) so they're recognizable in multi-project contexts. Let the user confirm the prefix in Q8.
5. **Don't invent agents.** Propose only agents from this table or obvious derivatives. "Unknown architecture" → greenfield fallback (baseline only).
