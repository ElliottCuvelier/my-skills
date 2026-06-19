# First-Use Setup Interview

Full reference for the questions `ct-o10r` asks on first use. Conduct via `AskUserQuestion` — not stdin.

Questions are asked in sequence. After collection, run `scripts/analyze_codebase.py`, compose the teammate-role roster, run `scripts/detect_byterover.py`, show Q8 (roster confirmation), then call `scripts/setup.py --answers <json>`.

---

## Step 0 — Enable agent teams (notice, not a question)

Before the interview, check whether agent teams are enabled: is `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` set to `1` (shell env or `settings.json` `env`)?

- **If not set:** tell the user this skill requires it, and offer to add it:
  ```json
  // settings.json
  { "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }
  ```
  The flag is read at **startup**, so they must **restart Claude Code** after adding it. Setup can still install the roles/commands now — the flag only matters when running `/ct-orchestrate`. (The `update-config` skill can write the env var if asked.)

---

## Question 1 — Scope

**Prompt:** "Where should ct-o10r's teammate roles and commands live?"

| id | label |
|----|-------|
| `project` | This project only (`.claude/agents/`, `.claude/commands/`) |
| `user` | All my projects (`~/.claude/agents/`, `~/.claude/commands/`) |
| `both` | Both — project overrides user-wide when they overlap |

**Default:** `project` · **Writes to:** `answers.scope`

---

## Question 2 — Teammate-role model tiers

**Prompt:** "Which model tiers should I install as teammate-role baselines? Each becomes an `impl-<tier>` role the lead can spawn a teammate from. Add more later via `/update-ct-orchestrator --reconfigure`."

**Allow multiple:** yes

| id | label |
|----|-------|
| `haiku` | Claude Haiku — cheapest, fastest; bulk changes, simple refactors |
| `sonnet` | Claude Sonnet — balanced; default for most lanes |
| `opus` | Claude Opus — premium; complex logic, one hard lane |
| `inherit` | Inherit — same model as the lead |

**Default:** `haiku`, `sonnet`, `inherit` · **Writes to:** `answers.tiers`

---

## Question 3 — Default teammate model

**Prompt:** "Which model should teammates default to when a plan doesn't specify one? (Anthropic recommends Sonnet for team coordination.)"

**Options:** filtered to Q2 choices. **Default:** `sonnet` (if selected), else the first selected tier. **Writes to:** `answers.default_tier` (stored as the marker's default teammate model).

---

## Question 4 — Verification: reviewer teammate role

**Prompt:** "Completed tasks can be gated on scoped tests by the `TaskCompleted` hook (no extra teammate). Should I also install a read-only **reviewer teammate** role for semantic review when a plan asks for it?"

| id | label |
|----|-------|
| `yes` | Install the reviewer teammate role (used when a plan sets `team.verify: review`) — recommended |
| `no` | No reviewer role — rely on the test gate only |

**Default:** `yes` · **Writes to:** `answers.verifier` (bool — whether `verifier.md` is generated)

The test gate itself is installed via the `tests` hook (Q7.5), independent of this. The per-plan `team.verify` field (`hook` | `review` | `none`) chooses the strategy at run time.

---

## Question 5 — Memory curator

**Prompt:** "Install a memory-curator teammate? It's spawned once at the end of a run (its task depends on all others) to consolidate learnings into `.brv/context-tree/`. Recommended when ByteRover is enabled."

| id | label |
|----|-------|
| `yes` | Yes, install memory-curator (recommended if ByteRover enabled) |
| `no` | No, skip |

**Default:** `yes` if ByteRover is detected or installing, else `no` · **Writes to:** `answers.memory_curator`

---

## Question 6 — Slash commands

**Prompt:** "Install `/ct-orchestrate`, `/ct-orchestrate-resume`, and `/update-ct-orchestrator`? (Thin wrappers that point the lead at the team playbook.)"

| id | label |
|----|-------|
| `yes` | Yes, install all three (recommended) |
| `no` | No — I'll trigger orchestration in-session ("run this plan as a team") |

**Default:** `yes` · **Writes to:** `answers.commands`

If no: orchestration still works — ask in-session to run/resume a plan as a team and the lead follows `references/TEAM_ORCHESTRATION.md`.

---

## Question 7 — ByteRover

**Prompt varies** by `detect_byterover.py` output:

**If `brv` is detected on PATH:**
> "ByteRover is installed (version `<version>`). Enable the Recall→Work→Curate→Report memory loop in every teammate role?"

| id | label | default |
|----|-------|---------|
| `enable` | Yes, enable the memory loop (recommended) | ✓ |
| `skip` | No, omit the memory loop | |

**If a context tree is present but `brv` is not on PATH:**
> "ByteRover context tree detected at `.brv/` but `brv` CLI is not on PATH. Enable the loop? (You'll need `brv` before running plans.)" — `enable` / `skip`.

**If nothing ByteRover-related is detected:**
> "ByteRover is a free local memory layer that gives every teammate persistent recall across runs." — `install` (`npm install -g byterover-cli` + `brv providers connect byterover`) / `skip` (default `skip`).

**Writes to:** `answers.byterover_enabled` (bool). When `false`, teammate roles have **no** ByteRover loop section — a later `/update-ct-orchestrator` detects `brv` and offers to regenerate with the loop.

**Install-now flow:** have the user run `! npm install -g byterover-cli && brv providers connect byterover && brv status`; wait for confirmation; re-run `detect_byterover.py`; set `byterover_enabled` accordingly.

---

## Question 7.5 — Hooks

**Prompt varies** by whether `byterover_enabled` is true after Q7.

**When ByteRover enabled (multiSelect):**

| id | label |
|----|-------|
| `tests` | Test gate (`TaskCompleted` + `TaskCreated` sidecar) — runs scoped tests when a task is marked complete; blocks completion (exit 2) on failure and sends the output back to the teammate to fix |
| `taskids` | ByteRover taskId backstop (`TeammateIdle`) — scrapes idle teammates' transcripts for `Pending review:` ids into a backstop file the lead merges into its final report |

**Default:** both.

**When ByteRover NOT enabled:** single choice — `tests` or `none`. **Default:** `tests`. (`taskids` is ByteRover-specific and not offered; if somehow included it's dropped before generation.)

**Writes to:** `answers.hooks` — subset of `["taskids", "tests"]` (default `[]`).

Notes:
- `tests` installs **two** scripts under one selection: the `TaskCreated` files-sidecar writer + the `TaskCompleted` test gate.
- There is **no** teammate `Stop` hook — the lead's final report is the surface for pending ByteRover reviews.

---

## Q8 — Roster confirmation

After Q1–Q7, run `analyze_codebase.py`, compose the teammate-role roster from the snapshot + `AGENT_PATTERNS.md`, then present Q8:

**Prompt:** "Here's the proposed teammate-role roster based on codebase analysis:"

Show each proposed role: name, model, scope_hint, one-line purpose; flag any name conflicts with existing `.claude/agents/*.md`.

| id | label |
|----|-------|
| `accept` | Accept all — generate as proposed (recommended) |
| `edit` | I want changes — describe them |
| `baseline` | Baseline only — skip project roles |

**Default:** `accept` — roster is passed separately as `--project-agents` to `setup.py`.

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
  "hooks": ["taskids", "tests"]
}
```

## Invocation

```bash
python <skill-path>/scripts/setup.py \
  --answers '<answers-json>' \
  --project-agents '<roster-json-array>' \
  --byterover-info '<detect-byterover-json>' \
  --codebase-snapshot '<analyze-json>'
```

Where `<skill-path>` is `.claude/skills/ct-o10r/` in the target repo, or `~/.claude/skills/ct-o10r/` for user-wide installs.

## Re-running the interview

`/update-ct-orchestrator --reconfigure` re-opens the interview, re-analyzes the codebase, proposes a fresh roster, then regenerates files (SHA-protected — user-edited files are preserved).
