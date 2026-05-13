# ADR-0001: Architecture Principles

## Status

Accepted

## Context

This document defines the mandatory architecture principles for the project,
which is a modular, framework-agnostic Python API client library for external
HTTP APIs. These principles ensure the library is reusable, maintainable, and
suitable for integration with various Python frameworks, while remaining minimal
and testable.

## Decision

### Guiding Philosophy

The five core principles that guide every design decision in Plynth:

- **Foundation, not framework** — Plynth sits at the bottom of your stack,
  not as a full-featured framework.
- **Framework-agnostic** — works with FastAPI, Flask, Django, or plain
  ASGI/WSGI, and is independently testable without any of them.
- **Explicit over implicit** — no hidden globals, no magic startup behaviour,
  no side effects at import time.
- **Small surface area** — easy to understand, easy to replace.
- **Designed for longevity** — stable APIs and boring-by-design building
  blocks.

### Architecture Principles

- The core library must not import or depend on any web framework
  (e.g., Django, FastAPI, Starlette). Only pure Python code is allowed in
  the core. Framework integrations are implemented as thin, optional adapters.

- The core package must always be installable on its own. Framework-specific
  features are opt-in and enabled via Python packaging extras (PEP-compliant).
  Optional dependencies must never be required unless explicitly requested.

- Only one modern HTTP client library is used in the core, supporting both sync
  and async. No mixing of multiple HTTP libraries in the core.

- Avoid deep base-class hierarchies and magic methods (e.g., `__getattr__`).
  Use explicit objects, middleware, pipelines, and adapters for behaviour
  composition.

- Services, models, and responses must not be aware of sync or async execution.
  Only the transport layer determines blocking vs. non-blocking behaviour.

- The library is organised into distinct conceptual layers: Request, Transport,
  Response, Client, and Service. Each layer has clear responsibilities and
  boundaries. The Client Layer contains multiple flavours (e.g., `HTTPClient`,
  `APIClient`) at the same architectural tier.

- Layers are identified by **file names**, not by directory structure.
  Directories (`base/`, `http/`, `cache/`) are namespace groupings only, not
  architectural tier boundaries. A file's layer membership is evident from its
  name (e.g., `transport.py`, `client.py`, `response.py`).

- Request and response payloads must be explicitly typed and validated.
  Models are framework-independent and reusable.

- Authentication and caching are optional, pluggable components.
  Token and response caching must be opt-in and backend-agnostic.

- The library must be fully testable without real HTTP calls.
  No global state or singletons. Mocking occurs at the HTTP transport level.

- Core dependencies: one HTTP client, one data-model/validation library.
  Optional dependencies: framework integrations, OAuth, tooling.
  Forbidden in core: web frameworks, ORMs, multiple HTTP libraries.

## Consequences

- The library will be lightweight, extensible, and easy to integrate.
- Users can install only what they need, minimising dependency conflicts.
- The codebase will be maintainable and testable, supporting long-term use.
- If any principle is found to conflict with a later architectural decision,
  the more specific ADR takes precedence, and this document is updated.
