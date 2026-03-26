# Model Definition

Decorator-based model system for defining syncable, observable data models backed by TinyBase.

## Table of Contents

- [ModelRegistry](#modelregistry)
- [Decorators](#decorators)
  - [@ClientModel](#clientmodel)
  - [@Property](#property)
  - [@ManyToOne](#manytoone)
  - [@OneToMany](#onetomany)
- [Base Model Class](#base-model-class)
- [Property Types](#property-types)
- [Load Strategies](#load-strategies)
- [Collection Abstraction](#collection-abstraction)
- [Schema Hash and Migration](#schema-hash-and-migration)
- [Conventions](#conventions)
- [Complete Examples](#complete-examples)

---

## ModelRegistry

The `ModelRegistry` is a global static class that stores metadata about every model registered via decorators. It is populated at class definition time (when decorators execute) and used at runtime for:

- Automatic MobX observable wiring
- Transaction generation (knowing which properties are synced)
- Relationship traversal (resolving foreign keys to model instances)
- TinyBase table/row mapping
- Schema hash computation for migration detection

```typescript
export type PropertyMetadata = {
  key: string;
  type: 'string' | 'number' | 'boolean' | 'Date' | 'custom';
  isObservable: boolean;
};

export type RelationMetadata = {
  key: string;
  type: 'ManyToOne' | 'OneToMany' | 'ManyToMany';
  targetModel: string;
  foreignKey: string | undefined;
  relatedName: string | undefined;
};

export type ModelMetadata = {
  modelName: string;
  tableName: string;
  loadStrategy: LoadStrategy;
  properties: Map<string, PropertyMetadata>;
  relations: Map<string, RelationMetadata>;
  constructor: new (...args: unknown[]) => Model;
};

export class ModelRegistry {
  private static models = new Map<string, ModelMetadata>();

  static register(modelName: string, metadata: ModelMetadata): void;
  static get(modelName: string): ModelMetadata | undefined;
  static getAll(): Map<string, ModelMetadata>;
  static getPropertyMetadata(
    modelName: string,
    propertyKey: string,
  ): PropertyMetadata | undefined;
  static getRelationMetadata(
    modelName: string,
    relationKey: string,
  ): RelationMetadata | undefined;
  static hasModel(modelName: string): boolean;
  static clear(): void;
}
```

TypeScript processes property decorators before class decorators. By the time `@ClientModel` runs, all `@Property`, `@ManyToOne`, and `@OneToMany` decorators have already registered their metadata. The class decorator then finalizes the model entry and wraps the constructor with MobX observability.

---

## Decorators

### @ClientModel

Marks a class as a syncable model. Registers the model constructor and metadata in `ModelRegistry`, then wraps the constructor to apply MobX `makeObservable` automatically.

```typescript
export function ClientModel(tableName: string) {
  return function <T extends { new (...args: unknown[]): Model }>(
    constructor: T,
  ) {
    const modelName = constructor.name;

    let metadata = ModelRegistry.get(modelName);
    if (metadata === undefined) {
      metadata = {
        modelName,
        tableName,
        loadStrategy: LoadStrategy.INSTANT,
        properties: new Map(),
        relations: new Map(),
        constructor,
      };
      ModelRegistry.register(modelName, metadata);
    } else {
      metadata.tableName = tableName;
    }

    return class extends constructor {
      constructor(...args: unknown[]) {
        super(...args);

        const mobxConfig: Record<string, unknown> = {};

        metadata!.properties.forEach((prop, key) => {
          if (prop.isObservable) {
            mobxConfig[key] = observable;
          }
        });

        metadata!.relations.forEach((_rel, key) => {
          mobxConfig[key] = computed;
        });

        makeObservable(this, mobxConfig);
      }
    };
  };
}
```

**Usage:**

```typescript
@ClientModel('issues')
export class Issue extends Model {
  // properties and relations...
}
```

The `tableName` argument maps directly to a TinyBase table name. Convention: lowercase plural of the model name.

### @Property

Marks a field as observable and synced. The field will be persisted to TinyBase and changes will generate `UpdateTransaction`s.

```typescript
export function Property(type: PropertyMetadata['type'] = 'string') {
  return function (target: unknown, propertyKey: string): void {
    const modelName = (target as { constructor: { name: string } }).constructor
      .name;
    let metadata = ModelRegistry.get(modelName);

    if (metadata === undefined) {
      metadata = {
        modelName,
        tableName: modelName.toLowerCase(),
        loadStrategy: LoadStrategy.INSTANT,
        properties: new Map(),
        relations: new Map(),
        constructor: (
          target as { constructor: new (...args: unknown[]) => Model }
        ).constructor,
      };
      ModelRegistry.register(modelName, metadata);
    }

    metadata.properties.set(propertyKey, {
      key: propertyKey,
      type,
      isObservable: true,
    });
  };
}
```

**Usage:**

```typescript
@Property()            // defaults to 'string' — no change needed for string fields
public title!: string;

@Property('number')    // explicit type for non-string primitives
public priority!: number;

@Property('boolean')
public isActive!: boolean;

@Property()
public description: string | undefined;
```

Passing the correct `type` matters for TinyBase schema generation: if a `number` property is registered as `'string'`, TinyBase will coerce the cell value and schema validation will fail.

Only primitive types and serializable values should use `@Property`. Relationships use `@ManyToOne` or `@OneToMany` instead.

### @ManyToOne

Defines a many-to-one relationship. Creates a computed getter that resolves a foreign key to a model instance by querying TinyBase.

```typescript
export function ManyToOne<T>(relatedName: string | undefined = undefined) {
  return function (target: unknown, propertyKey: string): void {
    const modelName = (target as { constructor: { name: string } }).constructor
      .name;
    // ... register metadata ...

    const targetModel =
      propertyKey.charAt(0).toUpperCase() + propertyKey.slice(1);
    const foreignKey = `${propertyKey}Id`;

    metadata.relations.set(propertyKey, {
      key: propertyKey,
      type: 'ManyToOne',
      targetModel,
      foreignKey,
      relatedName,
    });

    Object.defineProperty(target, propertyKey, {
      get(this: Model): T | undefined {
        const fkValue = (this as Record<string, unknown>)[foreignKey] as
          | string
          | undefined;
        if (fkValue === undefined) return undefined;
        // In full implementation: hydrate to model instance via ObjectPool
        const row = this._store.getRow(
          targetModel.toLowerCase() + 's',
          fkValue,
        );
        // TinyBase returns {} (not undefined) for missing rows
        if (Object.keys(row).length === 0) return undefined;
        // In full implementation: hydrate to model instance via ObjectPool
        return ObjectPool.getOrCreate(targetModel, fkValue, row) as T;
      },
      enumerable: true,
      configurable: true,
    });
  };
}
```

**Usage:**

```typescript
@ClientModel('issues')
export class Issue extends Model {
  @Property()
  public assigneeId: string | undefined;

  @ManyToOne<User>('assignedIssues')
  public assignee!: User | undefined;
}
```

The decorator infers `assigneeId` as the foreign key from the property name `assignee` + `Id`. The `relatedName` argument (`'assignedIssues'`) names the inverse collection on the target model.

### @OneToMany

Defines a one-to-many relationship. Registers the metadata; the `Collection` instance is initialized in the constructor.

```typescript
export function OneToMany<T>(foreignKey: string | undefined = undefined) {
  return function (target: unknown, propertyKey: string): void {
    // ... register metadata with inferred targetModel and foreignKey ...
  };
}
```

**Usage:**

```typescript
@ClientModel('users')
export class User extends Model {
  @OneToMany<Issue>('assigneeId')
  public readonly assignedIssues = new Collection<Issue>(
    this,
    'Issue',
    'assigneeId',
  );
}
```

The `Collection` class provides computed access to related models. See [Collection Abstraction](#collection-abstraction).

---

## Base Model Class

All models extend the `Model` base class, which provides:

```typescript
export abstract class Model {
  public id: string; // UUID v7 (time-ordered)
  public createdAt: Date;
  public updatedAt: Date;
  public _store: Store; // TinyBase store reference

  constructor(data?: Partial<ModelData>);

  // Persistence
  save(): void; // Write to TinyBase + queue CreateTransaction
  delete(): void; // Remove from TinyBase + queue DeleteTransaction

  // Hydration
  hydrate(rowData: Record<string, unknown>): void; // Populate from TinyBase row (no transactions)
  toRow(): Record<string, unknown>; // Serialize to TinyBase row format
  toJSON(): Record<string, unknown>; // Serialize for GraphQL

  /**
   * Activate MobX observability for all @Property fields on this instance.
   * Called by SyncClient after hydrate() during bootstrap / delta processing.
   * Delegates to makeObservable() with the MobX config registered by @ClientModel.
   */
  makeObservable(): void;

  /**
   * Wire up computed relationship getters (@ManyToOne / @OneToMany).
   * Must be called after makeObservable() so that computed values can
   * observe the foreign-key @Property fields they depend on.
   */
  attachReferences(): void;

  // Static queries (read from TinyBase)
  static find<T extends Model>(id: string): T | undefined;
  static findAll<T extends Model>(): T[];
  static where<T extends Model>(filters: Record<string, unknown>): T[];
}
```

**Key behaviors:**

- `save()` writes the model to TinyBase via `setRow`, then queues a `CreateTransaction`. After the first save, change tracking via MobX reactions is activated.
- `delete()` removes the TinyBase row via `delRow` and queues a `DeleteTransaction`.
- `hydrate()` sets the `_isHydrating` flag to suppress transaction generation while populating from stored data.
- Static query methods (`find`, `findAll`, `where`) read from TinyBase and hydrate new model instances.

**MobX change tracking** is set up after the first `save()`:

```typescript
protected _setupChangeTracking(): void {
  const metadata = this._getMetadata();
  if (metadata === undefined) return;

  metadata.properties.forEach((prop) => {
    if (!prop.isObservable) return;

    reaction(
      () => (this as Record<string, unknown>)[prop.key],
      (newValue, oldValue) => {
        if (this._isHydrating || newValue === oldValue) return;
        this.updatedAt = new Date();
        // Queue UpdateTransaction with property name, old value, new value
      },
    );
  });
}
```

This is what powers the Linear-like DX: `issue.title = "New Title"` automatically generates an `UpdateTransaction` without any explicit method call.

---

## Property Types

Inspired by Linear's property type system, models support several property categories:

| Type                  | Description                                          | Persisted | Observable | Example                        |
| --------------------- | ---------------------------------------------------- | --------- | ---------- | ------------------------------ |
| `property`            | Owned by the model, synced to server                 | Yes       | Yes        | `title`, `priority`            |
| `ephemeralProperty`   | Not persisted to IndexedDB, exists only in memory    | No        | Yes        | `lastUserInteraction`          |
| `reference`           | Foreign key to another model (stores ID)             | Yes       | Yes        | `assigneeId`                   |
| `referenceModel`      | Computed getter resolving a `reference` to an object | No        | Computed   | `assignee` (from `assigneeId`) |
| `referenceCollection` | Collection of models via inverse foreign key         | No        | Computed   | `assignedIssues`               |
| `backReference`       | Inverse of a reference; deleted when target deletes  | No        | Computed   | `favorite` on Issue            |
| `referenceArray`      | Many-to-many via ID array                            | Yes       | Yes        | `memberIds` on Project         |

For most applications, `property`, `reference`/`referenceModel`, and `referenceCollection` cover all needs.

---

## Load Strategies

Each model has a `loadStrategy` that controls when its data is fetched:

| Strategy              | Behavior                                                       | Use For                                |
| --------------------- | -------------------------------------------------------------- | -------------------------------------- |
| `instant`             | Loaded during bootstrap (default)                              | Small, always-needed data (User, Team) |
| `lazy`                | Not loaded at bootstrap; all instances fetched on first access | Medium datasets (ExternalUser)         |
| `partial`             | Loaded on demand by relationship index                         | Large datasets (Comment, IssueHistory) |
| `explicitlyRequested` | Only loaded when explicitly requested by user action           | History, audit logs                    |
| `local`               | Stored only in IndexedDB, never synced to server               | Prototyping new features               |

The `local` strategy enables a powerful prototyping workflow: build entire features frontend-first with IndexedDB persistence, then enable server sync later by switching the strategy.

---

## Collection Abstraction

`Collection<T>` provides a computed, reactive array of related models:

```typescript
export class Collection<T extends Model> {
  constructor(
    private owner: Model,
    private targetModelName: string,
    private foreignKey: string,
  ) {}

  @computed
  get items(): T[] {
    const store = this.owner._store;
    const tableName = this.targetModelName.toLowerCase() + 's';
    const rowIds = store.getRowIds(tableName);
    const results: T[] = [];

    rowIds.forEach((rowId) => {
      const row = store.getRow(tableName, rowId);
      if (row[this.foreignKey] === this.owner.id) {
        // Hydrate via ObjectPool so callers get a real Model instance
        // with MobX observability and class methods, not a raw TinyBase row.
        results.push(
          ObjectPool.getOrCreate(this.targetModelName, rowId, row) as T,
        );
      }
    });

    return results;
  }

  get length(): number {
    return this.items.length;
  }

  forEach(callback: (item: T) => void): void {
    this.items.forEach(callback);
  }

  map<U>(callback: (item: T) => U): U[] {
    return this.items.map(callback);
  }

  filter(predicate: (item: T) => boolean): T[] {
    return this.items.filter(predicate);
  }
}
```

For large datasets, use `LazyReferenceCollection` (see [SYNC-PROTOCOL.md](SYNC-PROTOCOL.md)) which supports:

- Hydration on first access
- Suspense integration (`collection.hydrate()` returns a Promise)
- Partial index resolution for efficient server queries

---

## Schema Hash and Migration

The `ModelRegistry` computes a `__schemaHash` from all model names, property names, property types, and schema versions. This hash is stored in IndexedDB metadata. On app startup, if the computed hash differs from the stored hash, a database migration is triggered:

1. Compare `__schemaHash` against stored value
2. If different, increment `schemaVersion`
3. Pass new version to `indexedDB.open()` to trigger `onupgradeneeded`
4. `StoreManager.createStores()` creates or updates tables for each model

This ensures that model changes (new properties, new models, removed fields) are automatically detected and the local database is migrated.

---

## Conventions

### ID Generation

- **Entity IDs**: UUID v7 via `uuid` package -- time-ordered, database-friendly, globally unique
- **Transaction IDs**: Nano ID via `nanoid` package -- compact, URL-safe, ephemeral (transactions are short-lived)

### Branded ID Types

Use branded types so the compiler prevents passing an `IssueId` where a `UserId` is expected:

```typescript
type Brand<K, T> = K & { __brand: T };

/** Branded entity ID types — prevent cross-model ID confusion at compile time. */
export type IssueId = Brand<string, 'IssueId'>;
export type UserId = Brand<string, 'UserId'>;
export type TeamId = Brand<string, 'TeamId'>;
export type TransactionId = Brand<string, 'TransactionId'>;

// The model base class then declares:
export abstract class Model {
  public id: Brand<string, string>; // narrowed per model
  // ...
}

// In concrete models, narrow the id type:
@ClientModel('issues')
export class Issue extends Model {
  declare public id: IssueId;
  // ...
}

// Usage — type-safe call sites
function resolveIssue(id: IssueId): Issue | undefined {
  return Issue.find(id);
}
const userId = 'u-123' as UserId;
resolveIssue(userId); // TS error: UserId is not assignable to IssueId ✓
```

### Enums

Always use `const enum` with `SCREAMING_SNAKE_CASE`:

```typescript
const enum ItemStatus {
  DRAFT = 'DRAFT',
  PUBLISHED = 'PUBLISHED',
  ARCHIVED = 'ARCHIVED',
}
```

Zero runtime overhead. Values are inlined at compile time.

> **`isolatedModules` compatibility:** `const enum` requires `isolatedModules: false` in `tsconfig.json`. This is **incompatible with Vite, esbuild, and SWC**, which all mandate `isolatedModules: true`. If your bundler requires `isolatedModules: true`, replace `const enum` with a regular `enum` (safe across file boundaries) or an `as const` object + union type alias:
>
> ```typescript
> // isolatedModules-safe alternative
> const ItemStatus = {
>   DRAFT: 'DRAFT',
>   PUBLISHED: 'PUBLISHED',
>   ARCHIVED: 'ARCHIVED',
> } as const;
> type ItemStatus = (typeof ItemStatus)[keyof typeof ItemStatus];
> ```

### Null Policy

Never use `null`. Always use `undefined` with explicit union types:

```typescript
// Correct
public description: string | undefined;
public assigneeId: string | undefined;

// Wrong
public description: string | null;
public assigneeId?: string;
```

### MobX Computed Getters

The only permitted use of getters in model classes. Required for MobX reactivity on derived state:

```typescript
@computed
get isDraft(): boolean {
  return this.status === ItemStatus.DRAFT;
}
```

Everywhere else: use explicit methods (`getX()`, `setX()`).

### Table Names

Lowercase plural of the model name, passed to `@ClientModel`:

```typescript
@ClientModel('issues')    // not 'Issue' or 'issue'
@ClientModel('users')
@ClientModel('comments')
```

---

## Complete Examples

### Simple Model (No Relations)

```typescript
import { computed } from 'mobx';
import { ClientModel, Property } from '../decorators';
import { Model } from '../model.base';

const enum ItemStatus {
  DRAFT = 'DRAFT',
  PUBLISHED = 'PUBLISHED',
  ARCHIVED = 'ARCHIVED',
}

@ClientModel('items')
export class Item extends Model {
  @Property()
  public title!: string;

  @Property('string')
  public status!: ItemStatus;

  @Property()
  public description: string | undefined;

  @Property()
  public userId!: string;

  constructor(data: {
    id: string | undefined;
    createdAt: Date | string | undefined;
    updatedAt: Date | string | undefined;
    title: string;
    status: ItemStatus;
    description: string | undefined;
    userId: string;
  }) {
    super(data);
    this.title = data.title;
    this.status = data.status;
    this.description = data.description;
    this.userId = data.userId;
  }

  static create(data: {
    title: string;
    userId: string;
    description: string | undefined;
  }): Item {
    const item = new Item({
      id: undefined,
      createdAt: undefined,
      updatedAt: undefined,
      title: data.title,
      status: ItemStatus.DRAFT,
      description: data.description,
      userId: data.userId,
    });
    item.save();
    return item;
  }

  @computed
  get isDraft(): boolean {
    return this.status === ItemStatus.DRAFT;
  }

  publish(): void {
    this.status = ItemStatus.PUBLISHED; // Auto-generates UpdateTransaction
  }

  archive(): void {
    this.status = ItemStatus.ARCHIVED;
  }
}
```

### Model with Relationships

```typescript
@ClientModel('users')
export class User extends Model {
  @Property()
  public name!: string;

  @Property()
  public email!: string;

  @Property()
  public teamId: string | undefined;

  @ManyToOne<Team>('members')
  public team!: Team | undefined;

  @OneToMany<Media>('userId')
  public readonly media = new Collection<Media>(this, 'Media', 'userId');

  @OneToMany<Issue>('assigneeId')
  public readonly assignedIssues = new Collection<Issue>(
    this,
    'Issue',
    'assigneeId',
  );

  static create(data: { name: string; email: string }): User {
    const user = new User({
      id: undefined,
      createdAt: undefined,
      updatedAt: undefined,
      ...data,
    });
    user.save();
    return user;
  }

  assignToTeam(teamId: string): void {
    this.teamId = teamId; // Updates foreign key, auto-generates UpdateTransaction
  }
}
```

### Usage in React

```typescript
import { observer } from 'mobx-react-lite';
import { Item } from '@/sync-engine';

export const ItemCard = observer(({ itemId }: { itemId: string }) => {
  const item = Item.find(itemId);
  if (item === undefined) return undefined;

  return (
    <div>
      <h3>{item.title}</h3>
      <p>{item.description}</p>
      <button onClick={() => item.publish()}>Publish</button>
    </div>
  );
});
```

No loading states. No fetch calls. No error handling boilerplate. Data is just _there_.
