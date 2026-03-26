---
name: Prisma schema colocation
overview: Split the monolithic Prisma schema into per-aggregate `.prisma` files co-located alongside repositories in the module's new `infrastructure/persistence/` directory, and rename `database/` to `infrastructure/persistence/` with `infrastructure/adapters/` for external services.
todos:
  - id: prisma-adapter
    content: 'Update PRISMA-ADAPTER.md: add prisma.config.ts, split example schema into per-aggregate files, update generator output, update all code example paths from database/ to infrastructure/persistence/'
    status: completed
  - id: skill-main
    content: 'Update SKILL.md: directory structure, decision tree, building blocks table, implementation order steps'
    status: completed
  - id: layers
    content: 'Update LAYERS.md: infrastructure file conventions block, composition root imports'
    status: completed
  - id: hexagonal
    content: 'Update HEXAGONAL-NESTJS.md: port placement table, adapter examples, mapper placement'
    status: completed
  - id: persistence-patterns
    content: 'Update PERSISTENCE-PATTERNS.md: port extension path, file conventions'
    status: completed
  - id: cheatsheet
    content: 'Update CHEATSHEET.md: decision trees, file naming table, new feature checklist, DI wiring references'
    status: completed
  - id: cqrs-events
    content: 'Update CQRS-EVENTS.md: command handler import paths'
    status: completed
  - id: ddd-tactical
    content: 'Update DDD-TACTICAL.md: event handler import path for wallet repository port'
    status: completed
  - id: ddd-strategic
    content: 'Update DDD-STRATEGIC.md: infrastructure adapter path, user repository import'
    status: completed
  - id: testing
    content: 'Update TESTING.md: repository integration test import paths'
    status: completed
isProject: false
---

# Prisma Schema Colocation and Infrastructure Restructure

## Two Changes

1. **Split Prisma schema per aggregate, co-located in `src/` alongside repositories** -- Use Prisma v7's `prisma.config.ts` with `schema: "src/"` so `.prisma` files discovered anywhere under `src/` are automatically combined. Each module owns its aggregate's schema file.
2. **Rename `database/` to `infrastructure/persistence/`** and use `infrastructure/adapters/` for external service adapters.

## New Directory Structure

```
prisma.config.ts                           # Prisma v7 config: schema: "src/"
prisma/
├── migrations/                            # Migrations stay here (configured in prisma.config.ts)
└── seed.ts                                # Seed data
src/
├── schema.prisma                          # Generator + datasource blocks ONLY
├── modules/
│   └── {module-name}/
│       ├── {module-name}.module.ts
│       ├── {module-name}.di-tokens.ts
│       ├── {module-name}.mapper.ts
│       ├── domain/
│       │   ├── {entity}.entity.ts
│       │   ├── value-objects/
│       │   └── events/
│       ├── commands/
│       ├── queries/
│       ├── infrastructure/
│       │   ├── persistence/
│       │   │   ├── {entity}.repository.port.ts
│       │   │   ├── {entity}.repository.ts
│       │   │   └── {aggregate}.prisma         # Per-aggregate Prisma schema
│       │   └── adapters/                      # External service adapters (optional)
│       │       ├── {service}.port.ts
│       │       └── {service}.adapter.ts
│       └── dtos/
└── libs/
    ├── ddd/
    ├── db/
    ├── api/
    ├── ports/
    └── exceptions/
```

## Key Prisma Setup Changes

In [PRISMA-ADAPTER.md](skills/nestjs-domain-driven-hexagon/references/PRISMA-ADAPTER.md):

- Add `prisma.config.ts` example with `schema: "src/"` and `migrations.path: "prisma/migrations"`
- Move generator + datasource to `src/schema.prisma` (no models here)
- Replace the monolithic schema example with per-aggregate `.prisma` files:
  - `src/modules/user/infrastructure/persistence/user.prisma` containing `UserRole` enum and `User` model
  - `src/modules/wallet/infrastructure/persistence/wallet.prisma` containing `Wallet` model
- Update the generator `output` path from `"../src/generated/prisma"` to `"./generated/prisma"` (now relative to `src/`)
- Update all code examples referencing `prisma/schema.prisma` to the new locations
- Update migrations section to reference `prisma.config.ts`

## Files to Update (with match counts)

Every file below has path references (`database/`, `prisma/schema.prisma`, import paths) that need updating to the new structure:

| File                                                                                              | Changes                                                                                                         |
| ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| [SKILL.md](skills/nestjs-domain-driven-hexagon/SKILL.md)                                          | Directory structure diagram, decision tree, building blocks table, implementation order                         |
| [PRISMA-ADAPTER.md](skills/nestjs-domain-driven-hexagon/references/PRISMA-ADAPTER.md)             | Schema conventions, generator config, example schema, prisma.config.ts, repo example, module wiring, migrations |
| [PERSISTENCE-PATTERNS.md](skills/nestjs-domain-driven-hexagon/references/PERSISTENCE-PATTERNS.md) | Port extension example path, file conventions                                                                   |
| [LAYERS.md](skills/nestjs-domain-driven-hexagon/references/LAYERS.md)                             | Infrastructure file conventions block, composition root imports                                                 |
| [HEXAGONAL-NESTJS.md](skills/nestjs-domain-driven-hexagon/references/HEXAGONAL-NESTJS.md)         | Port placement table, adapter example imports, mapper placement diagram                                         |
| [CHEATSHEET.md](skills/nestjs-domain-driven-hexagon/references/CHEATSHEET.md)                     | Decision tree "database/" references, file naming table, new feature checklist                                  |
| [TESTING.md](skills/nestjs-domain-driven-hexagon/references/TESTING.md)                           | Repository integration test import paths                                                                        |
| [CQRS-EVENTS.md](skills/nestjs-domain-driven-hexagon/references/CQRS-EVENTS.md)                   | Command handler import of `../../database/user.repository.port`                                                 |
| [DDD-TACTICAL.md](skills/nestjs-domain-driven-hexagon/references/DDD-TACTICAL.md)                 | Event handler import of `../../database/wallet.repository.port`                                                 |
| [DDD-STRATEGIC.md](skills/nestjs-domain-driven-hexagon/references/DDD-STRATEGIC.md)               | Infrastructure adapter path, user repository import                                                             |

## Specific Path Replacements

All occurrences of these patterns will be updated:

- `database/{entity}.repository.port.ts` -> `infrastructure/persistence/{entity}.repository.port.ts`
- `database/{entity}.repository.ts` -> `infrastructure/persistence/{entity}.repository.ts`
- `../../database/` (in imports) -> `../../infrastructure/persistence/`
- `from './database/` -> `from './infrastructure/persistence/`
- `modules/{module}/infrastructure/` (old optional dir) -> merged into the new `infrastructure/` structure
- `prisma/schema.prisma` -> `src/schema.prisma` (base) + `src/modules/{module}/infrastructure/persistence/{aggregate}.prisma` (models)

## Important Considerations

- **Prisma v7 `prisma.config.ts`**: This is the recommended way to configure multi-file schema in v7 (no `previewFeatures` flag needed since GA in v6.7.0)
- **Cross-file model references**: Prisma automatically resolves references across `.prisma` files in the schema directory tree -- e.g., `Wallet` can reference `User` even though they're in different files
- **Migration command**: `npx prisma migrate dev` will still work because `prisma.config.ts` points to the correct schema directory and migrations path
- **Repository port stays in infrastructure/persistence/**: While the port conceptually belongs to the domain, keeping it co-located with the implementation and schema is the established convention for this skill (pragmatism over purity)
