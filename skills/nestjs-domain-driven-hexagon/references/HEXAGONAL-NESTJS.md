# Hexagonal Architecture in NestJS

Hexagonal Architecture (Ports and Adapters) isolates the application core from external concerns by defining ports (interfaces) that adapters (implementations) satisfy. NestJS's dependency injection system maps directly onto this pattern.

## Table of Contents

- [Ports = TypeScript Interfaces](#ports--typescript-interfaces)
- [Adapters = NestJS Injectable Providers](#adapters--nestjs-injectable-providers)
- [DI Token Pattern](#di-token-pattern)
- [Adapter Swapping](#adapter-swapping)
- [Mapper Pattern](#mapper-pattern)
- [Request Context](#request-context)
- [Centralized ACL Controllers](#centralized-acl-controllers)

---

**See also:** [PERSISTENCE-PATTERNS.md](PERSISTENCE-PATTERNS.md) for ORM-agnostic repository contracts, [PRISMA-ADAPTER.md](PRISMA-ADAPTER.md) for the concrete Prisma adapter, [LAYERS.md](LAYERS.md) for the full layer architecture.

---

## Ports = TypeScript Interfaces

A port defines a contract -- what must be done, without specifying how. The application core depends on ports, never on concrete implementations.

### Driven Ports (Outbound)

Driven ports define what the domain/application needs from external infrastructure. The application calls out through these ports.

```typescript
// src/libs/ddd/repository.port.ts -- Generic repository port

import { Paginated, PaginatedQueryParams } from './pagination';

export interface RepositoryPort<Entity> {
  insert(entity: Entity | Entity[]): Promise<void>;
  findOneById(id: string): Promise<Entity | undefined>;
  findAll(): Promise<Entity[]>;
  findAllPaginated(params: PaginatedQueryParams): Promise<Paginated<Entity>>;
  delete(entity: Entity): Promise<boolean>;
  transaction<T>(handler: () => Promise<T>): Promise<T>;
}
```

```typescript
// src/modules/user/infrastructure/persistence/user.repository.port.ts -- Module-specific port

import { RepositoryPort } from '@libs/ddd';
import { UserEntity } from '../domain/user.entity';

export interface UserRepositoryPort extends RepositoryPort<UserEntity> {
  findOneByEmail(email: string): Promise<UserEntity | undefined>;
}
```

```typescript
// src/libs/ports/logger.port.ts

export interface LoggerPort {
  log(message: string, ...meta: unknown[]): void;
  error(message: string, trace?: string, ...meta: unknown[]): void;
  warn(message: string, ...meta: unknown[]): void;
  debug(message: string, ...meta: unknown[]): void;
}
```

Other common driven ports: `EmailPort`, `PaymentGatewayPort`, `FileStoragePort`, `MessageBrokerPort`. Module-specific non-persistence ports belong in `modules/{module}/ports/`; those shared across modules go in `libs/ports/`.

### Driver Ports (Inbound)

Driver ports define how external actors interact with the application. In NestJS, controllers are the natural driver adapters, so explicit driver port interfaces are less common. The command/query handler interfaces effectively serve as driver ports:

```typescript
// The ICommandHandler from @nestjs/cqrs is the driver port.
// The handler implementation is the adapter.

@CommandHandler(CreateUserCommand)
export class CreateUserCommandHandler implements ICommandHandler {
  async execute(
    command: CreateUserCommand,
  ): Promise<Result<AggregateID, UserAlreadyExistsError>> {
    // ...
  }
}
```

### Port Placement

| Port Type                                      | Location                                                           | Rationale                                                | Example                   |
| ---------------------------------------------- | ------------------------------------------------------------------ | -------------------------------------------------------- | ------------------------- |
| Repository ports                               | `modules/{module}/infrastructure/persistence/*.repository.port.ts` | Tightly coupled to persistence layer                     | `UserRepositoryPort`      |
| Module-specific non-persistence outbound ports | `modules/{module}/ports/*.port.ts`                                 | Interface belongs at the application boundary, not infra | `PaymentGatewayPort`      |
| Shared cross-module ports                      | `libs/ports/*.port.ts`                                             | Shared contract across multiple modules                  | `LoggerPort`, `EmailPort` |

### Interface Segregation

Keep ports focused on one concern. A repository port handles persistence. A logger port handles logging. Resist the temptation to create a catch-all "infrastructure port."

```typescript
// Good -- focused ports
interface UserRepositoryPort extends RepositoryPort<UserEntity> {
  findOneByEmail(email: string): Promise<UserEntity | undefined>;
}

interface EmailPort {
  sendWelcomeEmail(to: string, name: string): Promise<void>;
  sendPasswordReset(to: string, token: string): Promise<void>;
}

// Bad -- god port
interface InfrastructurePort {
  findUser(id: string): Promise<UserEntity | undefined>;
  sendEmail(to: string, subject: string, body: string): Promise<void>;
  publishEvent(topic: string, data: unknown): Promise<void>;
  uploadFile(path: string, content: Buffer): Promise<string>;
}
```

---

## Adapters = NestJS Injectable Providers

An adapter implements a port using a specific technology. It's an `@Injectable()` class that is wired to the port via a DI token.

### Driven Adapter Example

```typescript
// src/modules/user/infrastructure/persistence/user.repository.ts

import { Injectable, Inject } from '@nestjs/common';
import { EventEmitter2 } from '@nestjs/event-emitter';
import { PrismaService } from '@libs/db/prisma.service';
import { PrismaRepositoryBase } from '@libs/db/prisma-repository.base';
import { UserEntity } from '../../domain/user.entity';
import { UserMapper } from '../../user.mapper';
import { UserRepositoryPort } from './user.repository.port';
import { LoggerPort } from '@libs/ports/logger.port';
import { USER_LOGGER } from '../../user.di-tokens';

@Injectable()
export class UserRepository
  extends PrismaRepositoryBase<UserEntity>
  implements UserRepositoryPort
{
  constructor(
    prisma: PrismaService,
    mapper: UserMapper,
    eventEmitter: EventEmitter2,
    @Inject(USER_LOGGER) logger: LoggerPort,
  ) {
    super(prisma, mapper, eventEmitter, logger, 'user');
  }

  async findOneByEmail(email: string): Promise<UserEntity | undefined> {
    const record = await this.prisma.user.findUnique({ where: { email } });
    return record ? this.mapper.toDomain(record) : undefined;
  }
}
```

### Adapter Requirements

Every adapter should:

1. Implement a port interface.
2. Be decorated with `@Injectable()`.
3. Be registered in a module via a DI token (not directly by class).
4. Handle technology-specific concerns (error mapping, serialization, connection management).
5. Translate between domain objects and external formats using a mapper.

---

## DI Token Pattern

DI tokens are the wiring mechanism that connects ports to adapters in NestJS. Instead of injecting a concrete class, inject via a Symbol token bound to a port interface.

### Define Tokens

```typescript
// src/modules/user/user.di-tokens.ts

export const USER_REPOSITORY = Symbol('USER_REPOSITORY');
export const USER_LOGGER = Symbol('USER_LOGGER');
```

Use a dedicated `*.di-tokens.ts` file per module. Tokens are module-scoped constants.

### Register in Module

```typescript
// src/modules/user/user.module.ts

@Module({
  imports: [CqrsModule],
  controllers: [CreateUserHttpController, FindUsersHttpController],
  providers: [
    { provide: USER_REPOSITORY, useClass: UserRepository },
    { provide: USER_LOGGER, useFactory: () => new Logger('UserModule') },
    UserMapper,
    CreateUserCommandHandler,
    FindUsersQueryHandler,
  ],
})
export class UserModule {}
```

### Inject in Consumers

```typescript
import { Inject } from '@nestjs/common';
import { USER_REPOSITORY } from '../../user.di-tokens';
import { UserRepositoryPort } from '../../infrastructure/persistence/user.repository.port';

@CommandHandler(CreateUserCommand)
export class CreateUserCommandHandler implements ICommandHandler {
  constructor(
    @Inject(USER_REPOSITORY)
    private readonly userRepo: UserRepositoryPort,
  ) {}
}
```

The handler depends on the interface `UserRepositoryPort`, not the class `UserRepository`. The token `USER_REPOSITORY` tells NestJS which concrete class to inject at runtime.

### Why Tokens Over Direct Class Injection

```typescript
// Direct class injection -- tightly coupled
constructor(private readonly userRepo: UserRepository) {}

// Token injection -- loosely coupled
constructor(
  @Inject(USER_REPOSITORY)
  private readonly userRepo: UserRepositoryPort,
) {}
```

With direct injection, changing the implementation requires modifying every consumer. With tokens, you change the binding in one place (the module file) and all consumers automatically get the new implementation.

---

## Adapter Swapping

The payoff of hexagonal architecture: swap technology without touching business logic.

### Per Environment

```typescript
// user.module.ts

const repositoryProvider = {
  provide: USER_REPOSITORY,
  useClass:
    process.env.NODE_ENV === 'test' ? InMemoryUserRepository : UserRepository,
};

@Module({
  providers: [repositoryProvider /* ... */],
})
export class UserModule {}
```

### Using ConfigModule for Flexibility

```typescript
import { ConfigService } from '@nestjs/config';

const repositoryProvider = {
  provide: USER_REPOSITORY,
  useFactory: (
    config: ConfigService,
    prisma: PrismaService,
    mapper: UserMapper,
    eventEmitter: EventEmitter2,
  ) => {
    const driver = config.get<string>('DATABASE_DRIVER', 'prisma');
    switch (driver) {
      case 'prisma':
        return new PrismaUserRepository(
          prisma,
          mapper,
          eventEmitter,
          new Logger('UserRepo'),
        );
      case 'in-memory':
        return new InMemoryUserRepository();
      default:
        throw new Error(`Unknown database driver: ${driver}`);
    }
  },
  inject: [ConfigService, PrismaService, UserMapper, EventEmitter2],
};
```

### In-Memory Adapter for Tests

```typescript
// src/modules/user/infrastructure/persistence/user.in-memory.repository.ts

export class InMemoryUserRepository implements UserRepositoryPort {
  private users: Map<string, UserEntity> = new Map();

  async insert(entity: UserEntity | UserEntity[]): Promise<void> {
    const entities = Array.isArray(entity) ? entity : [entity];
    for (const e of entities) {
      if (this.users.has(e.id)) {
        throw new ConflictException('User already exists');
      }
      this.users.set(e.id, e);
    }
  }

  async findOneById(id: string): Promise<UserEntity | undefined> {
    return this.users.get(id);
  }

  async findOneByEmail(email: string): Promise<UserEntity | undefined> {
    return [...this.users.values()].find((u) => u.getProps().email === email);
  }

  async findAll(): Promise<UserEntity[]> {
    return [...this.users.values()];
  }

  async findAllPaginated(
    params: PaginatedQueryParams,
  ): Promise<Paginated<UserEntity>> {
    const all = [...this.users.values()];
    const data = all.slice(params.offset, params.offset + params.limit);
    return new Paginated({
      data,
      count: all.length,
      limit: params.limit,
      page: params.page,
    });
  }

  async delete(entity: UserEntity): Promise<boolean> {
    return this.users.delete(entity.id);
  }

  async transaction<T>(handler: () => Promise<T>): Promise<T> {
    return handler();
  }
}
```

This in-memory implementation fulfills the same contract as the Prisma repository, making it trivial to swap in tests without touching any handler code.

---

## Mapper Pattern

Mappers translate between the domain model and the persistence model. The domain should never be shaped to accommodate database concerns.

### Mapper Interface

```typescript
// src/libs/ddd/mapper.interface.ts

export interface Mapper<DomainEntity, DbRecord> {
  toDomain(record: DbRecord): DomainEntity;
  toPersistence(entity: DomainEntity): DbRecord;
}
```

### Implementation

```typescript
// src/modules/user/user.mapper.ts

import { Injectable } from '@nestjs/common';
import { Mapper } from '@libs/ddd';
import { UserEntity } from './domain/user.entity';
import { Address } from './domain/value-objects/address.value-object';
import { UserRoles } from './domain/user.types';
import { User as UserRecord } from '@generated/prisma';

@Injectable()
export class UserMapper implements Mapper<UserEntity, UserRecord> {
  toDomain(record: UserRecord): UserEntity {
    return new UserEntity({
      id: record.id,
      createdAt: record.createdAt,
      updatedAt: record.updatedAt,
      props: {
        email: record.email,
        role: record.role.toLowerCase() as UserRoles,
        address: new Address({
          country: record.country,
          postalCode: record.postalCode,
          street: record.street,
        }),
      },
    });
  }

  toPersistence(entity: UserEntity): UserRecord {
    const props = entity.getProps();
    const address = props.address.unpack();
    return {
      id: props.id,
      createdAt: props.createdAt,
      updatedAt: props.updatedAt,
      email: props.email,
      role: props.role.toUpperCase(),
      country: address.country,
      postalCode: address.postalCode,
      street: address.street,
    } as UserRecord;
  }
}
```

### Why Mappers Matter

- **Domain model != database schema.** The domain uses value objects (`Address`), enums, and rich types. The database stores flat columns and strings.
- **Schema changes don't break the domain.** If you rename a database column or normalize a table, update the mapper -- the entity stays the same.
- **Mapper is `@Injectable()`** in NestJS. It's a regular provider, injected into repositories.
- **Handle nested value objects.** `toPersistence()` calls `unpack()` on value objects to flatten them. `toDomain()` reconstructs value objects from raw database values.

### Mapper Placement

Mappers live in the module root, next to the module file:

```
modules/user/
├── user.module.ts
├── user.mapper.ts     # <-- here
├── user.di-tokens.ts
├── domain/
├── infrastructure/
│   └── persistence/
└── commands/
```

They are infrastructure-layer code (they know about the persistence model shape) but are co-located with the module for convenience.

---

## Request Context

Cross-cutting concerns like correlation IDs and transaction connections need to flow through the entire request without being passed as arguments everywhere.

### AsyncLocalStorage Approach

Node.js `AsyncLocalStorage` provides request-scoped storage that propagates through async call chains.

```typescript
// src/libs/application/context/app-request-context.ts

import { AsyncLocalStorage } from 'async_hooks';

export class AppRequestContext {
  requestId: string;
  transactionConnection?: unknown;
}

export class RequestContextService {
  private static readonly storage = new AsyncLocalStorage<AppRequestContext>();

  static getContext(): AppRequestContext {
    const ctx = this.storage.getStore();
    if (!ctx) {
      throw new Error(
        'RequestContext is not available. Ensure the interceptor is applied.',
      );
    }
    return ctx;
  }

  static getRequestId(): string {
    return this.getContext().requestId;
  }

  static getTransactionConnection(): unknown | undefined {
    return this.getContext().transactionConnection;
  }

  static setTransactionConnection(connection: unknown): void {
    this.getContext().transactionConnection = connection;
  }

  static cleanTransactionConnection(): void {
    this.getContext().transactionConnection = undefined;
  }

  static run<T>(context: AppRequestContext, fn: () => T): T {
    return this.storage.run(context, fn);
  }
}
```

### NestJS Interceptor for Context Initialization

```typescript
// src/libs/application/context/context.interceptor.ts

import {
  CallHandler,
  ExecutionContext,
  Injectable,
  NestInterceptor,
} from '@nestjs/common';
import { Observable, tap } from 'rxjs';
import { randomUUID } from 'crypto';
import {
  AppRequestContext,
  RequestContextService,
} from './app-request-context';

@Injectable()
export class ContextInterceptor implements NestInterceptor {
  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const requestContext = new AppRequestContext();
    requestContext.requestId = randomUUID();

    return new Observable((subscriber) => {
      RequestContextService.run(requestContext, () => {
        next.handle().subscribe(subscriber);
      });
    });
  }
}
```

Register globally in `main.ts`:

```typescript
app.useGlobalInterceptors(new ContextInterceptor());
```

### Using Context in Repositories

The transaction connection sharing pattern allows all repositories in the same request to participate in a single transaction:

```typescript
// In the repository base class (types from @generated/prisma):
protected get connection(): PrismaClient | Prisma.TransactionClient {
  const txConnection = RequestContextService.getTransactionConnection();
  return (txConnection as Prisma.TransactionClient) ?? this.prisma;
}

async transaction<T>(handler: () => Promise<T>): Promise<T> {
  return this.prisma.$transaction(async (tx) => {
    RequestContextService.setTransactionConnection(tx);
    try {
      const result = await handler();
      return result;
    } finally {
      RequestContextService.cleanTransactionConnection();
    }
  });
}
```

When a command handler calls `this.userRepo.transaction(...)`, the transaction client is stored in the request context. Any other repository accessed within the same request (e.g., a wallet repository triggered by a domain event handler) automatically uses the same transaction.

### Correlation IDs for Tracing

The request context's `requestId` flows into domain events as the `correlationId`, enabling end-to-end tracing:

```typescript
// In DomainEvent constructor:
this.metadata = {
  correlationId:
    props?.metadata?.correlationId || RequestContextService.getRequestId(),
  // ...
};
```

This means every domain event emitted during a request carries the same correlation ID, making it possible to trace the entire flow from HTTP request through command handler, domain events, and side effects in logs and monitoring.

---

## Centralized ACL Controllers

An Anti-Corruption Layer (ACL) controller handles a single inbound channel — a webhook endpoint, a message-bus consumer, or a GraphQL gateway — and translates all incoming events or commands into internal application commands or domain events.

### When to Use

Use a centralized ACL controller when:

- A single external channel (webhook URL, Kafka consumer, SQS listener) triggers multiple distinct internal commands.
- You want to isolate the translation between external message formats and internal command objects in one place.
- The external format is outside your control and likely to change independently of your domain.

For REST APIs where each endpoint maps to one use case, prefer individual `*.http.controller.ts` files per use case — those are simpler and keep change locality.

### The Invariant

An ACL controller MUST dispatch exclusively via `CommandBus.execute()` or `EventEmitter2.emitAsync()`. It MUST NOT:

- Inject or call a repository directly.
- Import adapter classes.
- Contain domain logic.

The ACL controller is an infrastructure adapter. Its only job is format translation and dispatch.

### Webhook Controller Example

```typescript
// src/modules/payment/infrastructure/adapters/stripe-webhook.controller.ts

import { Controller, Post, Body, Headers, HttpCode } from '@nestjs/common';
import { CommandBus } from '@nestjs/cqrs';
import { HandlePaymentSucceededCommand } from '../../application/commands/handle-payment-succeeded/handle-payment-succeeded.command';
import { HandlePaymentFailedCommand } from '../../application/commands/handle-payment-failed/handle-payment-failed.command';

@Controller('webhooks/stripe')
export class StripeWebhookController {
  constructor(private readonly commandBus: CommandBus) {}

  @Post()
  @HttpCode(200)
  async handle(
    @Body() payload: unknown,
    @Headers('stripe-signature') signature: string,
  ): Promise<void> {
    const event = this.parseAndVerify(payload, signature);

    switch (event.type) {
      case 'payment_intent.succeeded':
        await this.commandBus.execute(
          new HandlePaymentSucceededCommand({
            paymentIntentId: event.data.object.id,
            amount: event.data.object.amount,
          }),
        );
        break;
      case 'payment_intent.payment_failed':
        await this.commandBus.execute(
          new HandlePaymentFailedCommand({
            paymentIntentId: event.data.object.id,
            failureCode: event.data.object.last_payment_error?.code,
          }),
        );
        break;
      default:
        break;
    }
  }

  private parseAndVerify(payload: unknown, signature: string): StripeEvent {
    // Signature verification; throw if invalid
  }
}
```

### Contrast with Per-Use-Case Controllers

| Pattern                    | When                                       | Location                                                              |
| -------------------------- | ------------------------------------------ | --------------------------------------------------------------------- |
| `*.http.controller.ts`     | One REST endpoint, one use case            | `application/commands/{use-case}/` or `application/queries/{query}/` |
| Centralized ACL controller | One external channel, multiple use cases   | `infrastructure/adapters/{channel}.controller.ts`                     |

Default to per-use-case controllers. Reach for the ACL controller only when the external channel forces multiplexing.
