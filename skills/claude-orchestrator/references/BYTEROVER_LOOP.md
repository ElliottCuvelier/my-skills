# ByteRover Memory Loop

This is the canonical **Recall → Work → Curate → Report** fragment that gets inlined
verbatim into every generated sub-agent when ByteRover is enabled.

The inlined version (in `templates/byterover_loop_fragment.md.tmpl`) contains two
template slots that `generate_agents.py` fills at agent-generation time:

| Slot | What it becomes |
|------|----------------|
| `{{AGENT_SCOPE_FLAG}}` | `--scope "<scope>" ` (with trailing space) when the agent has a scope, or empty string when not |
| `{{CURATE_WHEN}}` | Per-agent description of when to curate (e.g., "a new domain invariant is introduced") |

## The four steps

### 1. Recall
```bash
brv search "<task keywords>" {{AGENT_SCOPE_FLAG}}--format json --limit 10
```

If the scoped search returns 0 results, broaden by dropping `--scope`.

**Rule**: Sub-agents use `brv search` only. `brv query` (LLM-synthesized answer) is reserved for
the orchestrator because it costs an LLM call.

### 2. Work
The agent's actual job (per its "When invoked" section).

### 3. Curate
```bash
brv curate "<one-paragraph summary>" -f <up-to-5-relevant-paths>
```

Hygiene rules (apply uniformly across all agents):
- **Blocking** — never `--detach` inside a sub-agent (context dies on return).
- **Max 5 `-f` files**, project-relative paths only.
- **Skip when nothing new** — "skipped — nothing new" beats low-signal curates.
- **Never auto-approve** — return `taskId`s; the orchestrator surfaces them to the user.
- **Non-fatal** — `curate: failed — <reason>` in the report; don't fail the step.

### 4. Report
End every response with a `## Memory` section:
```
## Memory
Recalled: <what search returned, or "no relevant prior context">
Curated: <curate text + logId, "skipped — nothing new", or "curate: failed — <reason>">
Pending review: <taskId, or "none">
```

## Scope namespace convention

See [BYTEROVER_SCOPES.md](BYTEROVER_SCOPES.md) for the full scope tree. Key principle:
**agent scopes are codebase-shaped, not agent-name-shaped.** Curates go into subtrees
that describe what they're about (`architecture/auth/`), not who wrote them
(`agents/impl-haiku/`).

## Source reference

The loop fragment is in `templates/byterover_loop_fragment.md.tmpl`. The wi-be project
at `/Users/elliottcuvelier/Work/development/wip/wi-be/.claude/agents/_byterover-loop.md`
is the original reference implementation.
