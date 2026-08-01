---
name: ts-code-style
description: >
  General TypeScript project code style: prefer simple structure over ceremony,
  no empty abstractions, no dead exports, static imports by default, clear
  module boundaries, and latest-major dependencies without legacy shims. Use
  when writing or refactoring TypeScript, reviewing structure, cleaning up
  abstractions, scaffolding a TS app/library, or when the user mentions code
  style, 代码风格, 别包一层, 过度抽象, TypeScript conventions, or runs
  /ts-code-style.
---

# TypeScript project code style

General rules for TypeScript apps and libraries. Framework-agnostic: apply the
*intent* to whatever stack is in use (Node, browser, monorepo, Hono, React, …)
without forcing a particular folder name or framework pattern.

## Principle

**Abstraction must pay rent.**  
If a layer only renames a call, constructs a single process-wide object, or
hides three lines behind a name that is never reused, delete it and write the
direct form.

---

## 1. Prefer direct structure over ceremony

| Prefer | Avoid |
|--------|--------|
| Export the real value (`export const x = …`) when there is one process-wide instance | `createX()` / `makeX()` / `getInstance()` with no config and a single call site |
| Put logic where it belongs; keep entry/bootstrap as composition only | Dumping hash/crypto/MIME/business rules into the boot file |
| Modules that export useful units (handlers, pure helpers, services) | “Register” helpers that only call a fixed list of setup once |
| Top-level static `import` | `await import("./local-module")` with no real need |

**Factories are fine** when callers pass different options, tests inject fakes,
or multiple instances coexist. They are **not** fine as default boilerplate.

**Lazy init** (e.g. open a DB on first use) is fine when path/env truly matters
at first access—not as a ritual wrapper around a constant.

---

## 2. Module boundaries

- **Bootstrap / entry**: wire dependencies, start the process, set global
  defaults. Keep it short.
- **Domain / services**: application behavior and persistence.
- **Integrations / adapters**: external protocols and third-party APIs only;
  do not mix local business rules into them.
- **Shared pure helpers**: only when **two or more** real call sites need the
  same logic. One private function does not deserve a public package API.

Do not invent directory or naming schemes for the agent to copy; follow the
repo’s existing layout. If the repo has no layout yet, choose the smallest
clear split for *this* project and stay consistent.

---

## 3. Imports

- **Default to static imports** for first-party code and normal dependencies.
- Use dynamic `import()` only when there is a concrete reason:
  - break a real circular dependency that cannot be restructured cheaply, or
  - defer a heavy optional dependency that must not load at startup.
- If you use dynamic import, a one-line comment of *why* is enough; no essay.

---

## 4. Surfaces and dead code

- Every **exported** symbol should have a caller outside its defining file
  (or be the intentional public API of a package).
- Do not add “for later” builders, unused option bags, or dual names for the
  same behavior.
- Prefer deleting unused code over leaving it “in case”.
- After refactors, grep for orphaned exports and remove them in the same change.

---

## 5. Types and API shape

- **One source of truth** for shared types (package export, schema, or domain
  module). Do not redefine the same DTO on client and server until they drift.
- Validate at boundaries (request body, env, untrusted input); keep internal
  code typed and mostly free of redundant runtime checks.
- Thin client helpers are OK for **cross-cutting** concerns (auth header,
  error unwrap, URL building). Do **not** add a 1:1 mirror function for every
  remote method with zero extra logic.

---

## 6. Dependencies and upgrades

- Prefer **current major** versions of direct dependencies unless the project
  pins otherwise.
- After a major bump, **update call sites** to the new API. Do not keep long-lived
  compatibility aliases (`oldName` → `newName`) “just in case”.
- Drop unused dependencies and config that nothing reads.

---

## 7. Logging, errors, comments

- **Logging**: quiet by default in libraries and services; noisy paths behind
  an explicit level or flag. Do not spam every request at default level.
- **Errors**: one consistent shape at the public boundary of a service (code +
  message, or a small error class hierarchy). Do not invent parallel formats
  per file.
- **Comments**: explain non-obvious constraints (why, not what). Delete comments
  that restate the next line of code.
- **Docs / commits**: follow the repo’s language rule (many projects use English
  for commits and contributor docs; product UI strings may differ).

---

## 8. Self-check before finishing

1. Is there a factory or “register” helper with a single call site and no
   parameters that change behavior? → flatten.
2. Is the entry file full of implementation detail? → move it next to the
   feature that owns it.
3. Any dynamic import of a local module without a real circular/lazy reason?
   → static import.
4. Any new export with zero external callers? → unexport or delete.
5. Any client/API facade that only renames existing calls 1:1? → remove.
6. Any leftover shim from a dependency upgrade? → remove and use the current API.

---

## When reviewing

- Prefer the **smallest** change that removes empty ceremony.
- Do not redesign unrelated modules while “fixing style”.
- Preserve behavior unless the user asked for a behavior change.
- After cleanup: typecheck and the narrowest relevant tests.
