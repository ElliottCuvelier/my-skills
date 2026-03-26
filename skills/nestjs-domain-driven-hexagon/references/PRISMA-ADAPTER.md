# Prisma Adapter

Concrete implementation of the persistence patterns using Prisma ORM. This document covers everything needed to wire Prisma as the persistence adapter in the hexagonal architecture.

## Table of Contents

- [Prisma Setup in NestJS](#prisma-setup-in-nestjs)
- [Schema Conventions](#schema-conventions)
- [PrismaRepositoryBase](#prismarepositorybase)
- [Concrete Repository Example](#concrete-repository-example)
- [Mapper Example](#mapper-example)
- [Transaction Patterns](#transaction-patterns)
- [Migrations and Schema Management](#migrations-and-schema-management)
- [Module Wiring](#module-wiring)

---

**See also:** [PERSISTENCE-PATTERNS.md](PERSISTENCE-PATTERNS.md) for the ORM-agnostic contracts this adapter implements, [HEXAGONAL-NESTJS.md](HEXAGONAL-NESTJS.md) for the DI token and adapter swapping patterns.

---

## Prisma Setup in NestJS

> **Prisma v7+ Compatibility:** Prisma v7 ships as ESM by default. NestJS uses CommonJS. You **must** set `moduleFormat = "cjs"` in your generator block and use a custom output path. See [Schema Conventions](#schema-conventions) for the full generator config.

### PrismaService

Wrap `PrismaClient` in a NestJS service. Prisma v7 manages connections automatically, so lifecycle hooks are optional:

```typescript
// src/libs/db/prisma.service.ts

import { Injectable } from '@nestjs/common';
import { PrismaClient } from '@generated/prisma';

@Injectable()
export class PrismaService extends PrismaClient {
  constructor() {
    super({
      datasources: {
        db: { url: process.env.DATABASE_URL },
      },
    });
  }
}
```

If you need explicit connection management (e.g., for graceful shutdown logging), add NestJS lifecycle hooks:

```typescript
import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { PrismaClient } from '@generated/prisma';

@Injectable()
export class PrismaService extends PrismaClient implements OnModuleDestroy {
  async onModuleDestroy(): Promise<void> {
    await this.$disconnect();
  }
}
```

### PrismaModule

Register as a global module so every feature module can inject `PrismaService` without importing `PrismaModule` explicitly:

```typescript
// src/libs/db/prisma.module.ts

import { Global, Module } from '@nestjs/common';
import { PrismaService } from './prisma.service';

@Global()
@Module({
  providers: [PrismaService],
  exports: [PrismaService],
})
export class PrismaModule {}
```

Import once in `AppModule`:

```typescript
@Module({
  imports: [PrismaModule, UserModule, WalletModule],
})
export class AppModule {}
```

### Path Alias for Generated Client

Configure a `tsconfig.json` path alias so imports stay clean across the codebase:

```json
{
  "compilerOptions": {
    "paths": {
      "@generated/prisma": ["src/generated/prisma"],
      "@generated/prisma/*": ["src/generated/prisma/*"]
    }
  }
}
```

All examples in this skill use `@generated/prisma` as the import path for Prisma-generated types.

### Environment Configuration

```env
# .env
DATABASE_URL="postgresql://user:password@localhost:5432/mydb?schema=public"

# .env.test
DATABASE_URL="postgresql://user:password@localhost:5432/mydb_test?schema=public"
```

---

## Schema Conventions

The Prisma schema defines the database structure. Follow these conventions to keep a clean mapping between the domain and persistence layers.

### Naming

| Element        | Convention                      | Example                                       |
| -------------- | ------------------------------- | --------------------------------------------- |
| Model name     | PascalCase singular             | `User`, `Wallet`, `OrderLineItem`             |
| Table mapping  | snake_case plural via `@@map()` | `@@map("users")`, `@@map("order_line_items")` |
| Column mapping | snake_case via `@map()`         | `@map("created_at")`, `@map("postal_code")`   |
| Enum name      | PascalCase                      | `UserRole`, `OrderStatus`                     |
| Enum values    | UPPER_SNAKE_CASE                | `ADMIN`, `GUEST`, `IN_PROGRESS`               |

### Standard Fields

Every model representing an aggregate root should have:

```prisma
model User {
  id        String   @id @default(uuid())
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")

  // ... domain fields

  @@map("users")
}
```

- `@id @default(uuid())` -- aggregate roots always have UUID primary keys.
- `@default(now())` and `@updatedAt` -- automatic timestamp management.
- `@@map("users")` -- decouples Prisma model name from table name.

### Multi-File Schema (Per-Aggregate)

Prisma schemas are split per aggregate and co-located alongside the repository implementation. Prisma v7 uses `prisma.config.ts` to discover all `.prisma` files under the configured schema directory. Set `schema: "src/"` so each module owns its aggregate's schema file.

#### prisma.config.ts

```typescript
// prisma.config.ts (project root)

import { defineConfig, env } from 'prisma/config';
import 'dotenv/config';

export default defineConfig({
  schema: 'src/',
  migrations: {
    path: 'prisma/migrations',
    seed: 'tsx prisma/seed.ts',
  },
  datasource: {
    url: env('DATABASE_URL'),
  },
});
```

#### Base Schema (Generator + Datasource)

```prisma
// src/schema.prisma

generator client {
  provider     = "prisma-client"
  output       = "./generated/prisma"
  moduleFormat = "cjs"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
```

This file contains only the generator and datasource blocks -- no models. Models live alongside their aggregate's repository.

#### Per-Aggregate Schema Files

Each aggregate root gets its own `.prisma` file co-located with its repository:

```prisma
// src/modules/user/infrastructure/persistence/user.prisma

enum UserRole {
  ADMIN
  MODERATOR
  GUEST
}

model User {
  id        String   @id @default(uuid())
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")
  email     String   @unique
  country   String
  postalCode String  @map("postal_code")
  street    String
  role      UserRole @default(GUEST)

  wallets   Wallet[]

  @@map("users")
}
```

```prisma
// src/modules/wallet/infrastructure/persistence/wallet.prisma

model Wallet {
  id        String   @id @default(uuid())
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")
  balance   Decimal  @default(0) @db.Decimal(10, 2)
  userId    String   @map("user_id")

  user      User     @relation(fields: [userId], references: [id])

  @@map("wallets")
}
```

Prisma automatically resolves cross-file references -- `Wallet` can reference `User` even though they live in different `.prisma` files. The `wallets Wallet[]` relation field in `User` and the `user User @relation(...)` in `Wallet` are resolved at generation time across the entire schema directory tree.

#### Schema File Ownership

| File Location                                                        | Contains                           | Owned By              |
| -------------------------------------------------------------------- | ---------------------------------- | --------------------- |
| `src/schema.prisma`                                                  | Generator + datasource blocks only | Shared infrastructure |
| `src/modules/{module}/infrastructure/persistence/{aggregate}.prisma` | Models and enums for one aggregate | Module team           |

This keeps merge conflicts localized -- changes to the User aggregate never conflict with changes to the Wallet aggregate.

### Relations vs Domain References

Prisma models define relations (`@relation`) for database integrity and query convenience. The domain model references other aggregates by ID only:

```typescript
// Domain: reference by ID
interface WalletProps {
  userId: string; // ID reference, not a User object
  balance: Money;
}

// Prisma: relational field for joins
model Wallet {
  userId String @map("user_id")
  user   User   @relation(fields: [userId], references: [id])
}
```

The mapper handles the translation -- the domain never sees the Prisma relation object.

---

## PrismaRepositoryBase

Abstract base class that implements `RepositoryPort` using Prisma.

```typescript
// src/libs/db/prisma-repository.base.ts

import { AggregateRoot } from '@libs/ddd';
import {
  Mapper,
  Paginated,
  PaginatedQueryParams,
  RepositoryPort,
} from '@libs/ddd';
import { LoggerPort } from '@libs/ports/logger.port';
import { ConflictException } from '@libs/exceptions';
import { EventEmitter2 } from '@nestjs/event-emitter';
import { PrismaService } from './prisma.service';
import { Prisma, PrismaClient } from '@generated/prisma';
import { RequestContextService } from '@libs/application/context/app-request-context';

export abstract class PrismaRepositoryBase<
  Aggregate extends AggregateRoot<unknown>,
  DbModel extends Record<string, unknown> = Record<string, unknown>,
> implements RepositoryPort<Aggregate> {
  protected constructor(
    protected readonly prisma: PrismaService,
    protected readonly mapper: Mapper<Aggregate, DbModel>,
    protected readonly eventEmitter: EventEmitter2,
    protected readonly logger: LoggerPort,
    protected readonly modelName: Uncapitalize<Prisma.ModelName>,
  ) {}

  /**
   * Returns the active transaction client if one exists in the
   * request context, otherwise falls back to the default PrismaService.
   */
  protected get client(): PrismaClient | Prisma.TransactionClient {
    return (
      (RequestContextService.getTransactionConnection() as Prisma.TransactionClient) ??
      this.prisma
    );
  }

  private get model() {
    return (this.client as Record<string, unknown>)[this.modelName] as {
      create: (args: { data: DbModel }) => Promise<DbModel>;
      findUnique: (args: {
        where: { id: string };
      }) => Promise<DbModel | undefined>;
      findMany: (args?: Record<string, unknown>) => Promise<DbModel[]>;
      delete: (args: { where: { id: string } }) => Promise<DbModel>;
      count: (args?: Record<string, unknown>) => Promise<number>;
    };
  }

  async insert(entity: Aggregate | Aggregate[]): Promise<void> {
    const entities = Array.isArray(entity) ? entity : [entity];
    entities.forEach((e) => e.validate());

    try {
      for (const e of entities) {
        const record = this.mapper.toPersistence(e);
        await this.model.create({ data: record });
      }

      await this.publishEvents(entities);
    } catch (error: unknown) {
      if (this.isUniqueConstraintError(error)) {
        throw new ConflictException('Record already exists', error as Error);
      }
      throw error;
    }
  }

  async findOneById(id: string): Promise<Aggregate | undefined> {
    const record = await this.model.findUnique({ where: { id } });
    return record ? this.mapper.toDomain(record) : undefined;
  }

  async findAll(): Promise<Aggregate[]> {
    const records = await this.model.findMany();
    return records.map((r) => this.mapper.toDomain(r));
  }

  async findAllPaginated(
    params: PaginatedQueryParams,
  ): Promise<Paginated<Aggregate>> {
    const [records, count] = await Promise.all([
      this.model.findMany({
        skip: params.offset,
        take: params.limit,
        orderBy: { [params.orderBy.field]: params.orderBy.param },
      }),
      this.model.count(),
    ]);

    return new Paginated({
      data: records.map((r) => this.mapper.toDomain(r)),
      count,
      limit: params.limit,
      page: params.page,
    });
  }

  async delete(entity: Aggregate): Promise<boolean> {
    entity.validate();

    try {
      await this.model.delete({ where: { id: entity.id } });
      await this.publishEvents([entity]);
      return true;
    } catch {
      return false;
    }
  }

  async transaction<T>(handler: () => Promise<T>): Promise<T> {
    // If already in a transaction, just run the handler
    if (RequestContextService.getTransactionConnection()) {
      return handler();
    }

    return this.prisma.$transaction(async (tx) => {
      this.logger.debug('Transaction started');
      RequestContextService.setTransactionConnection(tx);

      try {
        const result = await handler();
        this.logger.debug('Transaction committed');
        return result;
      } catch (error) {
        this.logger.debug('Transaction aborted');
        throw error;
      } finally {
        RequestContextService.cleanTransactionConnection();
      }
    });
  }

  private async publishEvents(entities: Aggregate[]): Promise<void> {
    await Promise.all(
      entities.map((entity) =>
        entity.publishEvents(this.logger, this.eventEmitter),
      ),
    );
  }

  private isUniqueConstraintError(error: unknown): boolean {
    return (
      error instanceof Prisma.PrismaClientKnownRequestError &&
      error.code === 'P2002'
    );
  }
}
```

### Key Design Choices

**`modelName` as a string.**
Prisma generates a typed client where each model is accessible as `prisma.user`, `prisma.wallet`, etc. The `modelName` string parameter (`'user'`, `'wallet'`) tells the base class which delegate to use. This avoids making the base class generic over Prisma model types, which creates complex type gymnastics.

**Nested transaction detection.**
If `RequestContextService.getTransactionConnection()` is already set, `transaction()` skips starting a new one. This prevents nested transaction issues when a domain event handler calls another repository's write method within the same request.

**Event publishing after writes.**
`publishEvents()` is called after the database operation succeeds. If the write throws, no events are emitted.

---

## Concrete Repository Example

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
import { User as UserRecord } from '@generated/prisma';

@Injectable()
export class UserRepository
  extends PrismaRepositoryBase<UserEntity, UserRecord>
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
    const record = await this.client.user.findUnique({ where: { email } });
    return record ? this.mapper.toDomain(record as UserRecord) : undefined;
  }

  async updateAddress(user: UserEntity): Promise<void> {
    user.validate();
    const address = user.getProps().address;

    await (this.client as PrismaService).user.update({
      where: { id: user.id },
      data: {
        country: address.country,
        postalCode: address.postalCode,
        street: address.street,
      },
    });

    await user.publishEvents(this.logger, this.eventEmitter);
  }
}
```

The concrete repository adds only the query methods that `UserRepositoryPort` demands beyond the generic `RepositoryPort` base. All standard CRUD is inherited from `PrismaRepositoryBase`.

---

## Mapper Example

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
      role: props.role.toUpperCase() as UserRecord['role'],
      country: address.country,
      postalCode: address.postalCode,
      street: address.street,
    } as UserRecord;
  }
}
```

### Enum Mapping

Domain uses lowercase enums (`UserRoles.admin = 'admin'`). Prisma uses uppercase enums (`UserRole.ADMIN`). The mapper converts between the two:

- `toDomain`: `record.role.toLowerCase() as UserRoles`
- `toPersistence`: `props.role.toUpperCase() as UserRecord['role']`

### Value Object Handling

The `Address` value object flattens into three columns (`country`, `postalCode`, `street`) in the database. The mapper:

- `toPersistence`: calls `props.address.unpack()` to get a plain object, then spreads its fields.
- `toDomain`: constructs `new Address({ country, postalCode, street })` from the raw columns.

---

## Transaction Patterns

### Interactive Transactions (Preferred)

Prisma's `$transaction()` with a callback provides full control:

```typescript
await this.userRepo.transaction(async () => {
  await this.userRepo.insert(user);
  // Any domain event handlers that fire here also participate
  // in the same transaction via RequestContextService.
});
```

Under the hood, `PrismaRepositoryBase.transaction()`:

1. Calls `prisma.$transaction(async (tx) => { ... })`.
2. Stores `tx` in `RequestContextService`.
3. All repository calls within the callback use `tx` instead of the default client.
4. On success, the transaction commits. On failure, it rolls back.

### Why Not Sequential Transactions?

Prisma also supports `prisma.$transaction([query1, query2])` for batching independent queries. This is simpler but doesn't support the request-context sharing pattern needed for domain events that trigger writes in other repositories. Always use interactive transactions for command handlers.

### Transaction Isolation

For critical operations, you can specify isolation level:

```typescript
return this.prisma.$transaction(
  async (tx) => {
    RequestContextService.setTransactionConnection(tx);
    try {
      return await handler();
    } finally {
      RequestContextService.cleanTransactionConnection();
    }
  },
  {
    isolationLevel: Prisma.TransactionIsolationLevel.Serializable,
    maxWait: 5000,
    timeout: 10000,
  },
);
```

Use `Serializable` only when strict consistency is required (e.g., financial operations). `ReadCommitted` (Prisma default) is sufficient for most cases.

---

## Migrations and Schema Management

### Development Workflow

All CLI commands automatically read `prisma.config.ts` from the project root, which specifies `schema: "src/"` and `migrations.path: "prisma/migrations"`.

```bash
# Create and apply a new migration
npx prisma migrate dev --name add_wallet_table

# Reset database (drops all data, re-applies migrations)
npx prisma migrate reset

# Regenerate Prisma client after schema changes (outputs to the path in your generator config)
npx prisma generate
```

Prisma discovers all `.prisma` files under `src/` and combines them before running any command. New models added in any module's `infrastructure/persistence/` directory are automatically included.

### Production Deployment

```bash
# Apply pending migrations (no data loss, no interactive prompts)
npx prisma migrate deploy
```

### Migration Best Practices

- **Keep migrations in version control.** The `prisma/migrations/` directory is part of the codebase.
- **Never edit applied migrations.** Create new migrations to alter previous changes.
- **Test migrations against a copy of production data** before deploying.
- **Name migrations descriptively:** `add_user_role_column`, `create_wallets_table`, not `migration_1`.
- **Schema files are split, migrations are not.** Even though each aggregate has its own `.prisma` file, migrations are generated against the combined schema and stored in a single `prisma/migrations/` directory.

### Seed Data

Seed configuration lives in `prisma.config.ts` (the `migrations.seed` field). The seed script itself stays in `prisma/seed.ts`:

```typescript
// prisma/seed.ts

import { PrismaClient } from '@generated/prisma';

const prisma = new PrismaClient();

async function main(): Promise<void> {
  await prisma.user.upsert({
    where: { email: 'admin@example.com' },
    update: {},
    create: {
      email: 'admin@example.com',
      country: 'United States',
      postalCode: '10001',
      street: '123 Main St',
      role: 'ADMIN',
    },
  });
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
```

Run with `npx prisma db seed`.

---

## Module Wiring

Complete example showing how everything connects in a NestJS module:

```typescript
// src/modules/user/user.module.ts

import { Module, Logger } from '@nestjs/common';
import { CqrsModule } from '@nestjs/cqrs';
import { USER_REPOSITORY, USER_LOGGER } from './user.di-tokens';
import { UserRepository } from './infrastructure/persistence/user.repository';
import { UserMapper } from './user.mapper';
import { CreateUserService } from './commands/create-user/create-user.service';
import { CreateUserHttpController } from './commands/create-user/create-user.http.controller';
import { DeleteUserService } from './commands/delete-user/delete-user.service';
import { DeleteUserHttpController } from './commands/delete-user/delete-user.http-controller';
import { FindUsersQueryHandler } from './queries/find-users/find-users.query-handler';
import { FindUsersHttpController } from './queries/find-users/find-users.http.controller';

@Module({
  imports: [CqrsModule],
  controllers: [
    CreateUserHttpController,
    DeleteUserHttpController,
    FindUsersHttpController,
  ],
  providers: [
    // Infrastructure: adapter bindings
    { provide: USER_REPOSITORY, useClass: UserRepository },
    { provide: USER_LOGGER, useFactory: () => new Logger('UserModule') },

    // Infrastructure: mapper
    UserMapper,

    // Application: command handlers
    CreateUserService,
    DeleteUserService,

    // Application: query handlers
    FindUsersQueryHandler,
  ],
})
export class UserModule {}
```

### DI Tokens

```typescript
// src/modules/user/user.di-tokens.ts

export const USER_REPOSITORY = Symbol('USER_REPOSITORY');
export const USER_LOGGER = Symbol('USER_LOGGER');
```

### Swapping to a Different ORM

To switch from Prisma to another ORM, only one line changes:

```typescript
// Prisma (current):
{ provide: USER_REPOSITORY, useClass: UserRepository }

// Drizzle (swap):
{ provide: USER_REPOSITORY, useClass: DrizzleUserRepository }

// TypeORM (swap):
{ provide: USER_REPOSITORY, useClass: TypeOrmUserRepository }

// In-memory for tests:
{ provide: USER_REPOSITORY, useClass: InMemoryUserRepository }
```

Everything else -- command handlers, query handlers, controllers, domain entities -- remains completely untouched. This is the payoff of hexagonal architecture with properly defined ports and DI tokens.
