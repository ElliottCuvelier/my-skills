---
name: Remove Zustand, update versions
overview: Remove all Zustand mentions across the skill files, update package versions to reflect current latest releases, and update TinyBase patterns for v8 (native object/array cells, middleware) and MobX decorator guidance for TC39 compatibility.
todos:
  - id: remove-zustand-skill
    content: 'Remove all Zustand mentions from SKILL.md: compatibility table row, decision tree entry, directory structure `stores/` block, and REACT-PATTERNS reference table description'
    status: completed
  - id: remove-zustand-cheatsheet
    content: Remove Zustand store row from CHEATSHEET.md file naming conventions table
    status: completed
  - id: update-versions
    content: 'Update compatibility table in SKILL.md: TinyBase v5+ to v8+, uuid v11+ to v10+, TypeScript decorator notes'
    status: completed
  - id: update-tinybase-patterns
    content: 'Update TINYBASE-FOUNDATION.md: cell types table for native object/array, schema section for object/array types, toRow() bridge note about simplified serialization'
    status: completed
isProject: false
---

# Remove Zustand and Update Package Versions

## 1. Remove Zustand references (2 files)

### [SKILL.md](skills/reactive-local-first-sync-engine/SKILL.md)

- **Line 21**: Delete the Zustand row from the compatibility table
- **Line 98**: Change `|-- UI chrome state (theme, sidebar, modals) --> stores/ (Zustand, NOT model data)` to point at a MobX model approach (e.g. `UserSettings model (synced preferences)`) and React state for ephemeral UI
- **Lines 160-162**: Remove the `stores/` directory and `ui-store.ts` entry from the directory structure
- **Line 177**: Update the REACT-PATTERNS reference table description from `observer(), props-based vs local-first, Zustand, Suspense, testing` to `observer(), props-based vs local-first, state boundaries, Suspense, testing`

### [references/CHEATSHEET.md](skills/reactive-local-first-sync-engine/references/CHEATSHEET.md)

- **Line 44**: Remove the `| Zustand store | [name]-store.ts | ui-store.ts |` row from file naming conventions

---

## 2. Update compatibility table versions ([SKILL.md](skills/reactive-local-first-sync-engine/SKILL.md) lines 12-21)

| Package         | Current in Skill | Latest Available | Update To                | Notes                                                                                                                                     |
| --------------- | ---------------- | ---------------- | ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- |
| TinyBase        | `v5+`            | 8.0.1            | `v8+`                    | v8 adds native object/array cells and middleware                                                                                          |
| MobX            | `v6+`            | 6.15.0           | `v6+` (no change)        | Still current major version                                                                                                               |
| mobx-react-lite | `v4+`            | 4.1.1            | `v4+` (no change)        | Still current                                                                                                                             |
| React           | `v18+ / v19`     | 19.x             | `v18+ / v19` (no change) | Fine                                                                                                                                      |
| TypeScript      | `v5+`            | 5.x              | `v5+` (no change)        | Update notes: mention TC39 decorators as preferred path, `experimentalDecorators` still supported in MobX 6 but will be dropped in MobX 7 |
| uuid            | `v11+`           | 13.0.0           | `v10+`                   | UUID v7 introduced in v10; v12+ drops CJS (fine for ESM)                                                                                  |
| nanoid          | `v5+`            | 5.1.7            | `v5+` (no change)        |                                                                                                                                           |

---

## 3. Update TinyBase patterns for v8 ([references/TINYBASE-FOUNDATION.md](skills/reactive-local-first-sync-engine/references/TINYBASE-FOUNDATION.md))

### Cell types table (lines 127-138)

TinyBase v8 natively supports `object` and `array` cell types with transparent JSON round-tripping. Update the table:

- Remove the manual `JSON.stringify()` note for `object` and `array`
- Mark them as "Native (v8+)" instead of `string` cell type
- Keep `Date` as `string` (still needs `toISOString()`)

### Schema definition (lines 99-139)

- Add `object` and `array` as valid schema types in the prose and example
- Mention the new middleware system as an option for validation

### Bridge section (`toRow()` at lines 278-302)

- Add a note that with TinyBase v8, objects and arrays can be passed through `toRow()` directly without `JSON.stringify()` serialization

---

## 4. Update TypeScript decorator guidance ([SKILL.md](skills/reactive-local-first-sync-engine/SKILL.md) line 18)

Update the TypeScript row notes from `Decorator support (experimentalDecorators)` to note that TC39 decorators (no flag needed) are the forward-looking choice, and `experimentalDecorators` is supported in MobX 6 but will be dropped in MobX 7. The custom decorators (`@ClientModel`, `@Property`) implementation will need to match the chosen decorator style.
