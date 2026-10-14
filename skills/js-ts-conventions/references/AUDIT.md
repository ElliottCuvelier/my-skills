# Audit: reading the report, finishing the review, writing PLAN.md

## Contents

- [What audit.py measures](#what-auditpy-measures)
- [Reading REPORT.md](#reading-reportmd)
- [Agent review procedure](#agent-review-procedure)
- [PLAN.md format](#planmd-format)
- [Time estimates](#time-estimates)

## What audit.py measures

| Source | How | Precision |
|---|---|---|
| Lint preferences (12) | The repo's own linter with a temp config that keeps the repo's parser, plugins and ignores but runs **only** convention rules | Exact |
| ESLint repos without the needed plugin | Rule skipped, listed under *Not run*. Example: no `@typescript-eslint` plugin, or type-aware rules without `projectService` | n/a |
| ESLint not installed / legacy config | Falls back to `npx oxlint` with the same custom plugin | Exact for the custom and `typescript/*` rules |
| No linter or npx at all | Regex estimate (`~N (grep)`) | Rough |
| `strict-compiler` | Effective tsconfig after the `extends` chain; `--tsc-impact` counts the type errors each missing flag adds | Exact |
| Config conflicts | oxlint: the repo config's own `rules` (they beat `extends`). ESLint: `--print-config` on a sample file | Exact for that file |
| Review preferences (6) | Regex signals only; the agent does the judging | Signals |

Not applicable (`➖`): DDD-scoped preferences (`value-object-structure`, `result-type`, `typed-exceptions`) need folders
named `domain` plus `application` or `infrastructure`. `alias-imports` needs a tsconfig `@/*` path alias. Force a
scoped preference with `"scope": { "<id>": true }` in overrides.json.

## Reading REPORT.md

- **Summary table**: ❌ failing, ⚙️ tsconfig gaps, ❔ unmeasured, 🔍 agent review, ✅ clean, ➖ not applicable.
- **Config discrepancies**:
  - "**wins over the conventions**": the repo setting will beat the convention rule even after wiring. This is an
    oxlint `overrides` entry, or an ESLint block after `withConventions`. Resolve it before enforcing.
  - "**the conventions override it once wired**": the setting will stop mattering. This is an oxlint top-level rule,
    or an ESLint setting before the wrapper. Delete it during Batch 0 so the config doesn't mislead.
- **Boundary candidates** (for `no-null`): how many violations sit in boundary-looking paths. A high share in
  `**/infrastructure/**` or `*.orm-entity.ts` usually means legitimate boundary code: propose an exemption, don't plan
  a fix.
- `audit.json` → `preferences[].per_file` and `by_area`: use these to cut batches by package or module.

## Agent review procedure

For each 🔍 preference in REPORT.md:

1. Use the signals to choose where to look. Example: "0 files using `Result.ok(`" in a DDD repo means the Result
   pattern is missing entirely, which is a finding by itself.
2. Sample up to 10 relevant files (the `Check:` line says which). Prefer recently changed files:
   `git log --since=90.days --name-only --pretty=format: -- '*.ts' | sort | uniq -c | sort -rn | head`.
3. Replace `Findings: _pending_` with a verdict and evidence:

   ```markdown
   - Findings: **partial**. 6 of 10 sampled factories return `Result`; 4 throw
     (`src/modules/sales/request/domain/request.entity.ts:41`, `…/contact.entity.ts:28`, …).
   ```

   Verdicts: **compliant**, **partial**, **non-compliant**, **unclear** (say what you would need to decide).
4. Never estimate counts for review preferences. Report what you sampled.

## PLAN.md format

Write `.js-ts-conventions/PLAN.md`. Keep it executable: every batch is one PR, every step one command or edit.

```markdown
# js-ts-conventions fix plan: <repo>

Source: REPORT.md (<date>) · <N> violations across <M> preferences · Progress: 0/<B> batches

## Decisions (max 3, answer before batch 1)

1. `no-null` in `src/**/infrastructure/**` (210 of 412): exempt as boundary code? Recommended: yes.
2. ...

## Batch 0: Wire the conventions (no code changes) · ~15 min

- [ ] Record the decided exemptions in `.js-ts-conventions/overrides.json`
- [ ] `enforce.py` → apply the wiring steps → `enforce.py --ratchet` → `enforce.py --check`
- [ ] tsconfig: enable `noImplicitReturns` in `apps/api/tsconfig.json` (+0 errors)

## Batch 1: Autofix `type-imports` · ~10 min · 1 commit

- [ ] `python3 <skill>/scripts/audit.py --fix`
- [ ] Run lint and typecheck; commit `style: apply import type autofix`
- [ ] Add the commit SHA to `.git-blame-ignore-revs`

## Batch 2: `naming` in `apps/api/src/modules/sales` (38 violations, 9 files) · ~40 min

- [ ] ...
- [ ] Tighten the freeze: `eslint . --prune-suppressions` (ESLint) or `enforce.py --ratchet` (oxlint)

## Later (not scheduled)

- `readonly-props`: 1,240 violations, mostly React props interfaces. Revisit or opt out.
```

Batching rules:

1. **Batch 0 is always config**: overrides, wiring, ratchet, and tsconfig flags whose impact is 0. A flag that adds
   type errors gets its own batch, after the code batches that reduce those errors.
2. **Autofix next**, one commit per rule, each SHA added to `.git-blame-ignore-revs` so `git blame` skips it.
3. **Manual batches** go by area (`by_area` in audit.json) and stay under ~50 violations or ~400 changed lines, so
   one person can review each in one sitting. Within an area, order must before should, then by count.
4. **Renames** (`filename-case`) get their own batch per area: `git mv`, update imports, run typecheck. Ask before
   starting; renames touch every importer.
5. Put **should-level preferences with more than 500 violations** under *Later* with a recommendation (fix
   gradually, or opt out with a reason) rather than scheduling them.

## Time estimates

Base each batch estimate on the violation count, then round up to the nearest 5 minutes:

| Kind | Per violation | Notes |
|---|---|---|
| Autofix (`type-imports`) | ~0 | ~10 min per batch for run + review + commit |
| `naming`, `constant-case`, `as-const-constants`, `readonly-props` | ~1 min | IDE rename; `readonly` can surface writes elsewhere |
| `no-null` | ~3 min | Types ripple; boundary mappers need `?? undefined` |
| `no-getters` | ~3 min | Every call site changes from `x.name` to `x.getName()` |
| `no-any`, `explicit-types` | ~3 min | Needs the real type; slower in untyped legacy code |
| `typed-exceptions` | ~2 min | Pick or create the exception class |
| `alias-imports` | ~1 min | Mechanical; one batch per module |
| `filename-case` | ~4 min | `git mv` plus importer updates |
| tsconfig flag | ~2 min per type error it adds | Use `--tsc-impact` numbers |

State estimates as ranges when the count is large (e.g. "~3–4 h, split over 4 PRs").
