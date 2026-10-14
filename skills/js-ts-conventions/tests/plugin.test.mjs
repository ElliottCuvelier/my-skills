// RuleTester suite for templates/plugin.mjs.
//
// Run from any directory where eslint, typescript-eslint and typescript (< 6.1) are installed:
//   npm i eslint typescript-eslint "typescript@<6.1"
//   node --test <skill>/tests/plugin.test.mjs
import { createRequire } from "node:module";
import { describe, it } from "node:test";
import { pathToFileURL } from "node:url";
import plugin from "../templates/plugin.mjs";

// Resolve the linters from the working directory, not from this file, so the skill ships without node_modules.
const requireFromCwd = createRequire(pathToFileURL(`${process.cwd()}/`));
const importFromCwd = async (name) => import(pathToFileURL(requireFromCwd.resolve(name)).href);
const { RuleTester } = await importFromCwd("eslint");
const tseslint = (await importFromCwd("typescript-eslint")).default;

RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;

const tester = new RuleTester({
  languageOptions: { parser: tseslint.parser, parserOptions: { ecmaFeatures: { jsx: true } } },
});
const r = plugin.rules;

tester.run("no-null", r["no-null"], {
  valid: [
    "Object.create(null)",
    "useRef(null)",
    "React.useRef<HTMLDivElement>(null)",
    "JSON.stringify(x, null, 2)",
    "parent.insertBefore(a, null)",
    "this.el.insertBefore(a, null)",
    "Object.setPrototypeOf(a, null)",
    'const s = "null";',
    "const u: string | undefined = undefined;",
    { code: "if (x === null) {}", options: [{ checkComparisons: false }] },
  ],
  invalid: [
    { code: "const a = null;", errors: [{ messageId: "literal" }] },
    { code: "let b: string | null;", errors: [{ messageId: "type" }] },
    { code: "if (x === null) {}", errors: [{ messageId: "literal" }] },
    { code: "const v: string | null = null;", errors: [{ messageId: "type" }, { messageId: "literal" }] },
    { code: "JSON.parse(x, null)", errors: [{ messageId: "literal" }] },
  ],
});

tester.run("no-getters", r["no-getters"], {
  valid: [
    "class A { getName(): string { return ''; } }",
    "class A { set name(v: string) {} }",
    "class A { get [Symbol.toStringTag]() { return ''; } }",
    "const o = { get a() { return 1; } };",
  ],
  invalid: [
    { code: "class A { get firstName(): string { return ''; } }", errors: [{ message: "Replace getter `firstName` with an explicit method `getFirstName()`." }] },
    { code: "class A { get isValid() { return true; } }", errors: [{ message: "Replace getter `isValid` with an explicit method `isValid()`." }] },
    { code: "abstract class A { abstract get id(): string; }", errors: [{ messageId: "getter" }] },
    { code: "class A { static get instance() { return 1; } }", errors: [{ messageId: "getter" }] },
  ],
});

tester.run("readonly-props", r["readonly-props"], {
  valid: [
    "interface P { readonly a: string; m(): void }",
    "type T = { readonly a: string };",
    "class C { readonly a = 1; }",
    "class C { count = 0; inc() { this.count++; } }",
    "class C { x = 0; set() { this.x = 1; } }",
    "class C { #x = 0; set() { this.#x = 1; } }",
    "class C { readonly a: string; constructor() { this.a = ''; } }",
    "class C { constructor(private readonly repo: R) {} }",
    "class C { declare a: string; }",
    "class C { x = 0; m() { this.x += 1; } }",
  ],
  invalid: [
    { code: "interface P { a: string }", errors: [{ messageId: "signature" }] },
    { code: "type T = { a: string; readonly b: number };", errors: [{ messageId: "signature" }] },
    { code: "class C { a = 1; }", errors: [{ messageId: "field" }] },
    { code: "class C { a: string; constructor() { this.a = ''; } }", errors: [{ messageId: "field" }] },
    { code: "class C { constructor(private repo: R) {} }", errors: [{ messageId: "parameter" }] },
    { code: "class C { x = 0; m() { const f = () => { this.y = 1; }; } }", errors: [{ messageId: "field" }] },
  ],
});

tester.run("naming", r.naming, {
  valid: [
    "enum RequestStatus { NEW = 'NEW', MEETING_PLANNED = 'MEETING_PLANNED' }",
    "const { first_name } = row;",
    "const { first_name: firstName } = row;",
    "const MAX_RETRY = 3;",
    "const CreateRequestDtoSchema = z.object({});",
    { code: "function Button() { return null; }", filename: "button.tsx" },
    { code: "function withX(Component: unknown) {}", filename: "with-x.tsx" },
    "function f(_unused: string) {}",
    "class A { static readonly MAX = 1; }",
    "class A { #secret = 1; doIt() {} }",
    "const fn = <TValue,>(v: TValue) => v;",
    "const o = { some_key: 1 };",
    "import { some_thing } from 'x';",
    "type Props = { some_key: string };",
    "try {} catch (error) {}",
    "class RequestEntity {} interface RequestProps {} type RequestId = string;",
    "const __DEV__ = true;",
    "function Controller(): ClassDecorator { return () => {}; }",
    "export function Roles(...roles: string[]) { return SetMetadata('roles', roles); }",
    "export function Auth() { return applyDecorators(UseGuards()); }",
    "export async function GET(request: Request) { return Response.json({}); }",
    "export function POST() {}",
  ],
  invalid: [
    { code: "enum request_status { A = 'A' }", errors: [{ message: "Enum `request_status` should be PascalCase." }] },
    { code: "enum RequestStatus { meetingPlanned = 'X' }", errors: [{ message: "Enum member `meetingPlanned` should be SCREAMING_SNAKE_CASE." }] },
    { code: "class my_class {}", errors: [{ messageId: "wrongCase" }] },
    { code: "interface iFoo {}", errors: [{ messageId: "wrongCase" }] },
    { code: "type foo = string;", errors: [{ messageId: "wrongCase" }] },
    { code: "function Do_thing() {}", errors: [{ messageId: "wrongCase" }] },
    { code: "function Button() {}", filename: "button.ts", errors: [{ messageId: "wrongCase" }] },
    { code: "const user_id = 1;", errors: [{ messageId: "wrongCase" }] },
    { code: "function f(user_id: string) {}", errors: [{ messageId: "wrongCase" }] },
    { code: "class A { Do_it() {} }", errors: [{ messageId: "wrongCase" }] },
    { code: "class A { my_prop = 1; }", errors: [{ messageId: "wrongCase" }] },
    { code: "const fn = (Bad_Name: string) => Bad_Name;", errors: [{ messageId: "wrongCase" }] },
    { code: "type Box<value> = { v: value };", errors: [{ messageId: "wrongCase" }] },
  ],
});

tester.run("constant-case", r["constant-case"], {
  valid: [
    'export const dynamic = "force-dynamic";',
    "const MAX = 3;",
    "function f() { const local = 3; }",
    "const obj = {};",
    "const fn = () => 1;",
    { code: "const special = 1;", options: [{ allow: ["special"] }] },
    "let counter = 0;",
  ],
  invalid: [
    { code: "const defaultTimeout = 5000;", errors: [{ message: "Module-level constant `defaultTimeout` should be SCREAMING_SNAKE_CASE (`DEFAULT_TIMEOUT`)." }] },
    { code: 'export const apiUrl = "x";', errors: [{ messageId: "constant" }] },
    { code: "const negative = -1;", errors: [{ messageId: "constant" }] },
    { code: "const tpl = `abc`;", errors: [{ messageId: "constant" }] },
    { code: "const lit = 'a' as const;", errors: [{ messageId: "constant" }] },
  ],
});

tester.run("prefer-as-const-constants", r["prefer-as-const-constants"], {
  valid: [
    "const REQUEST_TYPES = ['A'] as const;",
    "const X = { a: 1 } as const satisfies Y;",
    "const list = [1];",
    "const ITEMS: readonly string[] = [];",
    "const FROZEN = Object.freeze([1]);",
    "function f() { const LOCAL = [1]; }",
  ],
  invalid: [
    { code: "const REQUEST_TYPES = ['A', 'B'];", errors: [{ messageId: "asConst" }] },
    { code: "export const CONFIG = { a: 1 };", errors: [{ messageId: "asConst" }] },
    { code: "const X = { a: 1 } satisfies Y;", errors: [{ messageId: "asConst" }] },
  ],
});

tester.run("filename-case", r["filename-case"], {
  valid: [
    { code: "x", filename: "/repo/src/request-status.value-object.ts" },
    { code: "x", filename: "/repo/pages/[id].tsx" },
    { code: "x", filename: "/repo/pages/_app.tsx" },
    { code: "x", filename: "/repo/next-env.d.ts" },
    { code: "x", filename: "/repo/app/[[...slug]].tsx" },
    { code: "x", filename: "/repo/src/routes/+page.ts" },
    { code: "x", filename: "/repo/app/routes/$id.tsx" },
    { code: "x", filename: "/repo/eslint.config.mjs" },
    { code: "x", filename: "C:\\repo\\src\\create-request.command.ts" },
    { code: "x", filename: "/repo/src/README.ts", options: [{ ignore: ["^README\\."] }] },
  ],
  invalid: [
    { code: "x", filename: "/repo/src/BadName.ts", errors: [{ message: "Filename `BadName.ts` should be kebab-case (`bad-name.ts`)." }] },
    { code: "x", filename: "/repo/src/request_status.ts", errors: [{ messageId: "filename" }] },
    { code: "x", filename: "/repo/src/Button.stories.tsx", errors: [{ message: "Filename `Button.stories.tsx` should be kebab-case (`button.stories.tsx`)." }] },
    { code: "x", filename: "/repo/src/HTTPClient.ts", errors: [{ message: "Filename `HTTPClient.ts` should be kebab-case (`http-client.ts`)." }] },
  ],
});

tester.run("no-generic-error", r["no-generic-error"], {
  valid: ["throw new ArgumentInvalidException('x');", "throw err;", "const e = new Error('x');"],
  invalid: [
    { code: "throw new Error('x');", errors: [{ messageId: "generic" }] },
    { code: "throw Error('x');", errors: [{ messageId: "generic" }] },
  ],
});

tester.run("no-deep-relative-imports", r["no-deep-relative-imports"], {
  valid: [
    "import { a } from './a';",
    "import { a } from '../a';",
    "import { a } from '@/libs/a';",
    "export * from '../x';",
    { code: "import { a } from '../../a';", options: [{ maxParentDepth: 2 }] },
    "const m = import('../a');",
    "import x from 'lodash';",
  ],
  invalid: [
    { code: "import { Command } from '../../../libs/ddd/command.base';", errors: [{ message: "Import `../../../libs/ddd/command.base` climbs 3 directories; use the `@/` alias for cross-module imports." }] },
    { code: "export { a } from '../../a';", errors: [{ messageId: "deep" }] },
    { code: "export * from './../../a';", errors: [{ messageId: "deep" }] },
    { code: "const m = import('../../a');", errors: [{ messageId: "deep" }] },
    { code: "const m = require('../../a');", errors: [{ messageId: "deep" }] },
    { code: "import type { T } from '../../t';", errors: [{ messageId: "deep" }] },
    { code: "import { a } from '../../../a';", options: [{ maxParentDepth: 2, alias: "~/" }], errors: [{ message: "Import `../../../a` climbs 3 directories; use the `~/` alias for cross-module imports." }] },
  ],
});
