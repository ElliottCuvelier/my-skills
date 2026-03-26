---
name: nestjs-domain-driven-hexagon
description: NestJS backend architecture combining DDD, Clean Architecture, and Hexagonal (ports and adapters) patterns with Prisma persistence. Proactively apply when designing NestJS APIs, microservices, or scalable backend structure. Triggers on NestJS DDD, hexagonal architecture, ports and adapters, entities, value objects, domain events, CQRS, repository pattern, Prisma repository, aggregate root, bounded contexts, NestJS modules, NestJS CQRS, NestJS DI tokens, domain-driven design with NestJS, onion architecture NestJS, clean architecture NestJS. Use when scaffolding NestJS modules, implementing domain models, setting up Prisma with hexagonal architecture, creating command/query handlers, designing module boundaries, or structuring a new NestJS project beyond simple CRUD.
---

# NestJS Domain-Driven Hexagonal Architecture

NestJS backend architecture combining DDD tactical patterns, Clean Architecture dependency rules, and Hexagonal ports/adapters with Prisma persistence.

## Compatibility

| Dependency              | Minimum Version | Notes                                                              |
| ----------------------- | --------------- | ------------------------------------------------------------------ |
| NestJS                  | v11+            | Express v5 default, updated CQRS type aliases                      |
| Prisma                  | v7+             | Requires `moduleFormat = "cjs"` in generator config                |
| Node.js                 | v18+            | v20 LTS recommended                                                |
| TypeScript              | v5+             |                                                                    |
| `@nestjs/cqrs`          | v11+            | `ICommandHandler`/`IQueryHandler` are type aliases, not interfaces |
| `@nestjs/event-emitter` | v3+             | Requires `@nestjs/common` ^10 or ^11                               |
| `oxide.ts`              | v1.0+           | Result pattern (`Ok`/`Err`/`match`)                                |

## When to Use (and When NOT to)

| Use When                                           | Skip When                                |
| -------------------------------------------------- | ---------------------------------------- |
| Complex business domain with many rules            | Simple CRUD, few business rules          |
| Long-lived NestJS system (years of maintenance)    | Prototype, MVP, throwaway code           |
| Team of 3+ developers                              | Solo developer, small team (1-2)         |
| Multiple entry points (REST, GraphQL, CLI, events) | Single REST API with no business logic   |
| Need to swap infrastructure (DB, broker)           | Fixed infrastructure, unlikely to change |
| High test coverage required                        | Quick scripts, internal tools            |

**Start simple. Evolve complexity only when needed.** Most systems don't need full CQRS or Event Sourcing from day one.

## CRITICAL: The Dependency Rule

Dependencies point **inward only**. Outer layers depend on inner layers, never the reverse.

```
Infrastructure → Application → Domain
   (adapters)     (use cases)    (core)
```

**Violations to catch:**

- Domain importing Prisma, HTTP, or NestJS framework modules
- Controllers calling repositories directly (bypassing command/query handlers)
- Entities depending on application services
- Cross-module direct imports (bypassing module boundaries)

**Design validation:** "Create your application to work without either a UI or a database" -- Alistair Cockburn. If you can run your domain logic from tests with no infrastructure, your boundaries are correct.

## Quick Decision Trees

### "Where does this code go?"

```
Where does it go?
├─ Pure business logic, no I/O           → domain/
├─ Orchestrates domain + has side effects → commands/ or queries/ (application layer)
├─ Talks to external systems              → database/ or infrastructure/
├─ Defines HOW to interact (interface)    → port (*.repository.port.ts or libs/ports/)
├─ Implements a port                      → adapter (*.repository.ts, infrastructure/)
└─ Handles HTTP/GraphQL/CLI input         → *.http.controller.ts, *.graphql-resolver.ts
```

### "Is this an Entity or Value Object?"

```
Entity or Value Object?
├─ Has unique identity that persists → Entity
├─ Defined only by its attributes    → Value Object
├─ "Is this THE same thing?"         → Entity (identity comparison)
└─ "Does this have the same value?"  → Value Object (structural equality)
```

### "Should this be its own Aggregate?"

Apply Vernon's four rules of thumb:

```
Aggregate boundaries?
├─ Is there a true invariant that requires transactional consistency?
│   ├─ Yes → Same aggregate (Rule 1: model true invariants)
│   └─ No, it's compositional convenience → Separate aggregates
├─ Can consistency be delayed by seconds/minutes?
│   ├─ Yes → Separate aggregates + domain events (Rule 4: eventual consistency)
│   └─ No, must be immediate → Same aggregate
├─ Is it the user's job to make this consistent, or the system's?
│   ├─ User's job → Transactional (same aggregate)
│   └─ System's job → Eventual consistency (separate aggregates)
├─ Referenced by ID only?                        → Separate aggregates (Rule 3)
└─ >10 entities in aggregate?                    → Split it (Rule 2: design small)
```

**Rule:** One aggregate per transaction. Cross-aggregate consistency via domain events (eventual consistency). See [references/AGGREGATE-DESIGN.md](references/AGGREGATE-DESIGN.md) for the full methodology.

## NestJS Module = Bounded Context

Each NestJS `@Module()` maps to a bounded context. Treat module internals as private -- only export what other modules genuinely need.

- Module providers are private by default. Export only application services or specific ports that other modules need.
- Modules communicate through domain events (`@OnEvent()`), the `CommandBus`, or explicitly exported services -- never through direct imports of another module's internal files.
- Keep modules small and focused. If a module grows beyond ~15-20 providers, consider splitting it along subdomain lines.

## Directory Structure

```
src/
├── modules/
│   └── {module-name}/
│       ├── {module-name}.module.ts          # NestJS module (composition root)
│       ├── {module-name}.di-tokens.ts       # DI token constants
│       ├── {module-name}.mapper.ts          # Domain <-> Persistence mapper
│       ├── domain/
│       │   ├── {entity}.entity.ts           # Aggregate root / entities
│       │   ├── {entity}.types.ts            # Domain types and interfaces
│       │   ├── {entity}.errors.ts           # Domain error classes
│       │   ├── value-objects/
│       │   │   └── {vo}.value-object.ts
│       │   └── events/
│       │       └── {event}.domain-event.ts
│       ├── commands/
│       │   └── {use-case}/
│       │       ├── {use-case}.command.ts            # Command DTO
│       │       ├── {use-case}.service.ts            # Command handler
│       │       ├── {use-case}.http.controller.ts    # HTTP entry point
│       │       └── {use-case}.request.dto.ts        # Request validation
│       ├── queries/
│       │   └── {query}/
│       │       ├── {query}.query-handler.ts
│       │       ├── {query}.http.controller.ts
│       │       └── {query}.request.dto.ts
│       ├── database/
│       │   ├── {entity}.repository.port.ts  # Repository interface (DRIVEN PORT)
│       │   └── {entity}.repository.ts       # Prisma implementation
│       └── dtos/
│           └── {entity}.response.dto.ts     # Response serialization
├── libs/
│   ├── ddd/                                 # Base classes (Entity, AggregateRoot, ValueObject, DomainEvent)
│   ├── api/                                 # Shared API utilities, response bases, interceptors
│   ├── ports/                               # Shared port interfaces (LoggerPort, etc.)
│   └── exceptions/                          # Base exception classes and error codes
└── main.ts
```

This structure uses **vertical slicing** -- each use case (command or query) gets its own directory containing the handler, controller, DTO, and command/query object. Files that change together live together.

## DDD Building Blocks

| Pattern             | Purpose                            | Layer             | Key Rule                             | File Naming                           |
| ------------------- | ---------------------------------- | ----------------- | ------------------------------------ | ------------------------------------- |
| **Entity**          | Identity + behavior                | Domain            | Equality by ID                       | `*.entity.ts`                         |
| **Value Object**    | Immutable data                     | Domain            | Equality by value, no setters        | `*.value-object.ts`                   |
| **Aggregate Root**  | Consistency boundary               | Domain            | Only root is referenced externally   | `*.entity.ts` (extends AggregateRoot) |
| **Domain Event**    | Record of change                   | Domain            | Past tense naming (`UserCreated`)    | `*.domain-event.ts`                   |
| **Repository Port** | Persistence abstraction            | Domain (port)     | Per aggregate, not per table         | `*.repository.port.ts`                |
| **Domain Service**  | Stateless cross-entity logic       | Domain            | When logic doesn't fit one entity    | `*.domain-service.ts`                 |
| **Command Handler** | Write use case orchestration       | Application       | One handler per command              | `*.service.ts`                        |
| **Query Handler**   | Read use case                      | Application       | Can bypass domain, query DB directly | `*.query-handler.ts`                  |
| **Controller**      | HTTP/GraphQL/CLI entry point       | Interface Adapter | Parses input, returns output         | `*.http.controller.ts`                |
| **Mapper**          | Domain <-> Persistence translation | Infrastructure    | Keeps domain ignorant of DB schema   | `*.mapper.ts`                         |

## Anti-Patterns (CRITICAL)

| Anti-Pattern                | Problem                                                         | Fix                                                                              |
| --------------------------- | --------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| **Anemic Domain Model**     | Entities are plain data bags, all logic in services             | Move behavior INTO entities and aggregates                                       |
| **Leaking Prisma Client**   | Domain layer imports `PrismaClient` or Prisma types             | Domain has ZERO infrastructure deps; use ports                                   |
| **God Module**              | One module with 50+ providers                                   | Split along subdomain boundaries                                                 |
| **Skipping DI Tokens**      | Injecting concrete repository classes directly                  | Use Symbol tokens + port interfaces for all adapters                             |
| **Cross-Module Imports**    | `import { UserEntity } from '../other-module/...'`              | Communicate via events, CommandBus, or exported services                         |
| **Repository per Entity**   | One repo for each entity in an aggregate                        | One repository per AGGREGATE root                                                |
| **CRUD Thinking**           | Modeling data tables, not business operations                   | Model domain behaviors and use cases                                             |
| **Skipping Ports**          | Controllers calling repositories directly                       | Always go through application layer (command/query handlers)                     |
| **Large-Cluster Aggregate** | Grouping all related objects into one aggregate for convenience | Split into separate aggregates connected by identity; model only true invariants |
| **Premature CQRS**          | Full event sourcing from day one                                | Start with simple command/query separation, evolve when needed                   |

## Implementation Order

1. **Discover the Domain** -- Event Storming, conversations with domain experts, identify aggregates and bounded contexts.
2. **Model the Domain** -- Entities, value objects, aggregates, domain events. No infrastructure code yet.
3. **Define Ports** -- Repository interfaces, external service interfaces. Place in `database/` and `libs/ports/`.
4. **Implement Use Cases** -- Command and query handlers in `commands/` and `queries/` directories.
5. **Add Adapters Last** -- Prisma repositories, HTTP controllers, mappers. Wire everything in the NestJS module.

**DDD is collaborative.** Modeling sessions with domain experts are as important as the code patterns.

## Reference Documentation

Read these reference files for detailed implementation guidance. Each covers a specific architectural concern.

| File                                                                     | Purpose                                                                      | Read When                                                      |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------- | -------------------------------------------------------------- |
| [references/LAYERS.md](references/LAYERS.md)                             | Complete layer specifications, composition root, dependency flow             | Setting up a new project or module structure                   |
| [references/DDD-TACTICAL.md](references/DDD-TACTICAL.md)                 | Entity, ValueObject, AggregateRoot, DomainEvent base classes with full code  | Implementing domain model classes                              |
| [references/DDD-STRATEGIC.md](references/DDD-STRATEGIC.md)               | Bounded contexts, context mapping, ubiquitous language                       | Designing module boundaries and inter-module communication     |
| [references/CQRS-EVENTS.md](references/CQRS-EVENTS.md)                   | Commands, queries, domain events, integration events                         | Implementing use cases with NestJS CQRS                        |
| [references/HEXAGONAL-NESTJS.md](references/HEXAGONAL-NESTJS.md)         | Ports, adapters, DI tokens, mapper pattern                                   | Wiring ports and adapters with NestJS DI                       |
| [references/PERSISTENCE-PATTERNS.md](references/PERSISTENCE-PATTERNS.md) | ORM-agnostic repository patterns, transaction management                     | Understanding the persistence architecture                     |
| [references/PRISMA-ADAPTER.md](references/PRISMA-ADAPTER.md)             | Prisma-specific repository implementation, schema conventions                | Implementing Prisma persistence layer                          |
| [references/AGGREGATE-DESIGN.md](references/AGGREGATE-DESIGN.md)         | Vernon's four rules of aggregate design, boundary discovery, BOTE estimation | Designing aggregate boundaries, splitting or sizing aggregates |
| [references/TESTING.md](references/TESTING.md)                           | Testing strategies per layer, architecture tests                             | Writing tests for any layer                                    |
| [references/CHEATSHEET.md](references/CHEATSHEET.md)                     | Quick decision guide, file naming, new feature checklist                     | Day-to-day development reference                               |

## Sources

### Primary Sources

- [The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html) -- Robert C. Martin (2012)
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/) -- Alistair Cockburn (2005)
- [Domain-Driven Design: The Blue Book](https://www.domainlanguage.com/ddd/blue-book/) -- Eric Evans (2003)
- [Implementing Domain-Driven Design](https://openlibrary.org/works/OL17392277W) -- Vaughn Vernon (2013)
- [Effective Aggregate Design Part I: Modeling a Single Aggregate](https://www.dddcommunity.org/wp-content/uploads/files/pdf_articles/Vernon_2011_1.pdf) -- Vaughn Vernon (2011)
- [Effective Aggregate Design Part II: Making Aggregates Work Together](https://www.dddcommunity.org/wp-content/uploads/files/pdf_articles/Vernon_2011_2.pdf) -- Vaughn Vernon (2011)
- [Effective Aggregate Design Part III: Gaining Insight Through Discovery](https://www.dddcommunity.org/wp-content/uploads/files/pdf_articles/Vernon_2011_3.pdf) -- Vaughn Vernon (2011)
- [Secure by Design](https://www.manning.com/books/secure-by-design) -- Dan Bergh Johnsson, Daniel Deogun, Daniel Sawano

### Pattern References

- [CQRS](https://martinfowler.com/bliki/CQRS.html) -- Martin Fowler
- [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html) -- Martin Fowler (PoEAA)
- [Unit of Work](https://martinfowler.com/eaaCatalog/unitOfWork.html) -- Martin Fowler (PoEAA)
- [Bounded Context](https://martinfowler.com/bliki/BoundedContext.html) -- Martin Fowler
- [Transactional Outbox](https://microservices.io/patterns/data/transactional-outbox.html) -- microservices.io

### NestJS Ecosystem

- [NestJS Documentation](https://docs.nestjs.com/)
- [NestJS CQRS Recipe](https://docs.nestjs.com/recipes/cqrs)
- [NestJS Event Emitter](https://docs.nestjs.com/techniques/events)
- [Prisma with NestJS](https://docs.nestjs.com/recipes/prisma)
