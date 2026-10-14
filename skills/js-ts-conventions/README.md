# js-ts-conventions

One set of JavaScript/TypeScript conventions, audited and enforced the same way in every repo.

## What it does

- **Audit**: measures every preference with the repo's own linter, isolated from the repo's rules, and checks tsconfig
  strictness and config conflicts. Writes `REPORT.md`, then the agent reviews what lint can't check and writes a
  batched `PLAN.md` with time estimates.
- **Enforce**: generates a conventions config that oxlint `extends` or ESLint wraps (`withConventions`). A zero-dependency
  custom plugin covers what stock rules can't. Also writes Claude Code and Cursor rule files.
- **Ratchet**: freezes today's violations (ESLint bulk suppressions, oxlint per-file exemptions) so the rules can be
  errors for new code on day one.
- **SHA-protected regeneration**: hand-edited generated files are never overwritten; per-repo exceptions live in
  `.js-ts-conventions/overrides.json` with a reason.

## Installation

Add to the target repo's `skills-lock.json`, then run the skills installer:

```json
{
  "js-ts-conventions": {
    "source": "ElliottCuvelier/my-skills",
    "sourceType": "github",
    "skillPath": "skills/js-ts-conventions"
  }
}
```

Invoke with `/js-ts-conventions`, or ask to "audit the code style" or "enforce our conventions".

## Compatibility

| Tool | Supported | Verified |
|---|---|---|
| Python | 3.9+, stdlib only | 3.9, 3.13 |
| oxlint | `.oxlintrc.json` with `jsPlugins` | 1.88 (full cycle), 1.57 and 1.73 (audit) |
| ESLint | flat config (`eslint.config.*`) | 10.12 (full cycle), 9.39 (audit), 8.57 (wrapper) |
| ESLint bulk suppressions (ratchet) | ESLint ≥ 9.24 | 10.12 |
| typescript-eslint | v8 (TypeScript < 6.1) | 8.71 |
| No linter | audit via `npx oxlint@1` | 1.88 |

Not supported for enforce: Biome-only repos, legacy `.eslintrc*`, `oxlint.config.ts` (wire by hand).

## Layout

```
js-ts-conventions/
├── SKILL.md                 # agent workflow (audit / enforce / fix)
├── preferences.json         # THE catalog: 19 preferences and their enforcement mapping
├── references/
│   ├── AUDIT.md             # report reading, agent review, PLAN.md format, estimates
│   └── ENFORCE.md           # wiring, monorepos, overrides, ratchet, troubleshooting
├── scripts/
│   ├── analyze_repo.py      # signals: lint units, tsconfigs, aliases, DDD layout
│   ├── audit.py             # REPORT.md + audit.json; --fix applies convention autofixes
│   ├── enforce.py           # generate, --ratchet, --check
│   ├── lint_engine.py       # isolated oxlint/ESLint runs
│   └── utils.py
├── templates/
│   ├── plugin.mjs           # custom rules, copied verbatim into .js-ts-conventions/
│   ├── eslint.mjs.tmpl      # withConventions() wrapper
│   ├── claude-rule.md.tmpl, cursor-rule.mdc.tmpl, state-readme.md.tmpl
└── tests/plugin.test.mjs    # RuleTester suite for the custom rules
```

## Changing the conventions

The catalog is the single source of truth. To add or change a preference:

1. Edit `preferences.json`. Each entry has `statement`, `why`, `bad`/`good` examples, `level` (must → error,
   should → warn), `files` (`ts` / `all` / `ddd` / globs), and `enforce` per tool (`eslint`, `oxlint`, `tsconfig`).
   An entry without `enforce` becomes an agent-review preference and needs a `review` instruction.
2. A rule no stock linter has goes in `templates/plugin.mjs`. Keep it ESLint-API compatible and dependency-free, and
   avoid `null` literals in the plugin source (it must pass the rules it defines).
3. Bump `catalog_version`.
4. Run the tests (below), then re-run `enforce.py` in each consuming repo after re-installing.

## Testing the custom rules

From any scratch directory with the linters installed:

```bash
npm i eslint typescript-eslint "typescript@<6.1"
node --test /path/to/js-ts-conventions/tests/plugin.test.mjs
```

The suite resolves `eslint` and `typescript-eslint` from the current directory. To check oxlint parity, run both linters
with the plugin over the same files; counts and line numbers must match.
