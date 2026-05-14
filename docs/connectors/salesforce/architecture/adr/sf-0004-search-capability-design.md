# SF-0004 — Salesforce Search Capability Design

**Status:** Accepted
**Date:** 2026-03-23
**Scope:** Salesforce Search Capability Design

______________________________________________________________________

## Context

Search capabilities have different semantics than query capabilities.

- Search uses SOSL syntax and search-specific endpoint behavior.
- Query uses SOQL syntax and query-specific paging behavior.

To keep service boundaries clear, search capability is specified in a dedicated
ADR and not hosted as a primary concern inside `UtilityService`.

______________________________________________________________________

## Decision

1. Search is a first-class capability owned by `SalesforceSearchService`.
1. `UtilityService` is not the primary home for search methods.
1. Facade exposes a dedicated `search()` entrypoint returning
   `SalesforceSearchService`.
1. SOSL safety follows the same secure-by-default principle as SOQL.
1. A dedicated `SOSLBuilder` is part of the planned search API surface.

### Search service API shape (planned)

1. `search(...)` for one SOSL execution result envelope.
1. `search_template(template, params)` for safe dynamic input.
1. `search_builder(builder)` for structured SOSL construction.

### SOSL security baseline

SOSL must be secure by default in the same way as SOQL.

1. User-provided search terms must flow through a safe formatter or builder
   path, not through direct string interpolation.
1. `search_template(template, params)` is the default API for dynamic search
   input.
1. `search(...)` with raw SOSL remains available only for trusted input and
   must be documented as advanced usage.
1. Structured builder APIs must route all literal values through the same
   escaping and validation helpers.

Security baseline for the safe path:

1. Provide a dedicated SOSL formatter utility, or a shared formatter with
   explicit SOSL modes, for search-term rendering.
1. Escape characters that would otherwise break SOSL literal boundaries or
   change query meaning.
1. Reject unsupported parameter types with `ValueError`.
1. Keep object names, field names, and other structural query parts on
   explicit trusted code paths; do not treat arbitrary user input as a safe
   identifier.
1. If the builder exposes object names or field names, it must validate them
   as identifiers before rendering.
1. If `RETURNING` filters reuse SOQL-style predicates, those values must use
   the same safe literal formatting rules as the query service.

Security objective: make safe dynamic SOSL the default path while keeping raw
SOSL available only as an explicit expert mode.

SOSL does not require SOQL-style `query_all_iter` semantics by default.
If a concrete search endpoint requires continuation behavior, it should be
added explicitly and documented as search-specific pagination.

Normative example:

```python
search_svc = SalesforceSearchService(client)

result = search_svc.search_template(
    "FIND {term} IN NAME FIELDS RETURNING Lead(Id, Email)",
    params={"term": "Acme"},
)
```

### SOSLBuilder (planned)

`SOSLBuilder` provides structured construction for common SOSL statements.

1. `find(...)`
1. `in_all_fields()` / `in_name_fields()` / `in_email_fields()`
1. `returning(...)`
1. `limit(...)`

Normative example:

```python
sosl = (
    SOSLBuilder()
    .find("Acme")
    .in_name_fields()
    .returning("Lead", ["Id", "Email"])
    .returning("Account", ["Id", "Name"])
    .limit(200)
    .build()
)
```

### Shared foundations strategy

SOQL and SOSL should share principles and internal helpers, not a forced public
inheritance model.

1. Services stay separate: `SalesforceQueryService` and
   `SalesforceSearchService`.
1. Builders stay separate: `SOQLBuilder` and `SOSLBuilder`.
1. Internal helper reuse is allowed for shared concerns such as literal
   formatting and deterministic output ordering.

______________________________________________________________________

## Consequences

### Positive

- Keeps query and search responsibilities explicit and easier to evolve.
- Improves discoverability via a dedicated facade `search()` entrypoint.
- Avoids coupling search lifecycle to utility endpoint lifecycle.

### Neutral

- Adds one dedicated service surface to document and maintain.

### Negative / Trade-offs

- Requires migration for callers currently using utility search methods.

______________________________________________________________________

## References

- SF-0003 — Salesforce Query Service Design
- ADR-0001 — Architecture Principles
- ADR-0002 — Layered Architecture
