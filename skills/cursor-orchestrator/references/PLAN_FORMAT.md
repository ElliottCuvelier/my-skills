# Plan File Format

The `cursor-orchestrator` skill adds an `execution:` block to a plan's YAML frontmatter so `/orchestrate` knows how to dispatch the plan's steps.

## Full frontmatter schema

```yaml
---
name: <string> # Plan name (existing Plan Mode field)
overview: <string> # Short description (existing)
todos: # Existing Plan Mode todos list
  - id: <string> # Unique todo id
    content: <string> # Step description
    status: pending | in_progress | completed | cancelled | failed
    # Optional fields the orchestrator understands:
    depends_on: [<todo-id>, ...] # Ids this step depends on (for parallelism)
    files: [<path>, ...] # Files this step will touch (for parallel safety)
isProject: <bool> # Existing

execution: # Added by the cursor-orchestrator skill
  implementation_model: <tier> # One of: composer, fast, mini, haiku, premium
  parallelism: sequential | parallel # Default: sequential
  verify_each_step: <bool> # Whether to invoke /verifier between steps
  # Optional:
  max_retries_per_step: <int> # Default: 0 (fail fast)
  stop_on_first_failure: <bool> # Default: true
---
```

## The `execution` block

### `implementation_model` (required)

One of the tier names declared in the marker's `tiers` list. If the tier isn't installed in the target project, `/orchestrate` errors with a clear message and lists installed tiers.

Valid values:

- `composer` — Cursor's agentic coding model (Composer 2 at time of writing)
- `fast` — Cursor fast tier keyword
- `mini` — cheapest OpenAI mini/nano
- `haiku` — cheapest Anthropic Haiku
- `premium` — inherit from orchestrator (escape hatch)

### `parallelism`

- `sequential` (default) — steps run one at a time, in the order they appear in `todos`. Safe and predictable.
- `parallel` — the orchestrator can dispatch multiple implementers in a single message when steps are independent. Independence is inferred from:
  - `depends_on` (if present)
  - `files` (if two steps touch overlapping files, they're considered dependent)
  - Fallback: sequential if the orchestrator can't determine independence.

### `verify_each_step`

If `true` and the verifier sub-agent is installed, the orchestrator invokes `/verifier` after each step with the step description and the implementer's report. The verifier's `INCOMPLETE:` / `CONCERNS:` / `DOWNGRADE:` output is surfaced in the final report.

If the verifier sub-agent wasn't installed at setup time, this field is ignored (the orchestrator logs a warning once and continues).

### `max_retries_per_step` (optional)

How many times to retry a failing step before stopping or moving on. Default `0` (no retry; fail fast). A retry re-dispatches the same implementer with the original step + the previous failure report.

### `stop_on_first_failure` (optional)

- `true` (default) — the orchestrator stops at the first failed step and asks the user what to do (skip / retry / abort).
- `false` — the orchestrator continues past failures and reports them all at the end. Useful for "dry-run what would fail" passes.

## Example plan

```markdown
---
name: widget-crud
overview: Add widget CRUD endpoints and a minimal creation form.
todos:
  - id: schema
    content: Add the widget table migration
    status: pending
    files: [db/migrations/, db/schema.sql]
  - id: api
    content: POST/GET /api/widgets
    status: pending
    depends_on: [schema]
    files: [api/widgets.py, api/routes.py]
  - id: form
    content: Widget creation form at /widgets/new
    status: pending
    depends_on: [api]
    files: [web/widgets/new.tsx]
  - id: tests
    content: Integration tests covering create + list
    status: pending
    depends_on: [api, form]
    files: [tests/widgets_test.py]
execution:
  implementation_model: composer
  parallelism: sequential
  verify_each_step: true
---

# Widget CRUD

Minimal CRUD for widgets, dispatched to Composer 2.
```

## How the orchestrator reads it

1. Parse frontmatter as YAML.
2. Validate `execution.implementation_model` against installed tiers (marker file).
3. Map to sub-agent name: `composer` → `/impl-composer`, etc.
4. Build execution graph:
   - If `parallelism: sequential`, run todos in list order.
   - If `parallelism: parallel`, topologically sort by `depends_on` and `files` overlap; batch independent siblings.
5. For each step:
   - Update `status` from `pending` → `in_progress` in the plan file.
   - Dispatch to the implementer.
   - If `verify_each_step`, invoke `/verifier`.
   - Update `status` → `completed` (or `failed`).
6. Produce a final summary report.

## Omitted execution block

If the plan has no `execution:` block, the orchestrator asks the user which tier to use (listing installed tiers from the marker). It then offers to add the block to the plan file before starting.
