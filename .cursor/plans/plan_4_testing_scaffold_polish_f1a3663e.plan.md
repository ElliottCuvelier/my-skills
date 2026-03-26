---
name: 'Plan 4: Testing Scaffold Polish'
overview: Create the testing reference, quick-reference cheatsheet, scaffold generator scripts, and finalize cross-references across all documents.
todos:
  - id: write-testing-md
    content: Write references/TESTING.md with domain unit tests, application unit tests (mocked ports), integration tests (Prisma + real DB), E2E/behavioral tests, architecture tests, test fixtures
    status: completed
  - id: write-cheatsheet-md
    content: Write references/CHEATSHEET.md with layer summary, file naming conventions, decision trees, new feature checklist, anti-patterns table, DI wiring reference
    status: completed
  - id: cross-reference-audit
    content: Audit all cross-references across SKILL.md and all reference files, ensure link consistency and code example alignment
    status: completed
  - id: consistency-pass
    content: 'Final consistency pass: same entity examples (User/Wallet), same import aliases, same error handling pattern, same DI token pattern across all files'
    status: completed
isProject: false
---

# Plan 4: Testing, Scaffold Scripts, and Cheatsheet

## Files to Create

```
skills/nestjs-domain-driven-hexagon/
├── references/
│   ├── TESTING.md
│   └── CHEATSHEET.md
└── scripts/
    └── (scaffold guidance embedded in SKILL.md -- see notes below)
```

## TESTING.md

NestJS-specific testing strategies for DDD + Hexagonal architecture with Prisma.

**Sections:**

1. **Testing Pyramid** -- Unit -> Integration -> E2E with NestJS tooling:

- Mermaid diagram of the pyramid
- Domain unit tests: most numerous, fastest, no mocks needed
- Application unit tests: mock driven ports
- Integration tests: real database (Prisma + test DB)
- E2E tests: full HTTP request cycle

1. **Domain Layer Unit Tests** -- Test entities, VOs, aggregates in isolation:

- No NestJS test utilities needed -- pure TypeScript tests
- Test entity creation with valid/invalid props
- Test value object validation and equality
- Test aggregate business methods and invariants
- Test domain event emission (check `entity.domainEvents` array)
- Example: `UserEntity.create()` test, `Address` validation test
- Key principle: if domain tests need mocks, your domain has leaked dependencies

1. **Application Layer Unit Tests** -- Mock the ports:

- Use NestJS `Test.createTestingModule()` with mock providers
- Mock `RepositoryPort` implementations (in-memory or jest mocks)
- Test command handlers: verify correct domain operations + repository calls
- Test query handlers: verify correct data retrieval
- Example: `CreateUserService` test with mocked `UserRepositoryPort`
- Pattern: create `InMemoryUserRepository implements UserRepositoryPort` for tests

1. **Integration Tests** -- Real database with Prisma:

- Test setup: Docker Compose for test PostgreSQL
- `beforeAll`: run Prisma migrations on test DB
- `afterEach`: clean database (truncate tables or use transactions)
- Test repositories with real Prisma client
- Test full command flow: handler -> repository -> database -> verify state
- NestJS `INestApplication` for HTTP-level tests with `supertest`

1. **E2E / Behavioral Tests** -- Full request cycle:

- Gherkin + jest-cucumber for human-readable scenarios
- `.feature` files describing business scenarios
- Step definitions mapping to HTTP requests
- Example: "Given no users exist, When I create a user with valid data, Then I should receive 201 with user ID"

1. **Architecture Tests** -- Enforce dependency rules:

- Use `dependency-cruiser` to validate layer boundaries
- Rule: domain/ cannot import from database/, api/, infrastructure/
- Rule: no cross-module direct imports
- Example `.dependency-cruiser.js` configuration
- Run as part of CI pipeline

1. **Test Fixtures and Builders** -- Reusable test data:

- Builder pattern for creating test entities: `UserBuilder().withEmail('test@example.com').build()`
- Shared test utilities directory structure
- Mock factory for common domain objects

## CHEATSHEET.md

One-page quick reference for developers actively building with this architecture.

**Sections:**

1. **Layer Summary** -- 4-layer ASCII diagram with key rules per layer
2. **File Naming Conventions** -- Table:

- `*.entity.ts` -- Domain entities / aggregate roots
- `*.value-object.ts` -- Value objects
- `*.domain-event.ts` -- Domain events
- `*.errors.ts` -- Domain error classes
- `*.types.ts` -- Domain types and interfaces
- `*.command.ts` -- CQRS commands
- `*.service.ts` -- Command/query handlers (application services)
- `*.http.controller.ts` -- HTTP controllers
- `*.message.controller.ts` -- Message/event controllers
- `*.request.dto.ts` -- Request DTOs
- `*.response.dto.ts` -- Response DTOs
- `*.repository.port.ts` -- Repository port interface
- `*.repository.ts` -- Repository implementation
- `*.mapper.ts` -- Domain <-> persistence mapper
- `*.di-tokens.ts` -- DI token definitions
- `*.module.ts` -- NestJS module

1. **Decision Trees** -- Compact versions of the 3 decision trees from SKILL.md
2. **New Feature Checklist** -- Step-by-step when adding a new use case:

- Define command/query DTO
- Create command/query class
- Implement handler (application service)
- Create/update domain entity if needed
- Implement repository port if new aggregate
- Implement Prisma repository adapter
- Create mapper if new aggregate
- Create HTTP controller
- Create request/response DTOs
- Register in NestJS module
- Write tests (domain -> application -> integration)

1. **Common Anti-Patterns** -- Quick table with problem and fix
2. **NestJS DI Wiring Quick Reference** -- Token definition -> Module registration -> Injection

## Scaffold Scripts Approach

Rather than creating standalone scaffold scripts (which add maintenance burden and framework version coupling), the skill will embed scaffold generation guidance directly in SKILL.md and reference docs. When the skill is triggered by a prompt like "scaffold a new module" or "create a new aggregate", the model will:

1. Read the CHEATSHEET.md "New Feature Checklist"
2. Follow the directory structure from SKILL.md
3. Use the code templates from DDD-TACTICAL.md and PRISMA-ADAPTER.md
4. Generate all necessary files following the naming conventions

This approach is more maintainable than shell scripts because it leverages the model's ability to adapt templates to the specific domain context (entity names, properties, business rules) rather than generating generic boilerplate.

**If the user later wants actual script-based scaffolding**, a `scripts/scaffold.ts` can be added that uses `@nestjs/schematics` or custom Plop.js templates. This would be a follow-up enhancement.

## Final Polish Tasks

1. **Cross-reference audit** -- Verify all `[references/X.md](references/X.md)` links in SKILL.md point to correct files
2. **Table of contents** -- Add TOC to any reference file exceeding 200 lines
3. **Consistency pass** -- Ensure all code examples use the same:

- Entity names (User, Wallet as primary examples)
- Import path aliases (`@libs/`, `@modules/`, `@src/`)
- Error handling pattern (oxide.ts Result)
- DI token pattern (Symbol-based)

1. **SKILL.md description optimization** -- Make the frontmatter description trigger-friendly for NestJS-related prompts
