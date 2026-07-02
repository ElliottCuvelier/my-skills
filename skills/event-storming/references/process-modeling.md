# Process Modeling EventStorming — facilitation script

The solution-space format: design (or redesign) **one end-to-end business process** as a
cooperative game. Where Big Picture diverges on purpose, Process Modeling must **converge on a
working design** — typically for the problem that won the Big Picture vote, a feature about to be
built, or a flow that keeps breaking. Smaller cast (3–5 personas: the stakeholders of *this*
process), tighter grammar, explicit win conditions.

"You wouldn't need EventStorming to agree on a trivial process" — expect a branching festival, and
manage it.

## The color grammar

The picture that explains everything, linearized:

```
🟢 Read Model → 🟡 Person → 🔵 Command → 🩷 System → 🟠 Event → 🟢 Read Model → …
                                                    🟠 Event → 🟪 Policy → 🔵 Command → …
```

Two grammar laws, stated dumb on purpose ("we need a blue one after a lilac one"):

- **A pink System sits between a blue Command and an orange Event.** Someone/something executes
  the intention; commands can fail — the event records what actually happened.
- **A lilac Policy sits between an orange Event and a blue Command.** ALWAYS. "There is always a
  business decision between an event and the reaction" — even when it feels too obvious to notice.
  The mandatory lilac forces the team to think. Phrase every policy `Whenever [event(s)], then
  [command(s)]`, and give it a **policy read model** if the decision needs data.

Building-block notes beyond the grammar:

- **Events** need more precision here than in Big Picture: state transitions, rewritten as
  understanding deepens. Four sources — user interaction, external system, **time** (⏰; "when
  things happen 'at the right time' there's an implicit time-triggered event waiting to emerge"),
  cascading reaction (which always means a policy hides between the two events).
- **Events that DON'T happen** can't be modeled directly — model the time window instead:
  `🟠 End of Day Reached ⏰` before `🟠 Greeting Received` is how "we forgot" becomes visible.
- **Read models** = the information a decision needs, named as data, not as fetch-sequence
  ("many times, fetching data is not a process step: it's a piece of one possible solution leaking
  into the problem space"). They're also where assumptions hide — challenge them ("does the
  traveler actually know the nearest station?").
- **Conversational systems** (email threads, phone calls, chat) resist event decomposition — don't
  script the conversation; mark the system conversational and model only the **terminal outcomes**
  ("what ends this conversation?"), taking the downstream perspective: "I don't care how you reach
  the deal, I only care about the deal details."
- **People**: differentiate when behavior differs (New vs Returning Customer), not before.
- **Systems**: resist genericization — different systems have different pain points; pick a
  representative and hot-spot the ones not explored.

## Win conditions (the game ends when ALL hold)

1. **Every process path is complete** — from trigger (a command, or an external/time event) to a
   stable state: terminal events (*system happy*) **and** the read models that let humans see it
   ended (*user happy*). Both. An order that's "done" but invisible to the customer isn't done.
2. **The color grammar holds everywhere** — no orange→blue without a lilac, no blue→orange without
   a pink. Grammar holes are unexamined business decisions.
3. **Every hot spot is addressed** — open 🟣 count is zero: resolved, or explicitly converted to an
   open question owned by a real human in outcome.md. "We're not going to cheat."
4. **Every stakeholder is reasonably happy** — check per persona + user, in character. *Reasonably*:
   a refund flow has no delighted parties; maximize value given the constraints, and let the value
   stickies (🟢+/🔴−) make the trade-offs visible.

## Phase sequence

### 1. Frame the game

- Restate the problem (import the hot spot / brief). Agree the **trigger** and the **desired
  outcomes** with the user before modeling: outcomes as events + read models, sorted by priority.
- Present the cast (process stakeholders only) and the grammar in one breath.
- Leave room *before* the trigger — "often some unexpected preconditions pop up."

### 2. Opening move (pick one, tell the user which and why)

- **Forward** (default): from the trigger, build the colored railway toward the outcomes. Natural
  storytelling, easy for everyone; maximizes branching — pair it with Rush to the Goal.
- **Reverse narrative** (best when outcomes are crisp or the team is stuck): from the top outcome,
  step left: which 🩷 system emits this? which 🔵 command tells it to? which 🟪 policy issues that
  command — "Whenever [?], then [command]"? which 🟠 event triggers the policy? what data does it
  need (policy read model — and where is that collected)? Repeat to the trigger. Watch the known
  failure mode: reverse mode tempts the facilitator to take over — keep handing beats back to
  personas and user.
- **Make a little mess** (when contradictions are suspected): a short, strictly timeboxed
  events-only braindump (divergent round, subagents in full mode), spaced out, then enforce the
  grammar over the skeleton. Quick, confrontational, harder to sort. "Don't fall in love with the
  skeleton — probably every single sticky needs one or more rewrites."

Switching mid-game is normal ("I've found myself often starting from the beginning, and then
turning to reverse narrative to get out of a rabbit hole").

### 3. Rush to the Goal (the core loop)

1. **Sprint a baseline happy path** end-to-end in full grammar, narrating out loud, no wording
   debates. "I just need a solution, not a good one."
2. **Hot-spot flood**: every persona (and the user) dumps everything they dislike about the
   baseline as 🟣 stickies. In full mode this is a cheap parallel round.
3. **Drain the queue, WIP = 1**: pick the most interesting hot spot, resolve it into model changes
   (a branch, a policy split, a read model, a rename), close it, take the next. Every branch NOT
   being worked on right now is parked as a hot spot — visible, postponed, not forgotten. "It's
   very hard to solve two problems at the same time."

### 4. The policy interrogation (run on every policy — this is where people lie)

"Policies is where people lie. Discovering the real implementation of an existing policy is an
investigation game." The facilitator's two moves, in order:

1. **Speak it out loud, complete sentence:** "Whenever we receive an email asking to hold a room,
   we just do it." Saying it aloud is the lie detector — the sentence corrects itself, or a persona
   corrects it. (In simulation: the facilitator states it in conversation; personas with
   conflicting evidence or incentives MUST object — check each persona's card for a reason to.)
2. **Add the magic keywords:** re-read with "…**always**? …**immediately**?" and enjoy the show.
   Every objection becomes a 🟣, then a read-model condition, a split policy (`Regulars Hold
   Policy` vs `Standard Refusal Policy`), or a compensating flow (the reminder that releases the
   hold).

Name policies from the implementation, last ("How would you call a policy like this one?") — never
ask experts for the name first.

For repo-grounded sessions the interrogation has teeth: the *actual* policy is in the code. When a
persona asserts a policy, check it against handlers/jobs/listeners (`[code:]`) — divergence between
stated policy and coded policy is the highest-value hot spot this format produces.

### 5. Observable state pass

Business transactions are never atomic — they're "a process of reconciliation" running on trust
through deliberately inconsistent intermediate states (the book's hot-dog stand). Walk the flow
once asking, at each step:

- **What can each actor SEE here** that tells them it's safe/necessary to act? (missing → read model)
- **Does state exist that no one can observe?** (the cooked hot dog nobody serves — value decays;
  add a read model or a notification event)
- **Which actions are irreversible?** Mark them; they bound the compensation paths.
- **Where does elapsed time change the story?** (⏰ events, timeouts, "the customer got impatient")

### 6. Close the game

- Verify the four win conditions explicitly; per-stakeholder happiness check runs in character,
  one line each, user last.
- Value pass if trade-offs surfaced: 🟢+/🔴− per party at contested steps.
- Write outcome.md: the designed process, decisions taken (with the policy wordings — they're the
  spec), open questions, and the recommended next step — often Design-Level on the same scope, or
  straight to implementation ("the roll is not the deliverable").

## Facilitator conduct specific to this format

- **Keep everything visible** — "we don't talk about invisible things." Every objection, branch,
  and alternative becomes a sticky before it may be discussed. This is the #1 duty, and it's hard
  because "puzzles are addictive" — the facilitator models the *board*, not the *solution*.
- **Rabbit-hole detection**: talk detaching from the board, topics with no sticky, chained
  "Yes, but if…" — name it, park branches as 🟣, switch opening strategy or take a break.
- **Split & merge** when one voice dominates or two solutions compete: model both alternatives
  (subagents make this cheap — one per approach), then compare the *visible* models. "It's never
  fair to choose between the visible model we built together and the invisible one this person is
  talking about."
- **Doubt fear-shaped edge cases**: "What if every customer does [something stupid]?" — some will;
  all at once is fear, not analysis. Model the real frequency as a policy condition.
