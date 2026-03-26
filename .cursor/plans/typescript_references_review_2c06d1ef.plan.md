---
name: TypeScript References Review
overview: A comprehensive TypeScript review of all reference files in both skills, identifying bugs, type-safety gaps, and improvements aligned with the typescript-expert and typescript-advanced-types skill standards.
todos:
  - id: nestjs-guard-null
    content: 'Fix Guard.isEmpty null check: change `value !== undefined` to `value !== null` in the typeof object branch'
    status: completed
  - id: nestjs-vo-equals
    content: Fix ValueObject.equals to compare `this.props` not `this` via JSON.stringify
    status: completed
  - id: nestjs-command-props
    content: Extract props interfaces for Command subclasses (CreateUserCommand, FindUsersQuery) to remove self-referential constructor types and Object.assign pattern
    status: completed
  - id: nestjs-repo-client
    content: 'Fix runtime transaction bypass: narrow PrismaRepositoryBase.client return type to Prisma.TransactionClient (eliminating the union), then replace this.prisma with this.client in concrete repository methods (findOneByEmail, updateAddress)'
    status: completed
  - id: nestjs-findunique-null
    content: 'Fix PrismaRepositoryBase.model getter: type findUnique return as `Promise<DbModel | null>` not `undefined`'
    status: completed
  - id: nestjs-correlationid
    content: Fix ExceptionBase.toJSON to populate correlationId from RequestContextService instead of hardcoding empty string
    status: completed
  - id: reactive-clientmodel-api
    content: "Make @ClientModel call site in REACT-PATTERNS.md consistent with its definition: @ClientModel('userSettings') not @ClientModel({ tableName: ... })"
    status: completed
  - id: reactive-getrow-check
    content: "Fix @ManyToOne getter: replace `if (row === undefined)` with `if (Object.keys(row).length === 0)` to match TinyBase's actual return for missing rows"
    status: completed
  - id: reactive-collection-hydrate
    content: 'Fix Collection.items: hydrate TinyBase rows into Model instances via Object Pool instead of casting raw rows as T'
    status: completed
  - id: reactive-const-enum
    content: Add an isolatedModules compatibility callout to SKILL.md and the relevant reference files — const enum is preferred but requires isolatedModules:false, which is incompatible with Vite/esbuild/SWC
    status: completed
  - id: reactive-syncaction-type
    content: Add SyncAction TypeScript interface to SYNC-PROTOCOL.md with typed action union 'I' | 'U' | 'D' | 'A' | 'V' | 'C' | 'G'
    status: completed
  - id: reactive-use-hook
    content: Replace hand-rolled resolvePromise with React 18 use() hook in REACT-PATTERNS.md Suspense examples
    status: completed
  - id: reactive-model-base
    content: Add makeObservable(), attachReferences(), and missing SyncClient fields (lastSyncId, subscribedSyncGroups) to the Model base class definition
    status: completed
  - id: both-property-type
    content: Update @Property decorator in both skills to accept an explicit type argument instead of hardcoding 'string'
    status: completed
  - id: both-branded-ids
    content: Add branded type examples for entity/model IDs (AggregateID, TransactionId) in both skills using the Brand<K, T> pattern from typescript-expert
    status: completed
isProject: false
---

# TypeScript References Review

Applied lenses: **typescript-expert** (branded types, code review checklist, strict best practices) and **typescript-advanced-types** (conditional types, mapped types, discriminated unions, type safety patterns).

---

## Skill 1: `nestjs-domain-driven-hexagon`

### Critical Bug

`**Guard.isEmpty` treats `null` as a non-empty object ([references/DDD-TACTICAL.md](skills/nestjs-domain-driven-hexagon/references/DDD-TACTICAL.md))

`typeof null === 'object'` is true in JavaScript, but the guard checks `value !== undefined` instead of `value !== null`. `null` slips through to `Object.keys(value)` which throws in older runtimes or produces a misleading empty-object result.

```typescript
// Bug: typeof null === 'object', and null !== undefined
if (typeof value === 'object' && value !== undefined && Object.keys(value).length === 0)

// Fix
if (typeof value === 'object' && value !== null && Object.keys(value).length === 0)
```

---

### High-Severity Issues

**1. `ValueObject.equals` uses `JSON.stringify(this)` instead of `JSON.stringify(this.props)`** ([references/DDD-TACTICAL.md](skills/nestjs-domain-driven-hexagon/references/DDD-TACTICAL.md))

Serialising the full class instance includes inherited prototype properties in some runtimes and is unreliable. Only the `props` object should be compared.

```typescript
// Current (unreliable)
return JSON.stringify(this) === JSON.stringify(vo);

// Fix
return JSON.stringify(this.props) === JSON.stringify(vo.props);
```

**2. `Command` / concrete command self-referential constructor type** ([references/CQRS-EVENTS.md](skills/nestjs-domain-driven-hexagon/references/CQRS-EVENTS.md))

`CreateUserCommand` takes `props: CreateUserCommand` as its own constructor argument. This creates a recursive structural type. The pattern works but confuses inference and IDE tooling. A separate props interface is the TypeScript-correct approach.

```typescript
// Current: self-referential
constructor(props: CreateUserCommand) { super(props); ... }

// Fix: extract a props interface
export interface CreateUserCommandProps { email: string; country: string; ... }
export class CreateUserCommand extends Command {
  constructor(props: CreateUserCommandProps) { ... }
}
```

Same issue exists in `FindUsersQuery`. Additionally, `FindUsersQuery` uses `Object.assign(this, props)` — not type-safe; explicit property assignment is preferred.

**3. Concrete repository `findOneByEmail` uses `this.prisma` instead of `this.client`** ([references/PRISMA-ADAPTER.md](skills/nestjs-domain-driven-hexagon/references/PRISMA-ADAPTER.md))

This is a **runtime correctness bug**, not just a typing issue. `this.prisma` always opens a fresh connection from the pool — it ignores `RequestContextService` entirely. When a command handler calls `this.userRepo.transaction(async () => { ... })`, Prisma stores the `tx` client in `RequestContextService`. Any method called within that callback (including domain-event-triggered calls like `findOneByEmail`) must use that same `tx` client to be part of the same atomic write. Using `this.prisma` instead runs the query on a separate connection — outside the transaction — so it won't see uncommitted data and won't roll back if the transaction fails.

The cleanest fix is to narrow the return type of the `client` getter itself. Prisma defines `Prisma.TransactionClient` as `Omit<PrismaClient, '$connect' | '$disconnect' | '$transaction' | ...>`, so `PrismaClient` structurally satisfies it. Changing `client`'s return type to `Prisma.TransactionClient` eliminates the union `PrismaClient | Prisma.TransactionClient` and removes the need for casts everywhere:

```typescript
// In PrismaRepositoryBase — narrow the return type
protected get client(): Prisma.TransactionClient {
  return (
    (RequestContextService.getTransactionConnection() as Prisma.TransactionClient) ??
    this.prisma  // PrismaClient satisfies Prisma.TransactionClient structurally
  );
}

// Concrete repository — no cast needed
async findOneByEmail(email: string): Promise<UserEntity | undefined> {
  const record = await this.client.user.findUnique({ where: { email } });
  return record ? this.mapper.toDomain(record) : undefined;
}
```

The `updateAddress` method has the same `this.prisma` bypass. Both methods need to use `this.client`.

**4. `PrismaRepositoryBase.model` getter types `findUnique` as returning `undefined`** ([references/PRISMA-ADAPTER.md](skills/nestjs-domain-driven-hexagon/references/PRISMA-ADAPTER.md))

Prisma returns `null` (not `undefined`) for missing rows. The hand-typed delegate incorrectly uses `undefined`, which will cause type errors for consumers that properly distinguish `null | undefined`.

```typescript
findUnique: (args: { where: { id: string } }) => Promise<DbModel | null>;
//                                                                   ^^^^
```

**5. `ExceptionBase.toJSON` hardcodes `correlationId: ''`** ([references/DDD-TACTICAL.md](skills/nestjs-domain-driven-hexagon/references/DDD-TACTICAL.md))

The `correlationId` field is always an empty string in the serialised exception, defeating its purpose for tracing. Should pull from `RequestContextService` or require subclasses to provide it.

---

### Medium-Severity Issues

**6. `@Property` decorator type inferred as `type: 'string'` for all properties** ([references/DDD-TACTICAL.md](skills/nestjs-domain-driven-hexagon/references/DDD-TACTICAL.md) context applies to the reactive skill too)

All decorated properties are registered with `type: 'string'` regardless of their actual TypeScript type. The fix is to accept an explicit type argument:

```typescript
export function Property(type: PropertyMetadata['type'] = 'string') { ... }

// Usage
@Property('number')
public priority!: number;
```

**7. Missing `GraphQLMutation` named interface in `Transaction.toGraphQL()`** ([references/TRANSACTION-SYSTEM.md](skills/reactive-local-first-sync-engine/references/TRANSACTION-SYSTEM.md))

`toGraphQL()` returns an anonymous structural type. Per the typescript-expert review checklist, complex return types for public APIs must be named interfaces.

**8. `ContextInterceptor` creates an `Observable` without unsubscription cleanup** ([references/HEXAGONAL-NESTJS.md](skills/nestjs-domain-driven-hexagon/references/HEXAGONAL-NESTJS.md))

The manual `new Observable + subscriber` pattern doesn't wire up `teardownLogic`, leaking subscriptions if the downstream subscriber unsubscribes early. Use `switchMap` or provide a teardown.

---

### Lower-Severity / Best Practice Gaps

- `**convertPropsToObject` in `DDD-TACTICAL.md` iterates with `for...in` on a cast `Record<string, unknown>`. `Object.entries()` is cleaner and type-safe.
- `**AppRequestContext.transactionConnection` is typed as `unknown`. A union type `PrismaClient | Prisma.TransactionClient | undefined` eliminates all the force-casts in `client` getters.
- **Branded types not used for IDs** — `AggregateID = string` allows mixing user IDs and wallet IDs. The typescript-expert skill's `Brand<K, T>` pattern should be applied at minimum to `AggregateID`.
- `**toPersistence` mapper casts `role.toUpperCase() as UserRecord['role']` — safe only by convention. A lookup map or Prisma-generated enum import is safer.
- `**DomainEventProps<T>` with `Omit<T, 'id' | 'metadata'>` where `T` is the concrete event class itself creates an implicit circular definition. A dedicated `{email: string; country: string; ...}` interface per event is cleaner.

---

## Skill 2: `reactive-local-first-sync-engine`

### Critical Bugs

**1. `@ClientModel` API is inconsistent across reference files** ([references/MODEL-DEFINITION.md](skills/reactive-local-first-sync-engine/references/MODEL-DEFINITION.md) vs [references/REACT-PATTERNS.md](skills/reactive-local-first-sync-engine/references/REACT-PATTERNS.md))

`MODEL-DEFINITION.md` defines the decorator as `ClientModel(tableName: string)` (string argument), but `REACT-PATTERNS.md` uses it as `@ClientModel({ tableName: 'userSettings' })` (object argument). One of these is wrong and will cause a runtime TypeError.

The object-form call site in `REACT-PATTERNS.md` must be updated to the string form:

```typescript
// Fix
@ClientModel('userSettings')
class UserSettings extends Model { ... }
```

**2. `store.getRow()` returns `{}` for missing rows, not `undefined`** ([references/MODEL-DEFINITION.md](skills/reactive-local-first-sync-engine/references/MODEL-DEFINITION.md))

In `@ManyToOne`'s getter:

```typescript
const row = this._store.getRow(targetModel.toLowerCase() + 's', fkValue);
if (row === undefined) return undefined; // Bug: TinyBase never returns undefined here
return row as T;
```

TinyBase's `getRow()` returns an empty object `{}` when the row doesn't exist, not `undefined`. The check must be:

```typescript
if (Object.keys(row).length === 0) return undefined;
```

**3. `Collection<T>.items` returns raw TinyBase rows cast as `T`** ([references/MODEL-DEFINITION.md](skills/reactive-local-first-sync-engine/references/MODEL-DEFINITION.md))

```typescript
results.push(row as T); // row is Record<string, CellOrUndefined>, not a Model instance
```

This cast is unsafe — callers receive a plain object without MobX observability or class methods. Items must be hydrated into model instances (via the Object Pool) before being pushed.

---

### High-Severity Issues

**4. `const enum` requires an explicit `isolatedModules` callout** ([references/MODEL-DEFINITION.md](skills/reactive-local-first-sync-engine/references/MODEL-DEFINITION.md), [references/TRANSACTION-SYSTEM.md](skills/reactive-local-first-sync-engine/references/TRANSACTION-SYSTEM.md), [references/CHEATSHEET.md](skills/reactive-local-first-sync-engine/references/CHEATSHEET.md))

`const enum ItemStatus`, `const enum TransactionType`, `const enum IssueFilter` are used throughout and are the preferred style. However, modern frontend bundlers (Vite, esbuild, SWC) require `isolatedModules: true`, under which `const enum` values from imported files cannot be inlined and will cause a runtime error. The skill's compatibility table makes no mention of this constraint.

Fix: Add a note to the Compatibility table in `SKILL.md` and to the relevant reference files:

> `**const enum` requires `isolatedModules: false` in `tsconfig.json`. This is incompatible with Vite, esbuild, and SWC. If your project uses one of those bundlers, replace `const enum` with a regular `enum` (which works with `isolatedModules`) or an `as const` object + type alias.

**5. `SyncAction` interface is never formally defined** ([references/SYNC-PROTOCOL.md](skills/reactive-local-first-sync-engine/references/SYNC-PROTOCOL.md))

Delta packets are described with JSON examples and action type tables, but the TypeScript interface is absent. `applyDelta` takes `syncActions: SyncAction[]` but `SyncAction` is never declared. The reference needs:

```typescript
export interface SyncAction {
  id: number; // syncId for this action
  modelName: string;
  modelId: string;
  action: 'I' | 'U' | 'D' | 'A' | 'V' | 'C' | 'G';
  data: Record<string, unknown>;
}
```

**6. `resolvePromise` in `REACT-PATTERNS.md` should use React 18 `use()`** ([references/REACT-PATTERNS.md](skills/reactive-local-first-sync-engine/references/REACT-PATTERNS.md))

The hand-rolled `resolvePromise` manually attaches `.status`, `.value`, `.reason` to a standard `Promise` — non-standard, type-unsafe, and fragile. React 18+ ships the `use()` hook which does this correctly:

```typescript
import { use } from 'react'; // React 18+

const comments = use(issue.comments.hydrate());
```

The compatibility table lists React v18+/v19, so `use()` is available. The `resolvePromise` utility should either be removed or relegated to a "React 17 fallback" note.

**7. `Model` base class is incomplete** ([references/MODEL-DEFINITION.md](skills/reactive-local-first-sync-engine/references/MODEL-DEFINITION.md), [references/SYNC-PROTOCOL.md](skills/reactive-local-first-sync-engine/references/SYNC-PROTOCOL.md))

`SYNC-PROTOCOL.md` calls `instance.makeObservable()` and `instance.attachReferences()` on hydrated models, but these methods are absent from the `Model` base class definition in `MODEL-DEFINITION.md`. Similarly, `SyncClient.lastSyncId` and `SyncClient.subscribedSyncGroups` are referenced but not declared in the class body shown. The base class definition needs these members added.

**8. `@Property` decorator hardcodes `type: 'string'`** ([references/MODEL-DEFINITION.md](skills/reactive-local-first-sync-engine/references/MODEL-DEFINITION.md))

All properties are registered with `type: 'string'` regardless of their actual TypeScript type. This breaks the schema generation in `TINYBASE-FOUNDATION.md` which maps `PropertyMetadata.type` to TinyBase cell types. `number` and `boolean` properties would be stored incorrectly. The fix is the same as noted for the NestJS skill: accept an explicit type argument in `@Property`.

---

### Medium-Severity Issues

**9. `metadata!.` non-null assertions inside `@ClientModel`** ([references/MODEL-DEFINITION.md](skills/reactive-local-first-sync-engine/references/MODEL-DEFINITION.md))

After checking `if (metadata === undefined) { metadata = ... }`, the code proceeds with `metadata!.properties.forEach(...)`. Since `metadata` is reassigned in the `if` block, TypeScript should be able to narrow it — but the `!` is used anyway. Removing the `!` and ensuring the narrowing is correct is the standard approach.

**10. `UpdateTransaction.oldValue / newValue: unknown`** ([references/TRANSACTION-SYSTEM.md](skills/reactive-local-first-sync-engine/references/TRANSACTION-SYSTEM.md))

While `unknown` is better than `any`, every consumer must type-assert these values. A union type matching TinyBase's valid cell values would be more precise:

```typescript
type CellValue = string | number | boolean | undefined;
public oldValue: CellValue;
public newValue: CellValue;
```

**11. `executeTransactionBatch` has an unchecked cast on server response** ([references/TRANSACTION-SYSTEM.md](skills/reactive-local-first-sync-engine/references/TRANSACTION-SYSTEM.md))

```typescript
...Object.values(response.data).map(
  (r: { lastSyncId: number }) => r.lastSyncId,
)
```

`Object.values(response.data)` is `unknown[]`. The inline type annotation `(r: { lastSyncId: number })` is not a type guard — it's an unchecked assertion that will fail silently at runtime if the server returns unexpected data. A type guard or Zod/schema validation is needed here.

**12. `LazyReferenceCollection` references undefined private methods** ([references/SYNC-PROTOCOL.md](skills/reactive-local-first-sync-engine/references/SYNC-PROTOCOL.md))

`getCoveringPartialIndexValues()`, `hasModelsForPartialIndexValues()`, and `queryLocal()` are called inside `_doHydrate()` but never defined in the reference file. Even as pseudocode, the signatures should be declared.

---

### Lower-Severity / Best Practice Gaps

- `**@ManyToOne` infers `targetModel` from property name at runtime via string manipulation (`propertyKey.charAt(0).toUpperCase() + propertyKey.slice(1)`). There is no compile-time check that the inferred model name exists in `ModelRegistry`. A `targetModelName: string` argument would be safer.
- `**LazyReference.value` getter fires `this.hydrate()` without awaiting — intentional for the "empty-then-populated" pattern, but the JSDoc should state this explicitly to prevent accidental `async` misuse.
- **Branded types not used for entity IDs** — `model.id: string` allows mixing `Issue` IDs and `User` IDs. Same recommendation as the NestJS skill: apply `Brand<string, 'IssueId'>` to domain-critical ID fields.
- `**BootstrapConfig` type is inferred but never declared in `SYNC-PROTOCOL.md` — `determineBootstrapType(): BootstrapConfig` references a type that is never shown.

---

## Summary Table

| #   | Location                                 | Severity | Issue                                                           |
| --- | ---------------------------------------- | -------- | --------------------------------------------------------------- |
| 1   | NestJS / `DDD-TACTICAL.md` `Guard`       | Critical | `null` passes `typeof === 'object'` check                       |
| 2   | NestJS / `DDD-TACTICAL.md` `ValueObject` | High     | `JSON.stringify(this)` instead of `JSON.stringify(this.props)`  |
| 3   | NestJS / `CQRS-EVENTS.md` Commands       | High     | Self-referential constructor type                               |
| 4   | NestJS / `PRISMA-ADAPTER.md` repos       | High     | `this.prisma` bypasses transaction context                      |
| 5   | NestJS / `PRISMA-ADAPTER.md` base        | High     | `findUnique` typed as `undefined` instead of `null`             |
| 6   | NestJS / `DDD-TACTICAL.md` errors        | Medium   | `correlationId: ''` hardcoded in `toJSON`                       |
| 7   | Reactive / `MODEL-DEFINITION.md`         | Critical | `@ClientModel` API inconsistency across files                   |
| 8   | Reactive / `MODEL-DEFINITION.md`         | Critical | `getRow()` undefined check is wrong                             |
| 9   | Reactive / `MODEL-DEFINITION.md`         | Critical | `Collection.items` returns raw rows, not model instances        |
| 10  | Reactive / multiple refs                 | High     | `const enum` incompatible with `isolatedModules: true`          |
| 11  | Reactive / `SYNC-PROTOCOL.md`            | High     | `SyncAction` interface never declared                           |
| 12  | Reactive / `REACT-PATTERNS.md`           | High     | Hand-rolled `resolvePromise` instead of React `use()`           |
| 13  | Reactive / `MODEL-DEFINITION.md`         | High     | `Model` base class missing `makeObservable`, `attachReferences` |
| 14  | Both skills                              | Medium   | `@Property` always registers `type: 'string'`                   |
| 15  | Both skills                              | Low      | No branded types for entity/model IDs                           |
