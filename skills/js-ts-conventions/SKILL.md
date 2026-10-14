---
name: js-ts-conventions
description: "Audit and enforce personal JavaScript/TypeScript coding conventions in any repo. Covers no null (undefined only), no any, strict tsconfig, kebab-case filenames, PascalCase types, SCREAMING_SNAKE_CASE enum members and constants, explicit methods instead of getters, readonly properties, import type, @/ alias imports, Result types, Zod at boundaries, and ISO 8601/E.164 data. Finds style discrepancies, writes a report and a fix plan, then adds the rules to the repo's oxlint or ESLint flat config (custom plugin included), freezes existing violations so new code must comply, and generates Claude Code and Cursor rule files. Use when the user asks to audit, check, lint, standardize or enforce code style, coding standards, conventions, naming rules or TypeScript preferences, find style inconsistencies, add lint rules for their conventions, ratchet lint rules, apply their conventions, house style or TS standards, or types /js-ts-conventions, even if they don't name the skill."
---

# JS/TS conventions

One catalog of TypeScript/JavaScript preferences ([preferences.json](preferences.json), 19 entries), enforced
the same way in every repo:

- **lint**: oxlint or ESLint rules, plus a custom plugin for what stock rules can't express
- **tsconfig**: strictness flags
- **review**: agent rule files for what no linter can check

`<skill>` below is this skill's installed directory. Check `.claude/skills/js-ts-conventions/` first (Claude Code), then
`.agents/skills/js-ts-conventions/` (Cursor), then `~/.claude/skills/js-ts-conventions/`. Scripts need Python 3.9+
and no packages. Everything the skill writes lives in `.js-ts-conventions/` plus the two agent rule files.

## Pick the mode

| The user says | Mode |
|---|---|
| audit, check, "how far off are we", first run, anything unclear | **Audit**. It writes only inside `.js-ts-conventions/` |
| add/enforce the rules, set up lint, wire it into CI | **Enforce**. Run Audit first if `.js-ts-conventions/audit.json` is missing or stale |
| fix the violations, "do batch 2" | **Fix**, from `.js-ts-conventions/PLAN.md` |
| the skill was updated, "refresh the conventions" | **Enforce** again. Generated files are SHA-protected |

## Audit

1. Run `python3 <skill>/scripts/audit.py --root .`. It runs every lint preference through the repo's own linter,
   isolated from the repo's rules. With no linter installed it uses `npx oxlint`. Add `--tsc-impact` to count the
   type errors each missing tsconfig flag would add (slower: one `tsc` run per flag).
2. Read `.js-ts-conventions/REPORT.md` and `audit.json`.
3. Complete the **Agent review** section. For each 🔍 preference, follow its `Check:` line, sample the code, and replace
   `Findings: _pending_` with what you found, citing `file:line`. Never mark a preference compliant without looking.
4. Write `.js-ts-conventions/PLAN.md` following [references/AUDIT.md](references/AUDIT.md): decisions first, then batches
   ordered config → autofix → manual, each sized for one PR and given a time estimate.
5. Reply with three things: the top 3 discrepancies by impact, the decisions you need from the user (max 3), and the
   next step.

## Enforce

Details and config shapes: [references/ENFORCE.md](references/ENFORCE.md).

1. Settle exemptions first. Ask the user about each *Boundary candidate* in REPORT.md (e.g. `**/infrastructure/**`
   for `no-null`), then record the confirmed ones in `.js-ts-conventions/overrides.json` with a reason.
2. Run `python3 <skill>/scripts/enforce.py --root .`. It writes the generated files and prints one wiring step per lint
   config: an `extends` entry for oxlint, or a `withConventions()` wrapper for ESLint.
3. Apply each wiring step exactly. In monorepos with a shared ESLint preset, wire the preset once.
4. Run `enforce.py --check`. Resolve each conflict: remove the repo setting that wins over a convention, or record an
   override with a reason the user gave. Notes are cleanup: delete the repo settings the conventions now override.
5. Run `enforce.py --ratchet`. Existing violations are frozen (ESLint ≥ 9.24 bulk suppressions; oxlint per-file
   exemptions), so convention rules run as errors for new code from now on.
6. Run the repo's own lint command (`package.json` scripts) and `enforce.py --check`. Both must pass before you
   report done.
7. Report what now fails for new code, what is frozen (counts), and what remains for PLAN.md.

## Fix

Work through PLAN.md one batch at a time, one commit per batch:

- Autofix batches: `python3 <skill>/scripts/audit.py --fix` (only convention rules with safe fixes, currently
  `type-imports`). Add the commit SHA to `.git-blame-ignore-revs`.
- Manual batches: fix, run the repo's lint and typecheck, then tighten the freeze. ESLint:
  `eslint . --prune-suppressions` in that package. oxlint: `enforce.py --ratchet` again.
- Re-run the audit at the end and update PLAN.md's progress line.

## Rules

- The catalog is the user's standard. Never edit `preferences.json` to fit a repo. Repo differences go in
  `overrides.json` with a reason.
- Never edit generated files (`.js-ts-conventions/*.mjs`, `oxlint*.json`, the agent rule files). Change overrides and
  re-run enforce; a hand-edited generated file is skipped, not overwritten.
- Ask before you install dependencies, enable a tsconfig flag that adds type errors, rename files (`filename-case`),
  or delete an existing style rule file that the audit lists as overlapping.
- NestJS with `emitDecoratorMetadata`: never convert injected constructor types to `import type`; that breaks DI at
  runtime. The generated configs already exempt these files.
- Biome-only repos and legacy `.eslintrc` configs are out of scope for enforce. Say so, and offer the audit (it still
  runs through `npx oxlint`).
