# First-Use Setup Interview

Full reference for the 7 questions `claude-orchestrator` asks on first use. Conduct via `AskUserQuestion` — not stdin.

All 7 are asked in sequence. After collection, run `scripts/analyze_codebase.py`, compose the roster, run `scripts/detect_byterover.py`, show Q8 (roster confirmation), then call `scripts/setup.py --answers <json>`.

---

## Question 1 — Scope

**Prompt:** "Where should the orchestrator's sub-agents and commands live?"

**Options:**

| id | label |
|----|-------|
| `project` | This project only (`.claude/agents/`, `.claude/commands/`) |
| `user` | All my projects (`~/.claude/agents/`, `~/.claude/commands/`) |
| `both` | Both — project overrides user-wide when they overlap |

**Default:** `project`

**Writes to:** `answers.scope`

**Effect:** Controls the target directories where `setup.py` and `generate_agents.py` write files. `both` produces two copies; project-scoped agents shadow user-wide ones when the same name exists at both scopes.

---

## Question 2 — Tiers to install

**Prompt:** "Which implementation tiers should I install? Each is a sub-agent pinned to a Claude model. Pick the ones you'll actually use — you can add more via `/update-claude-orchestrator --reconfigure`."

**Allow multiple:** yes

**Options:**

| id | label |
|----|-------|
| `haiku` | Claude Haiku — cheapest, fastest; bulk changes, typo fixes, simple refactors |
| `sonnet` | Claude Sonnet — balanced; default for most implementation work |
| `opus` | Claude Opus — premium; complex logic, system design, architecture |
| `inherit` | Inherit — same model as the orchestrator; escape hatch for steps needing full planning-tier reasoning |

**Default:** `haiku`, `sonnet`, `inherit`

**Writes to:** `answers.tiers` (list)

**Effect:** One `agents/impl-<tier>.md` file is generated per selected tier. Unselected tiers get no file; trying to run a plan with `implementation_model: <missing-tier>` errors with a clear message.

---

## Question 3 — Default tier

**Prompt:** "Which tier should I use as the default for new plans when you don't specify one?"

**Options:** Filtered to whatever was selected in Q2.

**Default:** `sonnet` (if selected), otherwise the first tier in Q2.

**Writes to:** `answers.default_tier`

**Effect:** Written into the plan's `execution.implementation_model` when the user doesn't override per-plan.

---

## Question 4 — Verifier sub-agent

**Prompt:** "Install a verifier sub-agent? It runs a check pass after each step on the `haiku` tier to confirm the implementation actually works (reports `VERIFIED:`, `INCOMPLETE:`, `CONCERN:`, or `DOWNGRADE:`)."

**Options:**

| id | label |
|----|-------|
| `yes` | Yes, install verifier (recommended) |
| `no` | No, skip verification — I'll verify manually |

**Default:** `yes`

**Writes to:** `answers.verifier` (bool)

**Effect:** If yes, `agents/verifier.md` is generated with `model: haiku`. The `plan-orchestrator` invokes it between steps when the plan has `verify_each_step: true`.

---

## Question 5 — Memory curator

**Prompt:** "Install a memory-curator agent? It runs once after all todos complete to consolidate learnings into `.brv/context-tree/`. Recommended when ByteRover is enabled."

**Options:**

| id | label |
|----|-------|
| `yes` | Yes, install memory-curator (recommended if ByteRover enabled) |
| `no` | No, skip — I don't use ByteRover or prefer manual curation |

**Default:** `yes` (if ByteRover is detected or user selected "install now" in Q7); otherwise `no`

**Writes to:** `answers.memory_curator` (bool)

**Effect:** If yes, `agents/memory-curator.md` is generated with `model: inherit`. The orchestrator dispatches it as the final step when `curate_on_completion: true` in the plan.

---

## Question 6 — Slash commands

**Prompt:** "Install `/claude-orchestrate`, `/claude-orchestrate-resume`, and `/update-claude-orchestrator` as slash commands? (These are thin wrappers so you can invoke the orchestrator with a short command.)"

**Options:**

| id | label |
|----|-------|
| `yes` | Yes, install all three commands (recommended) |
| `no` | No, I'll invoke `plan-orchestrator` directly |

**Default:** `yes`

**Writes to:** `answers.commands` (bool)

**Effect:** If yes, generates three files in `.claude/commands/`:
- `claude-orchestrate.md` — delegates to `plan-orchestrator` with a plan path argument
- `claude-orchestrate-resume.md` — resumes from the first `pending` or `in_progress` todo
- `update-claude-orchestrator.md` — re-analyzes the codebase and regenerates agents

---

## Question 7 — ByteRover

**Prompt varies** based on `detect_byterover.py` output:

**If `brv` is detected on PATH:**

> "ByteRover is installed (version: `<version>`). Enable the Recall→Work→Curate→Report memory loop in every generated agent?"

| id | label |
|----|-------|
| `enable` | Yes, enable the memory loop (recommended) |
| `skip` | No, omit the memory loop |

**Default:** `enable`

**If `brv` is NOT detected but skill/context-tree is present:**

> "ByteRover context tree detected at `.brv/` but `brv` CLI is not on PATH. Enable the memory loop? (You'll need to install `brv` before running plans.)"

| id | label |
|----|-------|
| `enable` | Yes, enable loop — I'll install `brv` |
| `skip` | No, omit the memory loop for now |

**If nothing ByteRover-related is detected:**

> "ByteRover is not installed. It's a free local memory layer that gives every sub-agent persistent recall — agents remember patterns across plan runs. Options:"

| id | label |
|----|-------|
| `install` | Install now — `npm install -g byterover-cli` + `brv providers connect byterover` |
| `skip` | Skip — omit the memory loop entirely |

**Default:** `skip` (when not installed)

**Writes to:** `answers.byterover_enabled` (bool)

**Install now flow:**
1. Tell the user to run `! npm install -g byterover-cli && brv providers connect byterover && brv status`.
2. Wait for user confirmation that `brv status` shows connected.
3. Re-run `detect_byterover.py` to confirm.
4. If confirmed, set `byterover_enabled: true`. If not, set `false` with a note to run `/update-claude-orchestrator` once installed.

**Effect when `false`:** Generated agents have **no** ByteRover loop section — not a commented-out block, not a placeholder. A later `/update-claude-orchestrator` run detects `brv` and offers to regenerate with the loop.

---

## Question 7.5 — Hooks to install

**Prompt varies** based on whether `byterover_enabled` is true after Q7.

**When ByteRover enabled:**

> "Which hooks should I install? They run automatically in the background during agent sessions."

**Options (multiSelect):**

| id | label |
|----|-------|
| `taskids` | Collect ByteRover taskIds (SubagentStop) — captures `Pending review: <taskId>` from sub-agent final messages into `.claude/orchestrator-taskids.txt` |
| `pending` | Surface pending reviews on session end (Stop) — prints `brv review approve/reject` commands when the session ends; clears the file |
| `tests` | Run scoped tests after file writes (PostToolUse) — runs your test suite narrowed to the changed file after every Write/Edit |

**Default:** all three

**When ByteRover NOT enabled:**

> "Should I install the scoped test-runner hook? It runs your test suite narrowed to the changed file after every Write/Edit."

**Options:**

| id | label |
|----|-------|
| `tests` | Yes, run scoped tests after file writes |
| `none` | No, skip hooks |

**Default:** `tests`

Note: selecting `none` sets `answers["hooks"] = []`. The `taskids` and `pending` options are not offered when ByteRover is disabled; if somehow included, they are silently dropped before generation.

**Writes to:** `answers.hooks` — `list[str]`, subset of `["taskids", "pending", "tests"]`. Default `[]`.

**Effect:** Writes Python hook scripts to `<scope>/.claude/hooks/` and registers them in `<scope>/.claude/settings.local.json`. Tracked in the marker under `hooks_installed` and `hooks_settings` for idempotent re-runs and clean removal.

---

## Q8 — Roster confirmation

After collecting Q1–Q7, run `analyze_codebase.py`, compose the roster from the snapshot + `AGENT_PATTERNS.md`, then present Q8:

**Prompt:** "Here's the proposed agent roster based on codebase analysis:"

Present each proposed agent as a list:
- Name, model, scope_hint, one-line purpose
- Flag any name conflicts with existing `.claude/agents/*.md`

**Options:**

| id | label |
|----|-------|
| `accept` | Accept all — generate as proposed (recommended) |
| `edit` | I want to make changes — describe them |
| `baseline` | Baseline only — skip project-specific agents |

**Default:** `accept`

**No Writes to answers** — roster is passed separately as `--project-agents` to `setup.py`.

---

## Final answers payload

```json
{
  "scope": "project",
  "tiers": ["haiku", "sonnet", "inherit"],
  "default_tier": "sonnet",
  "verifier": true,
  "memory_curator": true,
  "commands": true,
  "byterover_enabled": true,
  "hooks": ["taskids", "pending", "tests"]
}
```

## Invocation

After all answers and Q8 roster confirmation:

```bash
python <skill-path>/scripts/setup.py \
  --answers '<answers-json>' \
  --project-agents '<roster-json-array>' \
  --byterover-info '<detect-byterover-json>' \
  --codebase-snapshot '<analyze-json>'
```

Where `<skill-path>` is the install location of this skill (`.claude/skills/claude-orchestrator/` in the target repo, or `~/.claude/skills/claude-orchestrator/` for user-wide installs). The script validates the payload, renders templates, writes files, and prints a JSON report with `next_steps` to relay to the user.

## Re-running the interview

Users can re-answer all 7 questions and re-compose the roster by running:

```
/update-claude-orchestrator --reconfigure
```

This re-opens the interview, re-analyzes the codebase, proposes a fresh roster, then regenerates files (SHA-protected — user-edited files are preserved).
