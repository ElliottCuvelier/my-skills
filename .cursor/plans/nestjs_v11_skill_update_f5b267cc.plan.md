---
name: NestJS v11 Skill Update
overview: Update the nestjs-domain-driven-hexagon skill from NestJS v9-era patterns to NestJS v11 / Prisma v7 current best practices, addressing breaking changes in @nestjs/cqrs, Express v5, Prisma generator config, and event-emitter.
todos:
  - id: prisma-v7-schema
    content: 'Update PRISMA-ADAPTER.md: generator config (prisma-client + moduleFormat cjs + output), PrismaService pattern, all @prisma/client imports'
    status: completed
  - id: cqrs-v11-types
    content: 'Update CQRS-EVENTS.md and LAYERS.md: add note about ICommandHandler/IQueryHandler type alias change in @nestjs/cqrs v11'
    status: completed
  - id: express-v5-note
    content: Add Express v5 route syntax note to LAYERS.md Interface Adapters section
    status: completed
  - id: prisma-imports-other-files
    content: Update @prisma/client import paths in HEXAGONAL-NESTJS.md, LAYERS.md, TESTING.md, PERSISTENCE-PATTERNS.md
    status: completed
  - id: skill-md-compat
    content: Add version compatibility note to SKILL.md (NestJS v11+, Prisma v7+, Node v18+, TS v5+)
    status: completed
  - id: final-review
    content: 'Final review pass: verify all code examples compile conceptually with NestJS v11 + Prisma v7 + @nestjs/cqrs v11'
    status: completed
isProject: false
---

# NestJS v11 Compatibility Update for Skill

## Version Gap Summary

The Sairyss/domain-driven-hexagon repo uses **NestJS v9** (2022). The current latest is **NestJS v11.1.17** (March 2026). Two major version jumps with the following breaking changes affecting our skill:

## Changes Required

### 1. Prisma v7 Generator Config and Setup ([PRISMA-ADAPTER.md](skills/nestjs-domain-driven-hexagon/references/PRISMA-ADAPTER.md))

**What changed:** Prisma v7 ships as ESM by default. NestJS is CommonJS.

- Update generator provider: `"prisma-client-js"` -> `"prisma-client"`
- Add `moduleFormat = "cjs"` to generator block (required for NestJS compatibility)
- Add `output = "../src/generated/prisma"` (new recommended pattern)
- Update `PrismaService` import path from `'@prisma/client'` to the generated output path
- Add a compatibility note about Prisma v7+ ESM changes
- Update all `import { ... } from '@prisma/client'` references throughout the file

**Current schema (line ~131):**

```prisma
generator client {
  provider = "prisma-client-js"
}
```

**Updated:**

```prisma
generator client {
  provider     = "prisma-client"
  output       = "../src/generated/prisma"
  moduleFormat = "cjs"
}
```

### 2. @nestjs/cqrs v11 Type Alias Change ([CQRS-EVENTS.md](skills/nestjs-domain-driven-hexagon/references/CQRS-EVENTS.md), [LAYERS.md](skills/nestjs-domain-driven-hexagon/references/LAYERS.md))

**What changed:** `ICommandHandler` and `IQueryHandler` changed from interfaces to type aliases in @nestjs/cqrs v11. Using `implements ICommandHandler<T, R>` with generic params on abstract base classes now causes a TypeScript error.

- Review all `implements ICommandHandler` / `implements IQueryHandler` usages across CQRS-EVENTS.md and LAYERS.md
- Our current examples use `implements ICommandHandler` without generics, which should still work, but add a note about the v11 change
- Add guidance: if users create abstract base handler classes with generics, they should drop the `implements` clause

**Files affected:**

- [CQRS-EVENTS.md](skills/nestjs-domain-driven-hexagon/references/CQRS-EVENTS.md) lines ~159, ~285 (command/query handler examples)
- [LAYERS.md](skills/nestjs-domain-driven-hexagon/references/LAYERS.md) lines ~194, ~237 (handler examples)

### 3. Express v5 Route Syntax Note ([LAYERS.md](skills/nestjs-domain-driven-hexagon/references/LAYERS.md), [CHEATSHEET.md](skills/nestjs-domain-driven-hexagon/references/CHEATSHEET.md))

**What changed:** NestJS v11 uses Express v5 by default. Wildcard routes must use named wildcards (`{*splat}` instead of `*`).

- Our skill doesn't use wildcard routes in examples, so code is unaffected
- Add a brief note in LAYERS.md Interface Adapters section about Express v5 route syntax
- Mention in CHEATSHEET.md anti-patterns or common gotchas

### 4. Prisma Import Path Updates (multiple files)

**What changed:** With Prisma v7 custom output, imports change from `@prisma/client` to the generated path.

Files with `@prisma/client` imports to update:

- [PRISMA-ADAPTER.md](skills/nestjs-domain-driven-hexagon/references/PRISMA-ADAPTER.md) -- ~10 occurrences
- [HEXAGONAL-NESTJS.md](skills/nestjs-domain-driven-hexagon/references/HEXAGONAL-NESTJS.md) -- mapper example (line ~375)
- [LAYERS.md](skills/nestjs-domain-driven-hexagon/references/LAYERS.md) -- query handler PrismaService import

Strategy: Update to show `from '@generated/prisma'` with a tsconfig path alias, keeping it clean. Add a note about configuring the path alias.

### 5. @nestjs/event-emitter v3 Note ([DDD-TACTICAL.md](skills/nestjs-domain-driven-hexagon/references/DDD-TACTICAL.md), [CQRS-EVENTS.md](skills/nestjs-domain-driven-hexagon/references/CQRS-EVENTS.md))

**What changed:** v3 requires @nestjs/common ^10.0.0 || ^11.0.0. Breaking change with durable event subscribers.

- Add a brief version compatibility note
- Our usage pattern (`@OnEvent(EventName, { async: true, promisify: true })`) is unaffected

### 6. PrismaService Lifecycle Hooks ([PRISMA-ADAPTER.md](skills/nestjs-domain-driven-hexagon/references/PRISMA-ADAPTER.md))

**What changed:** Latest NestJS Prisma recipe no longer shows `OnModuleInit`/`OnModuleDestroy` hooks. Prisma v7 handles connections automatically.

- Update `PrismaService` to remove lifecycle hooks (or keep them as optional with a note)
- Update constructor to use the simplified pattern

### 7. SKILL.md Version Compatibility Note ([SKILL.md](skills/nestjs-domain-driven-hexagon/SKILL.md))

- Add a "Compatibility" section or note indicating this skill targets NestJS v11+ / Prisma v7+
- Mention minimum Node.js v18, TypeScript v5+

### 8. oxide.ts Compatibility

**No changes needed.** oxide.ts v1.1.0 is the latest, backward compatible with v1.0.5 used in Sairyss. All `Result`, `Ok`, `Err`, `match` patterns remain identical.

## Files Unchanged

- [DDD-STRATEGIC.md](skills/nestjs-domain-driven-hexagon/references/DDD-STRATEGIC.md) -- no framework-version-specific code
- [PERSISTENCE-PATTERNS.md](skills/nestjs-domain-driven-hexagon/references/PERSISTENCE-PATTERNS.md) -- ORM-agnostic by design (update Prisma error code in conflict detection table only)
- [TESTING.md](skills/nestjs-domain-driven-hexagon/references/TESTING.md) -- test patterns are version-stable (minor Prisma import path update only)
