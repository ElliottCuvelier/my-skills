# cursor-orchestrator

Plan on a frontier model. Execute on cheaper sub-agents.

`cursor-orchestrator` is a Cursor skill that lets you split planning from implementation across models: use Claude 4.7 Opus (or GPT-5.4, or whatever frontier model you like) to draft a Plan Mode plan, then dispatch each step of the plan to cheaper model-pinned sub-agents — Composer 2 by default. No more paying frontier rates for mechanical implementation work.

## How it works

1. You open **Plan Mode** on a capable model and mention the skill (or the rule auto-triggers).
2. The skill helps you draft the plan as usual.
3. Before finalizing, it asks which _implementation_ tier to use (Composer, Fast, Mini, Haiku, or Premium-inherit).
4. It writes an `execution:` block into the plan's YAML frontmatter.
5. You save the plan and run `/orchestrate <plan-path>`.
6. The `plan-orchestrator` sub-agent reads the plan and dispatches each todo to `impl-<tier>` — each hard-pinned to a specific model.
7. An optional `verifier` checks each step's output and catches silent model downgrades.

The orchestrator doesn't write code. The implementers don't coordinate. You don't pay Opus rates to change an import statement.

## Installation

This skill is a **source skill** in the `my-skills` personal skills repo. Target projects install it via the repo's `skills-lock.json` mechanism — the same way [use-linear](../use-linear/) and other skills are distributed.

To add it to a target project's `skills-lock.json`:

```json
{
  "version": 1,
  "skills": {
    "cursor-orchestrator": {
      "source": "<user>/my-skills",
      "sourceType": "github",
      "computedHash": "<sha>"
    }
  }
}
```

The installer copies `skills/cursor-orchestrator/` into the target project's skill directory. First use in the target project runs the setup interview — see below.

## First use (bootstrap)

The first time the skill is triggered in a target project, it runs a **7-question setup interview** to decide what gets generated:

1. **Scope** — project (`.cursor/`), user-wide (`~/.cursor/`), or both?
2. **Tiers** — which of composer / fast / mini / haiku / premium to install?
3. **Default tier** — which tier is used when a plan doesn't specify one?
4. **Verifier?** — install the verification sub-agent?
5. **Plan Mode rule?** — install the Cursor rule that hints toward this skill?
6. **Slash command wrappers?** — install `/orchestrate` and `/update-orchestrator`?
7. **Max Mode status?** — do you have Max Mode enabled?

Full wording and option labels are in [references/SETUP.md](references/SETUP.md). The agent conducts the interview via the `AskQuestion` tool; no stdin or terminal interaction is required.

After the interview, the skill writes:

```
<scope>/agents/
├── plan-orchestrator.md              # dispatches plan steps
├── impl-composer.md                  # model: composer-2
├── impl-fast.md                      # model: fast
├── impl-<tier>.md                    # one per selected tier
├── verifier.md                       # (if Q4 = yes)
├── orchestrate.md                    # (if Q6 = yes) - /orchestrate wrapper
├── update-orchestrator.md            # (if Q6 = yes) - /update-orchestrator wrapper
└── .cursor-orchestrator-installed    # marker file (JSON with answers + file hashes)
<scope>/rules/
└── cursor-orchestrator-plan-mode.mdc # (if Q5 = yes)
```

The marker file tracks everything: the user's answers, the catalog timestamp, and the SHA256 of every generated file (for idempotent regeneration).

## Usage

### Drafting a plan

Start Plan Mode on your frontier model. Mention the skill if the rule doesn't auto-trigger:

> "Let's plan this feature. I want to orchestrate the build so Composer does the work."

The skill walks you through the plan and asks:

> "Which tier should this plan run on? (default: composer)"

It adds an `execution:` block to the plan frontmatter:

```yaml
execution:
  implementation_model: composer
  parallelism: sequential
  verify_each_step: true
```

Full schema in [references/PLAN_FORMAT.md](references/PLAN_FORMAT.md).

### Executing a plan

Save the plan, then:

```
/orchestrate .cursor/plans/my-feature.plan.md
```

The orchestrator reads the plan, dispatches each todo to `/impl-composer`, optionally runs `/verifier` between steps, and reports a summary.

> **Don't use the Build button.** Cursor's native Build button continues your current chat on your current model — it can't be reprogrammed to switch models per step. Use `/orchestrate` instead.

### Refreshing the model catalog

When new models ship or prices change:

```
/update-orchestrator
```

Fetches the latest `cursor.com/docs/models-and-pricing`, diffs against the cached catalog, asks for confirmation, and regenerates the `impl-*` files whose tier mapping changed. User-edited files are preserved (SHA mismatch → skip with warning).

To re-answer the 7 setup questions:

```
/update-orchestrator --reconfigure
```

## Scripts (for debugging / manual use)

All scripts are stdlib-only (no pip deps).

```bash
# Fetch the latest pricing page and emit JSON
python scripts/update_models.py

# Force the offline fallback (for testing)
python scripts/update_models.py --no-fetch

# Run the full setup (usually invoked by the agent after the interview)
python scripts/setup.py --answers '{"scope":"project","tiers":["composer","fast","premium"],"default_tier":"composer","verifier":true,"rule":true,"commands":true,"max_mode":true}'

# Regenerate from the existing marker (usually via /update-orchestrator)
python scripts/generate_agents.py --regenerate --tiers "$(python scripts/update_models.py | python3 -c 'import json,sys;print(json.dumps(json.load(sys.stdin)["tiers"]))')"
```

## Known limitations

- **Native Build button**. Can't be reprogrammed. Use `/orchestrate`.
- **Silent model downgrades**. Cursor falls back to a cheaper model when Max Mode isn't enabled, the model is admin-blocked, or the user's plan doesn't include it. The verifier sub-agent catches and reports this.
- **Stale model catalog**. The skill fetches on first-use and on `/update-orchestrator`. Between runs, the catalog may lag new model releases.
- **Parallelism is conservative**. The orchestrator falls back to sequential when it can't prove steps are independent. Add explicit `depends_on` and `files` fields to your todos to unlock parallel dispatch.
- **Model IDs are a moving target**. Cursor doesn't publish canonical model IDs on the pricing page. The skill uses a curated mapping (`CANONICAL_MODEL_IDS` in `scripts/utils.py`) plus a slugify fallback. If Cursor silently downgrades because the mapped ID is wrong, edit the generated `impl-*.md` file — your edit will be preserved across regenerates.

## Troubleshooting

See [references/TROUBLESHOOTING.md](references/TROUBLESHOOTING.md) for solutions to common issues (downgrades, missing tiers, stale catalog, reinstalling from scratch).

## Layout

```
skills/cursor-orchestrator/
├── SKILL.md                          # agent-facing entry point (triggers in Plan Mode)
├── README.md                         # this file
├── references/
│   ├── SETUP.md                      # full 7-question interview reference
│   ├── PLAN_FORMAT.md                # execution: block schema
│   ├── TROUBLESHOOTING.md            # common issues and fixes
│   ├── MODEL_CATALOG.md              # generated on fetch
│   └── MODEL_CATALOG.md.fallback     # committed offline snapshot
├── scripts/
│   ├── utils.py                      # shared helpers (stdlib only)
│   ├── update_models.py              # fetches cursor.com pricing, categorizes into tiers
│   ├── generate_agents.py            # renders templates into target agents/ and rules/
│   └── setup.py                      # first-use entry point
└── templates/
    ├── orchestrator.md.tmpl
    ├── implementer.md.tmpl
    ├── verifier.md.tmpl
    ├── orchestrate-cmd.md.tmpl
    ├── update-cmd.md.tmpl
    └── plan-mode-rule.md.tmpl
```
