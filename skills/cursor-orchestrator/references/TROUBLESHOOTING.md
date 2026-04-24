# Troubleshooting

Common issues and how to resolve them.

## Silent model downgrade

**Symptom:** You configured a plan to run on `claude-opus-4-7` (or similar), but the verifier reports `DOWNGRADE:` after a step, or the implementation quality is noticeably worse than expected.

**Cause:** Cursor silently falls back to a cheaper model when:

- The configured model requires **Max Mode** and the user's plan doesn't include it.
- The model is **admin-blocked** at the team/org level.
- The model **isn't on the user's plan** (some models gate by plan tier).

**Fix:**

1. Check Max Mode status: Settings → Model → Max Mode toggle.
2. Check with your Cursor admin if models appear missing from the picker.
3. Re-run the 7-question interview with correct Max Mode answer:
   ```
   /update-orchestrator --reconfigure
   ```
4. Pick a tier that works on your plan — `composer` and `fast` are always available on all plans.

The verifier (if installed) will catch and report these downgrades proactively. Trust its reports.

## Native Build button runs on the wrong model

**Symptom:** You clicked "Build" on a plan but it ran on whatever model was in the composer picker, not the tier you set in `execution.implementation_model`.

**Cause:** The native Build button cannot be reprogrammed — it continues the current chat session with the currently-selected model. This is a Cursor limitation, not a bug in the skill.

**Fix:** Use `/orchestrate <plan-path>` instead of Build. The `/orchestrate` command dispatches to the `plan-orchestrator` sub-agent, which in turn dispatches each step to the correct `impl-<tier>` sub-agent (each pinned to its model in the sub-agent's `model:` field).

Mnemonic: **Build = "continue this chat." Orchestrate = "dispatch this plan."**

## `/orchestrate` says "tier X is not installed"

**Symptom:**

```
Error: Tier 'haiku' is not installed. Installed tiers: composer, fast, premium.
```

**Cause:** The plan's `execution.implementation_model` references a tier that wasn't selected during the 7-question interview, so no `agents/impl-haiku.md` exists.

**Fix:** Two options:

1. Edit the plan and pick a tier that _is_ installed.
2. Install the missing tier:
   ```
   /update-orchestrator --reconfigure
   ```
   and select the missing tier at question 2.

## Model catalog looks stale

**Symptom:** `references/MODEL_CATALOG.md` shows old prices, or a new model you expect (e.g., Composer 3) isn't listed.

**Cause:** The catalog is refreshed only on:

- First-use setup (`setup.py` → `update_models.py`)
- Explicit `/update-orchestrator` command

**Fix:**

```
/update-orchestrator
```

This fetches the latest from `cursor.com/docs/models-and-pricing`, shows a diff, and asks before regenerating. If you also want to change tier selection or other answers, add `--reconfigure`.

## Fetch fails during setup or update

**Symptom:**

```
"source": "file://.../MODEL_CATALOG.md.fallback",
"stale": true
```

**Cause:** Network is down, `cursor.com` is unreachable, or the page format changed and parsing failed.

**Fix:**

- If temporary: retry `/update-orchestrator` later.
- If the page format changed: update the parser in `scripts/update_models.py`. The fallback snapshot at `references/MODEL_CATALOG.md.fallback` keeps setup working offline in the meantime.
- If you need a specific model immediately: edit the generated `agents/impl-<tier>.md` to hard-code the right `model:` ID. Your edit will be preserved on the next regenerate (SHA mismatch → skipped with a warning).

## I edited an `impl-*.md` file — will `/update-orchestrator` clobber my changes?

**No.** The skill stores a SHA256 of every generated file in the marker (`.cursor-orchestrator-installed`). On regenerate:

- Files whose current SHA matches the stored SHA → overwritten (expected case).
- Files whose current SHA differs → **skipped**, with a warning in the report.

If you want to accept the regenerated version and discard your edits, delete the file first, then run `/update-orchestrator`.

## The verifier reports `INCOMPLETE` but the build "looks done"

**Symptom:** The final report shows `INCOMPLETE: step-3` but you can see the files were modified.

**Cause:** The verifier checks that the implementation _actually works_ — not just that files were touched. Common reasons for `INCOMPLETE`:

- Tests don't pass
- Imports/exports don't wire up
- New symbol is defined but not used
- File edit was a stub / placeholder

**Fix:** Read the verifier's specific report, then either:

- Re-run the step on a more capable tier (e.g., retry on `premium`).
- Do the step manually and mark the todo `completed` in the plan.

## Rule doesn't seem to trigger in Plan Mode

**Symptom:** The Plan Mode rule was installed but the agent doesn't proactively suggest `cursor-orchestrator`.

**Cause:** `alwaysApply: false` means the rule is auto-attached by Cursor but may not always fire based on the current context.

**Fix:** Manually invoke the skill with something like "use cursor-orchestrator for this plan" or type `/orchestrate <existing-plan>` to test directly. The rule is a nudge, not a hard trigger.

## I don't see `/orchestrate` in the slash command list

**Symptom:** Typing `/` doesn't show `orchestrate` as a suggestion.

**Cause:** Either:

- You chose "no" to question 6 (slash command wrappers) at setup.
- The agent file is at `~/.cursor/agents/orchestrate.md` but you're in a project with its own `.cursor/agents/` that doesn't have it — project overrides.

**Fix:**

```
/update-orchestrator --reconfigure
```

and answer "yes" to question 6. Or invoke the full name directly: `/plan-orchestrator <plan-path>`.

## Reinstalling from scratch

If things are in a bad state and you want to start over:

1. Delete the marker and generated files:
   ```bash
   rm .cursor/agents/.cursor-orchestrator-installed
   rm .cursor/agents/plan-orchestrator.md .cursor/agents/impl-*.md
   rm .cursor/agents/verifier.md .cursor/agents/orchestrate.md .cursor/agents/update-orchestrator.md
   rm .cursor/rules/cursor-orchestrator-plan-mode.mdc
   ```
2. Invoke the skill from scratch (mention `cursor-orchestrator` in a Plan Mode chat) — the first-use interview will run again.
