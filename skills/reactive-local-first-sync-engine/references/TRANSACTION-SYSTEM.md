# Transaction System

Every mutation (create, update, delete) becomes a serializable, rebasable, undoable transaction that is queued, persisted to IndexedDB, batched, and sent to the server as a GraphQL mutation.

## Table of Contents

- [Transaction Types](#transaction-types)
- [Base Transaction Class](#base-transaction-class)
- [CreateTransaction](#createtransaction)
- [UpdateTransaction](#updatetransaction)
- [DeleteTransaction](#deletetransaction)
- [Transaction Queue](#transaction-queue)
- [Queue Stages](#queue-stages)
- [Microtask Batching](#microtask-batching)
- [GraphQL Mutation Generation](#graphql-mutation-generation)
- [Executing Transactions](#executing-transactions)
- [Conflict Resolution (Rebase)](#conflict-resolution-rebase)
- [Undo and Redo](#undo-and-redo)
- [Offline Persistence](#offline-persistence)
- [Transaction Lifecycle](#transaction-lifecycle)

---

## Transaction Types

| Type                  | Trigger                      | GraphQL Operation       | Undo Produces          |
| --------------------- | ---------------------------- | ----------------------- | ---------------------- |
| `CreateTransaction`   | `model.save()` (new model)   | `modelCreate` mutation  | `DeleteTransaction`    |
| `UpdateTransaction`   | Property assignment on model | `modelUpdate` mutation  | `UpdateTransaction`    |
| `DeleteTransaction`   | `model.delete()`             | `modelDelete` mutation  | `CreateTransaction`    |
| `ArchivalTransaction` | `model.archive()`            | `modelArchive` mutation | `UnarchiveTransaction` |

`UpdateTransaction` is the most common -- it is generated automatically by MobX reactions whenever an `@Property` field changes value.

---

## Base Transaction Class

All transaction types extend a common base:

```typescript
import { nanoid } from 'nanoid';

const enum TransactionType {
  CREATE = 'CREATE',
  UPDATE = 'UPDATE',
  DELETE = 'DELETE',
  ARCHIVE = 'ARCHIVE',
  UNARCHIVE = 'UNARCHIVE',
}

export abstract class Transaction {
  public readonly id: string;
  public readonly timestamp: number;
  public readonly type: TransactionType;
  public readonly tableName: string;
  public readonly entityId: string;

  // Sync tracking
  public syncId: string | undefined;
  public syncIdNeededForCompletion: number | undefined;
  public isSynced: boolean;
  public retries: number;

  // Batch grouping
  public batchIndex: number;

  constructor(type: TransactionType, tableName: string, entityId: string) {
    this.id = nanoid();
    this.timestamp = Date.now();
    this.type = type;
    this.tableName = tableName;
    this.entityId = entityId;
    this.isSynced = false;
    this.retries = 0;
    this.batchIndex = 0;
  }

  abstract toGraphQL(): {
    mutationText: string;
    variables: Record<string, unknown>;
    variableTypes: Record<string, string>;
  };

  abstract rebase(deltaData: Record<string, unknown>): void;
  abstract undoTransaction(): Transaction;
  abstract serialize(): Record<string, unknown>;

  markSynced(syncId: string): void {
    this.syncId = syncId;
    this.isSynced = true;
  }

  incrementRetries(): void {
    this.retries += 1;
  }
}
```

Key design decisions:

- **Nano ID** for transaction IDs: compact (21 chars), URL-safe, ephemeral. Transactions are short-lived; they don't need the ordering guarantees of UUID v7.
- **`batchIndex`**: Groups transactions created in the same event loop tick. Same `batchIndex` = same GraphQL request.
- **`syncIdNeededForCompletion`**: After the server responds, this stores the largest `lastSyncId` from the response. The transaction waits for the corresponding delta packet before completing.

---

## CreateTransaction

Generated when `model.save()` is called for a new model:

```typescript
export class CreateTransaction extends Transaction {
  private modelData: Record<string, unknown>;

  constructor(
    tableName: string,
    entityId: string,
    data: Record<string, unknown>,
  ) {
    super(TransactionType.CREATE, tableName, entityId);
    this.modelData = data;
  }

  toGraphQL() {
    const modelName = this.tableName.slice(0, -1); // 'issues' -> 'issue'
    const capitalized = modelName.charAt(0).toUpperCase() + modelName.slice(1);
    const inputType = `${capitalized}CreateInput`;
    const inputVar = `${modelName}CreateInput`;

    return {
      mutationText: `${modelName}Create(input: $${inputVar}) { lastSyncId }`,
      variables: { [inputVar]: { id: this.entityId, ...this.modelData } },
      variableTypes: { [inputVar]: inputType },
    };
  }

  rebase(_deltaData: Record<string, unknown>): void {
    // CreateTransactions are not rebased; if the UUID conflicts with a
    // server-side creation, the transaction is cancelled in applyDelta
  }

  undoTransaction(): Transaction {
    return new DeleteTransaction(this.tableName, this.entityId);
  }

  serialize(): Record<string, unknown> {
    return {
      type: this.type,
      tableName: this.tableName,
      entityId: this.entityId,
      modelData: this.modelData,
      timestamp: this.timestamp,
    };
  }
}
```

---

## UpdateTransaction

Generated automatically by MobX reactions when an `@Property` field changes:

```typescript
export class UpdateTransaction extends Transaction {
  public propertyKey: string;
  public oldValue: unknown;
  public newValue: unknown;

  constructor(
    tableName: string,
    entityId: string,
    propertyKey: string,
    oldValue: unknown,
    newValue: unknown,
  ) {
    super(TransactionType.UPDATE, tableName, entityId);
    this.propertyKey = propertyKey;
    this.oldValue = oldValue;
    this.newValue = newValue;
  }

  toGraphQL() {
    const modelName = this.tableName.slice(0, -1);
    const capitalized = modelName.charAt(0).toUpperCase() + modelName.slice(1);
    const inputType = `${capitalized}UpdateInput`;
    const inputVar = `${modelName}UpdateInput`;

    return {
      mutationText: `${modelName}Update(id: "${this.entityId}", input: $${inputVar}) { lastSyncId }`,
      variables: { [inputVar]: { [this.propertyKey]: this.newValue } },
      variableTypes: { [inputVar]: inputType },
    };
  }

  rebase(deltaData: Record<string, unknown>): void {
    // Server state arrived via delta packet. Update the "original" value
    // to the server's value so that the undo operation reverts to server state.
    if (this.propertyKey in deltaData) {
      this.oldValue = deltaData[this.propertyKey];
    }
    // The in-memory model retains our local newValue (optimistic)
  }

  undoTransaction(): Transaction {
    return new UpdateTransaction(
      this.tableName,
      this.entityId,
      this.propertyKey,
      this.newValue, // current becomes old
      this.oldValue, // original becomes new (revert)
    );
  }

  serialize(): Record<string, unknown> {
    return {
      type: this.type,
      tableName: this.tableName,
      entityId: this.entityId,
      propertyKey: this.propertyKey,
      oldValue: this.oldValue,
      newValue: this.newValue,
      timestamp: this.timestamp,
    };
  }
}
```

The `changeSnapshot` on the model captures the changed properties and their old/new values. When `save()` is called (or when a MobX reaction fires), this snapshot is used to create the transaction.

---

## DeleteTransaction

Generated when `model.delete()` is called:

```typescript
export class DeleteTransaction extends Transaction {
  private modelSnapshot: Record<string, unknown> | undefined;

  constructor(
    tableName: string,
    entityId: string,
    snapshot?: Record<string, unknown>,
  ) {
    super(TransactionType.DELETE, tableName, entityId);
    this.modelSnapshot = snapshot;
  }

  toGraphQL() {
    const modelName = this.tableName.slice(0, -1);
    return {
      mutationText: `${modelName}Delete(id: "${this.entityId}") { lastSyncId }`,
      variables: {},
      variableTypes: {},
    };
  }

  rebase(_deltaData: Record<string, unknown>): void {
    // Nothing to rebase -- either the delete succeeds or fails
  }

  undoTransaction(): Transaction {
    if (this.modelSnapshot === undefined) {
      throw new Error('Cannot undo delete without snapshot');
    }
    return new CreateTransaction(
      this.tableName,
      this.entityId,
      this.modelSnapshot,
    );
  }

  serialize(): Record<string, unknown> {
    return {
      type: this.type,
      tableName: this.tableName,
      entityId: this.entityId,
      modelSnapshot: this.modelSnapshot,
      timestamp: this.timestamp,
    };
  }
}
```

The `modelSnapshot` stores the full model state before deletion, enabling undo.

---

## Transaction Queue

The `TransactionQueue` manages the full lifecycle of transactions through four stages:

```typescript
export class TransactionQueue {
  // The four stages
  private createdTransactions: Transaction[] = [];
  private queuedTransactions: Transaction[] = [];
  private executingTransactions: Transaction[] = [];
  private completedButUnsyncedTransactions: Transaction[] = [];

  // Batch tracking
  private batchIndex: number = 0;

  // Schedulers
  private commitScheduler: MicrotaskScheduler;
  private dequeueScheduler: TimerScheduler;

  create(transaction: Transaction): void {
    transaction.batchIndex = this.batchIndex;
    this.createdTransactions.push(transaction);
    this.commitScheduler.schedule();
  }

  // Called by scheduler: moves created -> queued
  private commitCreatedTransactions(): void {
    const toCommit = [...this.createdTransactions];
    this.createdTransactions = [];
    this.batchIndex += 1;

    toCommit.forEach((tx) => {
      this.queuedTransactions.push(tx);
      this.persistTransaction(tx);
    });

    this.dequeueScheduler.schedule();
  }

  // Called by scheduler: moves queued -> executing
  private dequeueNextTransactions(): void {
    if (this.executingTransactions.length > 0) return;
    if (this.queuedTransactions.length === 0) return;

    const currentBatch = this.queuedTransactions[0].batchIndex;
    const batch: Transaction[] = [];
    let totalSize = 0;

    while (
      this.queuedTransactions.length > 0 &&
      this.queuedTransactions[0].batchIndex === currentBatch
    ) {
      const tx = this.queuedTransactions[0];
      const mutation = tx.toGraphQL();
      const size = JSON.stringify(mutation).length;

      if (totalSize + size > MAX_MUTATION_SIZE && batch.length > 0) break;

      batch.push(this.queuedTransactions.shift()!);
      totalSize += size;
    }

    this.executingTransactions = batch;
    this.executeTransactionBatch(batch);
  }

  // ... (see Executing Transactions section)
}
```

---

## Queue Stages

```
created          queued           executing        completedButUnsynced
[tx, tx, tx] --> [tx, tx, tx] --> [tx, tx]    --> [tx]
             ^                ^              ^               |
             |                |              |               |
    commitScheduler    dequeueScheduler  server response   delta packet
    (microtask)        (timer)          (GraphQL)          (WebSocket)
```

1. **`createdTransactions`**: Newly created transactions. A microtask scheduler moves them to `queuedTransactions` and increments `batchIndex`. All transactions created in the same event loop share a `batchIndex`.

2. **`queuedTransactions`**: Waiting to be sent to the server. Also persisted to the `_transactions` table in IndexedDB. A timer scheduler picks the next batch (same `batchIndex`, within size limit) and moves them to `executingTransactions`.

3. **`executingTransactions`**: Currently in-flight to the server. When the server responds, transactions are removed and either completed or rolled back.

4. **`completedButUnsyncedTransactions`**: The server accepted the mutation, but the corresponding delta packet has not yet arrived. Once the delta packet with the matching `syncId` is received, the transaction is fully completed and removed.

---

## Microtask Batching

Transactions created in the same event loop tick are automatically batched:

```typescript
// These three changes happen in one event loop tick:
issue.title = 'Updated Title';
issue.priority = 1;
issue.assigneeId = userId;

// Result: three UpdateTransactions with the same batchIndex
// Sent as a single GraphQL request with three mutations
```

The `commitScheduler` uses `queueMicrotask()` to defer the commit until the current synchronous code completes. This ensures that rapid successive changes are grouped without any manual batching.

---

## GraphQL Mutation Generation

Each transaction generates a GraphQL mutation fragment via `toGraphQL()`. When a batch is executed, the fragments are merged into a single request:

**Single mutation:**

```json
{
  "query": "mutation IssueUpdate($issueUpdateInput: IssueUpdateInput!) { issueUpdate(id: \"abc-123\", input: $issueUpdateInput) { lastSyncId } }",
  "variables": {
    "issueUpdateInput": {
      "title": "Updated Title"
    }
  }
}
```

**Batched mutations** (multiple transactions in one request):

```json
{
  "query": "mutation ProjectCreate_DocumentContentCreate($projectCreateInput: ProjectCreateInput!, $documentContentCreateInput: DocumentContentCreateInput!) { o1:projectCreate(input: $projectCreateInput) { lastSyncId }, o2:documentContentCreate(input: $documentContentCreateInput) { lastSyncId } }",
  "variables": {
    "projectCreateInput": {
      "id": "proj-123",
      "name": "New Project"
    },
    "documentContentCreateInput": {
      "id": "doc-456",
      "projectId": "proj-123"
    }
  }
}
```

Batched mutations use aliases (`o1:`, `o2:`) to disambiguate multiple operations in a single GraphQL request.

**Size limit**: If the accumulated mutation size exceeds a threshold (~100KB), the batch is split. Remaining transactions wait for the next dequeue cycle.

---

## Executing Transactions

The `TransactionExecutor` merges a batch into a single GraphQL request and handles the response:

```typescript
async function executeTransactionBatch(batch: Transaction[]): Promise<void> {
  const merged = mergeMutations(batch);

  try {
    const response = await graphqlClient.mutate(merged);

    // Extract lastSyncId from each mutation result
    const maxSyncId = Math.max(
      ...Object.values(response.data).map(
        (r: { lastSyncId: number }) => r.lastSyncId,
      ),
    );

    batch.forEach((tx) => {
      tx.syncIdNeededForCompletion = maxSyncId;
      removePersistedTransaction(tx.id);
    });

    // Move to completedButUnsynced until delta packet arrives
    completedButUnsyncedTransactions.push(...batch);
    executingTransactions = [];
  } catch (error) {
    // Rollback: revert in-memory models to pre-transaction state
    batch.forEach((tx) => {
      rollbackTransaction(tx);
    });
    executingTransactions = [];
  }
}
```

**On success:** The server returns `lastSyncId` for each mutation. The transaction waits for the delta packet with that `syncId` before fully completing. The local TinyBase database is NOT updated yet -- only the server-confirmed delta packet updates the local DB.

**On failure:** The transaction's `rollback` method reverts the in-memory model to its previous state. For `UpdateTransaction`, this means setting the property back to `oldValue`. The UI flickers back to the original state -- this is intentional and expected to be rare.

---

## Conflict Resolution (Rebase)

When a delta packet arrives that affects a model with pending local transactions, those transactions must be rebased:

```
Timeline:
  Client A: issue.assignee = 'Alice'   --> UpdateTransaction queued
  Client B: issue.assignee = 'Bob'     --> Server accepts, broadcasts delta
  Client A receives delta: assignee = 'Bob'
  Client A rebases: UpdateTransaction.oldValue changes from original to 'Bob'
  Client A's transaction executes: server sees change from 'Bob' to 'Alice'
  Server accepts, final state: assignee = 'Alice' (last-writer-wins)
```

The `rebase` method on `UpdateTransaction`:

```typescript
rebase(deltaData: Record<string, unknown>): void {
  if (this.propertyKey in deltaData) {
    // Update "original" value to server state
    this.oldValue = deltaData[this.propertyKey];
  }
  // In-memory model keeps our local value (optimistic UI preserved)
}
```

Rebasing happens inside `applyDelta` for all transactions in `completedButUnsyncedTransactions` and `queuedTransactions` whose model matches the delta.

---

## Undo and Redo

Undo/redo is transaction-based. Each transaction type implements `undoTransaction()` which returns the inverse:

| Original            | Undo Produces                                |
| ------------------- | -------------------------------------------- |
| `CreateTransaction` | `DeleteTransaction`                          |
| `UpdateTransaction` | `UpdateTransaction` (swapped old/new values) |
| `DeleteTransaction` | `CreateTransaction` (from snapshot)          |

The `UndoQueue` listens for new transactions and pushes them onto the undo stack:

```typescript
class UndoQueue {
  private undoStack: Transaction[] = [];
  private redoStack: Transaction[] = [];

  addOperation(transaction: Transaction): void {
    this.undoStack.push(transaction);
    this.redoStack = []; // Clear redo on new operation
  }

  undo(): void {
    const tx = this.undoStack.pop();
    if (tx === undefined) return;

    const undoTx = tx.undoTransaction();
    transactionQueue.create(undoTx);
    this.redoStack.push(undoTx);
  }

  redo(): void {
    const tx = this.redoStack.pop();
    if (tx === undefined) return;

    const redoTx = tx.undoTransaction();
    transactionQueue.create(redoTx);
    this.undoStack.push(redoTx);
  }
}
```

Integration with UI is handled at the component level. The UI determines what constitutes an undoable operation and wraps the mutation in an `addOperation` call:

```typescript
const previousTitle = issue.title;

issue.title = newTitle;
issue.save();

undoQueue.addOperation(
  new UpdateTransaction('issues', issue.id, 'title', newTitle, previousTitle),
);
```

---

## Offline Persistence

Transactions are persisted to the `_transactions` table in IndexedDB when they move to `queuedTransactions`. This ensures no mutations are lost if the browser closes or crashes.

### Saving transactions

```typescript
private persistTransaction(tx: Transaction): void {
  const store = getStore();
  store.setRow('_transactions', tx.id, tx.serialize());
}
```

### Loading on restart

During bootstrap, persisted transactions are loaded and replayed:

```typescript
loadPersistedTransactions(): void {
  const store = getStore();
  const rowIds = store.getRowIds('_transactions');

  rowIds.forEach((rowId) => {
    const data = store.getRow('_transactions', rowId);
    const tx = Transaction.fromSerializedData(data);

    // Replay: apply the transaction to in-memory models
    tx.replay();

    this.persistedTransactionsQueue.push(tx);
  });
}

confirmPersistedTransactions(): void {
  // Move to createdTransactions for re-execution
  this.createdTransactions.push(...this.persistedTransactionsQueue);
  this.persistedTransactionsQueue = [];
  this.commitScheduler.schedule();
}
```

### Removing after server confirmation

```typescript
private removePersistedTransaction(txId: string): void {
  const store = getStore();
  store.delRow('_transactions', txId);
}
```

### Edge case: duplicate transactions

If the client sends a transaction, the browser closes before receiving the response, and the transaction is re-sent on restart, the server may reject it (e.g., "cannot delete a model that doesn't exist"). This is a known trade-off of the at-least-once delivery model. Non-idempotent transactions may cause benign errors that are handled gracefully.

---

## Transaction Lifecycle

Complete flow from user action to completion:

```
1. User Action
   issue.title = 'New Title'

2. MobX Reaction Fires
   Detects property change, calls markPropertyChanged()
   Stores: propertyKey='title', oldValue='Old', newValue='New'

3. UpdateTransaction Created
   Added to createdTransactions with current batchIndex

4. Microtask Commits
   Moved to queuedTransactions, persisted to _transactions table
   batchIndex incremented

5. Dequeue Scheduler Fires
   Batch prepared: toGraphQL() called, mutations merged
   Moved to executingTransactions

6. GraphQL Request Sent
   mutation IssueUpdate($input) { issueUpdate(id: "...", input: $input) { lastSyncId } }

7a. Server Accepts
    Response: { lastSyncId: 12345 }
    Transaction removed from executingTransactions
    Moved to completedButUnsyncedTransactions
    Removed from _transactions table

7b. Server Rejects
    Transaction rolled back: issue.title reverted to 'Old'
    Transaction discarded

8. Delta Packet Arrives (WebSocket)
   Contains syncAction for issue update with syncId >= 12345
   Transaction removed from completedButUnsyncedTransactions
   TinyBase row updated with server-confirmed data
   Transaction fully complete
```
