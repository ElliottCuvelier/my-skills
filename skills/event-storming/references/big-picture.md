# Big Picture EventStorming — facilitation script

The discovery format: one large workshop mapping an entire line of business as domain events on a
timeline, with every perspective in the room. Use it to kick off a project, align on the most
compelling problem, explore an unfamiliar domain (or codebase), or onboard someone. It is **all
about discovery, not convergence**: the outcome is a shared model *including holes, gaps, and
conflicts* — "a Big Picture EventStorming is more of a *let's have a look under the carpet* party."

The goal sentence to open with (adapt the bracketed part):

> "We are going to explore [this business/product] as a whole by placing all the relevant events
> along a timeline. We'll highlight ideas, risks, and opportunities along the way."

Success is NOT a tidy diagram. "No conflicts and no problems doesn't mean honeymoon: it means
somebody was missing, or maybe lying."

## Phase sequence

Run the phases in order; each updates board.md before the next begins. Deviating is normal — "Big
Picture is a discovery format, and what we find along the way can be more interesting than the
original plan" — but announce deviations and note them in the journal.

### 1. Kick-off

- Present the scope (from brief.md) and the goal sentence. Present the cast; let the user adjust.
  Ask what role the user plays.
- Show the legend (board.md notation) in one compact block. Explain the only rule that matters now:
  **orange sticky, verb at past tense, placed on a timeline** — "everything you need to know about
  a domain event."
- Warn that the first phase is deliberately chaotic and unpolished. Don't lecture about the method:
  "don't talk, show."

### 2. Chaotic Exploration

The massively parallel braindump. Run the divergent protocol from cast-and-dialogue.md — one
independent contribution batch per persona (subagents in full mode).

Facilitator rules for the merge that follows — **hold these, they're the method**:

- **Keep duplicates and near-duplicates.** "There is no right one." Synonyms are bounded-context
  ore; deduplicate only literal identical wording.
- **Don't fix phrasing yet** ("postpone precision"). A phase-name instead of an event
  ("Registration", "Onboarding") hides complexity: mark it `⚠️` (the book's 45°-rotated sticky)
  and expand it into real events during sorting.
- Expect "locally ordered clusters in a disordered whole" — that's the intended raw state.
- Guessing is legitimate; gaps are expected.

Calibration: a real 2-hour Big Picture yields 100–200 events; under ~100 means the surface was only
scratched. A scoped simulated session may run smaller, but if the merged wall has under ~40 events,
say so and either narrow the stated scope or run another braindump round on the thin areas.

### 3. Enforce the Timeline

Make one consistent story from beginning to end. This is where discussions ignite — "local
sequences have to be merged with somebody else's view, and the whole thing needs to make sense."

Sorting strategies (combine as needed):

- **Pivotal events** (preferred): find the 4–5 most significant events — the ones with the most
  interested parties (`Order Placed` wakes billing, shipping, fraud). Mark `⭐`, use as section
  dividers, sort within the segments. Don't debate the perfect choice: "preserving flow is more
  important than reaching consensus."
- **Temporal milestones**: when concurrent processes or misaligned orderings make key events
  useless, use time markers instead (1 year before / launch day / after delivery…).
- **Chapters sorting**: if the wall is too messy, extract 15–25 chapter titles, sort those, then
  remodel the events under them. Do this *after* exploration, never before — the pre-agreed
  structure is the "official version", and the official version is exactly what we don't trust.
- **Swimlanes**: only for genuinely parallel processes, as separate `###` sections — never as the
  primary structure; they eat space and multiply.

During sorting, run convergent dialogue (cast-and-dialogue.md): naming clashes and ordering
conflicts play out in short persona exchanges; the facilitator marks 🟣 Hot Spots where discussion
heats or stalls — during this phase hot spots are the *facilitator's* tool (an open call for
problems comes later, in phase 8, when it won't flood the board with noise).

### 4. People and Systems

Add 🟡 people and 🩷 external systems wherever they matter in the flow.

- Definitions stay fuzzy on purpose. People: `User` to `Amy from Billing` — whatever sharpens the
  conversation. External system: "**whatever we can put the blame on**" — vendors, departments not
  in the room, regulators, `GDPR`, even `Bad Luck` (which promptly surfaces the unlucky events
  nobody modeled).
- Pre-harvest candidates from the repo: every integration, webhook, third-party SDK, and cron job
  found during grounding goes on the wall with `[code:]` provenance.
- Don't summarize systems ("Socials" hides Facebook/YouTube specifics that carry different rules).
- Systems attract sarcasm; sarcasm becomes 🟣 Hot Spots. A developer persona calling a component
  "external" that the org owns is a disengagement signal worth a hot spot of its own.
- New systems trigger new events (license renewals, sync failures, boundary rituals) — add them.

### 5. Explicit Walk-through

A narrator tells the story left to right while the room challenges. Rotate narrators at pivotal
events, relay-race style, so each persona narrates their own territory ("and this is where Mary's
team takes over").

- The audience must interrupt — a bumpy narration that keeps forcing new events is the phase
  working as designed. "Validation without a conversation is an illusion."
- The facilitator keeps the story synced with the board: missing events added on the fly, touched
  events count as *narrated*. Events no narrative ever touches are suspect — probe or hot-spot them.
- The user is invited to narrate the segment they know best; their narration outranks everyone's.

### 6. Reverse Narrative

Walk backwards from terminal and pivotal events: "So [Event A] is all it takes to have [Event B]?
What *else* needs to have happened?" Every event must be the direct consequence of prior events —
no magic gaps.

Expect this pass to surface a large chunk of the system (the book: 30–40%) that optimistic forward
thinking skipped: the group-ticket reassignments, the manual retries, the reconciliation nobody
mentions. Fold discoveries into the timeline; hot-spot what can't be explained.

### 7. Value round (optional — ask before opening this door)

Overlay where value is **created (🟢+) and destroyed (🔴−)**, anchored to specific events. Two
facilitator moves carry the phase:

- **Legitimize non-money currencies** — time, reputation, stress, pride, safety, belonging. "Once
  you signal that we can talk about something else than just money, people start to talk."
- **Contrast perspectives per step** — the same event can be a win for sales and a tax on
  engineering; an "it depends who" answer reveals hidden customer segments.

Run it only when the user is up for questioning purpose, not just mechanics (skip in a quick
technical discovery). In autonomous mode you can't ask — skip the full value round and offer it in
outcome.md as a follow-up. Always run the money sub-pass though, at least briefly, in every mode:
developer-derived casts neglect invoices, payouts, and dunning — "understanding money mechanics is
vital."

### 8. Problems and Opportunities

The explicit, open round (until now hot spots were facilitator-caught): every persona and the user
add 🟣 problems and 🟢 opportunities anywhere on the board. In full mode this is a cheap parallel
persona round; keep it quick. Expect the flood to be balanced — "we have problem-solvers in the
room too."

Close the phase with the book's checklist question, asked verbatim to cast and user:
**"What is missing from this picture?"**

### 9. Pick the Problem (arrow voting)

Everyone gets **two votes** on problems/opportunities; criteria deliberately personal ("most
important problem to solve"). Personas vote with one line of rationale; the **user votes last** so
nobody anchors them; user votes settle ties and their veto is final.

Don't vote when it would mislead: cast too partisan for a system-wide diagnosis, scope that missed
the real constraint, or a too-early startup where there are only assumptions to test — then the
outcome is a list of assumptions/questions instead of a winner.

### 10. Wrap-up

1. Run the quality gates: hot spots exist (none = someone missing or lying) · external systems on
   the board · event count sane for the scope · "what is missing?" was asked · money flow was at
   least glanced at.
2. Write outcome.md (board.md template file): picked problem, discoveries, open questions,
   candidate contexts, next step, not-explored.
3. Push momentum: "the worst thing one can do is spot the problem, gather consensus, and then lose
   all momentum by doing something else instead." Recommend the follow-up concretely — usually a
   Process Modeling session on the winner, or naming the real human who can close the top hot spot.
4. Don't fall in love with the artifact: "the model is still wrong." It's a snapshot of current
   understanding, not documentation.

## Bounded-context homework (after the workshop)

Boundary-finding is analyst work on the finished board, not a workshop phase — and business
stakeholders are not a reliable direct source ("asking about bounded contexts will get you an
answer; it can't be trusted blindly"). Read the board for:

1. **Business phases** — pivotal events delimit them; *designing* a thing and *running* it need
   different models. Follow the money between phases.
2. **Synonym clashes at boundaries** — `Schedule Ready` vs `Schedule Published` from different
   personas is two models touching. "You don't have to agree on the language! There's much more to
   discover by making disagreements visible." When two models interact, there are three languages:
   each side's, plus the published language between them.
3. **Competence clashes** — upstream knows the mechanics, downstream only wants the outcome
   ("I don't care how you decided the prices, I just need the amount per ticket type"). Complexity
   vanishing across a line = a boundary.
4. **Persona-split flows** — same apparent flow, different paths per persona upstream, converging
   downstream (invited speakers vs CfP submitters).
5. **Contribution zones** — the simulated advantage: braindump provenance records exactly which
   persona contributed which events. Dense single-persona regions are the digital twin of "experts
   hovering around the part of the wall they care about."
6. **Verbs over nouns** — a noun everyone shares (`Order`, `Talk`) with disjoint verb sets per
   region is several models wearing one name.

Write candidates into outcome.md as hypotheses with their evidence. Not every swimlane is a context
— "sometimes it's just an if statement."

## Variations

- **Onboarding / induction**: invert the roles — the newcomer models their guesses first ("Let's
  start modeling what YOU think is happening here!"), experts correct and must justify each
  correction. Works both directions: user as newcomer (personas correct) or user as expert
  (a newcomer persona guesses — often the best question-asker in the cast).
- **Retrospective**: baseline the *actual* recent flow, then hunt improvements; prioritize with
  "Which issue will have the biggest impact when solved?"
- **Startup / greenfield**: fewer personas, assumptions instead of facts; skip voting, output the
  riskiest-assumptions list; value round earns its keep here.
- **Model storming**: see facilitation.md — a minutes-long single-question micro-session, not a
  full Big Picture.
