# Testing Strategies

Testing guidance for each layer of the NestJS DDD + Hexagonal architecture. The architecture's clean boundaries make testing straightforward -- each layer has a natural testing strategy.

## Table of Contents

- [Testing Pyramid](#testing-pyramid)
- [Domain Layer Unit Tests](#domain-layer-unit-tests)
- [Application Layer Unit Tests](#application-layer-unit-tests)
- [Integration Tests](#integration-tests)
- [E2E / Behavioral Tests](#e2e--behavioral-tests)
- [Architecture Tests](#architecture-tests)
- [Test Fixtures and Builders](#test-fixtures-and-builders)

---

**See also:** [HEXAGONAL-NESTJS.md](HEXAGONAL-NESTJS.md) for in-memory adapter examples used in tests, [DDD-TACTICAL.md](DDD-TACTICAL.md) for the domain classes being tested, [PRISMA-ADAPTER.md](PRISMA-ADAPTER.md) for repository implementations tested in integration tests.

---

## Testing Pyramid

```mermaid
graph TB
  subgraph pyramid ["Testing Pyramid"]
    E2E["E2E / Behavioral Tests<br/>(few, slow, high confidence)"]
    Integration["Integration Tests<br/>(moderate, real DB)"]
    AppUnit["Application Unit Tests<br/>(many, mock ports)"]
    DomainUnit["Domain Unit Tests<br/>(most, fastest, no mocks)"]
  end

  E2E --- Integration
  Integration --- AppUnit
  AppUnit --- DomainUnit
```

| Layer       | What to Test                               | Mocks?            | Speed    | Volume     |
| ----------- | ------------------------------------------ | ----------------- | -------- | ---------- |
| Domain      | Entities, VOs, aggregates, domain services | None              | Fastest  | Most tests |
| Application | Command/query handlers, event handlers     | Mock driven ports | Fast     | Many tests |
| Integration | Repositories, mappers, full command flows  | Real DB           | Moderate | Some tests |
| E2E         | Full HTTP request → response cycle         | Real everything   | Slowest  | Few tests  |

### Key Principle

**If domain tests need mocks, your domain has leaked dependencies.** Domain objects are plain TypeScript classes with no I/O -- they should be testable with `new Entity(...)` and method calls. If you find yourself mocking something in a domain test, the dependency rule is violated.

---

## Domain Layer Unit Tests

Pure TypeScript tests. No NestJS test utilities, no DI container, no database.

### Test Directory Structure

```
tests/
├── unit/
│   └── modules/
│       └── user/
│           ├── domain/
│           │   ├── user.entity.spec.ts
│           │   └── value-objects/
│           │       └── address.value-object.spec.ts
│           └── ...
```

Or co-located with the source:

```
src/modules/user/domain/
├── user.entity.ts
├── user.entity.spec.ts          # co-located test
├── value-objects/
│   ├── address.value-object.ts
│   └── address.value-object.spec.ts
```

### Entity Creation Tests

```typescript
// user.entity.spec.ts

import { UserEntity } from '@modules/user/domain/user.entity';
import { Address } from '@modules/user/domain/value-objects/address.value-object';
import { UserRoles } from '@modules/user/domain/user.types';

describe('UserEntity', () => {
  const validAddress = new Address({
    country: 'United States',
    postalCode: '10001',
    street: '123 Main St',
  });

  describe('create', () => {
    it('should create a user with guest role by default', () => {
      const user = UserEntity.create({
        email: 'john@example.com',
        address: validAddress,
      });

      expect(user.id).toBeDefined();
      expect(user.role).toBe(UserRoles.guest);
      expect(user.getProps().email).toBe('john@example.com');
    });

    it('should emit a UserCreatedDomainEvent', () => {
      const user = UserEntity.create({
        email: 'john@example.com',
        address: validAddress,
      });

      expect(user.domainEvents).toHaveLength(1);
      expect(user.domainEvents[0].constructor.name).toBe(
        'UserCreatedDomainEvent',
      );
    });
  });

  describe('makeAdmin', () => {
    it('should change role to admin and emit event', () => {
      const user = UserEntity.create({
        email: 'john@example.com',
        address: validAddress,
      });
      user.clearEvents();

      user.makeAdmin();

      expect(user.role).toBe(UserRoles.admin);
      expect(user.domainEvents).toHaveLength(1);
      expect(user.domainEvents[0].constructor.name).toBe(
        'UserRoleChangedDomainEvent',
      );
    });
  });

  describe('updateAddress', () => {
    it('should update the address and emit event', () => {
      const user = UserEntity.create({
        email: 'john@example.com',
        address: validAddress,
      });
      user.clearEvents();

      user.updateAddress({ country: 'Canada' });

      const props = user.getProps();
      expect(props.address.country).toBe('Canada');
      expect(props.address.street).toBe('123 Main St');
      expect(user.domainEvents).toHaveLength(1);
    });
  });
});
```

### Value Object Tests

```typescript
// address.value-object.spec.ts

import { Address } from '@modules/user/domain/value-objects/address.value-object';
import { ArgumentInvalidException } from '@libs/exceptions';

describe('Address', () => {
  it('should create a valid address', () => {
    const address = new Address({
      country: 'United States',
      postalCode: '10001',
      street: '123 Main St',
    });

    expect(address.country).toBe('United States');
    expect(address.postalCode).toBe('10001');
    expect(address.street).toBe('123 Main St');
  });

  it('should reject empty country', () => {
    expect(
      () =>
        new Address({
          country: '',
          postalCode: '10001',
          street: '123 Main St',
        }),
    ).toThrow(ArgumentInvalidException);
  });

  it('should reject postal code outside 3-10 characters', () => {
    expect(
      () =>
        new Address({
          country: 'United States',
          postalCode: 'AB',
          street: '123 Main St',
        }),
    ).toThrow(ArgumentInvalidException);
  });

  it('should support structural equality', () => {
    const a = new Address({
      country: 'US',
      postalCode: '10001',
      street: '123 Main',
    });
    const b = new Address({
      country: 'US',
      postalCode: '10001',
      street: '123 Main',
    });

    expect(a.equals(b)).toBe(true);
  });

  it('should unpack to a plain object', () => {
    const address = new Address({
      country: 'US',
      postalCode: '10001',
      street: '123 Main',
    });

    const unpacked = address.unpack();
    expect(unpacked).toEqual({
      country: 'US',
      postalCode: '10001',
      street: '123 Main',
    });
  });
});
```

### What to Test in the Domain Layer

| Test                               | What It Validates                                  |
| ---------------------------------- | -------------------------------------------------- |
| Entity creation with valid props   | Factory method works, default values set correctly |
| Entity creation with invalid props | Invariants enforced, exceptions thrown             |
| Business method behavior           | State changes correctly, returns expected results  |
| Domain event emission              | Correct events emitted with correct data           |
| Value object validation            | Rejects invalid values, accepts valid ones         |
| Value object equality              | Structural comparison works                        |
| Aggregate invariants               | Cross-entity rules enforced                        |

---

## Application Layer Unit Tests

Test command/query handlers by mocking the driven ports (repositories, external services). Use NestJS `Test.createTestingModule()` or plain instantiation.

### With NestJS Test Module

```typescript
// create-user.service.spec.ts

import { Test } from '@nestjs/testing';
import { CreateUserService } from '@modules/user/commands/create-user/create-user.service';
import { USER_REPOSITORY } from '@modules/user/user.di-tokens';
import { UserRepositoryPort } from '@modules/user/database/user.repository.port';
import { CreateUserCommand } from '@modules/user/commands/create-user/create-user.command';
import { ConflictException } from '@libs/exceptions';

describe('CreateUserService', () => {
  let service: CreateUserService;
  let userRepo: jest.Mocked<UserRepositoryPort>;

  beforeEach(async () => {
    const mockRepo: jest.Mocked<UserRepositoryPort> = {
      insert: jest.fn(),
      findOneById: jest.fn(),
      findOneByEmail: jest.fn(),
      findAll: jest.fn(),
      findAllPaginated: jest.fn(),
      delete: jest.fn(),
      transaction: jest.fn((handler) => handler()),
    };

    const module = await Test.createTestingModule({
      providers: [
        CreateUserService,
        { provide: USER_REPOSITORY, useValue: mockRepo },
      ],
    }).compile();

    service = module.get(CreateUserService);
    userRepo = module.get(USER_REPOSITORY);
  });

  it('should create a user and return Ok with ID', async () => {
    const command = new CreateUserCommand({
      email: 'john@example.com',
      country: 'United States',
      postalCode: '10001',
      street: '123 Main St',
    });

    const result = await service.execute(command);

    expect(result.isOk()).toBe(true);
    expect(userRepo.insert).toHaveBeenCalledTimes(1);
    expect(userRepo.transaction).toHaveBeenCalledTimes(1);
  });

  it('should return Err when user already exists', async () => {
    userRepo.insert.mockRejectedValueOnce(
      new ConflictException('Record already exists'),
    );

    const command = new CreateUserCommand({
      email: 'existing@example.com',
      country: 'United States',
      postalCode: '10001',
      street: '123 Main St',
    });

    const result = await service.execute(command);

    expect(result.isErr()).toBe(true);
  });
});
```

### With In-Memory Repository

For more realistic tests, use the `InMemoryUserRepository` from [HEXAGONAL-NESTJS.md](HEXAGONAL-NESTJS.md):

```typescript
describe('CreateUserService (in-memory)', () => {
  let service: CreateUserService;
  let userRepo: InMemoryUserRepository;

  beforeEach(async () => {
    userRepo = new InMemoryUserRepository();

    const module = await Test.createTestingModule({
      providers: [
        CreateUserService,
        { provide: USER_REPOSITORY, useValue: userRepo },
      ],
    }).compile();

    service = module.get(CreateUserService);
  });

  it('should persist the user', async () => {
    const command = new CreateUserCommand({
      email: 'john@example.com',
      country: 'US',
      postalCode: '10001',
      street: '123 Main St',
    });

    const result = await service.execute(command);
    const userId = result.unwrap();

    const savedUser = await userRepo.findOneById(userId);
    expect(savedUser).toBeDefined();
    expect(savedUser!.getProps().email).toBe('john@example.com');
  });
});
```

In-memory repositories give you real collection behavior (duplicate detection, pagination) without the overhead of a database.

---

## Integration Tests

Test the real persistence layer with a real database. These verify that repositories, mappers, and Prisma queries work correctly.

### Setup: Docker Compose

```yaml
# docker/docker-compose.test.yml

services:
  postgres-test:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
      POSTGRES_DB: myapp_test
    ports:
      - '5433:5432'
    tmpfs:
      - /var/lib/postgresql/data
```

Using `tmpfs` keeps the test database entirely in memory for speed.

### Jest Global Setup

```typescript
// tests/setup/jest-global-setup.ts

import { execSync } from 'child_process';

export default async function globalSetup(): Promise<void> {
  process.env.DATABASE_URL =
    'postgresql://test:test@localhost:5433/myapp_test?schema=public';
  execSync('npx prisma migrate deploy', { stdio: 'inherit' });
}
```

### Jest Config

```json
// jest-e2e.json
{
  "moduleFileExtensions": ["js", "json", "ts"],
  "rootDir": ".",
  "testRegex": ".e2e-spec.ts$",
  "transform": { "^.+\\.(t|j)s$": "ts-jest" },
  "globalSetup": "./tests/setup/jest-global-setup.ts",
  "setupFilesAfterSetup": ["./tests/setup/jest-setup-after-env.ts"]
}
```

### Database Cleanup

```typescript
// tests/setup/jest-setup-after-env.ts

import { PrismaClient } from '@generated/prisma';

const prisma = new PrismaClient();

afterEach(async () => {
  // Truncate all tables between tests
  const tablenames = await prisma.$queryRaw<
    Array<{ tablename: string }>
  >`SELECT tablename FROM pg_tables WHERE schemaname='public'`;

  for (const { tablename } of tablenames) {
    if (tablename !== '_prisma_migrations') {
      await prisma.$executeRawUnsafe(
        `TRUNCATE TABLE "public"."${tablename}" CASCADE;`,
      );
    }
  }
});

afterAll(async () => {
  await prisma.$disconnect();
});
```

### Repository Integration Test

```typescript
// tests/integration/user.repository.spec.ts

import { Test } from '@nestjs/testing';
import { PrismaService } from '@libs/db/prisma.service';
import { UserRepository } from '@modules/user/database/user.repository';
import { UserMapper } from '@modules/user/user.mapper';
import { UserEntity } from '@modules/user/domain/user.entity';
import { Address } from '@modules/user/domain/value-objects/address.value-object';
import { EventEmitter2 } from '@nestjs/event-emitter';
import { Logger } from '@nestjs/common';
import { USER_LOGGER } from '@modules/user/user.di-tokens';

describe('UserRepository (integration)', () => {
  let repository: UserRepository;
  let prisma: PrismaService;

  beforeAll(async () => {
    const module = await Test.createTestingModule({
      providers: [
        PrismaService,
        UserMapper,
        EventEmitter2,
        { provide: USER_LOGGER, useValue: new Logger('Test') },
        UserRepository,
      ],
    }).compile();

    repository = module.get(UserRepository);
    prisma = module.get(PrismaService);
  });

  afterAll(async () => {
    await prisma.$disconnect();
  });

  it('should insert and retrieve a user', async () => {
    const user = UserEntity.create({
      email: 'integration@example.com',
      address: new Address({
        country: 'United States',
        postalCode: '10001',
        street: '123 Main St',
      }),
    });

    await repository.insert(user);

    const found = await repository.findOneById(user.id);
    expect(found).toBeDefined();
    expect(found!.getProps().email).toBe('integration@example.com');
  });

  it('should find a user by email', async () => {
    const user = UserEntity.create({
      email: 'findme@example.com',
      address: new Address({
        country: 'US',
        postalCode: '10001',
        street: '456 Oak Ave',
      }),
    });

    await repository.insert(user);

    const found = await repository.findOneByEmail('findme@example.com');
    expect(found).toBeDefined();
    expect(found!.id).toBe(user.id);
  });

  it('should throw ConflictException on duplicate email', async () => {
    const user1 = UserEntity.create({
      email: 'duplicate@example.com',
      address: new Address({ country: 'US', postalCode: '10001', street: 'A' }),
    });
    const user2 = UserEntity.create({
      email: 'duplicate@example.com',
      address: new Address({ country: 'CA', postalCode: '20002', street: 'B' }),
    });

    await repository.insert(user1);
    await expect(repository.insert(user2)).rejects.toThrow(
      'Record already exists',
    );
  });
});
```

### HTTP-Level Integration Test

```typescript
// tests/integration/create-user.e2e-spec.ts

import { Test } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '@src/app.module';

describe('POST /users', () => {
  let app: INestApplication;

  beforeAll(async () => {
    const module = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = module.createNestApplication();
    app.useGlobalPipes(
      new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true }),
    );
    await app.init();
  });

  afterAll(async () => {
    await app.close();
  });

  it('should return 201 with an ID', async () => {
    const response = await request(app.getHttpServer())
      .post('/users')
      .send({
        email: 'e2e@example.com',
        country: 'United States',
        postalCode: '10001',
        street: '789 Elm Dr',
      })
      .expect(201);

    expect(response.body.id).toBeDefined();
  });

  it('should return 409 on duplicate email', async () => {
    await request(app.getHttpServer())
      .post('/users')
      .send({
        email: 'dupe@example.com',
        country: 'US',
        postalCode: '10001',
        street: '111 Pine Rd',
      })
      .expect(201);

    await request(app.getHttpServer())
      .post('/users')
      .send({
        email: 'dupe@example.com',
        country: 'CA',
        postalCode: '20002',
        street: '222 Maple Ln',
      })
      .expect(409);
  });

  it('should return 400 on invalid input', async () => {
    await request(app.getHttpServer())
      .post('/users')
      .send({ email: 'not-an-email' })
      .expect(400);
  });
});
```

---

## E2E / Behavioral Tests

For business-critical flows, Gherkin syntax makes tests readable by non-developers.

### Feature File

```gherkin
# tests/user/create-user/create-user.feature

Feature: Create User

  Scenario: Successfully creating a new user
    Given no user exists with email "gherkin@example.com"
    When I create a user with:
      | email   | gherkin@example.com |
      | country | United States       |
      | postalCode | 10001            |
      | street  | 123 Main St         |
    Then the response status should be 201
    And the response should contain an "id" field

  Scenario: Rejecting a duplicate email
    Given a user exists with email "existing@example.com"
    When I create a user with email "existing@example.com"
    Then the response status should be 409
```

### Step Definitions (jest-cucumber)

```typescript
// tests/user/create-user/create-user.e2e-spec.ts

import { defineFeature, loadFeature } from 'jest-cucumber';
import * as request from 'supertest';

const feature = loadFeature('tests/user/create-user/create-user.feature');

defineFeature(feature, (test) => {
  let app: INestApplication;
  let response: request.Response;

  beforeAll(async () => {
    // ... app setup
  });

  test('Successfully creating a new user', ({ given, when, then, and }) => {
    given(/^no user exists with email "(.*)"$/, async (email: string) => {
      // Database is clean from afterEach hook
    });

    when('I create a user with:', async (table: { rawTable: string[][] }) => {
      const body = Object.fromEntries(table.rawTable);
      response = await request(app.getHttpServer()).post('/users').send(body);
    });

    then(/^the response status should be (\d+)$/, (status: string) => {
      expect(response.status).toBe(parseInt(status));
    });

    and(/^the response should contain an "(.*)" field$/, (field: string) => {
      expect(response.body[field]).toBeDefined();
    });
  });
});
```

---

## Architecture Tests

Automated enforcement of the dependency rule. These tests catch violations before they reach code review.

### dependency-cruiser Configuration

```javascript
// .dependency-cruiser.js

module.exports = {
  forbidden: [
    {
      name: 'no-domain-to-infra',
      comment: 'Domain layer cannot depend on infrastructure',
      severity: 'error',
      from: { path: '(^|/)domain/' },
      to: { path: '(^|/)database/|prisma|typeorm|@nestjs/' },
    },
    {
      name: 'no-domain-to-api',
      comment: 'Domain layer cannot depend on API / presentation layer',
      severity: 'error',
      from: { path: '(^|/)domain/' },
      to: { path: 'controller|\.dto\.|swagger' },
    },
    {
      name: 'no-cross-module-imports',
      comment: 'Modules should not import from each other directly',
      severity: 'warn',
      from: { path: 'src/modules/([^/]+)/' },
      to: {
        path: 'src/modules/([^/]+)/',
        pathNot: '$1',
      },
    },
    {
      name: 'no-controller-to-repo',
      comment: 'Controllers must not bypass application layer',
      severity: 'error',
      from: { path: 'controller' },
      to: { path: 'repository(?!\\.port)' },
    },
  ],
};
```

### Running

```bash
# Validate dependencies
npx depcruise --config .dependency-cruiser.js src/

# Generate dependency graph (optional)
npx depcruise --config .dependency-cruiser.js --output-type dot src/ | dot -T svg > dependency-graph.svg
```

Add to CI pipeline:

```yaml
# .github/workflows/ci.yml (excerpt)
- name: Architecture tests
  run: npx depcruise --config .dependency-cruiser.js src/
```

---

## Test Fixtures and Builders

Reusable test data factories avoid duplicating setup code across tests.

### Builder Pattern

```typescript
// tests/test-utils/user.builder.ts

import { UserEntity } from '@modules/user/domain/user.entity';
import { Address } from '@modules/user/domain/value-objects/address.value-object';

export class UserBuilder {
  private email = 'default@example.com';
  private country = 'United States';
  private postalCode = '10001';
  private street = '123 Default St';

  withEmail(email: string): this {
    this.email = email;
    return this;
  }

  withCountry(country: string): this {
    this.country = country;
    return this;
  }

  withPostalCode(postalCode: string): this {
    this.postalCode = postalCode;
    return this;
  }

  withStreet(street: string): this {
    this.street = street;
    return this;
  }

  build(): UserEntity {
    return UserEntity.create({
      email: this.email,
      address: new Address({
        country: this.country,
        postalCode: this.postalCode,
        street: this.street,
      }),
    });
  }
}
```

### Usage

```typescript
it('should allow admin promotion', () => {
  const user = new UserBuilder()
    .withEmail('admin-candidate@example.com')
    .build();

  user.makeAdmin();

  expect(user.role).toBe(UserRoles.admin);
});
```

### Test Directory Structure

```
tests/
├── unit/
│   └── modules/
│       ├── user/
│       │   └── domain/
│       └── wallet/
│           └── domain/
├── integration/
│   ├── user.repository.spec.ts
│   └── create-user.e2e-spec.ts
├── user/
│   └── create-user/
│       ├── create-user.feature
│       └── create-user.e2e-spec.ts
├── setup/
│   ├── jest-global-setup.ts
│   └── jest-setup-after-env.ts
└── test-utils/
    ├── user.builder.ts
    ├── wallet.builder.ts
    └── api-client.ts
```
