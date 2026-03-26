# Aggregate Design

How to discover, size, and compose aggregates correctly. Based on Vaughn Vernon's four rules of effective aggregate design, translated into NestJS/TypeScript guidance.

## Table of Contents

- [The Four Rules of Thumb](#the-four-rules-of-thumb)
- [Rule 1: Model True Invariants In Consistency Boundaries](#rule-1-model-true-invariants-in-consistency-boundaries)
- [Rule 2: Design Small Aggregates](#rule-2-design-small-aggregates)
- [Rule 3: Reference Other Aggregates By Identity](#rule-3-reference-other-aggregates-by-identity)
- [Rule 4: Use Eventual Consistency Outside the Boundary](#rule-4-use-eventual-consistency-outside-the-boundary)
- [The Large-Cluster Aggregate Anti-Pattern](#the-large-cluster-aggregate-anti-pattern)
- [Splitting Aggregates: The Factory Pattern](#splitting-aggregates-the-factory-pattern)
- [Favor Value Objects Over Entities](#favor-value-objects-over-entities)
- [Don't Trust Every Use Case](#dont-trust-every-use-case)
- [Ask Whose Job It Is](#ask-whose-job-it-is)
- [BOTE Cost Estimation](#bote-cost-estimation)
- [Reasons to Break the Rules](#reasons-to-break-the-rules)

---

**See also:** [DDD-TACTICAL.md](DDD-TACTICAL.md) for Entity, ValueObject, and AggregateRoot base class implementations, [CQRS-EVENTS.md](CQRS-EVENTS.md) for domain event flow and eventual consistency mechanics, [DDD-STRATEGIC.md](DDD-STRATEGIC.md) for bounded context boundaries.

---

## The Four Rules of Thumb

Vernon distills aggregate design into four interdependent rules. Apply them as a set -- skipping one undermines the others.

| #   | Rule                                                | In Practice                                                                                                 |
| --- | --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| 1   | **Model True Invariants In Consistency Boundaries** | The aggregate boundary wraps only the data that must be transactionally consistent. Nothing more.           |
| 2   | **Design Small Aggregates**                         | Root entity + minimal value-typed properties. Favor value objects over child entities.                      |
| 3   | **Reference Other Aggregates By Identity**          | Store `orderId: string`, not `order: OrderEntity`. No direct object references across aggregate boundaries. |
| 4   | **Use Eventual Consistency Outside the Boundary**   | Cross-aggregate rules are enforced through domain events, not multi-aggregate transactions.                 |

These rules exist because **aggregate is synonymous with transactional consistency boundary**. Aggregates are not about composing convenient object graphs -- they are about protecting business invariants within a single transaction.

---

## Rule 1: Model True Invariants In Consistency Boundaries

An invariant is a business rule that must always hold. The aggregate boundary must encompass exactly the data required to enforce those rules atomically.

### True invariants vs false invariants

The most common aggregate design mistake is treating **compositional convenience** as an invariant. Just because two concepts are associated ("a project has tasks") does not mean they must live inside the same aggregate.

**True invariant:** "The sum of all line item amounts must not exceed the order's spending limit." -- The order and its line items must be in the same aggregate because the rule cannot be checked without both.

**False invariant:** "A project has milestones and tasks." -- Creating a new task does not violate any rule about milestones. These are separate aggregates connected by `projectId`.

### How to identify true invariants

Ask these questions about each proposed consistency rule:

1. **If data A changes, must data B be immediately consistent in the same transaction?** If yes, they belong in the same aggregate.
2. **Could the rule be satisfied with a small delay (seconds, minutes)?** If yes, use eventual consistency with separate aggregates.
3. **Is the rule imposed by a domain expert, or by a developer's desire to keep objects together?** Developer convenience is not an invariant.

### Example: true invariant in TypeScript

An `Order` aggregate enforces a spending limit across its line items:

```typescript
// src/modules/order/domain/order.entity.ts

export class OrderEntity extends AggregateRoot<OrderProps> {
  protected readonly _id: AggregateID;

  addLineItem(product: ProductSnapshot, quantity: number): void {
    const itemTotal = product.price * quantity;
    const newTotal = this.currentTotal() + itemTotal;

    if (newTotal > this.props.spendingLimit) {
      throw new OrderSpendingLimitExceededError(
        this.props.spendingLimit,
        newTotal,
      );
    }

    this.props.lineItems = [
      ...this.props.lineItems,
      new LineItem({ productId: product.id, price: product.price, quantity }),
    ];

    this.addEvent(
      new LineItemAddedDomainEvent({
        aggregateId: this.id,
        productId: product.id,
        quantity,
      }),
    );
  }

  private currentTotal(): number {
    return this.props.lineItems.reduce(
      (sum, item) => sum + item.price * item.quantity,
      0,
    );
  }

  validate(): void {
    const total = this.currentTotal();
    if (total > this.props.spendingLimit) {
      throw new ArgumentInvalidException(
        `Order total ${total} exceeds spending limit ${this.props.spendingLimit}`,
      );
    }
  }
}
```

The `lineItems` collection lives inside the `Order` aggregate because the spending limit invariant requires checking all items atomically.

---

## Rule 2: Design Small Aggregates

Limit the aggregate to its root entity and a minimal number of value-typed properties. The correct minimum is the set of attributes that must be consistent with each other -- and no more.

### Why small matters

Large aggregates cause three problems that compound under load:

1. **Transactional failures.** With optimistic concurrency (versioned rows), any modification bumps the aggregate's version. Two users modifying unrelated parts of the same large aggregate will collide -- one transaction always fails.
2. **Memory overhead.** Loading an aggregate with thousands of child objects for a single-field update wastes memory and time.
3. **Scalability ceiling.** Large aggregates cannot be partitioned, distributed, or cached efficiently.

### The size guideline

In practice, a high percentage of aggregates consist of just a root entity with value-typed properties -- no child entities at all. On one project in the financial sector, approximately 70% of aggregates were root-entity-only, with the remaining 30% having two to three entities total.

When you think a part should be modeled as a child entity, first ask: **can this part be completely replaced when change is necessary?** If so, model it as a value object. Value objects are smaller, safer (immutable), easier to test, and cheaper to persist (serialized with the root, no joins).

### What "small" means concretely

```
Good:
  OrderEntity (root)
  ├── lineItems: LineItem[]          (value objects)
  ├── shippingAddress: Address       (value object)
  └── spendingLimit: number          (primitive)

  Total: 1 entity + value objects. Invariant: spending limit.

Avoid:
  OrderEntity (root)
  ├── lineItems: LineItemEntity[]    (child entities)
  ├── payments: PaymentEntity[]      (separate aggregate!)
  ├── shipments: ShipmentEntity[]    (separate aggregate!)
  ├── invoices: InvoiceEntity[]      (separate aggregate!)
  └── customer: CustomerEntity       (separate aggregate!)

  This is a large-cluster aggregate. Payments, shipments, invoices,
  and customers do not share invariants with order line items.
```

---

## Rule 3: Reference Other Aggregates By Identity

Store the ID of the referenced aggregate, not a direct object reference. This keeps aggregates decoupled, small, and distributable.

### Direct reference (avoid)

```typescript
// Holds an object reference -- couples the two aggregates
interface BacklogItemProps {
  product: ProductEntity; // direct reference to another aggregate
  summary: string;
}
```

Problems: the referenced aggregate is loaded eagerly or lazily, tempting developers to modify it in the same transaction. It also prevents independent scaling or distribution.

### Identity reference (prefer)

```typescript
// Holds only the ID -- aggregates stay independent
interface BacklogItemProps {
  productId: string; // identity reference
  summary: string;
}
```

When the aggregate needs data from another aggregate, the **application service** resolves the dependency before invoking the aggregate's behavior:

```typescript
@CommandHandler(AssignTeamMemberCommand)
export class AssignTeamMemberService implements ICommandHandler {
  constructor(
    @Inject(BACKLOG_ITEM_REPOSITORY)
    private readonly backlogItemRepo: BacklogItemRepositoryPort,
    @Inject(TEAM_REPOSITORY)
    private readonly teamRepo: TeamRepositoryPort,
  ) {}

  async execute(
    command: AssignTeamMemberCommand,
  ): Promise<Result<void, Error>> {
    const backlogItem = await this.backlogItemRepo.findOneByIdOrThrow(
      command.backlogItemId,
    );
    const team = await this.teamRepo.findOneByIdOrThrow(backlogItem.teamId);

    backlogItem.assignTeamMember(command.teamMemberId, team);

    await this.backlogItemRepo.update(backlogItem);
    return Ok(undefined);
  }
}
```

The application service loads both aggregates, but only one (the `backlogItem`) is modified and persisted. The `team` is read-only context.

### Benefits of identity references

- Aggregates are automatically smaller (no eager loading of referenced graphs).
- No temptation to modify multiple aggregates in one transaction.
- Persistent state can be repartitioned for horizontal scaling.
- Aggregates in different bounded contexts can reference each other by ID across process boundaries.

---

## Rule 4: Use Eventual Consistency Outside the Boundary

When a command on one aggregate must trigger a business rule on another aggregate, use domain events to achieve eventual consistency rather than modifying both in the same transaction.

### The DDD principle

> "Any rule that spans AGGREGATES will not be expected to be up-to-date at all times. Through event processing, batch processing, or other update mechanisms, other dependencies can be resolved within some specific time." -- Eric Evans, Domain-Driven Design, p. 128

### Implementation pattern

1. The command handler modifies one aggregate, which publishes a domain event.
2. An event handler (in the same or another module) subscribes to the event.
3. The subscriber loads the second aggregate and applies the necessary changes in a separate transaction.

```typescript
// 1. Aggregate publishes event
export class TaskEntity extends AggregateRoot<TaskProps> {
  protected readonly _id: AggregateID;

  estimateHoursRemaining(hours: number, memberId: string): void {
    this.props.hoursRemaining = hours;

    this.props.estimationLog = [
      ...this.props.estimationLog,
      new EstimationLogEntry({
        date: new Date(),
        hoursRemaining: hours,
        memberId,
      }),
    ];

    this.addEvent(
      new TaskHoursEstimatedDomainEvent({
        aggregateId: this.id,
        backlogItemId: this.props.backlogItemId,
        hoursRemaining: hours,
      }),
    );
  }
}

// 2. Subscriber coordinates consistency
@Injectable()
export class UpdateBacklogItemStatusWhenTaskEstimatedHandler {
  constructor(
    @Inject(BACKLOG_ITEM_REPOSITORY)
    private readonly backlogItemRepo: BacklogItemRepositoryPort,
    @Inject(TASK_REPOSITORY)
    private readonly taskRepo: TaskRepositoryPort,
  ) {}

  @OnEvent(TaskHoursEstimatedDomainEvent.name, { async: true, promisify: true })
  async handle(event: TaskHoursEstimatedDomainEvent): Promise<void> {
    const totalHours = await this.taskRepo.sumHoursRemainingByBacklogItem(
      event.backlogItemId,
    );

    const backlogItem = await this.backlogItemRepo.findOneByIdOrThrow(
      event.backlogItemId,
    );

    backlogItem.reconcileStatusFromTaskHours(totalHours);
    await this.backlogItemRepo.update(backlogItem);
  }
}
```

Each subscriber runs in its own transaction. If a subscriber fails, the messaging mechanism can retry delivery. See [CQRS-EVENTS.md](CQRS-EVENTS.md) for the full event flow and outbox pattern.

### Handling failure

If eventual consistency fails after retries, options include:

- **Compensating action.** Undo the original change.
- **Alert for manual intervention.** Log the failure and notify an operator.
- **Dead-letter queue.** Park the failed event for later investigation.

---

## The Large-Cluster Aggregate Anti-Pattern

The most common aggregate design mistake: grouping related objects into one huge aggregate for compositional convenience rather than for invariant protection.

### The pattern

A developer sees the ubiquitous language statement "A project has milestones, tasks, and sprints" and models it as:

```typescript
// Anti-pattern: large-cluster aggregate
export class ProjectEntity extends AggregateRoot<ProjectProps> {
  protected readonly _id: AggregateID;

  // All of these collections live inside the Project aggregate
  private props: {
    name: string;
    description: string;
    tasks: TaskEntity[]; // hundreds or thousands over time
    milestones: MilestoneEntity[];
    sprints: SprintEntity[];
  };

  addTask(summary: string, type: TaskType): void {
    this.props.tasks.push(/* ... */);
  }

  scheduleMilestone(name: string, date: Date): void {
    this.props.milestones.push(/* ... */);
  }

  scheduleSprint(name: string, goal: string, begins: Date, ends: Date): void {
    this.props.sprints.push(/* ... */);
  }
}
```

### Why it fails

With optimistic concurrency (Prisma's `@@version` or an explicit `version` column):

1. User A loads Project (version 1) and adds a task. Commits. Project is now version 2.
2. User B loaded Project (version 1) and schedules a milestone. Tries to commit. **Rejected** -- stale version.

Adding a task has nothing to do with scheduling a milestone, yet one operation blocked the other. These are **false invariants** -- the developers assumed "has" means "must be consistent with."

Under multi-user load (sprint planning meetings, daily standups), this causes frequent, frustrating transaction failures. As collections grow to thousands of items, memory and query performance degrade further.

### The fix

Split into separate aggregates connected by identity:

```typescript
// Project is now a small aggregate
export class ProjectEntity extends AggregateRoot<ProjectProps> {
  protected readonly _id: AggregateID;
  // Only name, description, and project-level settings
}

// Task is its own aggregate, referencing Project by ID
export class TaskEntity extends AggregateRoot<TaskProps> {
  protected readonly _id: AggregateID;
  // props.projectId: string -- identity reference
}

// Milestone is its own aggregate
export class MilestoneEntity extends AggregateRoot<MilestoneProps> {
  protected readonly _id: AggregateID;
  // props.projectId: string
}

// Sprint is its own aggregate
export class SprintEntity extends AggregateRoot<SprintProps> {
  protected readonly _id: AggregateID;
  // props.projectId: string
}
```

Any number of tasks, milestones, and sprints can now be created simultaneously without transaction conflicts.

---

## Splitting Aggregates: The Factory Pattern

When a large aggregate is split, the parent aggregate's methods change from void commands (adding to internal collections) to **factory methods** that return new aggregate instances.

### Before: internal collection mutation

```typescript
// Large aggregate -- method mutates internal state, returns void
export class ProjectEntity extends AggregateRoot<ProjectProps> {
  addTask(summary: string, type: TaskType, points: StoryPoints): void {
    this.props.tasks.push(
      new TaskEntity({
        /* ... */
      }),
    );
  }
}
```

### After: factory method returning a new aggregate

```typescript
// Small aggregate -- method creates and returns a separate aggregate
export class ProjectEntity extends AggregateRoot<ProjectProps> {
  planTask(summary: string, type: TaskType, points: StoryPoints): TaskEntity {
    return TaskEntity.create({
      projectId: this.id,
      summary,
      type,
      points,
    });
  }
}
```

The application service coordinates persistence of the new aggregate:

```typescript
@CommandHandler(PlanTaskCommand)
export class PlanTaskService implements ICommandHandler {
  constructor(
    @Inject(PROJECT_REPOSITORY)
    private readonly projectRepo: ProjectRepositoryPort,
    @Inject(TASK_REPOSITORY)
    private readonly taskRepo: TaskRepositoryPort,
  ) {}

  async execute(command: PlanTaskCommand): Promise<Result<AggregateID, Error>> {
    const project = await this.projectRepo.findOneByIdOrThrow(
      command.projectId,
    );

    const task = project.planTask(
      command.summary,
      command.type,
      command.points,
    );

    await this.taskRepo.insert(task);
    return Ok(task.id);
  }
}
```

The factory method on `Project` ensures the new `Task` is created with the correct `projectId` and any project-level defaults. The `Project` aggregate itself is not modified -- only the new `Task` is persisted.

### Why use the parent as a factory?

- The parent can enforce creation rules ("only active projects can plan tasks").
- It preserves the ubiquitous language: "a project plans tasks" reads naturally.
- It keeps creation logic in the domain layer rather than in the application service.

If the parent has no creation rules to enforce, creating the child aggregate directly in the application service is also acceptable.

---

## Favor Value Objects Over Entities

When deciding whether a composed part should be an entity or a value object, default to value object unless the part genuinely requires its own persistent identity and independent lifecycle.

### Why favor value objects

| Aspect          | Value Object                                            | Child Entity                                              |
| --------------- | ------------------------------------------------------- | --------------------------------------------------------- |
| **Persistence** | Serialized with the root (one table row or JSON column) | Requires a separate table, joins to load                  |
| **Concurrency** | No version tracking needed                              | Needs its own optimistic lock if independently modifiable |
| **Mutability**  | Immutable -- replace the whole value                    | Mutable -- track changes, partial updates                 |
| **Testing**     | Trivially testable (pure, no side effects)              | Requires setup of identity and lifecycle                  |
| **Bug surface** | Smaller (immutability eliminates mutation bugs)         | Larger (shared mutable state)                             |

### The 70/30 guideline

In well-designed domain models, roughly 70% of aggregates consist of just a root entity with value-typed properties. The remaining 30% have two to three entities. This isn't a hard rule, but if most of your aggregates have many child entities, you're likely either:

- Modeling entities that should be value objects, or
- Combining multiple aggregates into one

### The decision test

Ask: **Can this part be completely replaced when change is necessary, rather than mutated in place?**

- If yes, it's a value object. When the user changes their address, you create a new `Address` value object and replace the old one on the entity.
- If no (it has its own lifecycle, needs to be tracked over time by identity), it's a child entity.

### Example: replacing value objects

```typescript
// Address is a value object -- replaced entirely, never mutated
export class UserEntity extends AggregateRoot<UserProps> {
  updateAddress(props: UpdateAddressProps): void {
    const newAddress = new Address({
      ...this.props.address.unpack(),
      ...props,
    });
    this.props.address = newAddress;

    this.addEvent(
      new UserAddressUpdatedDomainEvent({
        aggregateId: this.id,
        ...newAddress.unpack(),
      }),
    );
  }
}
```

---

## Don't Trust Every Use Case

Business analysts and product specifications sometimes describe use cases that imply modifying multiple aggregates in a single transaction. Be skeptical.

### The problem

A use case reads: "When a team member finishes a task, update the task status, update the sprint progress, and recalculate the milestone completion percentage."

Taken literally, this requires modifying three aggregates (`Task`, `Sprint`, `Milestone`) in one transaction. Under concurrent use, this creates contention on all three -- two of the three concurrent requests will fail.

### How to challenge it

1. **Ask if the rule is truly immediate.** Can the sprint progress and milestone percentage be updated a few seconds after the task status changes? Domain experts are often more comfortable with delays than developers assume.
2. **Look for the real invariant.** The task status change is the user's primary intent. Sprint progress and milestone percentage are derived calculations -- they can be eventually consistent.
3. **Rewrite the use case** in terms of aggregate boundaries:
   - Transaction 1: Update `Task` status. Publish `TaskCompletedDomainEvent`.
   - Eventually: Subscriber updates `Sprint` progress.
   - Eventually: Subscriber updates `Milestone` percentage.

### When multi-aggregate modification reveals a missing concept

Sometimes a use case that modifies multiple aggregates exposes a concept you haven't modeled yet. If the "invariant" truly is immediate, consider whether the aggregates should be merged or whether a new aggregate captures the relationship. But be cautious -- forming a new large-cluster aggregate to satisfy one use case often creates worse problems than it solves.

---

## Ask Whose Job It Is

When you're torn between transactional consistency and eventual consistency, use this heuristic from Eric Evans:

> **Is it the job of the user executing the use case to make this data consistent?**

- **If yes** -- the user expects the data to be immediately consistent as part of their action. Use transactional consistency (same aggregate).
- **If no** -- consistency is the system's job, or another user's responsibility. Use eventual consistency (separate aggregates, domain events).

### Examples

| Scenario                                                                        | Whose job?                                              | Consistency                                                                                |
| ------------------------------------------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| User adds a line item. Order total must not exceed spending limit.              | The user placing the order.                             | Transactional -- same aggregate.                                                           |
| User completes a task. Sprint burndown chart should update.                     | The system. The user doesn't manually update the chart. | Eventual -- separate aggregates, domain event.                                             |
| Team lead assigns a task to a member. Member's workload view should reflect it. | The system. The lead doesn't update the workload view.  | Eventual -- domain event.                                                                  |
| User transfers money between accounts. Both balances must change.               | The user initiating the transfer.                       | Transactional -- consider a `Transfer` aggregate or domain service within one transaction. |

This heuristic doesn't always give the final answer -- other forces (performance, technical limitations) matter too -- but it consistently reveals deeper understanding of the domain.

---

## BOTE Cost Estimation

Before committing to a specific aggregate design, run a back-of-the-envelope (BOTE) calculation to estimate the aggregate's runtime cost. This takes 15-30 minutes and can prevent costly redesigns later.

### The methodology

1. **Estimate collection sizes.** How many child objects will the aggregate hold in a typical case? In a worst case after months of use?
2. **Estimate per-request memory.** How many objects must be loaded for the most common operations?
3. **Identify concurrency hotspots.** Will multiple users modify the same aggregate instance simultaneously? How often?
4. **Calculate contention probability.** With N concurrent users operating on the same aggregate, what fraction of requests will hit optimistic concurrency failures?

### Example calculation

Scenario: A `BacklogItem` aggregate contains `Task` entities, each with an `EstimationLog` (value object collection).

```
Assumptions:
- Sprint length: 12 working days
- Tasks per backlog item: 12
- Estimation log entries per task: 12 (one per day)
- Total collected objects: 12 tasks x 12 logs = 144

Per-request analysis (daily estimation):
- Load: 1 backlog item + 12 tasks + 12 logs for 1 task = 25 objects
  (Tasks lazy-loaded as collection, only one task's logs loaded)
- Concurrency: One team member per task. No contention on the
  same task. Status transition only on the final estimation.

Verdict: 25 objects is reasonable. Contention is minimal because
different team members work on different tasks. Acceptable design.
```

If the numbers came back as 500+ objects per request, or multiple users regularly contending on the same instance, that signals a need to split the aggregate.

### When to split based on BOTE

- **Per-request object count > 100** -- consider splitting unless the invariant truly requires all objects.
- **Regular concurrent modifications by different users** -- split to eliminate contention.
- **Collection sizes growing unbounded over time** -- the aggregate will only get slower. Split now.
- **Multiple lazy-load hops** -- each adds query latency. Fewer hops means better performance.

---

## Reasons to Break the Rules

The four rules are rules of thumb, not absolutes. An experienced practitioner may break them for good reason.

### Reason 1: UI batch operations

A user interface allows creating multiple aggregates in a single gesture (e.g., batch-creating backlog items from a template). Creating multiple aggregate instances in one transaction is acceptable when:

- Each instance is a separate aggregate maintaining its own invariants.
- Creating them individually would produce the same result.
- No shared invariant spans the batch.

```typescript
@CommandHandler(PlanBatchOfTasksCommand)
export class PlanBatchOfTasksService implements ICommandHandler {
  constructor(
    @Inject(PROJECT_REPOSITORY)
    private readonly projectRepo: ProjectRepositoryPort,
    @Inject(TASK_REPOSITORY)
    private readonly taskRepo: TaskRepositoryPort,
  ) {}

  async execute(
    command: PlanBatchOfTasksCommand,
  ): Promise<Result<AggregateID[], Error>> {
    const project = await this.projectRepo.findOneByIdOrThrow(
      command.projectId,
    );

    const tasks = command.descriptions.map((desc) =>
      project.planTask(desc.summary, desc.type, desc.points),
    );

    await this.taskRepo.insertMany(tasks);
    return Ok(tasks.map((t) => t.id));
  }
}
```

This is semantically identical to creating each task individually -- the batch is a UI convenience, not a domain invariant.

### Reason 2: Lack of eventual consistency infrastructure

If the project has no messaging, no background workers, and no way to process events asynchronously, you may be forced to modify multiple aggregates in one transaction. Mitigate by:

- Checking for **user-aggregate affinity** -- if only one user works on a given set of aggregates at a time, contention is rare.
- Using optimistic concurrency on each aggregate to catch the rare conflict.
- Planning to introduce eventual consistency infrastructure as the system matures.

### Reason 3: Query performance

Holding a direct object reference (instead of an ID) to another aggregate can improve query performance when the two are almost always loaded together. Weigh this against the coupling and contention trade-offs. If you do this:

- Never modify the referenced aggregate through the reference.
- Mark the association as read-only in your persistence mapping.
- Document the trade-off so future developers understand why the rule was broken.

### Reason 4: Global transactions

Enterprise policies may mandate two-phase commit (distributed transactions). Even so, avoid modifying multiple aggregates in your local bounded context if possible. The global transaction constraint applies to cross-system coordination, not to your internal domain model design.

---

## Sources

- [Effective Aggregate Design Part I: Modeling a Single Aggregate](https://www.dddcommunity.org/wp-content/uploads/files/pdf_articles/Vernon_2011_1.pdf) -- Vaughn Vernon (2011)
- [Effective Aggregate Design Part II: Making Aggregates Work Together](https://www.dddcommunity.org/wp-content/uploads/files/pdf_articles/Vernon_2011_2.pdf) -- Vaughn Vernon (2011)
- [Effective Aggregate Design Part III: Gaining Insight Through Discovery](https://www.dddcommunity.org/wp-content/uploads/files/pdf_articles/Vernon_2011_3.pdf) -- Vaughn Vernon (2011)
- [Domain-Driven Design](https://www.domainlanguage.com/ddd/blue-book/) -- Eric Evans (2003), especially Chapter 6: Aggregates
- [Implementing Domain-Driven Design](https://openlibrary.org/works/OL17392277W) -- Vaughn Vernon (2013), Chapters 10-11
