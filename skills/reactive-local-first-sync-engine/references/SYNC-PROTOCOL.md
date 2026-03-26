# Sync Protocol

End-to-end synchronization lifecycle: bootstrapping the local database, establishing WebSocket connections, processing delta packets, lazy-loading models on demand, and maintaining client-server consistency.

## Table of Contents

- [SyncId: The Global Version Number](#syncid-the-global-version-number)
- [Bootstrapping](#bootstrapping)
  - [Full Bootstrap](#full-bootstrap)
  - [Partial Bootstrap](#partial-bootstrap)
  - [Local Bootstrap](#local-bootstrap)
  - [Determining Bootstrap Type](#determining-bootstrap-type)
- [Object Pool and Hydration](#object-pool-and-hydration)
- [WebSocket Connection](#websocket-connection)
- [Delta Packets](#delta-packets)
  - [Sync Action Types](#sync-action-types)
  - [Applying Deltas](#applying-deltas)
  - [Rebasing Pending Transactions](#rebasing-pending-transactions)
- [Lazy Hydration](#lazy-hydration)
  - [LazyReferenceCollection](#lazyreferencecollection)
  - [LazyReference](#lazyreference)
  - [Partial Indexes](#partial-indexes)
  - [Suspense Integration](#suspense-integration)
- [Route-Based Preloading](#route-based-preloading)
- [Sync Groups and Access Control](#sync-groups-and-access-control)
- [Connection Management](#connection-management)

---

## SyncId: The Global Version Number

The `syncId` (also called `lastSyncId`) is a monotonically increasing integer that serves as the **global version number of the entire database**. Every change confirmed by the server increments the `syncId` by 1.

```
Client A sends: issue.title = "New"
  Server: syncId 1000 -> 1001 (issue updated)
  Server: syncId 1001 -> 1002 (IssueHistory record created -- side effect)
  Delta packet to all clients: [syncAction(1001), syncAction(1002)]
```

The `syncId` spans the entire database, not individual workspaces or models. Even if a change happens in another workspace, the global counter increments. This means the `syncId` may jump by large amounts between changes in your workspace.

**Client uses `syncId` to determine sync state:**

- Client `lastSyncId` < server `lastSyncId`: client is behind, missing delta packets
- Client `lastSyncId` === server `lastSyncId`: client is up to date
- After bootstrap: `firstSyncId` records the snapshot point, `lastSyncId` tracks the current state

The `syncId` is stored in the `_meta` table in IndexedDB and updated as delta packets are processed.

---

## Bootstrapping

Bootstrapping is the process of loading initial data into the client. There are three types, chosen based on the state of the local database.

### Full Bootstrap

Triggered when:

- The local database is empty (first load)
- No stores are ready (tables exist but are empty)
- `lastSyncId` is undefined
- Models are outdated and need refresh

**Flow:**

```
1. Client sends GET /sync/bootstrap?type=full&onlyModels=Issue,User,Team,...
2. Server responds with NDJSON stream (one model per line)
3. Last line contains metadata: lastSyncId, subscribedSyncGroups, databaseVersion
4. Client writes each model to its TinyBase table
5. Client updates _meta: lastSyncId, firstSyncId, subscribedSyncGroups
6. Models with loadStrategy=instant are hydrated into memory
7. MobX observability is activated on hydrated models
```

**Request:**

```
GET /sync/bootstrap?type=full&onlyModels=WorkflowState,Issue,Team,User,Comment&firstSyncId=0
```

The `onlyModels` parameter lists models with `instant` or `lazy` load strategies.

**Response (NDJSON stream):**

```json
{"id":"abc-123","title":"Welcome","priority":1,"teamId":"team-1","__class":"Issue"}
{"id":"def-456","name":"Engineering","__class":"Team"}
{"id":"ghi-789","name":"Alice","email":"alice@example.com","__class":"User"}
_metadata_={"lastSyncId":2326713666,"subscribedSyncGroups":["team-1","user-1"],"databaseVersion":948,"returnedModelsCount":{"Issue":3,"Team":1,"User":1}}
```

Each line except the last is a model instance. The `__class` field maps to the model constructor in `ModelRegistry`. The last line (`_metadata_`) contains sync state to store in the local database.

### Partial Bootstrap

Triggered when:

- Client joins a new sync group (e.g., added to a new team)
- Specific models need refreshing (e.g., team data loaded on demand)

```
GET /sync/bootstrap?type=partial&syncGroups=team-2&onlyModels=Issue,Comment&firstSyncId=3528373991
```

Only models belonging to the specified sync groups are loaded. The `firstSyncId` indicates the client's current sync state; the server may include delta information to bring the client up to date.

### Local Bootstrap

Triggered when:

- Local database exists and is valid
- `lastSyncId` is defined and schema hash matches

**Flow:**

```
1. Load models from IndexedDB into TinyBase (via persister auto-load)
2. Hydrate instant models into memory
3. Connect WebSocket for delta sync
4. Request any missed deltas since local lastSyncId
```

Local bootstrap is the fastest path -- no server request needed for initial data. The client uses its stored `lastSyncId` to request only missed delta packets.

### Determining Bootstrap Type

```typescript
function determineBootstrapType(): BootstrapConfig {
  const lastSyncId = getMetaValue('lastSyncId');
  const storedSchemaHash = getMetaValue('schemaHash');
  const currentSchemaHash = ModelRegistry.computeSchemaHash();

  // Schema changed: full bootstrap required
  if (storedSchemaHash !== currentSchemaHash) {
    return {
      type: 'full',
      modelsToLoad: getInstantAndLazyModels(),
      lastSyncId: 0,
    };
  }

  // No data: full bootstrap
  if (lastSyncId === undefined || lastSyncId === 0) {
    return {
      type: 'full',
      modelsToLoad: getInstantAndLazyModels(),
      lastSyncId: 0,
    };
  }

  // Stores not ready: full bootstrap
  if (!storeManager.allStoresReady()) {
    return {
      type: 'full',
      modelsToLoad: getInstantAndLazyModels(),
      lastSyncId: 0,
    };
  }

  // Local data exists and is valid: local bootstrap
  return { type: 'local', lastSyncId };
}
```

---

## Object Pool and Hydration

After bootstrapping, models with `loadStrategy: instant` are hydrated into memory and added to the **Object Pool**:

```typescript
class SyncClient {
  /** Monotonically increasing sync cursor — mirrors the last processed delta's `id`. */
  public lastSyncId: number = 0;

  /**
   * Sync group keys the client is currently subscribed to.
   * Sent in the WebSocket handshake and with every delta request so the server
   * knows which groups to include in delta packets.
   */
  public subscribedSyncGroups: string[] = [];

  private modelLookup = new Map<string, Model>();

  addModelToLiveCollections(model: Model): void {
    this.modelLookup.set(model.id, model);
  }

  getModel<T extends Model>(id: string): T | undefined {
    return this.modelLookup.get(id) as T | undefined;
  }

  removeModel(id: string): void {
    this.modelLookup.delete(id);
  }
}
```

The Object Pool ensures that all references to a model ID point to the same MobX observable instance. Without it, `Model.find('abc')` called in two different components would create two separate instances that don't share reactivity.

**Hydration flow for each model from bootstrap data:**

```typescript
function hydrateModel(data: Record<string, unknown>): Model {
  const className = data.__class as string;
  const metadata = ModelRegistry.get(className);
  if (metadata === undefined) throw new Error(`Unknown model: ${className}`);

  const instance = new metadata.constructor();
  instance.hydrate(data); // Populate fields (no transactions)
  instance.makeObservable(); // Activate MobX
  instance.attachReferences(); // Wire up relationship getters

  syncClient.addModelToLiveCollections(instance);
  return instance;
}
```

---

## WebSocket Connection

After bootstrap completes and persisted transactions are loaded, the client establishes a WebSocket connection:

```typescript
class SyncClient {
  public lastSyncId: number = 0;
  public subscribedSyncGroups: string[] = [];
  private ws: WebSocket;

  startSyncing(): void {
    this.ws = new WebSocket(`wss://api.example.com/sync`);

    this.ws.onopen = () => {
      this.handshake();
    };

    this.ws.onmessage = (event) => {
      const deltaPacket = JSON.parse(event.data);
      this.applyDelta(deltaPacket);
    };
  }

  private handshake(): void {
    // Server responds with its lastSyncId
    // If client.lastSyncId < server.lastSyncId, request missed deltas
    this.ws.send(
      JSON.stringify({
        type: 'handshake',
        lastSyncId: this.lastSyncId,
        syncGroups: this.subscribedSyncGroups,
      }),
    );
  }
}
```

The handshake callback includes the server's `lastSyncId`. If the client's `lastSyncId` is lower, the client requests delta packets to fill the gap:

```
GET /sync/delta?since=2326713000&syncGroups=team-1,user-1
```

---

## Delta Packets

### Sync Action Types

Delta packets contain an array of sync actions. Each action has a type indicating the operation:

| Action | Meaning    | Description                             |
| ------ | ---------- | --------------------------------------- |
| `I`    | Insert     | New model created                       |
| `U`    | Update     | Model properties changed                |
| `D`    | Delete     | Model removed                           |
| `A`    | Archive    | Model archived (soft delete)            |
| `V`    | Unarchive  | Model unarchived                        |
| `C`    | Covering   | Covering update (related model changes) |
| `G`    | Sync group | User added to / removed from sync group |

**Example delta packet** (user changed an issue's assignee):

```json
[
  {
    "id": 2361610825,
    "modelName": "Issue",
    "modelId": "abc-123",
    "action": "U",
    "data": {
      "id": "abc-123",
      "title": "Connect to Slack",
      "assigneeId": "user-456",
      "updatedAt": "2024-07-13T06:25:40.612Z"
    }
  },
  {
    "id": 2361610826,
    "modelName": "IssueHistory",
    "modelId": "hist-789",
    "action": "I",
    "data": {
      "id": "hist-789",
      "issueId": "abc-123",
      "toAssigneeId": "user-456"
    }
  }
]
```

Delta packets may contain more changes than the original transaction because the server can trigger side effects (creating history records, updating counters, sending notifications).

### SyncAction Interface

Every element in a delta packet conforms to the `SyncAction` interface:

```typescript
export interface SyncAction {
  /** Server-assigned monotonic sync ID for this action. */
  id: number;
  /** Name of the model affected (e.g. `'Issue'`, `'User'`). */
  modelName: string;
  /** UUID v7 of the affected model instance. */
  modelId: string;
  /**
   * Action type:
   * - `'I'` Insert — new model created on server
   * - `'U'` Update — model fields changed on server
   * - `'D'` Delete — model deleted on server
   * - `'A'` Archive — model archived on server
   * - `'V'` Verify — confirms a locally-created model (server accepted UUID)
   * - `'C'` Conflict — server rejected a local transaction; client must revert
   * - `'G'` Group — sync group membership changed
   */
  action: 'I' | 'U' | 'D' | 'A' | 'V' | 'C' | 'G';
  /** Full or partial row data for Insert/Update/Verify actions. */
  data: Record<string, unknown>;
}
```

### Applying Deltas

The `applyDelta` method processes sync actions in a specific order:

```typescript
async applyDelta(syncActions: SyncAction[]): Promise<void> {
  await this.updateLock.runExclusive(async () => {

    // 1. Handle sync group changes (G/S actions)
    //    If user joined a new group, partial bootstrap for that group
    await this.handleSyncGroupChanges(syncActions);

    // 2. Load dependencies for affected models
    //    If a partial-loaded model's references changed, load the new references
    await this.loadDependents(syncActions);

    // 3. Write to local database (TinyBase)
    //    Insert, update, or delete rows in the appropriate tables
    this.writeToLocalDatabase(syncActions);

    // 4. Cancel conflicting CreateTransactions
    //    If server created a model with the same UUID, cancel local transaction
    this.cancelConflictingCreations(syncActions);

    // 5. First pass: create/update in-memory model instances
    const newModels: Model[] = [];
    syncActions.forEach((action) => {
      if (action.action === 'I' || action.action === 'V' || action.action === 'U') {
        const model = this.upsertModel(action);
        if (model !== undefined) newModels.push(model);
      }
      if (action.action === 'A') {
        this.archiveModel(action);
      }
    });

    // 6. Attach references on new models
    newModels.forEach((model) => model.attachReferences());

    // 7. Second pass: rebase pending transactions and handle deletions
    syncActions.forEach((action) => {
      if (['I', 'V', 'U', 'C'].includes(action.action)) {
        this.rebaseTransactions(action);
      }
      if (action.action === 'D') {
        this.deleteModel(action);
      }
    });

    // 8. Update lastSyncId
    const maxSyncId = Math.max(...syncActions.map((a) => a.id));
    this.lastSyncId = maxSyncId;
    this.updateMetaSyncId(maxSyncId);

    // 9. Resolve completed transactions waiting for this syncId
    this.transactionQueue.progressQueue(this.lastSyncId);
  });
}
```

The `updateLock.runExclusive` ensures delta packets are processed sequentially, preventing race conditions between overlapping packets.

### Rebasing Pending Transactions

When a delta arrives for a model that has pending local transactions:

```typescript
rebaseTransactions(action: SyncAction): void {
  // Rebase queued transactions
  this.transactionQueue.queuedTransactions.forEach((tx) => {
    if (tx.entityId === action.modelId && tx.type === TransactionType.UPDATE) {
      tx.rebase(action.data);
    }
  });

  // Rebase completed-but-unsynced transactions
  this.transactionQueue.completedButUnsyncedTransactions.forEach((tx) => {
    if (tx.entityId === action.modelId && tx.type === TransactionType.UPDATE) {
      tx.rebase(action.data);
    }
  });

  // Check if any completed transactions can be fully resolved
  this.transactionQueue.completedButUnsyncedTransactions =
    this.transactionQueue.completedButUnsyncedTransactions.filter((tx) => {
      if (tx.syncIdNeededForCompletion !== undefined &&
          tx.syncIdNeededForCompletion <= this.lastSyncId) {
        return false; // Remove: fully synced
      }
      return true; // Keep: still waiting
    });
}
```

---

## Lazy Hydration

Not all models are loaded during bootstrap. Large datasets (comments, history, attachments) are loaded on demand.

### LazyReferenceCollection

Replaces `Collection<T>` for lazily-loaded one-to-many relationships:

```typescript
class LazyReferenceCollection<T extends Model> {
  private hydrated: boolean = false;
  private hydratePromise: Promise<void> | undefined;
  private items: T[] = [];

  constructor(
    private modelClass: new () => T,
    private owner: Model,
    private foreignKey: string,
    private options?: {
      canSkipNetworkHydration?: () => boolean;
      customNetworkHydration?: () => HydrationRequest[];
    },
  ) {}

  get elements(): T[] {
    if (!this.hydrated) {
      this.hydrate();
    }
    return this.items;
  }

  get length(): number {
    return this.elements.length;
  }

  async hydrate(): Promise<void> {
    if (this.hydrated) return;
    if (this.hydratePromise !== undefined) return this.hydratePromise;

    this.hydratePromise = this._doHydrate();
    await this.hydratePromise;
    this.hydrated = true;
  }

  private async _doHydrate(): Promise<void> {
    // 1. Try local database (TinyBase) first
    const localResults = this.queryLocal();
    if (localResults.length > 0) {
      this.items = localResults;
      return;
    }

    // 2. Check if network hydration can be skipped
    if (this.options?.canSkipNetworkHydration?.()) return;

    // 3. Check partial index store for previous fetches
    const coveringIndexes = this.getCoveringPartialIndexValues();
    if (this.hasModelsForPartialIndexValues(coveringIndexes)) {
      this.items = this.queryLocal();
      return;
    }

    // 4. Fetch from server via BatchModelLoader
    await batchModelLoader.addRequest({
      modelClass: this.modelClass,
      indexedKey: this.foreignKey,
      keyValue: this.owner.id,
      coveringPartialIndexValues: coveringIndexes,
    });

    this.items = this.queryLocal();
  }
}
```

**First access pattern:** `.elements` returns an empty array synchronously. The hydration triggers a network request. When the response arrives, MobX observability causes the component to re-render with the populated data (typically 10-20ms later).

### LazyReference

For single-model lazy references:

```typescript
class LazyReference<T extends Model> {
  private _value: T | undefined;
  private _hydrated: boolean = false;

  constructor(
    private modelClass: new () => T,
    private id: string,
  ) {}

  // Suspense-compatible: returns value or throws promise
  get value(): T | undefined {
    if (!this._hydrated) {
      this.hydrate();
    }
    return this._value;
  }

  async hydrate(): Promise<T | undefined> {
    // Try object pool first
    this._value = syncClient.getModel<T>(this.id);
    if (this._value !== undefined) {
      this._hydrated = true;
      return this._value;
    }

    // Try local database
    this._value = this.modelClass.find(this.id);
    if (this._value !== undefined) {
      this._hydrated = true;
      return this._value;
    }

    // Fetch from server
    await batchModelLoader.loadSingle(this.modelClass, this.id);
    this._value = this.modelClass.find(this.id);
    this._hydrated = true;
    return this._value;
  }
}
```

### Partial Indexes

Partial indexes answer: "What query parameters should we use to fetch lazily-loaded models?"

For example, to load all `Comment`s for an `Issue`, the partial index key is `issueId-<issue-id>`. For nested relationships (e.g., all comments for all issues in a cycle), partial indexes support up to three levels of depth:

```
Comment can be loaded by:
  - issueId           (direct parent)
  - issue.teamId      (grandparent via Issue)
  - issue.projectId   (grandparent via Issue)
  - issue.cycleId     (grandparent via Issue)
```

The partial index store (`_partial` table) tracks which indexes have been fetched. If `issueId-abc123` is in the partial index store, the client knows comments for issue `abc123` have already been fetched from the server.

### Suspense Integration

For React Suspense integration, collections and references expose a `hydrate()` method that returns a Promise:

```typescript
function resolvePromise<T>(promise: Promise<T>): T {
  if (promise.status === 'fulfilled') return promise.value;
  if (promise.status === 'rejected') throw promise.reason;
  throw promise; // Pending: triggers Suspense boundary
}

// In a React component:
const ItemComments = observer(({ issueId }: { issueId: string }) => {
  const issue = Issue.find(issueId);
  if (issue === undefined) return undefined;

  // This triggers Suspense if comments aren't loaded yet
  const comments = resolvePromise(issue.comments.hydrate());

  return (
    <div>
      {comments.map((c) => <CommentCard key={c.id} comment={c} />)}
    </div>
  );
});

// Wrap with Suspense boundary:
<Suspense fallback={<Spinner />}>
  <ItemComments issueId={id} />
</Suspense>
```

---

## Route-Based Preloading

Eliminate loading spinners by prefetching data before navigation:

```typescript
// Associate routes with required data
const routeDataRequirements = {
  '/issues/:id': (params) => [
    { model: Issue, id: params.id },
    { model: Comment, indexKey: 'issueId', value: params.id },
    { model: IssueHistory, indexKey: 'issueId', value: params.id },
  ],
  '/projects/:id': (params) => [
    { model: Project, id: params.id },
    { model: Issue, syncGroup: params.id },
  ],
};
```

**Hover-triggered prefetch:** When a user hovers over a link for more than 5ms, start loading the required data. By the time they click, data is usually already available:

```typescript
function PrefetchLink({ to, children }: { to: string; children: React.ReactNode }) {
  const timeoutRef = useRef<number>();

  const handleMouseEnter = () => {
    timeoutRef.current = window.setTimeout(() => {
      const requirements = matchRouteRequirements(to);
      if (requirements !== undefined) {
        requirements.forEach((req) => batchModelLoader.addRequest(req));
      }
    }, 5);
  };

  const handleMouseLeave = () => {
    if (timeoutRef.current !== undefined) {
      clearTimeout(timeoutRef.current);
    }
  };

  return (
    <Link
      to={to}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}
    </Link>
  );
}
```

This pattern provides coherent page transitions instead of gradual pop-in as individual data pieces load.

---

## Sync Groups and Access Control

Sync groups control which data a client receives. Each user has subscribed sync groups based on:

- Their user ID
- Team memberships
- Predefined roles

```json
{
  "subscribedSyncGroups": ["team-engineering", "user-alice-123", "role-admin"]
}
```

When a user is added to a new team:

1. Server sends a `G` (sync group change) action
2. Client triggers a partial bootstrap for the new sync group
3. Models associated with the new group are loaded
4. Future delta packets for that group are received

When a user is removed from a team:

1. Server sends a `G` action
2. Client removes models associated with that group from the object pool and TinyBase

Sync groups are stored in the `_meta` table and updated during delta packet processing.

---

## Connection Management

### Reconnection

When the WebSocket connection drops:

```typescript
class SyncClient {
  private reconnectAttempts = 0;

  private handleDisconnect(): void {
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    setTimeout(() => {
      this.reconnectAttempts += 1;
      this.startSyncing();
    }, delay);
  }
}
```

After reconnecting, the handshake determines if delta packets were missed. If the gap is small, delta packets fill it. If the gap is too large (e.g., client was offline for days), a full bootstrap may be triggered.

### Missed Delta Detection

During handshake, compare `lastSyncId`:

```typescript
private handleHandshakeResponse(serverState: { lastSyncId: number }): void {
  if (this.lastSyncId < serverState.lastSyncId) {
    // Request missed deltas
    this.requestDeltasSince(this.lastSyncId);
  }
}
```

### Multi-Tab Coordination

When multiple browser tabs are open, each tab maintains its own WebSocket connection and in-memory state. However, they share the same IndexedDB database. TinyBase's `startAutoLoad()` listens for external IndexedDB changes, so updates from one tab propagate to others via the shared database.
