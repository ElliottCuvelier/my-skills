# Cheatsheet

Quick reference for day-to-day development with this architecture. Keep this open while coding.

---

## Layer Summary

```
┌──────────────────────────────────────────────────────────────┐
│  Interface Adapters (controllers, CLI, GraphQL resolvers)    │
│  ► Parses input, validates DTOs, maps to commands/queries    │
│  ► Returns HTTP responses, handles serialization             │
├──────────────────────────────────────────────────────────────┤
│  Application (command handlers, query handlers)              │
│  ► Orchestrates domain objects and ports                     │
│  ► Owns transaction boundaries                               │
│  ► Returns Result<T, E>                                      │
├──────────────────────────────────────────────────────────────┤
│  Domain (entities, VOs, aggregates, domain services)         │
│  ► Pure business logic, ZERO infrastructure dependencies     │
│  ► Emits domain events, enforces invariants                  │
├──────────────────────────────────────────────────────────────┤
│  Infrastructure (repositories, external APIs, messaging)     │
│  ► Implements port interfaces defined by inner layers        │
│  ► Prisma, HTTP clients, message brokers                     │
└──────────────────────────────────────────────────────────────┘

Dependencies: Infrastructure → Application → Domain (inward only)
```

**Per-layer rules:**

| Layer              | Can Import                                     | Cannot Import                                    | Contains                                                                    |
| ------------------ | ---------------------------------------------- | ------------------------------------------------ | --------------------------------------------------------------------------- |
| Domain             | `@libs/ddd`, `@libs/exceptions`, standard lib  | Anything from outer layers, NestJS, Prisma, HTTP | Entities, VOs, aggregates, domain events, domain services, repository ports |
| Application        | Domain, `@libs/*`, `@nestjs/cqrs`              | Infrastructure, controllers, Prisma              | Command/query handlers, application services                                |
| Infrastructure     | Application, Domain, `@libs/*`, NestJS, Prisma | Nothing forbidden (outermost)                    | Repository implementations, mappers, external API clients                   |
| Interface Adapters | Application (commands/queries), `@libs/api`    | Domain internals, Infrastructure directly        | Controllers, DTOs, interceptors, pipes                                      |

---

## File Naming Conventions

| Pattern                   | Layer             | Example                             |
| ------------------------- | ----------------- | ----------------------------------- |
| `*.entity.ts`             | Domain            | `user.entity.ts`                    |
| `*.value-object.ts`       | Domain            | `address.value-object.ts`           |
| `*.domain-event.ts`       | Domain            | `user-created.domain-event.ts`      |
| `*.errors.ts`             | Domain            | `user.errors.ts`                    |
| `*.types.ts`              | Domain            | `user.types.ts`                     |
| `*.domain-service.ts`     | Domain            | `transfer-funds.domain-service.ts`  |
| `*.command.ts`            | Application       | `create-user.command.ts`            |
| `*.service.ts`            | Application       | `create-user.service.ts`            |
| `*.query-handler.ts`      | Application       | `find-users.query-handler.ts`       |
| `*.http.controller.ts`    | Interface Adapter | `create-user.http.controller.ts`    |
| `*.graphql-resolver.ts`   | Interface Adapter | `user.graphql-resolver.ts`          |
| `*.message.controller.ts` | Interface Adapter | `user-events.message.controller.ts` |
| `*.request.dto.ts`        | Interface Adapter | `create-user.request.dto.ts`        |
| `*.response.dto.ts`       | Interface Adapter | `user.response.dto.ts`              |
| `*.repository.port.ts`    | Domain (port)     | `user.repository.port.ts`           |
| `*.repository.ts`         | Infrastructure    | `user.repository.ts`                |
| `*.mapper.ts`             | Infrastructure    | `user.mapper.ts`                    |
| `*.di-tokens.ts`          | Module root       | `user.di-tokens.ts`                 |
| `*.module.ts`             | Module root       | `user.module.ts`                    |

---

## Decision Trees (Compact)

### Where does this code go?

```
Pure business logic, no I/O?             → domain/
Orchestrates domain + side effects?      → commands/ or queries/
Talks to external systems?               → infrastructure/persistence/ or infrastructure/adapters/
Defines interaction interface?           → *.repository.port.ts
Implements a port?                       → *.repository.ts
Handles HTTP/GraphQL/CLI input?          → *.http.controller.ts
```

### Entity or Value Object?

```
Has unique identity that persists?       → Entity
Defined only by its attributes?          → Value Object
"Is this THE same thing?"                → Entity (identity equality)
"Does this have the same value?"         → Value Object (structural equality)
```

### Aggregate boundaries?

```
True invariant requiring transactional consistency?
  Yes → Same aggregate
  No, just compositional convenience → Separate aggregates

Can consistency tolerate a short delay?
  Yes → Separate aggregates + domain events
  No  → Same aggregate

Whose job is it to keep this consistent?
  The user performing the action → Transactional (same aggregate)
  The system / another user     → Eventual consistency (separate)

Referenced by ID only?           → Separate aggregates
>10 entities in aggregate?       → Split it
```

**Rule:** One aggregate per transaction. Cross-aggregate consistency via domain events.

---

## Four Rules of Aggregate Design

Vernon's rules of thumb. Apply as a set. See [AGGREGATE-DESIGN.md](AGGREGATE-DESIGN.md) for the full methodology.

| #   | Rule                                                | Quick Check                                                         |
| --- | --------------------------------------------------- | ------------------------------------------------------------------- |
| 1   | **Model True Invariants In Consistency Boundaries** | Is there a real business rule, or is this just "has-a" convenience? |
| 2   | **Design Small Aggregates**                         | Root + value objects. ~70% of aggregates are root-only.             |
| 3   | **Reference Other Aggregates By Identity**          | Store `orderId: string`, not `order: OrderEntity`.                  |
| 4   | **Use Eventual Consistency Outside the Boundary**   | Domain events for cross-aggregate rules. Ask whose job it is.       |

---

## New Feature Checklist

Step-by-step when adding a new use case. Follow this order.

### Adding a Command (Write Operation)

- [ ] **Domain** -- Create/update entity with new behavior and invariants
- [ ] **Domain** -- Add domain event if the operation is significant
- [ ] **Domain** -- Add domain error classes if new failure modes exist
- [ ] **Application** -- Define command class (`create-user.command.ts`)
- [ ] **Application** -- Implement command handler (`create-user.service.ts`)
- [ ] **Port** -- Add repository port method if new persistence needed (`user.repository.port.ts`)
- [ ] **Infrastructure** -- Implement repository method in Prisma adapter (`user.repository.ts`)
- [ ] **Infrastructure** -- Update mapper if new fields (`user.mapper.ts`)
- [ ] **Infrastructure** -- Update aggregate's `.prisma` schema file + run migration if schema changed
- [ ] **Interface** -- Create request DTO with `class-validator` decorators
- [ ] **Interface** -- Create HTTP controller dispatching the command
- [ ] **Interface** -- Create/update response DTO
- [ ] **Module** -- Register new providers in `user.module.ts`
- [ ] **Tests** -- Domain unit test (entity behavior, invariants)
- [ ] **Tests** -- Application unit test (handler with mocked ports)
- [ ] **Tests** -- Integration test (repository + real DB)

### Adding a Query (Read Operation)

- [ ] **Application** -- Define query class (`find-users.query.ts`)
- [ ] **Application** -- Implement query handler (`find-users.query-handler.ts`)
- [ ] **Port** -- Add repository port method if needed
- [ ] **Infrastructure** -- Implement repository method
- [ ] **Interface** -- Create request DTO (query params, pagination)
- [ ] **Interface** -- Create HTTP controller dispatching the query
- [ ] **Interface** -- Create response DTO
- [ ] **Module** -- Register new providers
- [ ] **Tests** -- Application unit test, integration test

### Adding a New Aggregate

- [ ] **Domain** -- Create entity extending `AggregateRoot`
- [ ] **Domain** -- Create associated value objects
- [ ] **Domain** -- Define domain events
- [ ] **Domain** -- Define repository port interface
- [ ] **Infrastructure** -- Create per-aggregate `.prisma` schema file in `infrastructure/persistence/`
- [ ] **Infrastructure** -- Run migration
- [ ] **Infrastructure** -- Create mapper (domain ↔ persistence)
- [ ] **Infrastructure** -- Implement repository extending `PrismaRepositoryBase`
- [ ] **Module** -- Define DI tokens in `*.di-tokens.ts`
- [ ] **Module** -- Wire everything in `*.module.ts`
- [ ] **Tests** -- Full test suite (domain → application → integration)

---

## Common Anti-Patterns

| Anti-Pattern                       | Symptom                                                     | Fix                                               |
| ---------------------------------- | ----------------------------------------------------------- | ------------------------------------------------- |
| Anemic Domain Model                | Entities have only getters/setters, logic lives in services | Move behavior into entity methods                 |
| Leaking Prisma Types               | Domain imports `PrismaClient`, `@generated/prisma`          | Domain depends on port interfaces only            |
| God Module                         | Single module with 40+ providers                            | Split along subdomain boundaries                  |
| Skipping DI Tokens                 | `@Inject(UserRepository)` using concrete class              | Use `@Inject(USER_REPOSITORY)` with Symbol token  |
| Cross-Module Imports               | Importing `../other-module/domain/...`                      | Use events, CommandBus, or exported services      |
| Repository per Entity              | Separate repos for entities inside one aggregate            | One repository per aggregate root                 |
| Controller → Repository            | Controller calls repository, bypassing app layer            | Controller dispatches command/query               |
| Premature CQRS                     | Event sourcing + separate read DB on day one                | Start with command/query separation, evolve later |
| Synchronous Cross-Aggregate        | Transaction spans multiple aggregates                       | Use domain events for eventual consistency        |
| Business Logic in Controller       | Validation, calculations, conditionals in controller        | Move to command handler or domain entity          |
| Express v4 Wildcards (NestJS v11+) | `@Get('files/*')` returns 404                               | Use named params: `@Get('files/{*splat}')`        |

---

## NestJS DI Wiring Quick Reference

### 1. Define Tokens

```typescript
// user.di-tokens.ts
export const USER_REPOSITORY = Symbol('USER_REPOSITORY');
export const USER_LOGGER = Symbol('USER_LOGGER');
```

### 2. Register in Module

```typescript
// user.module.ts
@Module({
  imports: [PrismaModule, CqrsModule],
  controllers: [CreateUserHttpController, FindUsersHttpController],
  providers: [
    CreateUserService,
    FindUsersQueryHandler,
    UserMapper,
    {
      provide: USER_REPOSITORY,
      useClass: UserRepository, // swap to InMemoryUserRepository for tests
    },
    {
      provide: USER_LOGGER,
      useValue: new Logger('UserModule'),
    },
  ],
})
export class UserModule {}
```

### 3. Inject via Token

```typescript
// create-user.service.ts
@Injectable()
export class CreateUserService {
  constructor(
    @Inject(USER_REPOSITORY)
    private readonly userRepo: UserRepositoryPort,
  ) {}
}
```

### Adapter Swapping (per environment)

```typescript
{
  provide: USER_REPOSITORY,
  useFactory: (config: ConfigService, prismaRepo: UserRepository) => {
    return config.get('USE_IN_MEMORY_DB')
      ? new InMemoryUserRepository()
      : prismaRepo;
  },
  inject: [ConfigService, UserRepository],
}
```

---

## Import Aliases

Configure in `tsconfig.json`:

```json
{
  "compilerOptions": {
    "paths": {
      "@src/*": ["src/*"],
      "@modules/*": ["src/modules/*"],
      "@libs/*": ["src/libs/*"],
      "@generated/prisma": ["src/generated/prisma"],
      "@generated/prisma/*": ["src/generated/prisma/*"]
    }
  }
}
```

Usage:

```typescript
import { UserEntity } from '@modules/user/domain/user.entity';
import { Entity } from '@libs/ddd/entity.base';
import { RepositoryPort } from '@libs/ddd/repository.port';
import { ExceptionBase } from '@libs/exceptions/exception.base';
```

---

## Error Handling Pattern

```
Domain Error (oxide.ts Result) → Application Handler → Controller → HTTP Response
```

```typescript
// Domain: return typed errors
return Err(new UserAlreadyExistsError(email));

// Application: propagate Result<T, E>
const result = await this.createUser(command);
return result;

// Controller: match Result to HTTP status
match(result, {
  Ok: (id: string) => new IdResponse(id),
  Err: (error: ExceptionBase) => {
    throw error; // caught by NestJS exception filter
  },
});
```

| Domain Error                   | HTTP Status |
| ------------------------------ | ----------- |
| `NotFoundException`            | 404         |
| `ConflictException`            | 409         |
| `ArgumentInvalidException`     | 400         |
| `ArgumentOutOfRangeException`  | 400         |
| `ArgumentNotProvidedException` | 400         |
| Unhandled / unexpected         | 500         |

---

## Transaction Pattern

```typescript
// In command handler -- handler owns the transaction boundary
async execute(command: CreateUserCommand): Promise<Result<string, UserAlreadyExistsError>> {
  const user = UserEntity.create({ /* ... */ });

  const result = await this.userRepo.transaction(async () => {
    await this.userRepo.insert(user);
  });

  return Ok(user.id);
}
```

The `PrismaRepositoryBase.transaction()` method wraps the callback in `prisma.$transaction()` and publishes domain events after commit.
