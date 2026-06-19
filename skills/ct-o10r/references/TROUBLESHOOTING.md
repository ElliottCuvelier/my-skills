# Troubleshooting

Common issues, their root causes, and how to fix them.

---

## Agent teams aren't forming

**Symptom:** `/ct-orchestrate` behaves like a normal session — no teammates, no task list.

**Cause:** `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` isn't `1`, or it was set without restarting (read at startup).

**Fix:** Add it to `settings.json` `env` and **restart**:
```json
{ "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }
```
Verify with `! printenv CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`. Never fake a team with one-shot sub-agents — if you can't enable teams, use `claude-orchestrator` instead.

---

## Resume doesn't restore teammates

**Symptom:** After `/resume` or `/ct-orchestrate-resume`, the lead messages teammates that no longer exist, or dependents never start.

**Cause:** `/resume` restores the lead but **not** in-process teammates. The native task list persists (same `<team-name>`), but a task a dead teammate left `in_progress` is orphaned and blocks its dependents forever.

**Fix:** Follow TEAM_ORCHESTRATION Step 0R: read the task list as truth, **reset orphaned `in_progress` tasks to pending**, respawn the needed teammates, and re-assign the open tasks. Ignore the plan's old todo state.

---

## Two teammates corrupted the same file

**Symptom:** Edits clobber each other; a file ends up with half of each change.

**Cause:** Native file-locking serializes only task-**claim** races — it does **not** lock source files. Two tasks touching the same file, owned by two teammates, write concurrently.

**Fix:** Enforce file-disjoint lanes. Each file belongs to exactly one lane/teammate; assign every task to its lane's owner (don't leave tasks open for self-claim). If two todos must touch the same files, put them in the **same** lane or serialize them with `depends_on`. See PLAN_FORMAT `files:` and TEAM_ORCHESTRATION Step 4.

---

## A task is stuck (status lag)

**Symptom:** A teammate finished the work but the task stays `in_progress`, so its dependents never unblock.

**Cause:** Teammates sometimes fail to mark a task complete (a known agent-teams limitation). The `TaskCompleted` gate can't help — it fires only on completion *attempts*.

**Fix:** As lead, watch for idle-with-open-task (the `TeammateIdle` signal) or a stale `in_progress`. Message the teammate to mark it complete, or reopen/reassign so dependents proceed.

---

## The TaskCompleted gate keeps bouncing a task

**Symptom:** A task flips back to `in_progress` repeatedly with test-failure feedback.

**Cause:** The scoped tests for the task's files keep failing — the gate (exit 2) is working, but the teammate can't pass.

**Fix:** After `team.max_bounces` (default 2), the lead escalates: reassign to a higher-tier teammate, or take the failing test offline (fix it, or set the lane's `verify: none` if the test itself is wrong). If the gate fires on the wrong files, check the task description's `Files: [...]` line (the `TaskCreated` sidecar reads it).

---

## Permission prompt storm when spawning

**Symptom:** Every teammate blocks on the same permission (edit, run tests, git, brv).

**Cause:** Teammates inherit the lead's permission mode **at spawn**, fixed thereafter. Unapproved common operations prompt per teammate.

**Fix:** Before spawning (Step 3), allow-list the test runner, `git`, `brv`, and edits (or pick a permission mode up front). The `fewer-permission-prompts` skill can help build the allowlist.

---

## A teammate is slow to shut down or refuses

**Cause:** Teammates finish their current request / tool call before shutting down; one mid-write may reject with an explanation.

**Fix:** Ask all teammates to shut down roughly in parallel; surface any refusal + reason. Don't block the final report — team dirs auto-clean on session exit regardless.

---

## The run cost much more than expected

**Cause:** Expected — agent teams cost ~7× a single session (each teammate is a full instance with its own context window).

**Fix:** Keep teams to 3–5; default to a cheap `default_teammate_model` and reserve `opus` for one hard lane; shut idle teammates down; don't over-split lanes. If the work is sequential or single-file, use `claude-orchestrator` or a single session instead.

---

## Plan `team:` block missing

**Symptom:** `/ct-orchestrate <plan>` stops and asks how to run the plan.

**Fix:** Add a `team:` block. Minimum:
```yaml
team:
  default_teammate_model: sonnet
```
See [PLAN_FORMAT.md](PLAN_FORMAT.md).

---

## Pending ByteRover reviews didn't surface

**Cause:** The lead surfaces taskIds from two channels: teammates' `BRV-REVIEW` mailbox messages (primary) and the `TeammateIdle` backstop file. If teammates didn't message and the `taskids` hook isn't installed, nothing is collected.

**Fix:** Ensure teammate roles include the ByteRover loop and the "message the lead `BRV-REVIEW <taskId>`" instruction (regenerate if a role was edited). Install the `taskids` hook (Q7.5) as a backstop — it writes `~/.claude/ct-o10r/<team-name>/brv-pending.txt`.

---

## ByteRover loop not firing in a teammate

**Symptom:** A teammate's output has no `## Memory` section, or it skips `brv search`.

**Fix:**
1. Check the role file contains `<!-- BEGIN BYTEROVER LOOP -->`. If missing, `byterover_enabled` was `false` at generation — `/update-ct-orchestrator` to regenerate with the loop.
2. If present but skipped, the spawn prompt should say "follow the ByteRover memory loop — `brv search` first."
3. If `brv` isn't on PATH for teammates, install it and ensure PATH is inherited.

---

## `brv query` called by a teammate (expensive)

**Cause:** Only the **lead** may call `brv query` (an LLM call). Teammates must use `brv search` (free BM25).

**Fix:** Re-check the role's ByteRover loop says "Do NOT call `brv query`." If a role was edited and the line removed, re-add it or regenerate.

---

## `brv` not found after `npm install -g byterover-cli`

**Cause:** The npm global `bin` dir isn't on PATH in the shell Claude Code runs in.

**Fix:** `! npm root -g` → add `<prefix>/bin` to PATH in your shell profile → new terminal (or `source`) → `! brv --version` → `/update-ct-orchestrator`.

---

## User-edited role file preserved on regenerate

**Cause:** The file's SHA doesn't match the marker (`.ct-o10r-installed`) — modified after generation.

**Fix:** To discard edits and regenerate: delete the file, then `/update-ct-orchestrator`. To keep edits: do nothing — the SHA is refreshed on the next regenerate.

---

## Pre-existing agent name conflict

**Cause:** A `.claude/agents/<name>.md` existed before ct-o10r was set up. It's registered in `registered_existing_agents` and never clobbered.

**Options:** keep existing / rename the proposed role / skip it. To let ct-o10r overwrite it, remove its entry from `registered_existing_agents` in `.ct-o10r-installed` and `/update-ct-orchestrator`.

---

## Fingerprint false-positive on `/update-ct-orchestrator`

**Cause:** The fingerprint covers manifest files (`package.json`, `pyproject.toml`, `prisma/schema.prisma`, etc.); version bumps or script changes shift it.

**Fix:** Review the proposed roles; accept if the new signals are real, decline in Q8 otherwise (existing roles are unaffected).

---

## `analyze_codebase.py` slow on a large monorepo

**Fix:** It skips `node_modules/`, `.git/`, `dist/`, `build/`, `.next/`, `target/`, `.venv/`. Add other large generated dirs to `SKIP_DIRS` in the script, or pass `--max-files 50`.
