---
name: 'Plan 3: Prisma Infrastructure'
overview: Create the Prisma-specific persistence layer reference and a general persistence architecture guide that establishes the patterns for any ORM adapter, making future ORM additions straightforward.
todos:
  - id: write-persistence-patterns
    content: Write references/PERSISTENCE-PATTERNS.md defining ORM-agnostic repository port, mapper interface, base repository contract, transaction patterns, and 'add a new ORM' guide
    status: completed
  - id: write-prisma-adapter
    content: Write references/PRISMA-ADAPTER.md with PrismaService setup, schema conventions, PrismaRepositoryBase class, concrete repository example, mapper example, transaction patterns, module wiring
    status: completed
isProject: false
---

# Plan 3: Infrastructure and Prisma Persistence Layer

## Files to Create

```
skills/nestjs-domain-driven-hexagon/
└── references/
    ├── PERSISTENCE-PATTERNS.md
    └── PRISMA-ADAPTER.md
```

## PERSISTENCE-PATTERNS.md

ORM-agnostic persistence layer architecture. This file establishes the contract and patterns that any ORM adapter must follow, making it easy to add Drizzle, TypeORM, MikroORM, or Slonik adapters in the future.

**Sections:**

1. **Persistence Layer Architecture** -- The role of the persistence layer in hexagonal architecture:

- Domain model != persistence model (always separate them)
- Repository port defines the contract, adapter implements it
- Mapper translates between domain entities and persistence models
- Diagram: `DomainEntity <-> Mapper <-> PersistenceModel <-> Database`

1. **Generic Repository Port** -- The base interface all repository adapters implement:

```typescript
interface RepositoryPort<Entity> {
  insert(entity: Entity | Entity[]): Promise<void>;
  findOneById(id: string): Promise<Option<Entity>>;
  findAll(): Promise<Entity[]>;
  findAllPaginated(params: PaginatedQueryParams): Promise<Paginated<Entity>>;
  delete(entity: Entity): Promise<boolean>;
  transaction<T>(handler: () => Promise<T>): Promise<T>;
}
```

- `Paginated<T>` response type
- `PaginatedQueryParams` with limit, page, offset, orderBy
- `Option<T>` pattern (using `oxide.ts` or a simple union type) for nullable returns
- Module-specific ports extend this with domain-specific queries

1. **Mapper Interface** -- Standard contract:

```typescript
interface Mapper<DomainEntity, DbRecord> {
  toDomain(record: DbRecord): DomainEntity;
  toPersistence(entity: DomainEntity): DbRecord;
}
```

- Mapper is `@Injectable()` in NestJS
- Handles nested value objects (unpack VOs to primitives for DB, reconstruct on read)
- Handles date conversions, enum mappings

1. **Base Repository Abstract Class** -- What every ORM adapter's base class must provide:

- Constructor accepting: ORM client/pool, mapper, event emitter, logger
- `insert()` maps entity to persistence, writes, publishes domain events
- `findOneById()` queries, maps back to domain
- `delete()` validates, deletes, publishes events
- `transaction()` wraps operations in DB transaction
- Domain event publishing after successful writes (not before)
- Conflict detection (unique constraint violations -> `ConflictException`)

1. **Transaction Management** -- Patterns for transactions across the hexagonal boundary:

- Transaction initiated in application layer (command handler)
- Transaction connection shared via request context (`AsyncLocalStorage`)
- All repositories in same request use same transaction connection
- Rollback on any failure within the transaction scope

1. **Adding a New ORM Adapter** -- Step-by-step guide for future ORM additions:

- Create `{orm}-repository.base.ts` extending base patterns
- Implement `RepositoryPort` methods using ORM-specific APIs
- Create module-specific repositories extending the ORM base
- Wire via DI tokens in the NestJS module
- Provide example mapper for the ORM's model format

## PRISMA-ADAPTER.md

Concrete Prisma implementation of the persistence patterns.

**Sections:**

1. **Prisma Setup in NestJS** -- Standard setup:

- `PrismaService` extending `PrismaClient` with `onModuleInit`/`onModuleDestroy`
- Global module registration (`PrismaModule` with `@Global()`)
- `prisma/schema.prisma` location and conventions
- Environment-based database URL configuration

1. **Prisma Schema Conventions** -- How schema maps to domain:

- Table names: snake_case plural (`users`, `wallets`)
- Column names: snake_case matching domain concepts
- `@id` with `@default(uuid())` for aggregate root IDs
- `@createdAt` and `@updatedAt` timestamps on every model
- Relations modeled in Prisma, but domain references by ID only
- Example schema for User aggregate:

```prisma
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

1. **Prisma Repository Base Class** -- Abstract base implementing `RepositoryPort`:

- Constructor takes `PrismaService`, `Mapper`, `EventEmitter2`, `LoggerPort`
- Abstract `modelName` property (Prisma delegate accessor)
- `insert()` using `prisma[model].create({ data: mapper.toPersistence(entity) })`
- `findOneById()` using `prisma[model].findUnique({ where: { id } })`
- `findAllPaginated()` with `skip`, `take`, `orderBy`
- `delete()` using `prisma[model].delete({ where: { id } })`
- `transaction()` using `prisma.$transaction(async (tx) => { ... })`
- Event publishing after successful write operations
- Conflict handling: catch Prisma `P2002` unique constraint error -> `ConflictException`
- Full TypeScript implementation (~80-100 lines)

1. **Concrete Repository Example** -- `PrismaUserRepository`:

- Extends `PrismaRepositoryBase<UserEntity, Prisma.User>`
- Implements `UserRepositoryPort`
- Custom query methods: `findOneByEmail()`, `updateAddress()`
- Registered with DI token in `UserModule`

1. **Mapper Example** -- `UserMapper`:

- `toPersistence()`: extracts entity props, unpacks value objects (Address -> country, street, postalCode)
- `toDomain()`: reconstructs entity with `new UserEntity({ id, props, createdAt, updatedAt })`
- Handles enum mapping between Prisma enum and domain enum

1. **Transaction Patterns with Prisma** -- Two approaches:

- **Interactive transactions**: `prisma.$transaction(async (tx) => { ... })` -- preferred for complex flows
- **Request-scoped transaction**: share `tx` via `AsyncLocalStorage` so all repos in same request use it
- Transaction initiated in command handler, repository detects active transaction from context
- Example: `CreateUserService` wrapping insert in transaction

1. **Prisma Migrations and Schema Management** -- Brief guidance:

- `npx prisma migrate dev` for development
- `npx prisma migrate deploy` for production
- Keep migration history in version control
- Seed data patterns

1. **Module Wiring** -- Complete example of wiring it all together:

```typescript
@Module({
  providers: [
    { provide: USER_REPOSITORY, useClass: PrismaUserRepository },
    UserMapper,
    CreateUserService,
    // ... other handlers
  ],
  controllers: [CreateUserHttpController, FindUsersHttpController],
})
export class UserModule {}
```
