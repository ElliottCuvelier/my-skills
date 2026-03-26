# TinyBase Foundation

TinyBase serves as the local storage layer: an in-memory reactive data store with automatic IndexedDB persistence and optional CRDT-based multi-client synchronization.

## Table of Contents

- [Role in the Architecture](#role-in-the-architecture)
- [Store Singleton](#store-singleton)
- [Schema Definition](#schema-definition)
- [IndexedDB Persistence](#indexeddb-persistence)
- [MergeableStore and CRDT Sync](#mergeablestore-and-crdt-sync)
- [Bridge: TinyBase Rows and MobX Models](#bridge-tinybase-rows-and-mobx-models)
- [Static Query Methods](#static-query-methods)
- [React Bootstrap Hooks](#react-bootstrap-hooks)
- [When to Use CRDT Sync vs Transaction Queue](#when-to-use-crdt-sync-vs-transaction-queue)
- [Database Management](#database-management)

---

## Role in the Architecture

TinyBase occupies a specific niche in the layered architecture:

```
MobX Models (OOP view layer)
    |  writes via save()/delete()
    |  reads via find()/findAll()
    v
TinyBase Store (structured in-memory data)
    |  auto-persisted
    v
IndexedDB (durable local storage)
```

TinyBase is **not** the reactivity layer (that is MobX) and is **not** the sync protocol (that is the transaction queue + delta packets). TinyBase provides:

1. **Structured in-memory storage** -- tables, rows, cells with type safety
2. **IndexedDB persistence** -- automatic load/save, survives page reload
3. **Optional CRDT sync** -- `MergeableStore` for collaborative ephemeral state
4. **Efficient queries** -- row lookups by ID, table scans, cell-level access

Models read from and write to TinyBase. MobX observes model properties (not TinyBase directly). React components observe MobX models (not TinyBase directly). TinyBase is the storage engine underneath it all.

---

## Store Singleton

The application uses a single TinyBase store instance, initialized lazily:

```typescript
import { createStore } from 'tinybase';
import type { Store } from 'tinybase';
import { createIndexedDbPersister } from 'tinybase/persisters/persister-indexed-db';
import { createAppSchema } from './schema';

let storeInstance: Store | undefined = undefined;

export function getStore(): Store {
  if (storeInstance !== undefined) return storeInstance;

  storeInstance = createStore();

  const persister = createIndexedDbPersister(storeInstance, 'app-store');
  persister.startAutoLoad();
  persister.startAutoSave();

  return storeInstance;
}
```

For applications requiring CRDT sync, replace `createStore` with `createMergeableStore`:

```typescript
import { createMergeableStore } from 'tinybase';

export function getStore(): MergeableStore {
  if (storeInstance !== undefined) return storeInstance;

  storeInstance = createMergeableStore();

  const persister = createIndexedDbPersister(storeInstance, 'app-store');
  persister.startAutoLoad();
  persister.startAutoSave();

  return storeInstance;
}
```

The store name (`'app-store'`) becomes the IndexedDB database name. For multi-workspace applications (like Linear), derive the name from the user/workspace ID:

```typescript
const dbName = `app-store-${workspaceId}`;
```

---

## Schema Definition

TinyBase schemas can be defined to enforce table and cell types. Align the schema with the `ModelRegistry` metadata:

```typescript
import { createStore } from 'tinybase';

export function createAppStore() {
  return createStore().setTablesSchema({
    items: {
      id: { type: 'string' },
      title: { type: 'string' },
      status: { type: 'string' },
      description: { type: 'string' },
      userId: { type: 'string' },
      createdAt: { type: 'string' },
      updatedAt: { type: 'string' },
    },
    users: {
      id: { type: 'string' },
      name: { type: 'string' },
      email: { type: 'string' },
      teamId: { type: 'string' },
      createdAt: { type: 'string' },
      updatedAt: { type: 'string' },
    },
  });
}
```

TinyBase v8 cells support five types: `string`, `number`, `boolean`, `object`, and `array`. Objects and arrays are stored natively (transparent JSON round-tripping under the hood). `Date` and enum values still need explicit serialization:

| Model Type | TinyBase Cell Type | Serialization              |
| ---------- | ------------------ | -------------------------- |
| `string`   | `string`           | Direct                     |
| `number`   | `number`           | Direct                     |
| `boolean`  | `boolean`          | Direct                     |
| `Date`     | `string`           | `date.toISOString()`       |
| `enum`     | `string`           | String value of const enum |
| `object`   | `object`           | Native (v8+)               |
| `array`    | `array`            | Native (v8+)               |

Schema definition is optional but recommended. Without it, TinyBase accepts any value for any cell. With a schema, type mismatches are caught at write time. TinyBase v8 also provides a middleware system to intercept and validate data before writes, which can be combined with schemas for additional integrity checks.

For dynamic schema generation from `ModelRegistry`:

```typescript
export function generateSchema(): Record<
  string,
  Record<string, { type: string }>
> {
  const schema: Record<string, Record<string, { type: string }>> = {};

  ModelRegistry.getAll().forEach((metadata) => {
    const tableSchema: Record<string, { type: string }> = {
      id: { type: 'string' },
      createdAt: { type: 'string' },
      updatedAt: { type: 'string' },
    };

    metadata.properties.forEach((prop) => {
      const typeMap: Record<string, string> = {
        number: 'number',
        boolean: 'boolean',
        object: 'object',
        array: 'array',
      };
      tableSchema[prop.key] = {
        type: typeMap[prop.type] ?? 'string',
      };
    });

    schema[metadata.tableName] = tableSchema;
  });

  return schema;
}
```

---

## IndexedDB Persistence

TinyBase persists to IndexedDB via `createIndexedDbPersister`. Two auto-modes handle synchronization between the in-memory store and the durable database:

- **`startAutoLoad()`** -- On startup, loads existing data from IndexedDB into the in-memory store. Also listens for external changes (e.g., from another tab).
- **`startAutoSave()`** -- On every store change, writes the updated data back to IndexedDB.

```typescript
const persister = createIndexedDbPersister(store, 'app-store');

await persister.startAutoLoad();
await persister.startAutoSave();
```

Both methods return promises that resolve when the initial load/save is complete. For bootstrap flow:

```typescript
export async function initializeStore(): Promise<Store> {
  const store = createStore();

  const persister = createIndexedDbPersister(store, `app-${workspaceId}`);

  // Load existing data first
  await persister.startAutoLoad();

  // Then enable auto-save for future changes
  await persister.startAutoSave();

  return store;
}
```

### Multiple Databases

For multi-workspace applications, each workspace gets its own IndexedDB database. A metadata database tracks all workspace databases (mirroring Linear's `linear_databases` pattern):

```typescript
// Metadata database: tracks which workspace databases exist
const metaStore = createStore();
const metaPersister = createIndexedDbPersister(metaStore, 'app-databases');

// Workspace-specific database
const workspaceStore = createStore();
const workspacePersister = createIndexedDbPersister(
  workspaceStore,
  `app-${userId}-${workspaceId}`,
);
```

---

## MergeableStore and CRDT Sync

For collaborative state that does not require server-side validation (presence indicators, cursor positions, shared UI state), use TinyBase's built-in CRDT sync:

```typescript
import { createMergeableStore } from 'tinybase';
import { createWsSynchronizer } from 'tinybase/synchronizers/synchronizer-ws-client';

const store = createMergeableStore();
const synchronizer = await createWsSynchronizer(
  store,
  new WebSocket('ws://localhost:8080/workspace-id'),
);
await synchronizer.startSync();
```

The `MergeableStore` automatically tracks cell-level timestamps and uses last-writer-wins at the cell level to merge concurrent changes. No manual conflict resolution needed.

**Server setup:**

```typescript
import { createWsServer } from 'tinybase/synchronizers/synchronizer-ws-server';
import { WebSocketServer } from 'ws';

const server = createWsServer(new WebSocketServer({ port: 8080 }), (pathId) =>
  createIndexedDbPersister(
    createMergeableStore(),
    pathId.replace(/[^a-zA-Z0-9]/g, '-') + '.json',
  ),
);
```

The `pathId` in the URL path (`/workspace-id`) determines the sync group. Clients connecting to the same path share the same data.

### When MergeableStore is Enough

- Ephemeral collaborative state (who is online, cursor positions)
- Simple counters or toggles shared between users
- Data where any client's write is authoritative (no validation needed)

### When You Need the Transaction Queue Instead

- Business mutations requiring server-side validation
- Mutations that trigger server-side effects (emails, notifications, history)
- Data with access control (not all users can modify all fields)
- Need for audit trail / undo history

Many applications use **both**: `MergeableStore` for presence/ephemeral state and the transaction queue for domain mutations.

---

## Bridge: TinyBase Rows and MobX Models

The bridge between TinyBase storage and MobX models consists of two operations:

### Writing: Model to TinyBase (`toRow`)

```typescript
toRow(): Record<string, unknown> {
  const metadata = this._getMetadata();
  const row: Record<string, unknown> = {
    id: this.id,
    createdAt: this.createdAt.toISOString(),
    updatedAt: this.updatedAt.toISOString(),
  };

  metadata?.properties.forEach((prop) => {
    const value = (this as Record<string, unknown>)[prop.key];
    if (value instanceof Date) {
      row[prop.key] = value.toISOString();
    } else {
      row[prop.key] = value;
    }
  });

  return row;
}
```

Called by `save()` to write a model to TinyBase. Only `@Property` fields are serialized -- relationships are not stored (they are computed from foreign keys). With TinyBase v8, objects and arrays pass through directly without manual `JSON.stringify()` -- TinyBase handles the round-tripping transparently.

### Reading: TinyBase to Model (`hydrate`)

```typescript
hydrate(rowData: Record<string, unknown>): void {
  this._isHydrating = true;

  Object.keys(rowData).forEach((key) => {
    if (key in this) {
      (this as Record<string, unknown>)[key] = rowData[key];
    }
  });

  this._isHydrating = false;
}
```

Called by static query methods (`find`, `findAll`, `where`) to populate a model from a TinyBase row. The `_isHydrating` flag prevents transaction generation during population.

### Object Pool (Future Enhancement)

In Linear's architecture, hydrated models are stored in an **Object Pool** (`modelLookup` map) keyed by ID. This avoids creating duplicate instances for the same entity and ensures that all references to a model point to the same observable object.

```typescript
class ObjectPool {
  private models = new Map<string, Model>();

  get<T extends Model>(id: string): T | undefined {
    return this.models.get(id) as T | undefined;
  }

  set(model: Model): void {
    this.models.set(model.id, model);
  }

  remove(id: string): void {
    this.models.delete(id);
  }
}
```

Without an object pool, each `Model.find(id)` call creates a new instance. With an object pool, the same instance is returned every time, and MobX reactivity propagates correctly across all observers.

---

## Static Query Methods

All models inherit static query methods that read from TinyBase:

```typescript
// Find by ID -- O(1) row lookup
const user = User.find('user-id');
if (user !== undefined) {
  console.log(user.name);
}

// Find all -- table scan
const users = User.findAll();
users.forEach((user) => console.log(user.name));

// Filter by criteria -- table scan + predicate
const admins = User.where({ role: UserRole.ADMIN });
```

These methods are synchronous because TinyBase is an in-memory store. Data is always available locally -- no async/await, no loading states, no promises.

For indexed queries (filtering by foreign key), TinyBase indexes can be used:

```typescript
import { createIndexes } from 'tinybase';

const indexes = createIndexes(store);
indexes.setIndexDefinition('issuesByAssignee', 'issues', 'assigneeId');

// Efficient indexed lookup
const issueIds = indexes.getSliceRowIds('issuesByAssignee', userId);
```

---

## React Bootstrap Hooks

TinyBase provides React hooks for store management. Use these for app initialization, not for data access (use MobX `observer` for that):

```typescript
import { createStore } from 'tinybase';
import { createIndexedDbPersister } from 'tinybase/persisters/persister-indexed-db';
import { Provider, useCreateStore, useCreatePersister } from 'tinybase/ui-react';

function App() {
  const store = useCreateStore(() => createStore());

  useCreatePersister(
    store,
    (store) => createIndexedDbPersister(store, 'app-store'),
    [],
    async (persister) => {
      await persister.startAutoLoad();
      await persister.startAutoSave();
    },
  );

  return (
    <Provider store={store}>
      {/* App content -- components use observer() + Model.find(), not TinyBase hooks */}
    </Provider>
  );
}
```

The `Provider` makes the store available via context. Model classes access it via `getStore()` singleton. The React hooks are primarily for lifecycle management (creating and cleaning up the store and persister).

---

## When to Use CRDT Sync vs Transaction Queue

| Aspect              | TinyBase CRDT Sync                    | Transaction Queue                         |
| ------------------- | ------------------------------------- | ----------------------------------------- |
| **Mechanism**       | `MergeableStore` + `WsSynchronizer`   | Queue -> GraphQL mutation -> delta packet |
| **Conflict model**  | Cell-level LWW (automatic)            | Transaction-level LWW (rebase)            |
| **Server logic**    | None (pure data replication)          | Full (validation, side effects, events)   |
| **Access control**  | None (all clients can write anything) | Server-enforced per-mutation              |
| **Audit trail**     | No                                    | Yes (syncId, transaction history)         |
| **Offline support** | Yes (merge on reconnect)              | Yes (queue persisted to IndexedDB)        |
| **Best for**        | Presence, cursors, ephemeral state    | Domain mutations, business logic          |

**Recommendation:** Start with the transaction queue for all domain data. Add `MergeableStore` CRDT sync only for collaborative ephemeral state that does not need server validation.

---

## Database Management

### Special Tables

Following Linear's pattern, the TinyBase database includes special metadata tables:

- **`_meta`**: Stores per-model persistence state (`persisted: boolean`) and database metadata (`lastSyncId`, `firstSyncId`, `subscribedSyncGroups`, `updatedAt`)
- **`_transactions`**: Stores unsent or queued transactions for offline persistence and crash recovery

These are regular TinyBase tables but are not exposed as model classes. They are managed internally by the sync engine.

### Database Versioning

The database version is derived from the `ModelRegistry.__schemaHash`. When models change (new fields, new models), the hash changes, triggering a migration:

```typescript
async function openDatabase(workspaceId: string): Promise<Store> {
  const currentHash = ModelRegistry.computeSchemaHash();
  const storedHash = await getStoredSchemaHash(workspaceId);

  if (currentHash !== storedHash) {
    // Migration needed: clear and re-bootstrap
    await migrateDatabase(workspaceId, currentHash);
  }

  return initializeStore(workspaceId);
}
```

For full bootstrapping after migration, see [SYNC-PROTOCOL.md](SYNC-PROTOCOL.md).
