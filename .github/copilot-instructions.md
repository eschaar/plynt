# Copilot Instructions

These instructions define how GitHub Copilot and other AI agents must operate within this repository. They are aligned with the project's architecture, ADRs, and long-term goals.



## Language, Documentation, and Coding Requirements

- All comments, docstrings, and documentation must be written in clear, developer-friendly English.
- Use language that is easy to understand for developers of varying backgrounds.
- All markdown files must conform to markdown linting rules (e.g., blank lines around headings and lists, proper heading levels, no hard tabs, etc.).
- Keep documentation lines, comments, and docstrings concise: aim for 80 characters per line, and never exceed 120 characters per line.
- All code must use type hinting (type annotations) wherever possible, including function arguments, return types, and class attributes.
- All tests must be written using pytest (no unittest or nose). Use pytest idioms and fixtures.
- Prefer grouping tests in a class (e.g., TestSettings) that corresponds to the class under test.

### Docstring style

Use **Google-style docstrings** throughout. Apply the following rules:

**Summary line**

- One sentence, imperative mood, no trailing period.
- Must stand alone — a reader should understand the purpose without reading
  the body.
- Good: `"""Return the global SObject catalog for the org."""`
- Avoid: `"""This method returns..."""`

**When to add `Args:` / `Returns:` / `Raises:` sections**

Only add a section when it adds information not already expressed by the type
hints and parameter names. Omit it when the signature is self-explanatory.

| Situation | Add section? |
| --- | --- |
| Parameter has non-trivial semantics (format, validation, side-effects) | Yes |
| Parameter name and type are self-explanatory | No |
| Return type is a typed model and the summary says what it contains | No |
| Return has subtle behaviour (e.g. `None` on 204, pagination semantics) | Yes |
| Function always raises under a specific condition | Yes (`Raises:`) |
| Private / internal method | No — one-liner only |

**`Args:` format**

```python
Args:
    record_id: Salesforce 15- or 18-character record ID.
    fields: Field API names to include. Returns all fields when omitted.
```

- One line per parameter where possible.
- No Sphinx cross-references (`:class:`, `:meth:`, `:attr:`).
- Use plain names: `SalesforceQueryResponse`, not
  `:class:`~plynth.connectors.salesforce.models.SalesforceQueryResponse``.

**`Returns:` format**

```python
Returns:
    Parsed query response with a ``records`` list and pagination state.
```

- Describe the value, not the type — the type is already in the signature.
- Never repeat the class name as the sole content.

**`Example::` blocks**

- Add only on public API methods where usage is non-obvious.
- Omit on private methods, simple getters, and one-liners.
- Keep examples short — 4–8 lines maximum.

**Class docstrings**

- Describe the responsibility of the class, not its constructor.
- Put constructor parameter docs on the class docstring, not on `__init__`.
- Keep `__init__` docstrings to a single line or omit them entirely.

**What to avoid**

- Sphinx cross-reference syntax (`:class:`, `:meth:`, `:attr:`, `:param:`).
- Restating the type hint in prose: `"Returns a str"` when `-> str` is present.
- Long `Returns:` blocks that copy the class definition.
- Docstrings on private helpers (`_method`) longer than one line.

---

## 1. Project Intent & Scope

- Treat this repository as a framework-agnostic external API client library.
- Prioritize long-term reuse and architectural consistency over short-term feature delivery or local optimizations.
- When in doubt, defer to existing ADRs and design documentation.

## 2. Architectural Decision Records (ADRs)

- Always consult ADRs before making architectural or structural changes.
- Do **not** override or reinterpret an accepted ADR.
- If a required decision is missing or unclear:
  - Flag the gap.
  - Propose a new ADR instead of making assumptions.
- Reference ADR identifiers (e.g., ADR-003) in code comments and commit messages.

## 3. Core vs Optional Components

- Treat the core package as minimal and framework-independent.
- Do **not** introduce framework dependencies into the core.
- All framework-specific functionality must live in optional modules.
- Respect the modular installation model (extras such as `[django]`, `[fastapi]`, `[oauth]`).
- Assume users may install only a subset of the package.

## 4. Dependency Management Principles

- Keep core dependencies minimal and stable.
- Avoid introducing new dependencies without architectural justification.
- When adding a dependency:
  - Document the rationale.
  - Assess impact on optional installs.
  - Reference or propose an ADR.
- Prefer standard library solutions when feasible.

## 5. Sync and Async Design Constraints

- Treat sync vs async as a transport concern only.
- Services, models, and responses must remain execution-model agnostic.
- Never duplicate business logic for sync and async paths.
- Follow documented transport abstractions.

## 6. Composition Over Inheritance

- Prefer composition, explicit objects, and small interfaces.
- Avoid deep inheritance hierarchies or “god base classes.”
- Do **not** introduce implicit behavior via magic methods.
- Align with documented architectural patterns.

## 7. Service Layer Responsibilities

- Services represent external domains or APIs.
- Services:
  - Define endpoints.
  - Orchestrate requests.
  - Select response models.
- Services must **not**:
  - Manage HTTP internals.
  - Manage framework concerns.
  - Perform I/O outside the client abstraction.

## 8. Response and Error Handling

- Centralize response parsing and error handling.
- Avoid leaking raw HTTP responses outside the response layer.
- Use typed response models consistently.
- Do **not** implement ad-hoc error handling inside services or frameworks.

## 9. Models and Validation

- Models are data carriers only.
- No business logic inside models.
- Models must remain framework-independent.
- Reuse models across services, framework adapters, and tests.
- Follow documented validation and serialization rules.

## 10. Authentication and Caching

- Authentication must be pluggable, optional, and non-intrusive.
- Do **not** hard-code authentication logic into services.
- Token and response caching must:
  - Be explicitly enabled.
  - Use abstract cache interfaces.
- Framework-specific caches must be implemented via adapters.

## 11. Framework Integrations

- Framework integrations (Django, FastAPI, etc.) must:
  - Be thin adapters.
  - Avoid duplicating core logic.
  - Only depend on the core through public interfaces.
- No framework assumptions may leak back into the core.

## 12. Testing and Mocking Expectations

- Design all code to be testable without real network calls.
- Avoid global state and singletons.
- Prefer HTTP-level mocking over service stubbing.
- Follow documented testing conventions and tooling.

## 13. Documentation-Driven Development

- When behavior is unclear:
  - Search for existing documentation.
  - Reference ADRs, README, or design docs.
- If documentation is missing or outdated:
  - Note the discrepancy.
  - Suggest documentation updates.
- Do **not** “invent” undocumented behavior.

## 14. Code Generation & Refactoring Behavior

- Favor small, incremental changes.
- Keep changes aligned with existing patterns.
- Avoid large refactors without architectural context.
- Always preserve backward compatibility unless explicitly instructed otherwise.

## 15. Decision Escalation Rules

- If a change impacts:
  - Public APIs
  - Dependency structure
  - Installation model
  - Core abstractions
  → Stop and request an architectural decision.
- Do **not** silently introduce breaking changes.

## 16. Branch Workflow Safety

- Do **not** commit directly to `main` or `master` unless the user explicitly
  approves this in the current conversation.
- Implement new functionality on a dedicated branch first.
- Before starting work on a branch name, check whether that branch already
  exists on the remote and whether it has already been merged.
- If a branch has already been merged remotely, do not reuse it for new work;
  create a new branch.

---

## 🧭 Meta-Instruction for Copilot and AI Agents

- Act as an architectural contributor, not just a code generator.
- Prefer referencing decisions, documentation, and constraints over guessing intent.
- When uncertain, surface questions and propose ADRs instead of making assumptions.

### Python file/module naming conventions

- Use the singular form for modules (files) that define a single main concept (e.g., `request.py`, `response.py`, `client.py`).
- Use the plural form for modules that contain a collection of related objects or utilities (e.g., `errors.py`, `settings.py`, `utils.py`).
- Classes are always singular (e.g., `Request`, `Response`, `User`).
- Packages (folders) are usually plural if they contain a collection (e.g., `models`, `services`), but singular is allowed if it fits the domain.
- Follow the conventions of the Python standard library and popular frameworks for consistency.

> Example: `request.py` and `response.py` for single data carriers; `errors.py` for multiple error types.
