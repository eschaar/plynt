# ADR-0003: Dependency Policy

## Status

Accepted

## Context

To minimize conflicts and maintenance overhead, the library enforces a strict dependency policy.

## Decision

### Dependency Policy

- The core package always installs only one HTTP client library and one data-model/validation library.
- All framework-specific integrations (Django, FastAPI, etc.) are optional and enabled via extras.
- OAuth and other advanced features are also optional extras.
- No web frameworks, ORMs, or multiple HTTP libraries are allowed in the core.

### Chosen Libraries

- **HTTP client**: `httpx2` (sync and async, single dependency).
- **Data model validation and serialization**: `pydantic` v2 (`pydantic.BaseModel`),
  used in connectors and framework adapters.
- **Settings and configuration**: `pydantic-settings` v2, installed as a core
  dependency (all installs). See ADR-0004 for rationale and the full
  alternatives evaluation including msgspec and msgspec-ext.

## Consequences

- Users can install only the features they need.
- The risk of dependency conflicts is minimized.
- The library remains lightweight and easy to maintain.
