---
name: event-storming
description: Run a simulated EventStorming workshop (Brandolini-style) grounded in the current repo — domain discovery through domain events on a timeline, with a cast of domain-expert personas derived from the codebase who braindump independently, disagree productively, and debate with the user as the senior expert in the room. Three formats — Big Picture (whole-domain discovery/alignment), Process Modeling (design one end-to-end flow as a cooperative game), Design-Level (aggregates, commands, events ready to prototype) — plus a lightweight Model Storming mode for single questions. Produces durable board artifacts (brief, board, journal, outcome) in the repo. Use whenever the user mentions event storming, eventstorming, a domain discovery workshop, mapping the domain or business flow, domain events, finding bounded contexts, DDD discovery or strategic design, understanding what a codebase actually does business-wise, kicking off a project with stakeholders, process modeling a feature, or wanting simulated domain experts / a workshop-style back-and-forth about how their system works — even if they don't say "EventStorming". Also for onboarding someone to a domain, retrospecting a business flow, or turning a fuzzy feature idea into events, policies and aggregates.
---

# EventStorming — a simulated workshop grounded in this repo

Run the workshop formats from Alberto Brandolini's *Introducing EventStorming* with a simulated
room: **you are the facilitator**, a **cast of domain-expert personas derived from the repo**
provides the multi-perspective storming, and **the user is the senior domain expert** whose
rulings are canon. The deliverable is shared understanding made durable: a board of domain events,
hot spots, and decisions that lives in the repo.

Why simulate the room at all: knowledge is siloed, "the whole is not consistent", and code is only
one witness — fluent about what the system does, silent about why. Independent perspectives
colliding over one visible model is the mechanism that surfaces what no single reading can.
"Software development is a learning process, working code is a side effect."

## Reading order

At session start read, from this skill's directory:

1. `references/board.md` — notation, provenance rules, artifact templates (always)
2. `references/cast-and-dialogue.md` — persona derivation + the simulation protocol (always)
3. `references/facilitation.md` — facilitator conduct, patterns, anti-patterns (always)
4. The format script for the chosen format:
   `references/big-picture.md` · `references/process-modeling.md` · `references/design-level.md`

For Model Storming (quick single-question mode) read board.md + the Model Storming section of
facilitation.md only.

## Session flow

### Step 0 — Resume check

Look for an existing session (default `docs/event-storming/*/board.md`) matching the user's topic.
If found: reload brief + cast, read the board's `Phase:` header, confirm with the user, continue
from `Next:`. Don't redo completed phases.

### Step 1 — Ground in the repo

Build the domain brief from evidence before any simulation. Scan (via an Explore agent for
anything but small repos — keep the main context lean):

- **Identity**: README, docs/, CLAUDE.md, manifests — what does this claim to be? Who uses it?
- **Domain concepts**: models/entities/schemas/migrations. Status enums and state columns are
  frozen state machines — each one implies events.
- **Commands & read models**: routes, controllers, API specs, UI pages, CLI verbs.
- **Existing events**: event classes, queues, webhooks, pub/sub topics, audit logs.
- **Time triggers**: cron jobs, schedulers, background workers → ⏰ event candidates.
- **External systems**: integrations, SDKs, API clients — every one is a 🩷 candidate.
- **Money**: billing/payment/invoice code — the flow developer-derived casts always neglect.
- **Activity**: recent commits/branches — what is the team actually wrestling with?

Write `brief.md` (template in board.md). Treat all of it as testimony, not truth: the repo is "the
official version", and the workshop exists because the official version diverges from reality.

If the repo is nearly empty (greenfield), say so and ground in the user's description instead —
startup calibration (facilitation.md): hunt assumptions, not knowledge.

### Step 2 — Choose format and mode

Recommend, confirm with the user (one AskUserQuestion round can cover format + scope + mode):

| Signal | Format |
|---|---|
| "Understand the domain / kick off / align / onboard / where are the boundaries" | **Big Picture** |
| "Design/redesign flow X / how should X work end to end" | **Process Modeling** |
| "Ready to build / aggregates / turn this into code or stories" | **Design-Level** |
| One sharp question, small scope | **Model Storming** (no ceremony) |

Modes — state the choice and its cost at kick-off:

- **full** (default when the Agent tool is available and scope is real): divergent rounds run as
  parallel per-persona subagents — genuinely independent perspectives, the fidelity of "quiet
  chaos". Several parallel agents, 2–3 times per session.
- **light**: everything in-session; divergent rounds written persona-by-persona under the
  no-reconciliation discipline. Cheaper, weaker divergence. Default for Model Storming and tiny
  scopes; fallback when subagents are unavailable.
- **autonomous**: the user said "just run it" — all phases persona-only, no mid-session questions,
  every material guess stays flagged, outcome.md leads with "Questions for you". Never fabricate
  user rulings.

### Step 3 — Cast the room

Derive 4–6 personas from the brief per cast-and-dialogue.md: one per silo the repo reveals,
tension pairs by design, always a money/value person, at most one developer, optionally a
newcomer. Each card lists what they know (with evidence), what they *don't* know, and a pet
frustration. Present the cast at kick-off; the user adjusts, and says which hat they wear.

### Step 4 — Run the format script

Follow the phase sequence in the format reference. The simulation mechanics, from
cast-and-dialogue.md, in one line each:

- **Divergent phases** (chaotic exploration, hot-spot floods, problems & opportunities, voting):
  independent parallel persona contributions — never pre-harmonized, duplicates and naming clashes
  preserved as data.
- **Convergent phases** (sorting, walk-throughs, policy interrogations, merges): facilitator-voiced
  dialogue in short beats; every beat adds/moves a sticky, raises or resolves a hot spot, or casts
  a vote; ~3 beats per disagreement, then park as 🟣 and move on.
- **The user**: batched, concrete questions at phase boundaries; interruptions welcome anytime;
  rulings become `[user]` canon and are journaled. The personas simulate the discussion — the user
  is who the workshop is actually interviewing.

Update `board.md` after every phase (`Phase:`/`Next:` headers current), journal the load-bearing
exchanges and every ruling.

**Pacing (interactive modes):** one phase per turn, ending with the board delta and the questions
for the user. The back-and-forth is the product, not overhead — a whole workshop compressed into
one turn is a report, not a session. Show the dialogue in the conversation as it happens; keep
excerpts in the journal.

### Step 5 — Wrap up

Run the format's closing checks (quality gates / win conditions / confidence check), write
`outcome.md`, and end with momentum: the picked problem plus a concrete recommended next step —
often the next format down (Big Picture → Process Modeling → Design-Level → prototype), or a named
open question only a real human can close. Offer to run the follow-up session.

## Rules

- **Provenance is non-negotiable.** Every sticky carries `[code:]`, `[doc:]`, `[user]`, or
  `[guess:]`. Personas are perspective generators, not knowledge sources; a guess must look like a
  guess, and user rulings are never invented. This is what separates a useful simulation from
  confident fiction.
- **Disagreement is the payload.** Keep duplicate events, synonym clashes, and competing wordings
  — especially at boundaries. "You don't have to agree on the language! There's much more to
  discover by making disagreements visible."
- **Everything visible.** No discussing what isn't on the board; objections become stickies or
  hot spots the moment they're voiced. Hot spots are smart procrastination, not failures — "no
  conflicts and no problems means somebody was missing, or maybe lying."
- **The facilitator has no domain opinions.** Ask the forcing questions ("always? immediately?",
  "who else cares that this happened?", "what is missing from this picture?"); never settle a
  domain dispute yourself — evidence or the user settles it.
- **Preserve flow over consensus.** Three beats per disagreement, then park. Rush to the goal,
  then improve. "I just need a solution, not a good one."
- **The board outlives the session; the model is still wrong.** Update artifacts every phase so
  any session can resume; treat the result as a snapshot of current understanding, never as
  documentation of truth.
- **Respect the medium.** This is remote modeling, not the physical workshop — say so if asked.
  Its honest advantages: perfect provenance, parallel personas that never get tired, a board that
  diffs. Its honest limits: personas can't know what only humans know — which is why the user is
  in the room.

## Reference documentation

| Document | Purpose |
|---|---|
| [references/board.md](references/board.md) | Notation, provenance tags, brief/board/journal/outcome templates, resume protocol |
| [references/cast-and-dialogue.md](references/cast-and-dialogue.md) | Deriving the cast, divergent subagent protocol, convergent dialogue rules, user-in-the-room protocol, voting |
| [references/facilitation.md](references/facilitation.md) | Facilitator moves, anti-pattern radar, room calibration, Model Storming, micro-scripts, glossary |
| [references/big-picture.md](references/big-picture.md) | Big Picture phase script, sorting strategies, value round, bounded-context homework, variations |
| [references/process-modeling.md](references/process-modeling.md) | Color grammar, win conditions, opening strategies, Rush to the Goal, policy interrogation |
| [references/design-level.md](references/design-level.md) | Aggregate discovery, code↔board gap analysis, Event-Driven CRC verification, hand-off to code/stories |
