# DDD Tactical Building Blocks

Implementation guide for the core domain building blocks in NestJS/TypeScript. Each section covers the concept, its rules, and a concrete code implementation.

## Table of Contents

- [Entity Base Class](#entity-base-class)
- [Value Object Base Class](#value-object-base-class)
- [Aggregate Root](#aggregate-root)
- [Domain Events](#domain-events)
- [Domain Services](#domain-services)
- [Domain Errors](#domain-errors)
- [Guards and Invariants](#guards-and-invariants)

---

**See also:** [LAYERS.md](LAYERS.md) for where each building block lives in the architecture, [DDD-STRATEGIC.md](DDD-STRATEGIC.md) for bounded context design, [CQRS-EVENTS.md](CQRS-EVENTS.md) for domain event flow and handling.

---

## Entity Base Class

Entities are objects with a persistent identity. Two entities are equal if they share the same ID, regardless of their other attributes.

### Rules

- Equality is determined by ID, not by attribute values.
- Entities protect their invariants -- invalid states should be impossible to construct.
- Entities contain business behavior, not just data. If your entity is a bag of getters/setters with logic living in services, you have an anemic domain model.
- Properties are partially immutable: `id` and `createdAt` never change after creation.
- Every entity declares an abstract `validate()` method to enforce its invariants.

### Implementation

```typescript
// src/libs/ddd/entity.base.ts

import { Guard } from '@libs/guard';
import {
  ArgumentNotProvidedException,
  ArgumentInvalidException,
  ArgumentOutOfRangeException,
} from '@libs/exceptions';

export type AggregateID = string;

export interface BaseEntityProps {
  id: AggregateID;
  createdAt: Date;
  updatedAt: Date;
}

export interface CreateEntityProps<EntityProps> {
  id: AggregateID;
  props: EntityProps;
  createdAt?: Date;
  updatedAt?: Date;
}

export abstract class Entity<EntityProps> {
  protected readonly props: EntityProps;
  protected abstract _id: AggregateID;
  private readonly _createdAt: Date;
  private _updatedAt: Date;

  constructor({
    id,
    createdAt,
    updatedAt,
    props,
  }: CreateEntityProps<EntityProps>) {
    this.setId(id);
    this.validateProps(props);
    const now = new Date();
    this._createdAt = createdAt || now;
    this._updatedAt = updatedAt || now;
    this.props = props;
    this.validate();
  }

  get id(): AggregateID {
    return this._id;
  }

  private setId(id: AggregateID): void {
    this._id = id;
  }

  get createdAt(): Date {
    return this._createdAt;
  }

  get updatedAt(): Date {
    return this._updatedAt;
  }

  static isEntity(entity: unknown): entity is Entity<unknown> {
    return entity instanceof Entity;
  }

  /**
   * Identity-based equality. Two entities are the same if they share an ID.
   */
  public equals(object?: Entity<EntityProps>): boolean {
    if (object === undefined) return false;
    if (this === object) return true;
    if (!Entity.isEntity(object)) return false;
    return this.id === object.id;
  }

  /**
   * Returns a frozen copy of all props including base entity fields.
   */
  public getProps(): EntityProps & BaseEntityProps {
    const propsCopy = {
      id: this._id,
      createdAt: this._createdAt,
      updatedAt: this._updatedAt,
      ...this.props,
    };
    return Object.freeze(propsCopy);
  }

  /**
   * Converts nested domain objects to plain values for serialization.
   */
  public toObject(): unknown {
    const plainProps = convertPropsToObject(this.props);
    const result = {
      id: this._id,
      createdAt: this._createdAt,
      updatedAt: this._updatedAt,
      ...plainProps,
    };
    return Object.freeze(result);
  }

  /**
   * Override to enforce business invariants. Called on construction.
   * Throw if the entity is in an invalid state.
   */
  public abstract validate(): void;

  private validateProps(props: EntityProps): void {
    const MAX_PROPS = 50;
    if (Guard.isEmpty(props)) {
      throw new ArgumentNotProvidedException(
        'Entity props should not be empty',
      );
    }
    if (typeof props !== 'object') {
      throw new ArgumentInvalidException('Entity props should be an object');
    }
    if (Object.keys(props as Record<string, unknown>).length > MAX_PROPS) {
      throw new ArgumentOutOfRangeException(
        `Entity props should not have more than ${MAX_PROPS} properties`,
      );
    }
  }
}

function convertPropsToObject(props: unknown): unknown {
  const propsCopy = structuredClone(props);
  for (const prop in propsCopy as Record<string, unknown>) {
    const value = (propsCopy as Record<string, unknown>)[prop];
    if (value && typeof value === 'object' && 'unpack' in value) {
      (propsCopy as Record<string, unknown>)[prop] = (
        value as { unpack(): unknown }
      ).unpack();
    }
  }
  return propsCopy;
}
```

### Usage Example

```typescript
// src/modules/user/domain/user.types.ts
import { Address } from './value-objects/address.value-object';

export enum UserRoles {
  admin = 'admin',
  moderator = 'moderator',
  guest = 'guest',
}

export interface UserProps {
  email: string;
  role: UserRoles;
  address: Address;
}

export interface CreateUserProps {
  email: string;
  address: Address;
}
```

---

## Value Object Base Class

Value Objects are immutable objects defined entirely by their attributes. Two value objects with the same properties are equal. They have no identity of their own.

### Rules

- Immutable -- never expose setters. Create a new instance when you need different values.
- Equality by structure, not by reference.
- Self-validating via an abstract `validate()` method.
- Can represent either a composite (like `Address`) or a single domain primitive (like `Email`).

### When to use Value Objects vs plain types

Be pragmatic. Not every string needs a Value Object wrapper. Use VOs when:

- The value has validation rules (email format, postal code pattern).
- The value has behavior (money arithmetic, address formatting).
- Multiple fields form a conceptual unit (street + city + postalCode = Address).
- You want to replace primitive obsession with domain language.

Skip VOs for values with no special rules and no behavior -- a plain `string` property on an entity is fine in those cases.

### Implementation

```typescript
// src/libs/ddd/value-object.base.ts

import { Guard } from '@libs/guard';
import { ArgumentNotProvidedException } from '@libs/exceptions';

export type Primitives = string | number | boolean;

export interface DomainPrimitive<T extends Primitives | Date> {
  value: T;
}

type ValueObjectProps<T> = T extends Primitives | Date ? DomainPrimitive<T> : T;

export abstract class ValueObject<T> {
  protected readonly props: ValueObjectProps<T>;

  constructor(props: ValueObjectProps<T>) {
    this.checkIfEmpty(props);
    this.validate(props);
    this.props = props;
  }

  protected abstract validate(props: ValueObjectProps<T>): void;

  static isValueObject(obj: unknown): obj is ValueObject<unknown> {
    return obj instanceof ValueObject;
  }

  /**
   * Structural equality -- two VOs with the same data are equal.
   */
  public equals(vo?: ValueObject<T>): boolean {
    if (vo === undefined) return false;
    return JSON.stringify(this) === JSON.stringify(vo);
  }

  /**
   * Extract the raw value. For domain primitives returns the inner value;
   * for composite VOs returns a frozen plain object.
   */
  public unpack(): T {
    if (this.isDomainPrimitive(this.props)) {
      return this.props.value;
    }
    const propsCopy = structuredClone(this.props);
    return Object.freeze(propsCopy) as T;
  }

  private checkIfEmpty(props: ValueObjectProps<T>): void {
    if (
      Guard.isEmpty(props) ||
      (this.isDomainPrimitive(props) && Guard.isEmpty(props.value))
    ) {
      throw new ArgumentNotProvidedException('Property cannot be empty');
    }
  }

  private isDomainPrimitive(
    obj: unknown,
  ): obj is DomainPrimitive<T & (Primitives | Date)> {
    return Object.prototype.hasOwnProperty.call(obj, 'value');
  }
}
```

### Example: Composite Value Object

```typescript
// src/modules/user/domain/value-objects/address.value-object.ts

import { ValueObject } from '@libs/ddd';
import { ArgumentInvalidException } from '@libs/exceptions';
import { Guard } from '@libs/guard';

export interface AddressProps {
  country: string;
  postalCode: string;
  street: string;
}

export class Address extends ValueObject<AddressProps> {
  get country(): string {
    return this.props.country;
  }

  get postalCode(): string {
    return this.props.postalCode;
  }

  get street(): string {
    return this.props.street;
  }

  protected validate(props: AddressProps): void {
    if (Guard.isEmpty(props.country)) {
      throw new ArgumentInvalidException('Country cannot be empty');
    }
    if (Guard.isEmpty(props.street)) {
      throw new ArgumentInvalidException('Street cannot be empty');
    }
    if (props.postalCode.length < 3 || props.postalCode.length > 10) {
      throw new ArgumentInvalidException(
        'Postal code must be between 3 and 10 characters',
      );
    }
  }
}
```

### Example: Domain Primitive

```typescript
// Domain primitive wrapping a single value with validation

import { ValueObject, DomainPrimitive } from '@libs/ddd';
import { ArgumentInvalidException } from '@libs/exceptions';

export class Email extends ValueObject<string> {
  get value(): string {
    return this.props.value;
  }

  protected validate({ value }: DomainPrimitive<string>): void {
    if (!value.includes('@')) {
      throw new ArgumentInvalidException('Email must contain @');
    }
  }
}
```

Domain primitives give semantic meaning and validation to values that would otherwise be raw strings or numbers. Instead of passing `email: string` everywhere and hoping someone validated it, `Email` guarantees validity on construction.

---

## Aggregate Root

An Aggregate Root is an entity that acts as the entry point and consistency boundary for a cluster of related domain objects. It extends `Entity` and adds domain event collection.

### Rules

- Only aggregate roots are directly retrievable from repositories. Child entities are accessed through the root.
- One aggregate per transaction. Cross-aggregate consistency is achieved through domain events (eventual consistency).
- External references to objects inside an aggregate must go through the root and use IDs, not direct object references.
- Keep aggregates small. If an aggregate has more than ~10 entities, it's probably too big -- split it.
- **Favor value objects over child entities.** When a composed part can be completely replaced rather than mutated in place, model it as a value object. In well-designed models, roughly 70% of aggregates are root-entity-only with value-typed properties. Value objects are cheaper to persist (serialized with the root), immutable (fewer bugs), and easier to test.
- Aggregates publish domain events to signal that something important happened.

For detailed guidance on designing aggregate boundaries -- identifying true invariants, sizing aggregates, and deciding when to split -- see [AGGREGATE-DESIGN.md](AGGREGATE-DESIGN.md).

### Implementation

```typescript
// src/libs/ddd/aggregate-root.base.ts

import { Entity } from './entity.base';
import { DomainEvent } from './domain-event.base';
import { EventEmitter2 } from '@nestjs/event-emitter';
import { LoggerPort } from '@libs/ports/logger.port';

export abstract class AggregateRoot<EntityProps> extends Entity<EntityProps> {
  private _domainEvents: DomainEvent[] = [];

  get domainEvents(): DomainEvent[] {
    return this._domainEvents;
  }

  protected addEvent(domainEvent: DomainEvent): void {
    this._domainEvents.push(domainEvent);
  }

  public clearEvents(): void {
    this._domainEvents = [];
  }

  /**
   * Called by the repository after successful persistence.
   * Publishes all accumulated events then clears the list.
   */
  public async publishEvents(
    logger: LoggerPort,
    eventEmitter: EventEmitter2,
  ): Promise<void> {
    await Promise.all(
      this.domainEvents.map(async (event) => {
        logger.debug(
          `"${event.constructor.name}" event published for aggregate ${this.constructor.name} : ${this.id}`,
        );
        return eventEmitter.emitAsync(event.constructor.name, event);
      }),
    );
    this.clearEvents();
  }
}
```

### Example: Aggregate Root Entity

```typescript
// src/modules/user/domain/user.entity.ts

import { AggregateRoot, AggregateID } from '@libs/ddd';
import { UserCreatedDomainEvent } from './events/user-created.domain-event';
import { UserDeletedDomainEvent } from './events/user-deleted.domain-event';
import { UserRoleChangedDomainEvent } from './events/user-role-changed.domain-event';
import { UserAddressUpdatedDomainEvent } from './events/user-address-updated.domain-event';
import { Address, AddressProps } from './value-objects/address.value-object';
import {
  CreateUserProps,
  UpdateUserAddressProps,
  UserProps,
  UserRoles,
} from './user.types';
import { randomUUID } from 'crypto';

export class UserEntity extends AggregateRoot<UserProps> {
  protected readonly _id: AggregateID;

  /**
   * Factory method. Preferred over calling the constructor directly
   * because it encapsulates creation logic and emits the creation event.
   */
  static create(create: CreateUserProps): UserEntity {
    const id = randomUUID();
    const props: UserProps = { ...create, role: UserRoles.guest };
    const user = new UserEntity({ id, props });
    user.addEvent(
      new UserCreatedDomainEvent({
        aggregateId: id,
        email: props.email,
        ...props.address.unpack(),
      }),
    );
    return user;
  }

  get role(): UserRoles {
    return this.props.role;
  }

  makeAdmin(): void {
    this.addEvent(
      new UserRoleChangedDomainEvent({
        aggregateId: this.id,
        oldRole: this.props.role,
        newRole: UserRoles.admin,
      }),
    );
    this.props.role = UserRoles.admin;
  }

  makeModerator(): void {
    this.addEvent(
      new UserRoleChangedDomainEvent({
        aggregateId: this.id,
        oldRole: this.props.role,
        newRole: UserRoles.moderator,
      }),
    );
    this.props.role = UserRoles.moderator;
  }

  delete(): void {
    this.addEvent(new UserDeletedDomainEvent({ aggregateId: this.id }));
  }

  updateAddress(props: UpdateUserAddressProps): void {
    const newAddress = new Address({
      ...this.props.address.unpack(),
      ...props,
    } as AddressProps);

    this.props.address = newAddress;

    this.addEvent(
      new UserAddressUpdatedDomainEvent({
        aggregateId: this.id,
        country: newAddress.country,
        street: newAddress.street,
        postalCode: newAddress.postalCode,
      }),
    );
  }

  validate(): void {
    // Enforce aggregate-level invariants.
    // Example: a user must always have a valid email and address.
  }
}
```

Notice how every state mutation emits a domain event. The entity controls its own transitions -- no external service reaches in and sets properties directly.

---

## Domain Events

A Domain Event records that something meaningful happened within the domain. Events are named in the past tense (`UserCreated`, `OrderPlaced`) and carry the data needed by handlers.

### Rules

- Events are immutable data carriers. Once created, they never change.
- Named in past tense reflecting what happened in the business domain.
- Carry metadata: unique ID, aggregate ID, timestamp, and correlation/causation IDs for tracing.
- Published by the repository after successful persistence, not before.
- Handlers can live in the same module or in other modules (cross-aggregate side effects).

### Implementation

```typescript
// src/libs/ddd/domain-event.base.ts

import { randomUUID } from 'crypto';
import { Guard } from '@libs/guard';
import { ArgumentNotProvidedException } from '@libs/exceptions';

type DomainEventMetadata = {
  readonly timestamp: number;
  readonly correlationId: string;
  readonly causationId?: string;
  readonly userId?: string;
};

export type DomainEventProps<T> = Omit<T, 'id' | 'metadata'> & {
  aggregateId: string;
  metadata?: DomainEventMetadata;
};

export abstract class DomainEvent {
  public readonly id: string;
  public readonly aggregateId: string;
  public readonly metadata: DomainEventMetadata;

  constructor(props: DomainEventProps<unknown>) {
    if (Guard.isEmpty(props)) {
      throw new ArgumentNotProvidedException(
        'DomainEvent props should not be empty',
      );
    }
    this.id = randomUUID();
    this.aggregateId = props.aggregateId;
    this.metadata = {
      correlationId: props?.metadata?.correlationId || randomUUID(),
      causationId: props?.metadata?.causationId,
      timestamp: props?.metadata?.timestamp || Date.now(),
      userId: props?.metadata?.userId,
    };
  }
}
```

### Example: Concrete Domain Event

```typescript
// src/modules/user/domain/events/user-created.domain-event.ts

import { DomainEvent, DomainEventProps } from '@libs/ddd';

export class UserCreatedDomainEvent extends DomainEvent {
  readonly email: string;
  readonly country: string;
  readonly postalCode: string;
  readonly street: string;

  constructor(props: DomainEventProps<UserCreatedDomainEvent>) {
    super(props);
    this.email = props.email;
    this.country = props.country;
    this.postalCode = props.postalCode;
    this.street = props.street;
  }
}
```

### Event Handler Example

```typescript
// src/modules/wallet/application/event-handlers/create-wallet-when-user-is-created.domain-event-handler.ts

import { OnEvent } from '@nestjs/event-emitter';
import { Inject, Injectable } from '@nestjs/common';
import { UserCreatedDomainEvent } from '@modules/user/domain/events/user-created.domain-event';
import { WALLET_REPOSITORY } from '../../wallet.di-tokens';
import { WalletRepositoryPort } from '../../database/wallet.repository.port';
import { WalletEntity } from '../../domain/wallet.entity';

@Injectable()
export class CreateWalletWhenUserIsCreatedHandler {
  constructor(
    @Inject(WALLET_REPOSITORY)
    private readonly walletRepo: WalletRepositoryPort,
  ) {}

  @OnEvent(UserCreatedDomainEvent.name, { async: true, promisify: true })
  async handle(event: UserCreatedDomainEvent): Promise<void> {
    const wallet = WalletEntity.create({ userId: event.aggregateId });
    await this.walletRepo.insert(wallet);
  }
}
```

This pattern decouples the User module from the Wallet module. The User aggregate publishes the event; the Wallet module reacts to it independently.

### Domain Events vs Integration Events

| Aspect          | Domain Event                                                | Integration Event                                               |
| --------------- | ----------------------------------------------------------- | --------------------------------------------------------------- |
| Scope           | In-process, same bounded context or application             | Cross-process, between microservices                            |
| Transport       | In-memory event emitter (`EventEmitter2`)                   | Message broker (RabbitMQ, Kafka, SQS)                           |
| Reliability     | Synchronous or async within same process                    | Requires outbox pattern for at-least-once delivery              |
| Naming          | `UserCreatedDomainEvent`                                    | `UserCreatedIntegrationEvent`                                   |
| When to publish | After domain event handlers finish + DB transaction commits | After all domain events are processed and changes are persisted |

If a domain event handler needs to notify an external system, it should publish an integration event rather than making the external call directly. See [CQRS-EVENTS.md](CQRS-EVENTS.md) for the outbox pattern.

---

## Domain Services

A Domain Service encapsulates business logic that doesn't naturally fit within a single entity or value object. Typically this is logic that spans multiple aggregates or requires coordination.

### Rules

- Stateless. Domain services hold no state between calls.
- Operate only on domain objects (entities, VOs, other domain services).
- Named using ubiquitous language terms (`PricingService`, `ShippingCostCalculator`).
- Injected into command handlers, never into controllers directly.
- If the logic can live on an entity, put it there. Domain services are for cross-aggregate or genuinely stateless operations.

### Example

```typescript
// src/modules/order/domain/pricing.domain-service.ts

import { OrderEntity } from './order.entity';
import { DiscountPolicy } from './discount-policy.value-object';

export class PricingDomainService {
  /**
   * Applies a discount policy across an order's line items.
   * This logic spans the Order aggregate and external discount rules.
   */
  static calculateTotal(order: OrderEntity, discount: DiscountPolicy): number {
    const subtotal = order.lineItems.reduce(
      (sum, item) => sum + item.price * item.quantity,
      0,
    );
    return discount.apply(subtotal);
  }
}
```

Domain services can be static classes (when they need no injected dependencies) or injectable classes (when they need ports). If a domain service depends on an external resource, inject the port interface -- not the concrete adapter.

---

## Domain Errors

Domain errors represent business rule violations that are expected and recoverable. They are distinct from infrastructure errors (database connection failed, out of memory) which should be thrown as exceptions.

### Result Pattern

Use a `Result<T, E>` type to make errors explicit in return types. This forces callers to handle every possible error rather than relying on try/catch for control flow.

```typescript
// src/modules/user/domain/user.errors.ts

import { ExceptionBase } from '@libs/exceptions';

export class UserAlreadyExistsError extends ExceptionBase {
  static readonly message = 'User already exists';
  readonly code = 'USER.ALREADY_EXISTS';

  constructor(cause?: Error, metadata?: unknown) {
    super(UserAlreadyExistsError.message, cause, metadata);
  }
}

export class UserNotFoundError extends ExceptionBase {
  static readonly message = 'User not found';
  readonly code = 'USER.NOT_FOUND';

  constructor(cause?: Error, metadata?: unknown) {
    super(UserNotFoundError.message, cause, metadata);
  }
}
```

### Base Exception

```typescript
// src/libs/exceptions/exception.base.ts

export interface SerializedException {
  message: string;
  code: string;
  correlationId: string;
  stack?: string;
  cause?: string;
  metadata?: unknown;
}

export abstract class ExceptionBase extends Error {
  abstract code: string;

  constructor(
    readonly message: string,
    readonly cause?: Error,
    readonly metadata?: unknown,
  ) {
    super(message);
    Error.captureStackTrace(this, this.constructor);
  }

  toJSON(): SerializedException {
    return {
      message: this.message,
      code: this.code,
      stack: this.stack,
      cause: this.cause?.message,
      metadata: this.metadata,
      correlationId: '',
    };
  }
}
```

### Using Result in Command Handlers

```typescript
import { Err, Ok, Result } from 'oxide.ts';

async execute(
  command: CreateUserCommand,
): Promise<Result<AggregateID, UserAlreadyExistsError>> {
  const user = UserEntity.create({ /* ... */ });

  try {
    await this.userRepo.transaction(async () => this.userRepo.insert(user));
    return Ok(user.id);
  } catch (error: unknown) {
    if (error instanceof ConflictException) {
      return Err(new UserAlreadyExistsError(error));
    }
    throw error;
  }
}
```

### Mapping Errors to HTTP in Controllers

```typescript
import { match } from 'oxide.ts';

const result = await this.commandBus.execute(command);

return match(result, {
  Ok: (id: string) => new IdResponse(id),
  Err: (error: Error) => {
    if (error instanceof UserAlreadyExistsError) {
      throw new ConflictHttpException(error.message);
    }
    if (error instanceof UserNotFoundError) {
      throw new NotFoundException(error.message);
    }
    throw error;
  },
});
```

### When to return vs throw

| Situation                                                           | Approach                                                          |
| ------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Business rule violation (user already exists, insufficient balance) | Return `Err(...)` -- recoverable, expected                        |
| Infrastructure failure (DB down, network timeout)                   | Throw exception -- unrecoverable, exceptional                     |
| Invalid domain state (entity invariant violated)                    | Throw in `validate()` -- this is a bug, fail fast                 |
| Input validation failure                                            | Throw in DTO validation (class-validator) -- never reaches domain |

---

## Guards and Invariants

Validation happens at two tiers. The first is **input validation** at the boundary (DTOs). The second is **guarding** inside domain objects to enforce invariants.

### Tier 1: Input Validation (DTOs)

Uses `class-validator` decorators on request DTOs. This is filtration -- rejecting obviously bad input before it reaches the domain.

```typescript
// src/modules/user/commands/create-user/create-user.request.dto.ts

import { IsEmail, IsString, MaxLength, MinLength } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

export class CreateUserRequestDto {
  @ApiProperty({ example: 'john@example.com' })
  @IsEmail()
  readonly email: string;

  @ApiProperty({ example: 'United States' })
  @IsString()
  @MinLength(2)
  @MaxLength(50)
  readonly country: string;

  @ApiProperty({ example: '12345' })
  @IsString()
  @MinLength(3)
  @MaxLength(10)
  readonly postalCode: string;

  @ApiProperty({ example: '123 Main St' })
  @IsString()
  @MinLength(2)
  @MaxLength(100)
  readonly street: string;
}
```

### Tier 2: Domain Guards (Invariants)

Guards are the last line of defense inside domain objects. They catch programming errors -- situations where validated data still violates a business rule.

```typescript
// src/libs/guard.ts

export class Guard {
  static isEmpty(value: unknown): boolean {
    if (value === undefined) return true;
    if (typeof value === 'string' && value.trim().length === 0) return true;
    if (typeof value === 'number' && isNaN(value)) return true;
    if (Array.isArray(value) && value.length === 0) return true;
    if (
      typeof value === 'object' &&
      value !== undefined &&
      Object.keys(value).length === 0
    )
      return true;
    return false;
  }

  static isNegative(value: number): boolean {
    return value < 0;
  }

  static lengthIsBetween(
    value: string | unknown[],
    min: number,
    max: number,
  ): boolean {
    return value.length >= min && value.length <= max;
  }

  static isInRange(value: number, min: number, max: number): boolean {
    return value >= min && value <= max;
  }
}
```

### Guarding vs Validating

The distinction matters for how you handle violations:

- **Validation** (DTOs): external input filtering. Invalid input is expected and handled gracefully with error messages. Nothing exceptional about a user submitting a bad email.
- **Guarding** (domain objects): internal failsafe. If a guard fails, it means a bug got past the validation layer. Guards throw exceptions immediately -- fail fast to surface the problem.

Domain objects should always guard themselves. Even if you trust your validation layer, defensive programming in the domain catches bugs that validation missed. The cost is minimal (a few `if` checks) and the protection is significant.

### Using guards in value objects

```typescript
export class Address extends ValueObject<AddressProps> {
  protected validate(props: AddressProps): void {
    if (Guard.isEmpty(props.country)) {
      throw new ArgumentInvalidException('Country cannot be empty');
    }
    if (Guard.isEmpty(props.street)) {
      throw new ArgumentInvalidException('Street cannot be empty');
    }
    if (!Guard.lengthIsBetween(props.postalCode, 3, 10)) {
      throw new ArgumentInvalidException(
        'Postal code must be between 3 and 10 characters',
      );
    }
  }
}
```

The validation in the DTO checks format (is it a string? is it at least N characters?). The guard in the value object checks domain meaning (does a postal code make sense with 2 characters? No -- the business says minimum 3).
