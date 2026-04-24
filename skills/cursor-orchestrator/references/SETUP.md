# First-Use Setup Interview

This is the full reference for the 7 questions the `cursor-orchestrator` skill asks on first use. The agent should conduct this interview via the `AskQuestion` tool (not stdin) so it works inside a Cursor chat turn.

All seven questions are asked in sequence. Once complete, the agent invokes `scripts/setup.py --answers <json>` with the collected answers.

---

## Question 1 — Scope

**Prompt:** "Where should the orchestrator's sub-agents and rules live?"

**Options:**

| id        | label                                                     |
| --------- | --------------------------------------------------------- |
| `project` | This project only (`.cursor/agents/`, `.cursor/rules/`)   |
| `user`    | All my projects (`~/.cursor/agents/`, `~/.cursor/rules/`) |
| `both`    | Both — project overrides user-wide when they overlap      |

**Default:** `project`

**Writes to:** `answers.scope`

**Effect:** Controls the target directories where `setup.py` and `generate_agents.py` will write. `both` produces two copies of each file; project copies win when the same sub-agent name exists at both scopes (Cursor's project agents shadow user-wide ones).

---

## Question 2 — Tiers to generate

**Prompt:** "Which implementation tiers should I install? (Each tier is a sub-agent pinned to a specific model. Pick the ones you'll actually use — you can add more later via `/update-orchestrator --reconfigure`.)"

**Allow multiple:** yes

**Options:**

| id         | label                                                                                    |
| ---------- | ---------------------------------------------------------------------------------------- |
| `composer` | Composer 2 — Cursor's agentic coding model, best price/performance (recommended default) |
| `fast`     | Cursor fast tier — cheapest available                                                    |
| `mini`     | Cheapest OpenAI (currently GPT-5.4 Nano, ~$0.2/$1.25 per Mtok)                           |
| `haiku`    | Cheapest Anthropic Haiku (currently Claude 4.5 Haiku, ~$1/$5 per Mtok)                   |
| `premium`  | Inherit — implementer runs on the orchestrator's model (escape hatch)                    |

**Default:** `composer`, `fast`, `premium`

**Writes to:** `answers.tiers` (list)

**Effect:** One `agents/impl-<tier>.md` file is generated per selected tier. Unselected tiers get no file — trying to `/orchestrate` a plan with `implementation_model: <missing-tier>` will error with a clear message.

---

## Question 3 — Default tier

**Prompt:** "Which tier should I use as the default for new plans when you don't specify one?"

**Options:** filtered to whatever was selected in question 2.

**Default:** `composer` (if selected), otherwise the first tier in Q2.

**Writes to:** `answers.default_tier`

**Effect:** The agent writes this tier into the plan's `execution.implementation_model` when the user doesn't override per-plan.

---

## Question 4 — Verifier

**Prompt:** "Install a verifier sub-agent? It runs a check pass after each step on the `fast` tier to confirm the implementation actually works (and catches silent model downgrades)."

**Options:**

| id    | label                                        |
| ----- | -------------------------------------------- |
| `yes` | Yes, install verifier (recommended)          |
| `no`  | No, skip verification — I'll verify manually |

**Default:** `yes`

**Writes to:** `answers.verifier` (bool)

**Effect:** If yes, `agents/verifier.md` is generated with `model: fast`. The `plan-orchestrator` invokes it between steps when the plan has `verify_each_step: true`.

---

## Question 5 — Plan Mode rule

**Prompt:** "Install a Cursor rule that auto-attaches in Plan Mode to hint toward this skill? (Helpful if you want proactive suggestions to orchestrate plans; skip if you prefer to invoke the skill manually.)"

**Options:**

| id    | label                               |
| ----- | ----------------------------------- |
| `yes` | Yes, install the rule (recommended) |
| `no`  | No, I'll invoke the skill manually  |

**Default:** `yes`

**Writes to:** `answers.rule` (bool)

**Effect:** If yes, `rules/cursor-orchestrator-plan-mode.mdc` is written. The rule nudges the agent toward this skill when drafting plans that would benefit from cheaper implementation models.

---

## Question 6 — Slash command wrappers

**Prompt:** "Install `/orchestrate` and `/update-orchestrator` as slash-command sub-agents? (These are thin wrappers so you can invoke the orchestrator with a short command instead of the full agent name.)"

**Options:**

| id    | label                                        |
| ----- | -------------------------------------------- |
| `yes` | Yes, install both commands (recommended)     |
| `no`  | No, I'll invoke `plan-orchestrator` directly |

**Default:** `yes`

**Writes to:** `answers.commands` (bool)

**Effect:** If yes, generates `agents/orchestrate.md` and `agents/update-orchestrator.md`. Each is a thin sub-agent whose body is "delegate to `plan-orchestrator`" or "run `update_models.py` and regenerate." If no, the user must invoke `plan-orchestrator` by full name and run the update scripts manually.

---

## Question 7 — Max Mode status

**Prompt:** "Do you have Max Mode enabled on your Cursor plan? (Max Mode is required for Claude Opus variants and a few other frontier models. This affects which tiers can be safely defaulted to — if your tier silently downgrades, the verifier will report it.)"

**Options:**

| id    | label                    |
| ----- | ------------------------ |
| `yes` | Yes, Max Mode is enabled |
| `no`  | No / not sure            |

**Default:** `no`

**Writes to:** `answers.max_mode` (bool)

**Effect:** Stored in the marker for diagnostic use. In future revisions, if Max Mode is `no` and the user selects a tier that requires it, the skill can warn at setup time. For now, informational only.

---

## Example final answers payload

```json
{
  "scope": "project",
  "tiers": ["composer", "fast", "premium"],
  "default_tier": "composer",
  "verifier": true,
  "rule": true,
  "commands": true,
  "max_mode": true
}
```

## Invocation

After all answers are collected:

```bash
python <skill-path>/scripts/setup.py --answers '<json>'
```

Where `<skill-path>` is the install location of this skill. The script validates the payload, fetches the model catalog, generates files, and prints a JSON summary with next-steps for the agent to relay to the user.

## Re-running the interview

Users can re-answer the 7 questions anytime by running:

```
/update-orchestrator --reconfigure
```

This re-opens the interview, then regenerates sub-agent files (respecting the SHA idempotency rules — user-edited files are preserved).
