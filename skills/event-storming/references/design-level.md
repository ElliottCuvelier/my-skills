# Design-Level EventStorming — facilitation script

The implementation format: turn one well-understood process into a **robust candidate software
design** — commands, events, aggregates, policies, read models — ready to prototype. Prerequisites:
a clear focus (a specific process/feature, typically imported from a Process Modeling board or a
Big Picture hot spot) and a developer-heavy cast: the dev team plus only the domain experts
relevant to this scope (often just the user plus 2–3 personas).

What changes from the other formats:

- **The outcome is different.** Big Picture optimizes learning and can run out of time gracefully.
  Here "the workshop isn't over until we have something that looks like a robust candidate
  solution" — the stop condition is **confidence in the modeled solution**, not a timebox.
- **Precision becomes mandatory.** Event wording is strict; expect to "rewrite stickies like
  there's no tomorrow." That churn is the cheap part: "once released in production, Domain Events
  have a very annoying cost of update, due to their high number of potential listeners" —
  anticipate the mess while the model is still only paper.
- **The repo is now first-class.** This is the format where board and codebase must meet: existing
  entities, handlers, tables, queues and event classes are evidence, constraint, and gap-analysis
  target all at once.

## Grammar extension: the Aggregate

A new sticky: **🟨 Aggregate** (the book's big pale-yellow) — the decision-maker between a command
and its events:

```
🟡 Person → 🔵 Command → 🟨 Aggregate → 🟠 Event(s) → 🟪 Policy → 🔵 Command → …
                                       → 🟢 Read Model (what someone sees next)
```

An aggregate is a **unit of consistent behavior**: it receives commands, enforces invariants,
decides, and emits events. "Little state machines." Keep them small — "I am not expecting
consistency to scale much."

## Phase sequence

### 1. Import and re-frame

Load the process flow (or the scoped slice of the big picture). Re-state the problem and the
outcomes. Note that digging deeper makes the old board obsolete — that's the point: "the big
picture was a model of our current level of understanding."

### 2. Strict-grammar pass

Walk the flow enforcing full grammar. For every gap, probe with the four event sources (user
action, external system, time, reaction to another event). For every event, probe consequences:
symmetry hunting (`Seat Reserved` → where's `Reservation Cancelled`?), "what happens when this
fails?", time-outs. Rewrite wordings freely; log renames of load-bearing terms in the glossary.

Where the repo has corresponding code, annotate: `🟠 Order Placed [code: src/orders/events.ts]`.
Three findings matter, and each gets a 🟣 or a board correction:

- board event with **no code counterpart** → new build, or the code models it implicitly (where?)
- code event/handler with **no board counterpart** → the model missed real behavior — add it
- **name mismatch** (board says `Payment Received`, code says `invoice.paid`) → glossary entry;
  decide which language wins before it ships twice

### 3. Discover aggregates (name LAST)

Cluster commands with the events they produce. For each cluster the discipline is anti-naming —
"the habit of naming things is really too strong. Try the other way round":

1. **Responsibilities first**: what is this thing responsible for? What does the system expect
   of it?
2. **Invariant**: what must always be true for that decision? ("The cart subtotal is always the
   sum of quantity × unit price.")
3. **Information**: the minimal data needed to enforce that invariant — that's the state.
4. **Name it now**: "how would I call a class with this information and purpose?"

The trap to spring deliberately (it's the most instructive moment of the format): someone proposes
an aggregate holding whatever the screen shows. "'Data to be displayed to a user in order to make
a decision' will be a Read Model." Aggregates hold what the *decision* needs, not what the *user
sees* — superimposing the screen onto the model is the vicious temptation. A persona should walk
into this trap so the facilitator can dismantle it (the book's own detour: `ShoppingCart` is
associated with a `WebSession`, not a `Customer` — login can happen at checkout).

Regrouping by aggregate **breaks the timeline**. Expected: "the two groupings are orthogonal; we
can't have both." Keep the process flow section intact and add an `## Aggregates` section to the
board, one block per aggregate: responsibility, invariants, state, commands accepted, events
emitted, plus `[code:]` mapping to existing classes/tables if any.

### 4. Fan-out pass

For every significant event ask: **"who else cares that this happened?"** List consumers
(policies, read models, other contexts). "During EventStorming exploration, I prefer listening to
the needs of the downstream domains" — name and shape events for their consumers, not the
producer's convenience. High fan-out events are the ones whose names you must get right now.

### 5. Verify by role-play (Event-Driven CRC)

The strongest verification move, and a natural fit for personas: assign each a component role —
this persona *is* the `Billing` aggregate, that one *is* the `Order Status` read model, another is
the human user. Replay the scenario end to end, passing commands and events as messages, under one
rule: **"humans can't ask, only tell."**

A decision-maker may only act on information already delivered to it by prior events or its own
state. The moment a role needs data it never received, the design has a bug — route the missing
information via an event or read model, then replay. Run the happy path, then the nastiest
alternative paths from the hot-spot list. Gaps found here are design changes that would otherwise
have been production incidents.

### 6. Close: confidence check and hand-off

Ask cast and user: would you build this? Remaining doubts are 🟣 → either resolve or explicitly
accept as risks in outcome.md. Then hand off in whichever shape fits the repo:

- **Straight to prototype** (the book's default): "the roll is not the deliverable, it's just a way
  to get to the right implementation faster… There's nothing better than a good prototype to
  discover flaws in our reasoning." Scaffold the aggregates/events/handlers in the repo's idiom —
  match its structure and naming conventions, don't import book jargon into a codebase that
  doesn't speak DDD.
- **User stories**: one per command or policy, acceptance criteria binary by construction —
  *given* the preconditions, *when* the command/trigger, *then* these events are emitted and these
  read models updated. (UI polish criteria are qualitative — keep them separate.)
- **ADR / design doc**: aggregates, invariants, event contracts, the rejected alternatives with
  why (the board already has them — Religion Wars resolved by modeling both leave a record).

## Facilitator conduct specific to this format

- This is a **converging** session among technical egos — "a design session involving software
  architects and senior developers can easily turn into a bloodbath." The rule that keeps it
  civil: **"you won't agree on a solution before modeling it."** Competing designs are both
  modeled (cheaply, via one subagent per alternative), then compared visibly. Choose later.
- **Hide unnecessary complexity** at the end: the solution will look more sophisticated than the
  original understanding; check the user-facing surface stays simple even when internals aren't.
- Naive 1:1 command→event symmetry breaks down — one command can yield several events, events
  arrive with no command (time, external systems). Don't force pairs.
- Don't gate on ceremony: if confidence is reached early, stop modeling and go build.
