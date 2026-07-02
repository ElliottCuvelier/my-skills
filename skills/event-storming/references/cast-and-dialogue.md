# The Cast and the Discussion — simulating the room

EventStorming works because the right people disagree in front of the same wall. The skill recreates
that: a cast of domain-expert personas derived from the repo, a facilitator (you), and the user as
the senior expert in the room. This file defines how to build the cast and how to run the
conversation so it behaves like a workshop, not like theater.

## Why personas, and what they are epistemically

A persona is a **perspective generator**, not a knowledge source. Its knowledge is inference from
repo evidence plus plausible industry experience. That's genuinely useful — code encodes an enormous
amount of business reality, and independent perspectives surface contradictions a single reading
misses — but it is hypothesis, not testimony. Hence the provenance rule (see board.md): personas cite
evidence when they have it and their unbacked claims stay `[guess]` until the user rules.

The realism target is the *dynamics* of a workshop (silos, naming clashes, rants, knowledge
asymmetry), never fake authority.

## Deriving the cast

Build the cast at kick-off from the domain brief. 4–6 personas — enough for cross-silo friction,
few enough that each stays distinct.

Selection rules:

1. **One persona per major silo the repo reveals.** Map business functions to evidence: an
   `invoicing/` module implies someone who lives in billing; a `support`/`admin` panel implies
   someone answering angry emails; integration code implies someone who curses that vendor;
   a warehouse/logistics module implies operations. Pick the silos that cover the session scope.
2. **Engineer tension pairs.** Deliberately include perspectives whose incentives collide:
   revenue vs. compliance, ops throughput vs. customer experience, the maintainer of the legacy
   path vs. the owner of the new one. Discussion quality comes from these fault lines.
3. **Always cast a money/value person** (finance, billing ops, the founder who watches runway).
   The book is blunt: technical explorations systematically neglect the money flow — suppliers
   unpaid, invoices unsent. This persona exists to keep asking "who pays, when, and who notices
   if they don't?"
4. **Consider a newcomer.** Someone recently hired who asks naive questions. The book notes
   first-timers often contribute the most: they're allowed to question what everyone else treats
   as obvious.
5. **Domain-expert majority.** Most of the cast are business-side people. At most one developer
   persona — the workshop exists to get *out* of the codebase's own account of itself.
6. **Present the cast to the user at kick-off and adjust.** The user knows who the real
   stakeholders are; renaming personas after real roles ("this is basically our Kathrin") makes
   later rulings sharper. Cast changes are cheap before exploration, expensive after.

### Persona card format (goes in brief.md)

```markdown
### <Name> — <role>
- Silo: <business area they own · maps to <code area>>
- Knows: <3–5 concrete things, cite repo evidence where it exists>
- Doesn't know / wrongly assumes: <1–3 gaps — these create the discussion>
- Cares about: <goal + one pet frustration — fuel for rants and hot spots>
- Voice: <one line — e.g. "precise, impatient, speaks in ticket numbers">
```

The **"Doesn't know / wrongly assumes"** line is what makes the simulation honest and interesting:
knowledge asymmetry is the entire reason the workshop format exists ("the sum of separate
expertises is not the expertise of the whole"). Give each persona a real gap that another persona's
silo covers.

## Two interaction modes

### Divergent rounds → parallel independent subagents (full mode)

The book's chaotic exploration is *quiet chaos*: everyone writes stickies simultaneously,
independently, without agreeing on wording — the facilitator explicitly breaks up committees that
try to align before writing. Parallel subagents reproduce this faithfully: **one agent per persona,
launched in the same message, none seeing the others' output.** Their collisions and contradictions
are the raw material for every later phase — never pre-harmonize them.

Use for: chaotic exploration, the problems-and-opportunities round, arrow voting, and (design-level)
independent aggregate sketches.

Subagent prompt skeleton (fill from brief.md):

```
You are <Name>, <role>, in an EventStorming workshop for <scope>.
[paste their full persona card]
Cast in the room (so you know who else exists): <names + roles only>.
Domain brief: [paste brief.md's "What this system does" + scope + relevant signals]

Write the domain events YOU know about, from your silo only.
Rules:
- Orange sticky = one line, VERB AT PAST TENSE ("Order Placed", not "Place order" or "Ordering").
- 10–25 events, in the order they happen from where you sit (local order matters, global order is
  not your job).
- Use YOUR vocabulary for your work — do not try to guess what others would call it.
- Stay in your lane: do not cover areas outside your silo; gaps are expected and wanted.
- Guessing is legitimate: mark each event [code: <path>] if you can point at repo evidence,
  [doc: <ref>] for docs, [guess] otherwise. Do not fake evidence.
- Add 1–3 rants: things about this flow that make your job miserable (one line each) — and name
  the system or handoff you blame.
Return exactly:
EVENTS: (numbered list with tags)
RANTS: (numbered list)
```

Between 4–6 personas this yields 60–120 raw events with duplicates, contradictions, and naming
clashes. Perfect — that's what a real wall looks like before *Enforce the timeline*.

Mechanics that keep the round from stalling: launch every persona agent **in a single message** so
they run concurrently, and start the merge only once you actually hold all their returned batches.
Don't poll or idle-wait on agents — if a batch is lost or an agent dies, regenerate that persona's
batch yourself in light mode (from their card + the brief only), note the fallback in the journal,
and keep the session moving; if the lost output turns up later, ignore it (a wall merged twice is
worse than a persona re-voiced once). One divergent braindump round per phase; follow-up gaps are
handled in convergent dialogue, not by re-spawning the room.

Provenance constraint for every divergent round, spawned or light: a persona may only cite
`[code:]`/`[doc:]` paths that appear in the brief or their own card — anything else is `[guess]`,
even if it "feels" certain. Inventing an evidence path is the one unforgivable sin in this
simulation; when in doubt, tag the guess.

### Convergent rounds → facilitated dialogue in the main session

Merging, sorting, walk-throughs, policy checks, hot-spot arguments: these need shared context and
tight turn-taking, so the facilitator voices the personas directly in the conversation. This is
role-play with production rules:

- **Every beat earns its place.** A dialogue beat (1–3 sentences, one speaker) must do at least one
  of: add a sticky, rename/move a sticky, raise a hot spot, resolve a hot spot, or cast a vote.
  If it does none, cut it. No small talk, no "great point, Marco."
- **Three beats, then park.** If a disagreement isn't resolved after ~3 exchanges, the facilitator
  marks a 🟣 Hot Spot with both positions and moves on — the book's rule: preserve flow over
  consensus; hot spots are "smart procrastination", the discussion is visible and postponed, not
  killed.
- **Disagreement is signal — forbid polite convergence.** Personas may only concede when shown
  evidence (repo or user ruling). Two personas naming the same moment differently
  ("Shipped" vs. "Tracking Sent") must NOT merge their stickies: language splits are how bounded
  contexts announce themselves. Keep both, note the split.
- **Rants are data.** When a persona complains, the facilitator's move is to convert it: to a 🟣
  Hot Spot, a missing 🟠 event ("what actually happens when that fails?"), or a 🩷 system boundary.
- **Stay in character, lightly.** One register per persona (the Voice line), no catchphrases, no
  dialect. The characterization budget is one clause per beat; the content budget is the rest.
- **The facilitator never wins arguments.** You ask the forcing questions — "So `Payment Received`
  is all it takes for `Order Shipped`?", "Whenever a refund is requested, we just do it —
  *always*? *immediately*?" — and you write stickies. You don't hold domain opinions.

Render dialogue as a quoted block, compact:

```
> **Marco (Warehouse):** "Order Shipped is when the carrier scans the pallet — the batch job
> fires at 18:00." [code: jobs/shipping_sync.ts]
> **Priya (Support):** "Customers think 'shipped' means the tracking email. Between the scan and
> the email there's a gap and I eat the tickets for it." [guess]
> **Facilitator:** Two moments, two stickies: 🟠 Carrier Scan Registered, 🟠 Tracking Email Sent.
> 🟣 HS-3: is the 18:00 batch the cause of the gap? For the user.
```

Excerpt only load-bearing exchanges into journal.md; the rest stays in conversation.

### Light mode (no subagents)

When the Agent tool is unavailable, the scope is small, or the user wants it cheap: run divergent
rounds in-session, one persona at a time. Discipline substitutes for isolation — write each
persona's batch strictly from their card and the brief, in their vocabulary, without reconciling
against batches already written (reconciliation is a later phase, and pre-aligned stickies would
silently delete the workshop's best material). Say which mode you're using at kick-off.

## The user in the room

The user is not the audience — they're the most senior expert present, and the only real one.

- **Kick-off:** confirm scope, walk the cast past them, ask what hat they wear (founder? lead dev?
  actual support person?). Their hat determines which claims they can rule on.
- **Phase boundaries:** batch the questions — the 2–4 highest-leverage open points, concretely
  phrased ("When a payout bounces, does anyone get notified today?"), via AskUserQuestion when the
  options are enumerable, plain conversation otherwise. Never interrogate mid-flow; the book's
  facilitator keeps the room moving.
- **Rulings are canon.** A user answer upgrades stickies to `[user]`, closes or confirms hot spots,
  and is logged under "User rulings" in journal.md. Personas defer immediately — but may point out
  a consequence ("then who resets the flag the code checks?" — which may earn a new hot spot).
- **Interruptions welcome.** If the user speaks mid-phase, treat it as the expert grabbing a marker:
  incorporate, tag, continue.
- **Absent user = autonomous session.** If the user says "just run it" (or is clearly not
  answering), complete all phases persona-only, leave every material guess flagged, and make
  outcome.md's "Open questions" section the deliverable. Never fabricate a user ruling — an
  unresolved hot spot is a good outcome; a fake resolution poisons the board.

## Voting mechanics (Pick the problem)

Arrow voting, adapted: each persona casts 2 votes on 🟣 hot spots / 🟢 opportunities — in full mode
via one cheap parallel round (each votes from their card's priorities, with one line of rationale);
in light mode in-session. The user also gets 2 votes, cast last so the personas can't anchor them
(the book has the facilitator watch for exactly this power dynamic — leaders vote late). Show the
tally; the user's votes break ties and their veto is final. If the user is absent, report the
persona tally as *the cast's recommendation*, not a decision — and state the swing explicitly
("your two votes are still open: one ties it, two flip it").
