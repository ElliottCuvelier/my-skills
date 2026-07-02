# The Board — notation and session artifacts

The board is the workshop's paper roll: a set of markdown files in the target repo. It is the durable
outcome of the session — it must survive context resets, be resumable, be diffable, and stay
hand-editable by the user. Everything the workshop produces lives here; conversation output is
ephemeral commentary on it.

## Where the board lives

Default: `docs/event-storming/<scope-slug>/` in the repo being stormed (create it). If the repo has an
obvious other home for docs (`documentation/`, `notes/`, a wiki dir), or the user names a location,
use that instead. One directory per session scope:

```
docs/event-storming/<scope-slug>/
├── brief.md      # domain brief + cast — written at kick-off, mostly frozen after
├── board.md      # the wall of stickies — the living model, updated every phase
├── journal.md    # dialogue excerpts, user rulings, phase log — append-only
└── outcome.md    # aftermath summary — written at wrap-up
```

Update `board.md` **after every phase**, not at the end. A half-finished board from an interrupted
session is a feature of the format ("Phase:" header says where to resume), not a failure.

## Sticky-note notation

Emoji encode Brandolini's sticky colors. Always pair the emoji with its text form on first use in any
file (`🟠 Event`) — the notation must survive terminals that render emoji poorly.

| Sticky | Meaning | Grammar rule |
|---|---|---|
| 🟠 Event | Domain event — something relevant that happened | Verb at **past tense**: `Order Placed`, `Ticket Transferred` |
| 🔵 Command | Action / intention / user decision | Verb at **present tense**: `Place Order`. Does not imply success |
| 🟡 Person | People / actor / role / persona | Fuzzy on purpose: `Customer`, `Returning Customer`, `Amy from Billing` |
| 🩷 System | External system — "whatever we can put the blame on" | Software, departments, orgs, even `GDPR` or `Bad Luck` |
| 🟪 Policy | Reactive logic between an event and a command | Phrase as `Whenever [event], then [command]` |
| 🟢 Read Model | Information needed to make a decision (process/design level) | Name the data, not the fetch sequence: `Room availability + peak days` |
| 🟢 Opportunity | Improvement idea (big picture, problems round) | Prefix `Opportunity:` to disambiguate from read models |
| 🟣 Hot Spot | Problem, conflict, doubt, rant, unresolved discussion | One line; assign an id `HS-n` so dialogue can reference it |
| 🟨 Aggregate | Unit of consistent behavior: takes commands, enforces invariants, emits events (design level only) | Name it LAST — see design-level.md |
| ⭐ Pivotal Event | One of the 4–5 most significant events — phase boundary | Rendered as a timeline section divider |
| ⏰ | Time trigger annotation on an event | `🟠 Reservation Expired ⏰ 10min timeout`, `🟠 End of Quarter ⏰ recurring` |

Modifiers:

- **Provenance tags** — required on every sticky (see below): `[code: src/orders/checkout.ts]`,
  `[user]`, `[guess: Marco]`, `[doc: README]`.
- **Alternative paths** — indent under the step they branch from, marked `⑂ alt:`. Happy path stays
  on the main line (top position, per the book's convention).
- **Actor/system annotations on events** — append in-line: `🟠 Order Placed — 🟡 Customer via 🩷 Web Shop`.

## Provenance — the honesty rule

In a real workshop every sticky comes from a human expert. Here, most stickies come from simulated
personas whose knowledge is inference from the repo. **Untagged claims are how a simulated workshop
turns into confident fiction**, so every sticky carries where it came from:

- `[code: <path>]` — backed by repo evidence. Cite the actual file (and line if it matters).
- `[doc: <ref>]` — backed by README/docs/comments. Weaker than code: docs lie more often.
- `[user]` — stated or confirmed by the user. **Canon.** Overrides everything else.
- `[guess: <persona>]` — plausible hypothesis, not verified. Guessing is legitimate EventStorming
  (the book encourages it) — but a guess must look like a guess. Guesses that matter and stay
  unconfirmed should also raise a 🟣 Hot Spot.

When the user confirms or corrects a guess, update the tag to `[user]` and log the ruling in
`journal.md`. Never silently upgrade provenance.

## brief.md template

```markdown
# Domain Brief — <scope>
> Repo: <name> · Session: <date> · Format: <big picture | process modeling | design level>

## What this system does
<3–8 sentences, from repo evidence. Cite files.>

## Scope of this session
<The flow/question being stormed, as agreed at kick-off. What's explicitly out.>

## Signals found in the repo
- Domain concepts: <entities/models spotted, with paths>
- Existing events/messages: <if event classes, queues, webhooks exist>
- External integrations: <APIs, services — these become 🩷 candidates>
- Time-driven behavior: <cron jobs, schedulers — ⏰ candidates>
- Money touchpoints: <billing/payment code — the flow developers always neglect>

## The cast
<One block per persona — see cast-and-dialogue.md for the card format.>
```

## board.md template (Big Picture / Process Modeling)

```markdown
# EventStorming Board — <scope>
> Format: <format> · Started: <date> · Phase: <last completed phase> · Next: <next phase>

## Timeline

### <Chapter/phase name>
- 🟠 <Event> [<provenance>] — 🟡 <person> via 🩷 <system>
- 🟠 <Event> [<provenance>]
  - ⑂ alt: 🟠 <alternative outcome> [<provenance>]
  - ⑂ alt (multi-step branches stay one-event-per-line, nested):
    - 🟠 <first event of the branch> [<provenance>]
    - 🟠 <next event of the branch> [<provenance>]
    - ↩ rejoins main flow at <event>  <!-- note, not an arrow chain: arrows live only in Process flows -->

#### ⭐ <Pivotal Event> [<provenance>]

### <Next chapter>
- ...

## Process flows        <!-- process-modeling / design-level sessions -->
### Flow: <name>
🟢 <read model> → 🟡 <person> → 🔵 <command> → 🩷 <system> → 🟠 <event>
→ 🟪 Whenever <event>, then <command> → 🔵 <command> → ...
- 🟣 HS-4: <objection this flow hasn't answered>

## People & Systems
| Who/What | Type | Notes |
|---|---|---|
| <name> | 🟡 / 🩷 | <role in the flow, ownership quirks, sarcasm preserved> |

## Hot Spots
| id | 🟣 What | Raised by | Status |
|---|---|---|---|
| HS-1 | <one-line problem> | <persona/user/facilitator> | open / resolved: <how> / user-ruled: <ruling> |

## Opportunities
- 🟢 Opportunity: <idea> [<who>]

## Votes & Decision
| Target | Votes | Voters |
|---|---|---|
| HS-3 <label> | ●●●● | Marco ×2, Sofia, user |
**Picked problem:** <what won and why it matters>
```

Rendering rules:

- Keep the timeline **one event per line**. Dozens to hundreds of events is normal and good;
  resist summarizing clusters into phase-names ("Registration") — that filters out exactly the
  detail the workshop exists to surface.
- Pivotal events (`⭐`, as `####` dividers) emerge during *Enforce the timeline* — don't pre-impose
  them at exploration time.
- Parallel processes that genuinely run alongside the main flow get their own `###` section with a
  note on where they attach, rather than a swimlane table — markdown tables can't hold a wall.
- Arrow chains are the book's linearized grammar and belong **only** in `## Process flows`
  (blue→pink→orange, orange→lilac→blue). In the Timeline, plain event lines.

## journal.md template

Append-only. Not a transcript — capture only load-bearing moments:

```markdown
# Session Journal — <scope>

## <date time> — Kick-off
Goal as stated: "..." · Cast: <names> · User participating as: <role>

## <phase name>
<2–5 line summary of what changed on the board>

> **Marco (Ops):** "Payout Sent — that's when the batch job fires." [code: jobs/payouts.ts]
> **Priya (Support):** "Sellers call us because 'sent' ≠ 'received'. Bank clearing takes 2 days
> and nothing in the app shows it." [guess: Priya]
→ 🟣 HS-2 raised: seller-visible payout state is a fiction between two events.

### User rulings
- HS-2: confirmed — "biggest support ticket category." → [user], vote candidate.
```

Log **every user ruling** — they are the canon layer that makes the simulation trustworthy.

## outcome.md template

Written at wrap-up. The book's aftermath advice: do NOT transcribe the whole wall into a formal
document nobody reads — capture decisions, open questions, and momentum:

```markdown
# Outcome — <scope>
> Session: <date> · Format: <format> · Full board: ./board.md

## The picked problem
<Arrow-voting winner + one paragraph of why, citing hot spots.>

## What we now know (that we didn't)
<5–10 bullets: discoveries, corrected assumptions, each with provenance.>

## Open questions (unresolved 🟣)
<The hot-spot table rows still open — these are homework for real humans.>

## Candidate bounded contexts        <!-- big-picture sessions -->
<Name → the language/ownership shift that suggests the boundary. Hypotheses, not decisions.>

## Recommended next step
<e.g. "Process Modeling session on <picked problem>" / "Design-Level on <flow>" /
"Ask <real person> about HS-4 before building anything.">

## Not explored
<What the scope excluded or time cut — prevents the board reading as complete coverage.>
```

## Resuming a session

On invocation, before starting anything new, check the board directory for an existing session on a
matching scope: read `board.md`'s `Phase:` header, `journal.md`'s last entries, and continue from
`Next:`. Re-read `brief.md` to reload the cast. Never restart a phase that's already on the board
unless the user asks to redo it.
