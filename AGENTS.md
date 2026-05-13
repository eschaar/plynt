# Copilot Agent Governance

This file defines **global guardrails** for all GitHub Copilot agents operating in this repository.

These rules apply to:

- the default Copilot coding agent
- all custom agents defined in `.github/agents/`
- any autonomous or multi-file agent task

______________________________________________________________________

## Source of Architectural Truth

- Architectural decisions are documented as **Architecture Decision Records (ADRs)** in `docs/architecture/adr/`.
- ADRs are the **single source of truth** for architecture.
- Agents must not reinterpret, summarize, or override ADRs.

If a required decision is missing or unclear:

- stop implementation
- request or propose a new ADR

______________________________________________________________________

## Core Guardrails (Non-Negotiable)

Agents **must not**:

- introduce framework-specific dependencies into the core package
- change the sync/async execution model
- alter the modular installation model (extras)
- add or remove core abstractions
- introduce new runtime dependencies

Any change affecting these areas **requires an ADR**.

______________________________________________________________________

## Core vs Adapters Boundary

- The `core` package must remain **framework-agnostic**
- Framework integrations (Django, FastAPI, etc.) must live in adapter modules only
- Cross-boundary imports are not allowed

If a requested task would violate this boundary:

- stop
- explain the conflict
- escalate to an ADR

______________________________________________________________________

## Dependency and Installation Policy

- Core dependencies must remain minimal and stable
- Optional dependencies must be isolated behind install extras
- Agents must not add dependencies "for convenience"

Any dependency change:

- must reference an existing ADR
- or require a new ADR before implementation

______________________________________________________________________

## Scope of Autonomous Changes

Agents may:

- modify files explicitly related to the requested task
- create new files only when necessary for that task
- refactor code **only when explicitly requested**

Agents must not:

- perform opportunistic refactors
- apply stylistic cleanups beyond the task scope
- modify unrelated modules

______________________________________________________________________

## Escalation Rules

Agents must **stop immediately** if a task:

- affects core abstractions
- affects dependency structure
- affects sync vs async behavior
- affects installation or packaging
- introduces architectural uncertainty

In these cases:

- do not guess
- do not implement partial solutions
- request an ADR

______________________________________________________________________

## Relationship to Other Instructions

- Project-wide architectural rules are defined in `.github/copilot-instructions.md`
- Context-specific rules are defined in `.github/instructions/*.instructions.md`
- Role-specific behavior is defined in `.github/agents/*.agent.md`

This file defines **baseline governance only**.
