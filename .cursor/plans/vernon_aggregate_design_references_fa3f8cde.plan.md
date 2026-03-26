---
name: Vernon aggregate design references
overview: Add Vernon's "Effective Aggregate Design" three-part essay as a reference and review/enhance the skill based on the aggregate design principles it teaches -- the four rules of thumb, false invariants, BOTE estimation, and "ask whose job it is" heuristic.
todos:
  - id: create-aggregate-design-ref
    content: Create new references/AGGREGATE-DESIGN.md with Vernon's four rules, false invariants, BOTE estimation, aggregate-as-factory, and NestJS/TypeScript examples
    status: completed
  - id: update-skill-md
    content: 'Update SKILL.md: add Vernon essays to Sources, enrich aggregate decision tree, add to anti-patterns table, add AGGREGATE-DESIGN.md to reference table'
    status: completed
  - id: update-cheatsheet
    content: "Update CHEATSHEET.md: add compact 'Four Rules of Aggregate Design' section, expand aggregate decision tree"
    status: completed
  - id: update-ddd-tactical
    content: 'Update DDD-TACTICAL.md: add value-object-over-entity guidance and cross-reference to AGGREGATE-DESIGN.md in Aggregate Root section'
    status: completed
  - id: update-cqrs-events
    content: 'Update CQRS-EVENTS.md: add cross-reference to AGGREGATE-DESIGN.md in eventual consistency discussion'
    status: completed
isProject: false
---

# Add Vernon Aggregate Design References and Skill Review

## Source Material Summary

Vaughn Vernon's "Effective Aggregate Design" (2011) is a three-part essay that is one of the most cited resources on DDD aggregate boundaries:

- **Part I** -- Modeling a Single Aggregate: large-cluster anti-pattern, false vs true invariants, "design small aggregates", favor value objects over entities
- **Part II** -- Making Aggregates Work Together: reference by identity, eventual consistency outside boundaries, "ask whose job it is" heuristic, reasons to break the rules
- **Part III** -- Gaining Insight Through Discovery: BOTE (back-of-the-envelope) cost estimation, usage scenario analysis, practical aggregate splitting decisions

## Gap Analysis

The skill currently mentions aggregate concepts across multiple files but lacks depth on **how to discover and design correct aggregate boundaries**. Specifically:

**Already covered well:**

- One aggregate per transaction rule
- Keep aggregates small (mentioned but not deeply explained)
- Reference by ID (shown in `DDD-STRATEGIC.md` context mapping)
- Domain events for eventual consistency (`CQRS-EVENTS.md`)
- Value Object vs Entity decision tree

**Missing or shallow:**

- No dedicated treatment of aggregate boundary design methodology
- No coverage of **false invariants vs true invariants** -- the most common aggregate design mistake
- No "**ask whose job it is**" heuristic (Eric Evans' tie-breaker for transactional vs eventual consistency)
- No discussion of **BOTE cost estimation** for evaluating aggregate size trade-offs
- No "**don't trust every use case**" principle
- No discussion of **reasons to break the rules** (UI batch operations, lack of mechanisms, query performance)
- The **aggregate-as-factory pattern** (parent aggregate creating child aggregates) is not shown
- No structured **"Four Rules of Aggregate Design"** presented as a coherent set
- Vernon's essays are not in the Sources list

## Plan

### 1. Create new reference: `references/AGGREGATE-DESIGN.md`

A dedicated reference file covering Vernon's aggregate design methodology, translated into NestJS/TypeScript. Sections:

- **The Four Rules of Thumb** -- presented as a coherent set:
  1. Model True Invariants In Consistency Boundaries
  2. Design Small Aggregates
  3. Reference Other Aggregates By Identity
  4. Use Eventual Consistency Outside the Boundary
- **False Invariants vs True Invariants** -- with a concrete NestJS example (analogous to Vernon's Product/BacklogItem story but in TypeScript/NestJS terms, e.g., a Project aggregate with Tasks/Milestones/Sprints)
- **Large-Cluster Aggregate Anti-Pattern** -- showing the concurrency/optimistic locking failure with code
- **Splitting Aggregates** -- refactoring a large aggregate into smaller ones, including the aggregate-as-factory pattern (parent aggregate methods return new aggregate instances instead of adding to internal collections)
- **Favor Value Objects Over Entities** -- the 70/30 guideline, serialization and immutability benefits
- **Don't Trust Every Use Case** -- recognizing when a use case specification implies incorrect aggregate boundaries
- **Ask Whose Job It Is** -- Eric Evans' heuristic for deciding transactional vs eventual consistency
- **BOTE Cost Estimation** -- structured approach to estimate aggregate size and evaluate design trade-offs
- **Reasons to Break the Rules** -- UI batch operations, lack of technical mechanisms, global transactions, query performance (with NestJS-specific examples)
- **Eventual Consistency Implementation** -- domain event subscriber coordinating consistency (linking back to `CQRS-EVENTS.md`)

### 2. Update `SKILL.md`

- Add Vernon's three essays to the **Sources > Primary Sources** section
- Enrich the **"Should this be its own Aggregate?"** decision tree with the four rules and "ask whose job it is"
- Add the new reference file to the **Reference Documentation** table
- Add **"Large-Cluster Aggregate"** to the Anti-Patterns table

### 3. Update `references/CHEATSHEET.md`

- Add a compact "Four Rules of Aggregate Design" section to the quick reference
- Expand the "Aggregate boundaries?" decision tree with "ask whose job it is" and false-invariant checking

### 4. Minor updates to `references/DDD-TACTICAL.md`

- In the **Aggregate Root > Rules** section, add a note about favoring value objects over entities within aggregates (Vernon's 70/30 guideline)
- Add a cross-reference to the new `AGGREGATE-DESIGN.md` for boundary design guidance

### 5. Minor updates to `references/CQRS-EVENTS.md`

- In the **Domain Event Flow** section, add a brief note about eventual consistency being the primary mechanism for cross-aggregate coordination, linking to `AGGREGATE-DESIGN.md` for the full methodology

### Files Changed

- **New:** [references/AGGREGATE-DESIGN.md](skills/nestjs-domain-driven-hexagon/references/AGGREGATE-DESIGN.md)
- **Modified:** [SKILL.md](skills/nestjs-domain-driven-hexagon/SKILL.md) -- sources, decision tree, anti-patterns, reference table
- **Modified:** [references/CHEATSHEET.md](skills/nestjs-domain-driven-hexagon/references/CHEATSHEET.md) -- four rules section
- **Modified:** [references/DDD-TACTICAL.md](skills/nestjs-domain-driven-hexagon/references/DDD-TACTICAL.md) -- aggregate root section enrichment
- **Modified:** [references/CQRS-EVENTS.md](skills/nestjs-domain-driven-hexagon/references/CQRS-EVENTS.md) -- eventual consistency cross-reference
