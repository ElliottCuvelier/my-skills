---
name: 'Plan 2: Domain App Patterns'
overview: 'Create the core domain and application layer reference documents: DDD tactical building blocks (entities, value objects, aggregates), strategic DDD patterns (bounded contexts, modules), CQRS/events patterns, and hexagonal architecture with NestJS DI.'
todos:
  - id: write-ddd-tactical
    content: Write references/DDD-TACTICAL.md with Entity, ValueObject, AggregateRoot, DomainEvent base classes, domain services, domain errors, guards -- all with NestJS/TypeScript code examples
    status: completed
  - id: write-ddd-strategic
    content: Write references/DDD-STRATEGIC.md covering NestJS modules as bounded contexts, ubiquitous language, context mapping, subdomain classification
    status: completed
  - id: write-cqrs-events
    content: Write references/CQRS-EVENTS.md with NestJS CQRS command/query patterns, domain event flow, integration events, event sourcing guidance
    status: completed
  - id: write-hexagonal-nestjs
    content: Write references/HEXAGONAL-NESTJS.md covering ports as interfaces, adapters as Injectable providers, DI token pattern, adapter swapping, mapper pattern, request context
    status: completed
isProject: false
---

# Plan 2: Domain and Application Layer Patterns

## Files to Create

```
skills/nestjs-domain-driven-hexagon/
└── references/
    ├── DDD-TACTICAL.md
    ├── DDD-STRATEGIC.md
    ├── CQRS-EVENTS.md
    └── HEXAGONAL-NESTJS.md
```

## DDD-TACTICAL.md

NestJS/TypeScript implementation of DDD building blocks. Each section includes the concept, rules, and a concrete TypeScript code example using NestJS patterns.

**Sections:**

1. **Entity Base Class** -- Abstract generic `Entity<EntityProps>` with:

- `AggregateID` type alias (string UUID)
- `BaseEntityProps` (id, createdAt, updatedAt)
- Constructor validation via `Guard` utility
- Identity-based equality (`equals()`)
- `getProps()` returning frozen copy with base props
- `toObject()` for serialization
- Abstract `validate()` method for invariant enforcement
- Full TypeScript implementation (~60 lines)

1. **Value Object Base Class** -- Abstract generic `ValueObject<T>` with:

- Support for both composite VOs and domain primitives (`DomainPrimitive<T>`)
- Structural equality via `equals()`
- `unpack()` to extract raw value
- Immutability enforcement
- Abstract `validate()` for invariant checking
- Example: `Address` value object, `Email` domain primitive
- Guidance on when to use VOs vs plain types (pragmatic take: don't wrap every string)

1. **Aggregate Root** -- Extends `Entity`, adds domain event collection:

- `addEvent()`, `clearEvents()`, `publishEvents()` methods
- Integration with NestJS `EventEmitter2` from `@nestjs/event-emitter`
- Rule: one aggregate per transaction, cross-aggregate consistency via events
- Example: `UserEntity` as aggregate root with `create()` factory method
- Aggregate sizing heuristics (keep small, <10 entities, split if slow)

1. **Domain Events** -- Event base class with metadata:

- Auto-generated UUID, aggregateId, correlation/causation IDs, timestamp
- `RequestContextService` integration for tracing
- Past-tense naming convention (`UserCreatedDomainEvent`, `OrderPlacedDomainEvent`)
- Event handler pattern using `@OnEvent()` decorator
- Domain Events vs Integration Events distinction

1. **Domain Services** -- When entity logic doesn't fit one aggregate:

- Stateless, operates on multiple entities/aggregates
- Injected into application services, not controllers
- Example: `PricingService`, cross-aggregate validation

1. **Domain Errors** -- Result-based error handling pattern:

- Custom error class hierarchy (`DomainError` -> `UserAlreadyExistsError`)
- `Result<T, E>` pattern using `oxide.ts` (Ok/Err)
- Error mapping in controllers: domain error -> HTTP status
- When to return errors vs throw exceptions (recoverable vs unrecoverable)

1. **Guards and Invariants** -- Two-tier validation:

- First tier: DTO validation with `class-validator` (filtration)
- Second tier: Domain object guards (failsafe, invariants)
- `Guard` utility class for common checks (isEmpty, isNegative, etc.)
- Guarding vs validating distinction

## DDD-STRATEGIC.md

Strategic patterns mapped to NestJS module system.

**Sections:**

1. **NestJS Module as Bounded Context** -- Each `@Module()` represents a bounded context:

- Module encapsulation: private providers vs exported providers
- Module facade pattern: only export application services or specific ports
- Example: `UserModule` and `WalletModule` as separate bounded contexts
- `forRoot()` / `forFeature()` patterns for shared infrastructure

1. **Ubiquitous Language** -- How to enforce in NestJS:

- File naming conventions reflecting domain language
- Type names matching business concepts
- Avoid technical names in domain layer (no `UserTable`, no `UserDTO` in domain)

1. **Context Mapping** -- Inter-module communication patterns:

- **Anti-Corruption Layer**: adapter between modules, translate foreign concepts
- **Shared Kernel**: `src/libs/` for truly shared base classes (Entity, VO, etc.)
- **Event-based integration**: Module A emits domain event, Module B handles it via `@OnEvent()`
- **Command Bus**: cross-module commands via NestJS CQRS `CommandBus`
- Avoid direct imports between module directories

1. **Subdomain Classification** -- Core vs Supporting vs Generic:

- Core: your competitive advantage, full DDD treatment
- Supporting: necessary but not differentiating, simpler patterns OK
- Generic: use off-the-shelf (auth, logging, file upload)

## CQRS-EVENTS.md

NestJS CQRS module patterns and event handling.

**Sections:**

1. **CQRS Overview** -- Write side (Commands) vs Read side (Queries):

- Mermaid diagram of NestJS CQRS flow
- `@nestjs/cqrs` package: `CommandBus`, `QueryBus`, `EventBus`
- When to use CQRS vs simple service methods (pragmatic guidance)

1. **Commands** -- State-changing operations:

- `Command` base class (extends a simple base with metadata)
- `@CommandHandler` decorator pattern
- Command handler as the "use case" / application service
- One handler per command, one command per use case
- Return `Result<AggregateID, DomainError>` not raw data
- Full example: `CreateUserCommand` + `CreateUserService`

1. **Queries** -- Read-only operations:

- `Query` base class
- `@QueryHandler` decorator
- Key insight: queries can bypass domain layer entirely, query DB directly
- Can use Prisma client directly in query handlers (no repository abstraction needed for reads)
- Pagination pattern with `PaginatedQueryParams`

1. **Domain Event Flow** -- In-process event handling:

- Aggregate collects events via `addEvent()`
- Repository publishes events after successful persistence
- `@OnEvent('UserCreatedDomainEvent')` handlers in other modules
- Transaction wrapping: all side effects in one transaction
- Pitfall: avoid long event chains (Command -> Event -> Event -> Event)

1. **Integration Events** -- Cross-process communication:

- Domain event handler triggers integration event
- Outbox pattern for reliability (store event in DB, publish asynchronously)
- Message broker adapters (conceptual, not implementation-specific)

1. **Event Sourcing** -- When and why (brief, not implementation):

- Most projects don't need it
- Consider only when audit trail is a core requirement
- Can be added later without changing domain model

## HEXAGONAL-NESTJS.md

Ports and Adapters mapped to NestJS dependency injection.

**Sections:**

1. **Ports = TypeScript Interfaces** -- Port definition patterns:

- **Driven Ports** (outbound): `RepositoryPort`, `LoggerPort`, `EmailPort`
- **Driver Ports** (inbound): less common in NestJS since controllers are the drivers
- Port placement: repository ports in `database/` dir, other ports in `libs/ports/`
- Interface segregation: keep ports focused

1. **Adapters = NestJS Injectable Providers** -- Implementation patterns:

- `@Injectable()` class implementing port interface
- Registered via DI token in module providers array
- Example: `PrismaUserRepository implements UserRepositoryPort`

1. **DI Token Pattern** -- The NestJS-specific wiring mechanism:

- Define tokens in `{module}.di-tokens.ts`: `export const USER_REPOSITORY = Symbol('USER_REPOSITORY')`
- Register in module: `{ provide: USER_REPOSITORY, useClass: PrismaUserRepository }`
- Inject in handlers: `@Inject(USER_REPOSITORY) private readonly userRepo: UserRepositoryPort`
- Why tokens over class injection: enables swapping implementations, testing with mocks

1. **Adapter Swapping** -- The payoff of hexagonal:

- Test: `{ provide: USER_REPOSITORY, useClass: InMemoryUserRepository }`
- Dev: `{ provide: USER_REPOSITORY, useClass: PrismaUserRepository }`
- How to configure per environment using NestJS `ConfigModule`

1. **Mapper Pattern** -- Domain <-> Persistence translation:

- `Mapper<DomainEntity, PersistenceModel>` interface with `toDomain()` and `toPersistence()`
- NestJS `@Injectable()` mapper class
- Why: domain model shape != database schema shape
- Example: `UserMapper` converting between `UserEntity` and Prisma `User` model

1. **Request Context** -- Cross-cutting concerns:

- `AsyncLocalStorage` or NestJS `REQUEST` scope for request context
- Correlation IDs for event tracing
- Transaction connection sharing across repositories in same request
