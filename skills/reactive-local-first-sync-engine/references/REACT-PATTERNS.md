# React Patterns

Two component patterns coexist: **props-based** for design system and SSR, **local-first** for domain UIs with instant data access and optimistic mutations.

## Table of Contents

- [Two Patterns Overview](#two-patterns-overview)
- [Local-First Pattern (MobX Observer)](#local-first-pattern-mobx-observer)
  - [observer() Wrapping](#observer-wrapping)
  - [Pass IDs Not Objects](#pass-ids-not-objects)
  - [Direct Mutations](#direct-mutations)
  - [No Loading States](#no-loading-states)
- [Props-Based Pattern](#props-based-pattern)
- [State Boundaries](#state-boundaries)
- [Suspense Boundaries for Lazy Data](#suspense-boundaries-for-lazy-data)
- [Decision Tree](#decision-tree)
- [Comparison Table](#comparison-table)
- [Migration: Props-Based to Local-First](#migration-props-based-to-local-first)
- [Testing Patterns](#testing-patterns)
- [Anti-Patterns](#anti-patterns)

---

## Two Patterns Overview

| Pattern         | Used For                        | Data Source       | Reactivity         |
| --------------- | ------------------------------- | ----------------- | ------------------ |
| **Local-first** | Domain UIs (issue cards, lists) | MobX models       | Automatic (MobX)   |
| **Props-based** | Design system, SSR, shared UI   | Props from parent | Manual (re-render) |

Most domain components in a local-first app use the **local-first** pattern. The **props-based** pattern is reserved for reusable design system components and server-rendered pages.

---

## Local-First Pattern (MobX Observer)

### observer() Wrapping

Every component that accesses MobX observable data must be wrapped in `observer()`:

```typescript
import { observer } from 'mobx-react-lite';
import { Issue } from '@/sync-engine';

export const IssueCard = observer(({ issueId }: { issueId: string }) => {
  const issue = Issue.find(issueId);
  if (issue === undefined) return undefined;

  return (
    <div>
      <h3>{issue.title}</h3>
      <span>{issue.priority}</span>
      <button onClick={() => issue.publish()}>Publish</button>
    </div>
  );
});
```

`observer()` tracks which observable properties the component accesses during render. When any of those properties change (from any source -- local mutation, delta packet, hydration), only this component re-renders. No manual subscriptions, no `useEffect`, no dependency arrays.

### Pass IDs Not Objects

Local-first components receive entity IDs as props, not full model objects:

```typescript
// Correct: pass ID, query inside observer
export const IssueCard = observer(({ issueId }: { issueId: string }) => {
  const issue = Issue.find(issueId);
  // ...
});

// Wrong: passing full object breaks MobX tracking for nested renders
export const IssueCard = observer(({ issue }: { issue: Issue }) => {
  // This works but doesn't benefit from object pool deduplication
});
```

Passing IDs ensures:

- Each component queries the same object pool instance
- MobX tracks exactly which properties are accessed
- Components re-render independently when different properties change

### Direct Mutations

Mutations are method calls on the model object. No API calls, no dispatchers, no reducers:

```typescript
// Update a property (auto-generates UpdateTransaction)
issue.title = 'New Title';

// Call a business method
issue.publish();

// Create a new model (generates CreateTransaction)
const newIssue = Issue.create({
  title: 'Bug Report',
  teamId: team.id,
  assigneeId: currentUser.id,
});

// Delete a model (generates DeleteTransaction)
issue.delete();
```

The UI updates instantly (optimistic). The transaction is queued and sent to the server. If the server rejects, the change is rolled back automatically.

### No Loading States

Because data is local (in TinyBase / in-memory), there are no loading states for data that has been bootstrapped:

```typescript
// Traditional React: multiple states, loading spinner, error handling
function TraditionalIssueList() {
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(undefined);

  useEffect(() => {
    fetch('/api/issues')
      .then(res => res.json())
      .then(setIssues)
      .catch(setError)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;
  if (error) return <Error message={error} />;
  return issues.map(issue => <IssueCard issue={issue} />);
}

// Local-first: two lines, no loading, no error handling
export const IssueList = observer(() => {
  const issues = Issue.findAll();
  return issues.map(issue => <IssueCard key={issue.id} issueId={issue.id} />);
});
```

For lazily-loaded data (comments, history), use Suspense boundaries instead of manual loading states. See [Suspense Boundaries](#suspense-boundaries-for-lazy-data).

---

## Props-Based Pattern

For design system components and SSR-compatible components:

```typescript
type ButtonProps = {
  variant: ButtonVariant | undefined;
  onClick: (() => void) | undefined;
  children: React.ReactNode;
};

export function Button({ variant, onClick, children }: ButtonProps) {
  const finalVariant = variant ?? ButtonVariant.PRIMARY;
  return (
    <button className={variantClasses[finalVariant]} onClick={onClick}>
      {children}
    </button>
  );
}
```

Props-based components:

- Have no knowledge of MobX, TinyBase, or the sync engine
- Receive all data via props
- Report user actions via callback props
- Work in any context (SSR, tests, Storybook)
- Live in `components/` directory

---

## State Boundaries

With a local-first architecture, MobX models are the single source of truth for all persistent state. User preferences like theme, sidebar default, and notification settings are `@Property()` fields on a `UserSettings` model -- synced across devices for free. Ephemeral per-component state (a modal being open, a dropdown expanded) stays in React `useState`. No third state management layer is needed.

```typescript
@ClientModel({ tableName: 'userSettings' })
class UserSettings extends Model {
  @Property()
  theme: Theme = Theme.LIGHT;

  @Property()
  sidebarOpen: boolean = true;

  @Property()
  defaultView: ViewType = ViewType.LIST;

  setTheme(theme: Theme) {
    this.theme = theme;
  }

  toggleSidebar() {
    this.sidebarOpen = !this.sidebarOpen;
  }
}

// In a component -- reads from synced model, reactive via observer()
export const Sidebar = observer(() => {
  const settings = UserSettings.find(currentUserId);
  if (settings === undefined) return undefined;

  if (!settings.sidebarOpen) return undefined;

  return <nav>{/* sidebar content */}</nav>;
});

// Ephemeral state stays in React
function IssueActions({ issueId }: { issueId: string }) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div>
      <button onClick={() => setMenuOpen(!menuOpen)}>...</button>
      {menuOpen && <DropdownMenu issueId={issueId} />}
    </div>
  );
}
```

| State Type       | Store       | Example                              |
| ---------------- | ----------- | ------------------------------------ |
| Domain entities  | MobX models | Issue, User, Comment                 |
| User preferences | MobX models | Theme, sidebar default, default view |
| Ephemeral UI     | React state | Modal open, dropdown expanded        |
| URL / navigation | Router      | Current route, query params          |

---

## Suspense Boundaries for Lazy Data

For data with `partial` or `lazy` load strategy, wrap the consuming component in a Suspense boundary:

```typescript
import { Suspense } from 'react';

function IssuePage({ issueId }: { issueId: string }) {
  return (
    <div>
      {/* Issue data is instant -- no Suspense needed */}
      <IssueHeader issueId={issueId} />

      {/* Comments are lazy-loaded -- wrap in Suspense */}
      <Suspense fallback={<CommentsSkeleton />}>
        <IssueComments issueId={issueId} />
      </Suspense>

      {/* History is lazy-loaded */}
      <Suspense fallback={<HistorySkeleton />}>
        <IssueHistory issueId={issueId} />
      </Suspense>
    </div>
  );
}
```

The `IssueComments` component uses `resolvePromise` to integrate with Suspense:

```typescript
import { observer } from 'mobx-react-lite';

function resolvePromise<T>(promise: Promise<T>): T {
  const p = promise as Promise<T> & { status?: string; value?: T; reason?: unknown };
  if (p.status === 'fulfilled') return p.value as T;
  if (p.status === 'rejected') throw p.reason;
  throw p;
}

export const IssueComments = observer(({ issueId }: { issueId: string }) => {
  const issue = Issue.find(issueId);
  if (issue === undefined) return undefined;

  const comments = resolvePromise(issue.comments.hydrate());

  return (
    <div>
      {comments.map((comment) => (
        <CommentCard key={comment.id} commentId={comment.id} />
      ))}
    </div>
  );
});
```

**Alternative: non-Suspense lazy loading**

If Suspense is not desired, the empty-then-populated pattern works naturally with MobX:

```typescript
export const IssueComments = observer(({ issueId }: { issueId: string }) => {
  const issue = Issue.find(issueId);
  if (issue === undefined) return undefined;

  // First render: empty array. MobX re-renders when data arrives (~10-20ms)
  const comments = issue.comments.elements;

  if (comments.length === 0) return <CommentsSkeleton />;

  return comments.map((c) => <CommentCard key={c.id} commentId={c.id} />);
});
```

---

## Decision Tree

```
What are you building?

|-- Design system component (Button, Card, Modal)?
|   --> Props-based pattern
|   - No domain knowledge, pure presentational
|   - Lives in components/

|-- Domain component for SSR or static pages?
|   --> Props-based pattern
|   - Parent fetches data, passes as props
|   - Example: ItemCard.tsx

|-- Domain component for interactive SPA?
|   --> Local-first pattern (observer + Model.find)
|   - MobX observer(), direct model queries
|   - Lives in domains/
|   - Example: ItemCard-LocalFirst.tsx

|-- Need offline support?
|   --> Local-first pattern (mandatory)

|-- Need real-time updates from other users?
|   --> Local-first pattern (automatic via delta packets)
```

---

## Comparison Table

| Feature               | Props-Based            | Local-First                   |
| --------------------- | ---------------------- | ----------------------------- |
| **Data source**       | Props                  | MobX models (TinyBase)        |
| **Loading states**    | Required               | Not needed (data is local)    |
| **Offline support**   | No                     | Yes (automatic)               |
| **Real-time updates** | Manual                 | Automatic (MobX + delta sync) |
| **Testing**           | Easy (no dependencies) | Requires mock store           |
| **SSR**               | Yes                    | No                            |
| **Best for**          | Design system, SSR     | Domain UIs, SPAs              |
| **Directory**         | `components/`          | `domains/`                    |

---

## Migration: Props-Based to Local-First

```typescript
// Before: props-based
function ItemCard({ item }: { item: Item }) {
  return <Card title={item.title} />;
}

// After: local-first
import { observer } from 'mobx-react-lite';
import { Item } from '@/sync-engine';

export const ItemCard = observer(({ itemId }: { itemId: string }) => {
  const item = Item.find(itemId);
  if (item === undefined) return undefined;
  return <Card title={item.title} />;
});
```

**Steps:**

1. Add `observer()` wrapper (import from `mobx-react-lite`)
2. Change prop from full object to ID (`item: Item` -> `itemId: string`)
3. Query model inside component (`Item.find(itemId)`)
4. Handle `undefined` case (replaces loading state)
5. Replace callback props with direct model methods

---

## Testing Patterns

### Testing Local-First Components

Create a test helper that initializes a TinyBase store with test data:

```typescript
import { createStore } from 'tinybase';

function createTestStore(data: Record<string, Record<string, Record<string, unknown>>>): Store {
  const store = createStore();

  Object.entries(data).forEach(([tableName, rows]) => {
    Object.entries(rows).forEach(([rowId, cells]) => {
      store.setRow(tableName, rowId, cells);
    });
  });

  return store;
}

// In tests:
const store = createTestStore({
  issues: {
    'issue-1': {
      id: 'issue-1',
      title: 'Test Issue',
      status: 'DRAFT',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    },
  },
});

// Inject the test store before rendering
setStore(store);

render(<IssueCard issueId="issue-1" />);
expect(screen.getByText('Test Issue')).toBeInTheDocument();
```

### Testing Model Logic

Model business logic can be tested without React or TinyBase:

```typescript
describe('Issue', () => {
  beforeEach(() => {
    setStore(createStore());
  });

  it('publishes a draft issue', () => {
    const issue = Issue.create({
      title: 'Test',
      userId: 'user-1',
      description: undefined,
    });

    expect(issue.isDraft).toBe(true);

    issue.publish();

    expect(issue.isPublished).toBe(true);
  });

  it('throws when publishing an already published issue', () => {
    const issue = Issue.create({
      title: 'Test',
      userId: 'user-1',
      description: undefined,
    });
    issue.publish();

    expect(() => issue.publish()).toThrow('Item is already published');
  });
});
```

### Testing Transaction Generation

Verify that mutations produce the expected transactions:

```typescript
describe('Transaction generation', () => {
  it('generates UpdateTransaction on property change', () => {
    const issue = Issue.create({
      title: 'Original',
      userId: 'user-1',
      description: undefined,
    });

    const spy = vi.spyOn(transactionQueue, 'create');

    issue.title = 'Updated';

    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({
        type: TransactionType.UPDATE,
        propertyKey: 'title',
        oldValue: 'Original',
        newValue: 'Updated',
      }),
    );
  });
});
```

---

## Anti-Patterns

| Anti-Pattern                               | Problem                                    | Fix                                            |
| ------------------------------------------ | ------------------------------------------ | ---------------------------------------------- |
| `observer()` without accessing observables | Component never re-renders                 | Ensure model properties are read during render |
| Passing full model objects as props        | Bypasses object pool, breaks deduplication | Pass IDs, query with `Model.find(id)`          |
| `useEffect` for data fetching              | Unnecessary with local-first data          | Remove; data is synchronously available        |
| `useState` for domain data                 | Duplicates source of truth                 | Use MobX models as the single source           |
| Third-party store for domain data          | Extra dependency, split source of truth    | MobX models for all persistent state           |
| `observer()` on design system components   | Couples design system to MobX              | Keep design system props-based                 |
| Manual loading states for instant data     | Unnecessary complexity                     | Data is local; just check for `undefined`      |
| Calling `model.save()` after every change  | Generates unnecessary CreateTransactions   | `save()` is for new models; changes auto-sync  |
