---
name: reactive-local-first-sync-engine
description: Hybrid local-first sync engine architecture using TinyBase as storage foundation with MobX reactivity and TypeScript decorator-based models delivering Linear-like DX. Proactively apply when building local-first SPAs, offline-first apps, reactive data models, sync engines, optimistic UI, real-time collaboration, or transaction-based sync. Triggers on local-first, sync engine, TinyBase, MobX models, offline-first, reactive models, optimistic UI, transaction queue, decorator models, real-time sync, IndexedDB persistence, CRDT sync, WebSocket synchronization, model registry, observable models, lazy hydration. Use when designing local-first architecture, implementing decorator-based data models, setting up TinyBase with MobX, building transaction queues for sync, creating offline-capable SPAs, or structuring a new local-first project beyond simple state management.
---

# Reactive Local-First Sync Engine

Hybrid local-first architecture combining TinyBase (storage + CRDT sync), MobX (reactivity), and TypeScript decorators (model definition) to deliver Linear-grade developer experience: `issue.title = "New"; issue.save();`.

## Compatibility

| Dependency      | Minimum Version          | Notes                                                                                                                                                                                                                                                                                                    |
| --------------- | ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TinyBase        | v8+                      | Native object/array cells, middleware, `MergeableStore`, `createIndexedDbPersister`                                                                                                                                                                                                                      |
| MobX            | v6+                      | `makeObservable`, `observable`, `computed`, `reaction`                                                                                                                                                                                                                                                   |
| mobx-react-lite | v4+                      | `observer()` HOC for React components                                                                                                                                                                                                                                                                    |
| React           | v18+ / v19               | Suspense support required for lazy hydration                                                                                                                                                                                                                                                             |
| TypeScript      | v5+                      | TC39 decorators preferred; `experimentalDecorators` supported in MobX 6, dropped in MobX 7                                                                                                                                                                                                               |
| uuid            | v10+                     | UUID v7 for time-ordered entity IDs (v12+ drops CJS)                                                                                                                                                                                                                                                     |
| nanoid          | v5+                      | Compact IDs for ephemeral transaction IDs                                                                                                                                                                                                                                                                |
| `tsconfig.json` | `isolatedModules: false` | This skill uses `const enum` throughout. `const enum` requires `isolatedModules: false` — **incompatible with Vite, esbuild, and SWC** (which require `isolatedModules: true`). If you use one of those bundlers, replace every `const enum` with a regular `enum` or an `as const` object + type alias. |

## When to Use (and When NOT to)

| Use When                                               | Skip When                               |
| ------------------------------------------------------ | --------------------------------------- |
| Client-heavy SPA with real-time collaboration          | Server-rendered pages (Next.js SSR/RSC) |
| Offline-first requirement (works without network)      | Simple CRUD with no offline needs       |
| Need instant UI (no loading spinners for data)         | Backend-heavy workflow (admin panels)   |
| Complex domain models with relationships               | Flat key-value config storage           |
| Multiple users editing shared data simultaneously      | Single-user app with no collaboration   |
| Want Linear-like DX (decorator models, `model.save()`) | Prefer hooks-only architecture (no OOP) |

## Architecture Overview

The architecture has five layers, each with a clear responsibility:

```
React UI (observer)
    |
    v
MobX Models (@ClientModel, @Property, @ManyToOne, @OneToMany)
    |                          |
    v                          v
TinyBase Store             Transaction Queue
(in-memory + IndexedDB)    (pending mutations)
    |          |               |
    v          v               v
IndexedDB   MergeableStore   GraphQL Mutations
Persister   (CRDT sync)     (batched to server)
               |               |
               v               v
         WebSocket Sync    Backend Server
                               |
                               v
                        Delta Packets (WebSocket)
                               |
                               v
                        MobX Models (update)
```

**Data flow:**

1. UI mutates a model property (`item.title = "New"`) -- MobX observable triggers immediate re-render
2. The change is written to TinyBase (local source of truth) and a Transaction is queued
3. TinyBase persists to IndexedDB (survives page reload)
4. Transaction queue batches and sends GraphQL mutations to the server
5. Server executes mutations, broadcasts delta packets to all clients via WebSocket
6. Client applies deltas: updates TinyBase rows, rebases pending transactions, updates in-memory models

## Core Principles

1. **TinyBase is the local source of truth.** Models are an OOP view layer over TinyBase rows. All reads go through TinyBase; all writes flow through the transaction system.

2. **MobX provides reactivity.** Decorator registration wires up `makeObservable` automatically. React components wrapped in `observer()` re-render precisely when their accessed properties change.

3. **Transactions are the sync unit.** Every create, update, or delete becomes a serializable, rebasable, undoable transaction. Transactions are queued, batched, persisted to IndexedDB for crash recovery, and sent as GraphQL mutations.

4. **The server is the single source of truth (SSOT).** TinyBase rows only update after server confirmation via delta packets. In-memory models are optimistic (updated immediately for instant UI), but the local database never contains unconfirmed changes.

5. **Last-writer-wins conflict resolution.** When a delta packet conflicts with a pending local transaction, the transaction is rebased onto the server state. Simple, predictable, sufficient for most collaborative tools.

6. **No `null`, only `undefined`.** Consistent across the entire codebase. Use explicit `| undefined` types, never optional `?:` for model properties.

## Quick Decision Trees

### "Where does this code go?"

```
Where does it go?
|-- Pure model definition (fields, relationships)  --> models/ (@ClientModel, @Property)
|-- Model business logic (publish, archive)         --> methods on the model class
|-- Derived/computed state from model fields        --> @computed getter on model
|-- Local storage, persistence, schema              --> store/ (TinyBase setup)
|-- Sync mutations (create/update/delete)           --> transactions/ (auto-generated)
|-- Server communication (GraphQL, WebSocket)       --> sync/ (sync client, delta handler)
|-- React component consuming model data            --> domains/ (observer + Model.find)
|-- User preferences (theme, sidebar, default view) --> MobX model (e.g. UserSettings, synced)
|-- Ephemeral UI state (modal open, dropdown)       --> React useState (component-local)
|-- Design system component (Button, Card)          --> components/ (props-based, no models)
```

### "TinyBase CRDT sync vs Transaction queue?"

```
Which sync mechanism?
|-- Simple shared state (presence, cursors, counters)?
|   --> MergeableStore + WsSynchronizer (TinyBase native CRDT)
|
|-- Business mutations requiring server validation?
|   --> Transaction queue + GraphQL mutations
|   (access control, side effects, audit trail, domain events)
|
|-- Both? (common)
|   --> CRDT for ephemeral collaborative state
|   --> Transactions for persistent domain mutations
```

### "Eager vs Lazy loading?"

```
How should this model load?
|-- Small dataset, needed on every page?        --> instant (load at bootstrap)
|-- Large dataset, needed on demand?            --> lazy (load all when first accessed)
|-- Subset needed, loaded per-entity?           --> partial (load by relationship index)
|-- Only when explicitly requested by user?     --> explicitlyRequested
|-- Frontend-only, no server sync?              --> local (IndexedDB only)
```

## Directory Structure

```
src/
|-- sync-engine/
|   |-- models/
|   |   |-- model-registry.ts            # Global metadata map (ModelRegistry)
|   |   |-- decorators.ts                # @ClientModel, @Property, @ManyToOne, @OneToMany
|   |   |-- collection.ts                # Collection<T> for OneToMany relationships
|   |   |-- model.base.ts                # Base Model class (CRUD, hydration, queries)
|   |   |-- lazy-reference.ts            # LazyReference<T> and LazyReferenceCollection<T>
|   |   `-- [domain].model.ts            # Domain model definitions
|   |-- store/
|   |   |-- store.ts                     # TinyBase singleton (Store or MergeableStore)
|   |   `-- schema.ts                    # Schema definition aligned with ModelRegistry
|   |-- transactions/
|   |   |-- transaction.base.ts          # Base Transaction class
|   |   |-- create-transaction.ts        # CreateTransaction
|   |   |-- update-transaction.ts        # UpdateTransaction
|   |   |-- delete-transaction.ts        # DeleteTransaction
|   |   `-- transaction-queue.ts         # Queue with 4-stage pipeline
|   |-- sync/
|   |   |-- sync-client.ts              # WebSocket connection, delta handling
|   |   |-- bootstrap.ts                # Full/partial/local bootstrap
|   |   `-- delta-handler.ts            # Apply delta packets, rebase transactions
|   `-- index.ts                         # Public API exports
|-- domains/
|   `-- [domain]/
|       |-- index.ts                     # Public exports
|       |-- [Entity]Card.tsx             # observer() component (local-first)
|       `-- [Entity]List.tsx             # observer() component (local-first)
|-- components/                          # Design system (props-based, no models)
`-- layouts/
    `-- DashboardLayout.tsx              # Shell with navigation
```

## Reference Documentation

Read these reference files for detailed implementation guidance. Each covers a specific architectural concern.

| File                                                                   | Purpose                                                                     | Read When                                                |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------- | -------------------------------------------------------- |
| [references/MODEL-DEFINITION.md](references/MODEL-DEFINITION.md)       | Decorators, ModelRegistry, property types, relationships, load strategies   | Defining or modifying data models                        |
| [references/TINYBASE-FOUNDATION.md](references/TINYBASE-FOUNDATION.md) | TinyBase store, schema, persistence, MergeableStore, CRDT sync              | Setting up the store layer or persistence                |
| [references/TRANSACTION-SYSTEM.md](references/TRANSACTION-SYSTEM.md)   | Transaction types, queue, batching, GraphQL generation, undo/redo           | Implementing mutations, offline sync, or undo/redo       |
| [references/SYNC-PROTOCOL.md](references/SYNC-PROTOCOL.md)             | Bootstrapping, syncId, delta packets, lazy hydration, sync groups           | Implementing server sync, bootstrapping, or lazy loading |
| [references/REACT-PATTERNS.md](references/REACT-PATTERNS.md)           | observer(), props-based vs local-first, state boundaries, Suspense, testing | Building React components that consume models            |
| [references/CHEATSHEET.md](references/CHEATSHEET.md)                   | Quick decision guide, file naming, new feature checklist                    | Day-to-day development reference                         |

## Sources

### Primary Sources

- [Reverse Engineering Linear's Sync Engine](https://github.com/wzhudev/reverse-linear-sync-engine) -- Wenzhao Hu (2025)
- [Real-time sync for web apps](https://www.youtube.com/watch?v=WxK11RsLqp4) -- Tuomas Artman, React Helsinki (2020)
- [Unexpected Benefits of Going Local-First](https://www.youtube.com/watch?v=VLgmjzERT08) -- Tuomas Artman, Local-First Conf (2024)
- [Building a Synchronous Experience with Asynchronous Data](https://www.youtube.com/watch?v=bnOpm3a1fRE) -- Tuomas Artman, Local-First Conf (2025)
- [Scaling the Linear Sync Engine](https://linear.app/blog/scaling-the-linear-sync-engine) -- Linear Engineering Blog

### Technology References

- [TinyBase Documentation](https://tinybase.org/) -- Reactive data store and sync engine
- [MobX Documentation](https://mobx.js.org/) -- Simple, scalable state management
- [How Figma's Multiplayer Technology Works](https://www.figma.com/blog/how-figmas-multiplayer-technology-works/) -- Figma Engineering Blog
