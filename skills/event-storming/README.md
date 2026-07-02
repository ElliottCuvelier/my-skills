# event-storming

A Claude Code skill that runs simulated [EventStorming](https://www.eventstorming.com/) workshops
— based on Alberto Brandolini's *Introducing EventStorming* — grounded in whatever repo it's
installed in.

Claude plays the **facilitator**. A cast of **domain-expert personas is derived from your
codebase** (the billing person, the ops person, the support person your code implies…), each with
their own silo, blind spots, and pet frustrations. They braindump domain events independently, in
parallel, and then argue — naming clashes, contradictions and rants are kept on purpose, because
that's where the insight lives. **You are the senior domain expert in the room**: the workshop
pauses at phase boundaries to ask you the questions that actually matter, and your answers become
canon on the board.

## Formats

| Format | Use for | Output |
|---|---|---|
| **Big Picture** | Discover/align on a whole domain, kick off, onboard, find bounded contexts | Event timeline, hot spots, voted #1 problem, candidate contexts |
| **Process Modeling** | Design one flow end-to-end as a cooperative game | Full color-grammar process (events, commands, policies, read models), win conditions checked |
| **Design-Level** | Turn a flow into a software design | Aggregates with invariants, code↔board gap analysis, stories or prototype scaffold |
| **Model Storming** | One sharp question, no ceremony | A quick evented answer + open questions |

## What makes the simulation honest

- **Parallel, independent persona agents** for the divergent phases — mirroring the workshop's
  "quiet chaos", so perspectives genuinely collide instead of politely converging.
- **Provenance on every sticky**: `[code: path]` (repo evidence), `[doc:]`, `[user]` (your ruling —
  canon), `[guess: persona]` (hypothesis, visibly so). Personas generate perspectives, not facts.
- **Disagreement preserved as data** — synonym events at boundaries are bounded-context signals,
  not noise to dedupe.

## Artifacts

Sessions persist to `docs/event-storming/<scope>/` in the target repo:

```
brief.md     # domain brief + persona cast
board.md     # the wall: timeline, people & systems, hot spots, votes
journal.md   # key exchanges + your rulings (append-only)
outcome.md   # picked problem, discoveries, open questions, next step
```

Everything is resumable — an interrupted workshop continues from its `Phase:` header.

## Install

Copy `skills/event-storming/` into the target repo's `.claude/skills/` (or your user-level
`~/.claude/skills/`):

```bash
cp -r skills/event-storming /path/to/your-repo/.claude/skills/
```

## Usage

Just ask, e.g.:

- "Run an event storming session on this repo"
- "I want to understand what this codebase actually does, business-wise"
- "Let's process-model the refund flow"
- "Design-level storm the checkout so we can split the aggregate"
- "Quick model storm: what happens when a subscription lapses?"

Useful qualifiers: `light` (no subagents, cheaper), `just run it` (autonomous — no mid-session
questions, open questions delivered at the end), or name the format explicitly.

## Cost note

Full mode spawns one subagent per persona (4–6) for each divergent round (2–3 rounds per session).
Say "light" for a single-context session — cheaper, with somewhat weaker divergence.
