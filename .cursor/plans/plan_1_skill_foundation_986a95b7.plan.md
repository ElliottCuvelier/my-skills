---
name: 'Plan 1: Skill Foundation'
overview: Create the skill directory skeleton, write the main SKILL.md entry point, and the foundational LAYERS.md reference that defines the NestJS-specific layer structure and module organization.
todos:
  - id: create-skill-dir
    content: Create `skills/nestjs-domain-driven-hexagon/` directory with `references/` and `scripts/` subdirectories
    status: completed
  - id: write-skill-md
    content: Write SKILL.md with frontmatter, decision trees, directory structure, anti-patterns, reference table
    status: completed
  - id: write-layers-md
    content: Write references/LAYERS.md with 4-layer NestJS specification, composition root pattern, dependency flow diagram
    status: completed
isProject: false
---

# Plan 1: Skill Foundation and [SKILL.md](http://SKILL.md)

## Target Structure

```
skills/nestjs-domain-driven-hexagon/
├── SKILL.md
├── references/
│   └── LAYERS.md
└── scripts/
    (empty for now, populated in Plan 4)
```

## SKILL.md

The main entry point. Modeled after the clean-ddd-hexagonal SKILL.md structure but NestJS-specific and opinionated.

**Frontmatter:**

- `name: nestjs-domain-driven-hexagon`
- `description:` Aggressively trigger-friendly description covering: NestJS backend architecture, DDD, hexagonal, ports and adapters, entities, value objects, domain events, CQRS, repository pattern, Prisma, aggregate root, bounded contexts, NestJS modules, NestJS CQRS, NestJS DI. Use when scaffolding NestJS APIs, designing NestJS module structure, implementing domain models in NestJS, or setting up Prisma with hexagonal architecture.

**Body sections (following clean-ddd-hexagonal structure):**

1. **Title + one-liner** -- "NestJS backend architecture combining DDD tactical patterns, Clean Architecture dependency rules, and Hexagonal ports/adapters with Prisma persistence."
2. **When to Use / When NOT to** -- Table format. Use when: complex business domain, NestJS backend, team of 3+, multiple entry points, need testability. Skip when: simple CRUD, prototype/MVP, solo dev, GraphQL-only with no business logic.
3. **The Dependency Rule** -- Same core principle (Infrastructure -> Application -> Domain), but framed with NestJS module boundaries. Include the "Design validation" quote from Cockburn.
4. **Quick Decision Trees** -- 3 trees in ASCII:

- "Where does this code go?" (domain/ vs application/ vs infrastructure/ vs interface-adapters/)
- "Entity or Value Object?"
- "Should this be its own Aggregate?"

1. **NestJS Module = Bounded Context** -- Key differentiator from generic skill. Each NestJS module maps to a bounded context. Explain the `@Module()` boundary, private internals, public facade pattern via module exports.
2. **Directory Structure** -- NestJS-specific:

```
   src/
   ├── modules/
   │   └── {module-name}/
   │       ├── {module-name}.module.ts
   │       ├── {module-name}.di-tokens.ts
   │       ├── {module-name}.mapper.ts
   │       ├── domain/
   │       │   ├── {entity}.entity.ts
   │       │   ├── {entity}.types.ts
   │       │   ├── {entity}.errors.ts
   │       │   ├── value-objects/
   │       │   └── events/
   │       ├── commands/
   │       │   └── {use-case}/
   │       │       ├── {use-case}.command.ts
   │       │       ├── {use-case}.service.ts (command handler)
   │       │       ├── {use-case}.http.controller.ts
   │       │       └── {use-case}.request.dto.ts
   │       ├── queries/
   │       │   └── {query}/
   │       │       ├── {query}.query-handler.ts
   │       │       ├── {query}.http.controller.ts
   │       │       └── {query}.request.dto.ts
   │       ├── database/
   │       │   ├── {entity}.repository.port.ts
   │       │   └── {entity}.repository.ts (Prisma impl)
   │       └── dtos/
   │           └── {entity}.response.dto.ts
   ├── libs/
   │   ├── ddd/          (base classes: Entity, AggregateRoot, ValueObject, DomainEvent)
   │   ├── api/          (shared API utilities, response bases, exception interceptor)
   │   ├── ports/        (shared port interfaces: logger, etc.)
   │   └── exceptions/   (base exception classes)
   └── main.ts


```

1. **DDD Building Blocks Table** -- Same as clean-ddd-hexagonal but with NestJS file naming conventions (`.entity.ts`, `.value-object.ts`, `.domain-event.ts`, etc.)
2. **Anti-Patterns** -- NestJS-specific anti-patterns table:

- Anemic Domain Model (entities as plain interfaces, logic in `.service.ts`)
- Leaking Prisma Client (importing `PrismaClient` in domain layer)
- God Module (one module with 50+ providers)
- Skipping DI tokens (injecting concrete classes instead of port interfaces)
- Cross-module direct imports (bypassing module boundaries)

1. **Implementation Order** -- 5 steps, NestJS-framed
2. **Reference Documentation Table** -- Links to all reference files

## LAYERS.md

Complete specification of the 4-layer structure in NestJS context.

**Sections:**

1. **Domain Layer** -- Zero NestJS imports allowed (except possibly `@Inject` if absolutely needed). Contains entities, VOs, aggregates, domain events, domain services, repository port interfaces. File naming: `*.entity.ts`, `*.value-object.ts`, `*.domain-event.ts`, `*.errors.ts`.
2. **Application Layer** -- NestJS CQRS command/query handlers. Uses `@CommandHandler`, `@QueryHandler` decorators. Defines ports for driven adapters. Transaction boundaries live here. File naming: `*.service.ts` (handlers), `*.command.ts`, `*.query.ts`.
3. **Infrastructure Layer** -- Prisma repository implementations, Prisma schema, mappers, external API adapters. NestJS `@Injectable()` providers. DI token registration. File naming: `*.repository.ts`, `*.mapper.ts`, `*.prisma-schema`.
4. **Interface Adapters / Presentation Layer** -- NestJS controllers (`@Controller`), GraphQL resolvers (`@Resolver`), microservice handlers. Request/Response DTOs with `class-validator` and `@nestjs/swagger` decorators. File naming: `*.http.controller.ts`, `*.message.controller.ts`, `*.request.dto.ts`, `*.response.dto.ts`.
5. **Composition Root** -- The NestJS `@Module()` decorator as the composition root. DI token pattern: define tokens in `*.di-tokens.ts`, use `{ provide: TOKEN, useClass: ConcreteImpl }` in module providers. Show a complete module wiring example.
6. **Dependency Flow Diagram** -- Mermaid diagram showing NestJS-specific flow:
   Controller -> CommandBus -> CommandHandler -> Repository Port -> Prisma Repository -> Database
