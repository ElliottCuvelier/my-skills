# Cheatsheet

Quick-reference for day-to-day development with the reactive local-first sync engine.

## Table of Contents

- [File Naming Conventions](#file-naming-conventions)
- [New Model Checklist](#new-model-checklist)
- [New Feature Checklist](#new-feature-checklist)
- [Common Patterns](#common-patterns)
  - [Create](#create)
  - [Read](#read)
  - [Update](#update)
  - [Delete](#delete)
  - [Filter and Sort](#filter-and-sort)
  - [Relationships](#relationships)
- [React Component Patterns](#react-component-patterns)
- [Debugging Tips](#debugging-tips)
- [Quick Reference Card](#quick-reference-card)

---

## File Naming Conventions

| File Type               | Pattern                 | Example                 |
| ----------------------- | ----------------------- | ----------------------- |
| Model definition        | `[Entity].model.ts`     | `Issue.model.ts`        |
| Model decorators        | `decorators.ts`         | `decorators.ts`         |
| Model registry          | `model-registry.ts`     | `model-registry.ts`     |
| Base model              | `model.base.ts`         | `model.base.ts`         |
| Collection              | `collection.ts`         | `collection.ts`         |
| Lazy reference          | `lazy-reference.ts`     | `lazy-reference.ts`     |
| TinyBase store          | `store.ts`              | `store.ts`              |
| Schema definition       | `schema.ts`             | `schema.ts`             |
| Transaction base        | `transaction.base.ts`   | `transaction.base.ts`   |
| Transaction type        | `[type]-transaction.ts` | `update-transaction.ts` |
| Transaction queue       | `transaction-queue.ts`  | `transaction-queue.ts`  |
| Sync client             | `sync-client.ts`        | `sync-client.ts`        |
| Bootstrap               | `bootstrap.ts`          | `bootstrap.ts`          |
| Delta handler           | `delta-handler.ts`      | `delta-handler.ts`      |
| Local-first component   | `[Entity]Card.tsx`      | `IssueCard.tsx`         |
| Local-first list        | `[Entity]List.tsx`      | `IssueList.tsx`         |
| Design system component | `[Component].tsx`       | `Button.tsx`            |

---

## New Model Checklist

When adding a new model to the sync engine:

- [ ] Create `[Entity].model.ts` in `sync-engine/models/`
- [ ] Extend `Model` base class
- [ ] Add `@ClientModel('tableName')` decorator with lowercase plural table name
- [ ] Add `@Property()` to each synced field
- [ ] Add `@ManyToOne<T>()` for parent relationships (ensure `entityId` foreign key property exists)
- [ ] Add `@OneToMany<T>()` for child collections (initialize `Collection` in constructor)
- [ ] Add `@computed` getters for derived state
- [ ] Add business methods (publish, archive, etc.)
- [ ] Add static `create()` convenience method
- [ ] Add constructor that accepts partial data with `undefined` defaults
- [ ] Export from `sync-engine/index.ts`
- [ ] Add table schema to `store/schema.ts` (if using explicit schemas)
- [ ] Choose appropriate `loadStrategy` (instant/lazy/partial/local)
- [ ] Add to server bootstrap `onlyModels` list if not `local`

---

## New Feature Checklist

End-to-end checklist for building a feature with local-first architecture:

1. **Model** -- Define or extend model(s) with decorators
2. **Business Logic** -- Add methods on the model for domain operations
3. **UI Component** -- Create `observer()` component in `domains/`
4. **Lazy Data** -- If model is `partial`, add Suspense boundary around component
5. **Preloading** -- Add route data requirements for prefetch on hover
6. **Test Model** -- Unit test model business logic
7. **Test Component** -- Integration test with mock TinyBase store
8. **Backend** -- Implement GraphQL mutations and subscriptions (if applicable)

---

## Common Patterns

### Create

```typescript
// Static factory method (preferred)
const issue = Issue.create({
  title: 'Bug Report',
  teamId: team.id,
  assigneeId: currentUser.id,
  description: 'Steps to reproduce...',
});
// Returns: saved model, CreateTransaction queued

// Manual construction
const issue = new Issue({
  id: undefined,
  createdAt: undefined,
  updatedAt: undefined,
  title: 'Bug Report',
  status: IssueStatus.OPEN,
  teamId: team.id,
});
issue.save(); // Writes to TinyBase, queues CreateTransaction
```

### Read

```typescript
// By ID (O(1) lookup)
const issue = Issue.find('issue-id');
if (issue !== undefined) {
  console.log(issue.title);
}

// All instances (table scan)
const issues = Issue.findAll();

// Filtered (table scan + predicate)
const openIssues = Issue.where({ status: IssueStatus.OPEN });
const myIssues = Issue.where({ assigneeId: currentUser.id });
```

### Update

```typescript
// Direct property assignment (auto-generates UpdateTransaction)
issue.title = 'Updated Title';
issue.priority = 2;
issue.assigneeId = newAssignee.id;
// No save() needed for updates -- MobX reactions handle it

// Business method (encapsulates domain logic)
issue.publish(); // sets status = PUBLISHED
issue.archive(); // sets status = ARCHIVED
issue.assignTo(userId);
```

### Delete

```typescript
issue.delete(); // Removes from TinyBase, queues DeleteTransaction
```

### Filter and Sort

```typescript
// Filter by multiple criteria
const urgentBugs = Issue.findAll().filter(
  (issue) => issue.priority >= 3 && issue.type === IssueType.BUG,
);

// Sort by field
const sortedByDate = Issue.findAll().sort(
  (a, b) => b.createdAt.getTime() - a.createdAt.getTime(),
);

// Computed filter on model (cached by MobX)
@computed
get openIssues(): Issue[] {
  return this.issues.items.filter((issue) => issue.status === IssueStatus.OPEN);
}
```

### Relationships

```typescript
// ManyToOne: access parent
const team = issue.team; // Resolves teamId -> Team instance
console.log(team?.name);

// OneToMany: access children
const comments = issue.comments.items; // Collection of Comment instances
const count = issue.comments.length;

// Traverse relationships
const teamMembers = team.members.items;
const memberIssues = teamMembers.flatMap((m) => m.assignedIssues.items);
```

---

## React Component Patterns

### Basic Local-First Component

```typescript
export const IssueCard = observer(({ issueId }: { issueId: string }) => {
  const issue = Issue.find(issueId);
  if (issue === undefined) return undefined;

  return (
    <Card title={issue.title}>
      <Badge>{issue.status}</Badge>
      <span>{issue.assignee?.name ?? 'Unassigned'}</span>
      <Button onClick={() => issue.archive()}>Archive</Button>
    </Card>
  );
});
```

### List with Filtering

```typescript
// NOTE: const enum requires isolatedModules: false. Replace with a regular enum
// or as const object if your bundler (Vite/esbuild/SWC) mandates isolatedModules: true.
const enum IssueFilter {
  ALL = 'ALL',
  OPEN = 'OPEN',
  CLOSED = 'CLOSED',
}

export const IssueList = observer(({ teamId }: { teamId: string }) => {
  const [filter, setFilter] = useState(IssueFilter.ALL);
  const team = Team.find(teamId);
  if (team === undefined) return undefined;

  const issues = team.issues.items.filter((issue) => {
    if (filter === IssueFilter.ALL) return true;
    if (filter === IssueFilter.OPEN) return issue.isOpen;
    return issue.isClosed;
  });

  return (
    <div>
      <FilterBar value={filter} onChange={setFilter} />
      {issues.map((issue) => (
        <IssueCard key={issue.id} issueId={issue.id} />
      ))}
    </div>
  );
});
```

### Lazy-Loaded Section with Suspense

```typescript
function IssuePage({ issueId }: { issueId: string }) {
  return (
    <div>
      <IssueHeader issueId={issueId} />
      <Suspense fallback={<Skeleton lines={5} />}>
        <IssueComments issueId={issueId} />
      </Suspense>
    </div>
  );
}
```

### Inline Edit

```typescript
export const InlineTitle = observer(({ issueId }: { issueId: string }) => {
  const issue = Issue.find(issueId);
  if (issue === undefined) return undefined;

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(issue.title);

  const handleSave = () => {
    issue.title = draft; // Auto UpdateTransaction
    setEditing(false);
  };

  if (editing) {
    return (
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={handleSave}
        onKeyDown={(e) => e.key === 'Enter' && handleSave()}
        autoFocus
      />
    );
  }

  return <h3 onClick={() => setEditing(true)}>{issue.title}</h3>;
});
```

---

## Debugging Tips

### Inspect TinyBase Store

```typescript
// In browser console:
const store = getStore();

// View all tables
console.log(store.getTables());

// View a specific table
console.log(store.getTable('issues'));

// View a specific row
console.log(store.getRow('issues', 'issue-id'));

// View table row count
console.log(store.getRowIds('issues').length);
```

### Inspect Transaction Queue

```typescript
// In browser console:
console.log(transactionQueue.createdTransactions);
console.log(transactionQueue.queuedTransactions);
console.log(transactionQueue.executingTransactions);
console.log(transactionQueue.completedButUnsyncedTransactions);
```

### Inspect Persisted Transactions (IndexedDB)

```typescript
const store = getStore();
const pendingTx = store.getTable('_transactions');
console.log('Pending transactions:', pendingTx);
```

### Inspect Sync State

```typescript
const store = getStore();
const meta = store.getRow('_meta', 'database');
console.log('lastSyncId:', meta.lastSyncId);
console.log('firstSyncId:', meta.firstSyncId);
console.log('syncGroups:', meta.subscribedSyncGroups);
```

### MobX Debugging

```typescript
import { spy } from 'mobx';

// Log all MobX actions and reactions
spy((event) => {
  if (event.type === 'action') {
    console.log(`MobX action: ${event.name}`);
  }
  if (event.type === 'reaction') {
    console.log(`MobX reaction: ${event.name}`);
  }
});
```

### Common Issues

| Symptom                     | Likely Cause                      | Fix                                            |
| --------------------------- | --------------------------------- | ---------------------------------------------- |
| Component doesn't re-render | Missing `observer()` wrapper      | Wrap with `observer()` from mobx-react-lite    |
| Stale data after mutation   | Accessing non-observable property | Ensure field has `@Property()` decorator       |
| Duplicate model instances   | Not using object pool             | Use `SyncClient.getModel()` instead of `new`   |
| Transaction not generated   | Hydration flag stuck              | Check `_isHydrating` is reset after hydrate    |
| Data lost on refresh        | Persister not started             | Verify `startAutoLoad()` and `startAutoSave()` |
| Offline changes lost        | Transactions not persisted        | Check `_transactions` table in IndexedDB       |

---

## Quick Reference Card

```
MODEL DEFINITION
  @ClientModel('tableName')     Register model with ModelRegistry
  @Property()                   Observable, synced field
  @ManyToOne<T>('inverse')      Parent relationship (computed)
  @OneToMany<T>('fk')           Child collection
  @computed get x()             Derived reactive state

CRUD
  Model.create({...})           Create + save + return
  Model.find(id)                Find by ID (sync, O(1))
  Model.findAll()               Get all (sync, table scan)
  Model.where({...})            Filter (sync)
  model.save()                  Write to TinyBase + queue CreateTransaction
  model.delete()                Remove + queue DeleteTransaction
  model.prop = value            Auto UpdateTransaction via MobX reaction

REACT
  observer(Component)           MobX reactive wrapper
  <Component itemId={id} />     Pass IDs, not objects
  item.method()                 Direct mutation (optimistic)
  <Suspense fallback={...}>     Boundary for lazy data

TINYBASE
  getStore()                    Singleton store access
  store.getRow(table, id)       Read row
  store.setRow(table, id, row)  Write row
  store.delRow(table, id)       Delete row

TRANSACTIONS
  CreateTransaction             model.save() (new model)
  UpdateTransaction             property change (auto)
  DeleteTransaction             model.delete()
  transaction.rebase(delta)     Conflict resolution
  transaction.undoTransaction() Returns inverse

SYNC
  lastSyncId                    Global version number
  Bootstrap: full/partial/local Initial data load
  Delta packets: I/U/D/A/V      Server -> client updates
  Sync groups                   Access control
```
