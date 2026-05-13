# SF-0003 — Salesforce Query Service Design

**Status:** Accepted
**Date:** 2026-03-23
**Scope:** Salesforce Query Service Design

______________________________________________________________________

## Context

The Salesforce connector already provides a query service with raw SOQL
execution and pagination helpers. This is functional but not yet ergonomic for
common query composition tasks such as filters, ordering, and limits.

At the same time, advanced usage must remain possible because Salesforce orgs
often require custom or highly specific SOQL statements.

______________________________________________________________________

## Decision

### Category 1: Pattern

Adopt a hybrid query pattern:

1. Keep a global raw SOQL entry point as a first-class API.
1. Add a structured object-scoped query path for common filtering use cases.
1. Support both template+params and builder-style query construction.
1. Use a shallow two-level service model, not a broad subclass tree.

The query flow remains service-centric, while callers can choose between
global SOQL and object-scoped query composition.

### Category 2: Field management

Use minimal field handling in v1.

1. No field validation in v1.
1. No describe dependency in query flows in v1.
1. If `select(...)` is provided, use that list as-is.
1. If `select(...)` is not provided, use a default select set:
   - default minimum: `Id`
   - optional override via a service-level constant/config setting

Field validation and describe-based field discovery are explicitly deferred to a
future revision.

### Category 3: Architecture

Adopt a facade-first architecture with explicit service boundaries.

1. `SalesforceAPIFacade` remains the primary integration entrypoint.
1. The connector exposes two query services:
   - `SalesforceQueryService`: global SOQL execution across object types.
   - `SalesforceObjectQueryService`: object-scoped query service derived from
     `SalesforceQueryService` for common list/filter workflows.
1. `SalesforceQueryService` is the execution core and supports:
   - raw SOQL
   - template+params safe rendering
1. `SalesforceObjectQueryService` adds object-focused ergonomics:
   - implicit/default object context
   - parameter-driven filtering patterns
   - default select behavior when `select(...)` is omitted
1. Query services must not duplicate utility endpoint logic.
1. Sync and async shapes must remain structurally equivalent.

Non-goal:

- Business- or org-specific convenience services are out of scope for the
  generic connector and belong in the consuming application layer.

This keeps orchestration at the facade layer and keeps endpoint ownership in
the correct service layer.

### Category 4: Security

`query()` must enforce secure SOQL handling by default.

1. User-provided values must be bound through a safe formatter/builder path
   that applies SOQL escaping and quoting rules.
1. Direct string interpolation with untrusted input is not an accepted usage
   pattern for `query()`.
1. The service must provide a clear safe API for parameterized execution, for
   example `query(template, params=...)` or equivalent builder usage.
1. Raw SOQL execution remains available only for trusted input paths and must
   be explicitly documented as advanced usage.

Security baseline for the safe path:

1. Provide a dedicated SOQL formatter utility that:
   - escapes quotes and backslashes in string literals
   - escapes `%` and `_` in LIKE contexts
   - formats `null`, booleans, numbers, dates, and datetimes as SOQL literals
   - formats list/tuple/set values for `IN (...)` clauses
1. Provide parameterized template rendering, so callers pass values separately
   from the query template text.
1. Fail closed on unsupported value types by raising `ValueError`.
1. Validate Salesforce IDs with a strict check before inserting them in SOQL:
   - only alphanumeric IDs
   - only 15-char or 18-char forms
   - reject invalid IDs with `ValueError`
1. Provide a helper for ID lists used in `IN` clauses that validates every ID
   before formatting.
1. Ensure the builder APIs (`where_equals`, `where_like`, `where_in`) always
   route through the same escaping and validation helpers.

Security objective: reduce injection risk by making the safe path the default
and the unsafe path explicit.

### Category 5: Method placement

Use dedicated helper modules for query construction and safety utilities.

1. Keep transport-facing query execution methods in `SalesforceQueryService`
   (for example `query`, `query_more`, `query_all_iter`, `query_all`).
1. Place SOQL building logic in a dedicated builder module/class.
1. Place SOQL escaping and parameter formatting in a dedicated formatter
   module.
1. Place Salesforce ID validation and ID-list helpers in a dedicated
   validator module.
1. Keep object-specific query ergonomics in `SalesforceObjectQueryService`,
   while delegating execution to `SalesforceQueryService` core flows.
1. Re-export these public utilities at connector package level for
   discoverability, while preserving internal module boundaries.

Pagination semantics:

1. Global query methods:
   - `query(...)` returns one page envelope.
   - `query_all_iter(...)` lazily yields page envelopes.
   - `query_all(...)` eagerly returns merged records.
1. Object query methods mirror the same behavior:
   - `list_page(...)` for one page envelope.
   - `list_iter(...)` for lazy multi-page iteration.
   - `list(...)` for eager merged records.
1. `page_size` is an optional hint for paginated responses and must be applied
   consistently across first-page and follow-up page requests.
1. Invalid `page_size` values must fail fast with `ValueError`.

This separation keeps query orchestration readable and avoids turning
`QueryService` into a catch-all utility container.

SOQL builder behavior (normative):

1. `order_by` must support explicit direction per field (`ASC` or `DESC`).
1. `where` must support both default `AND` composition and explicit grouped
   `OR` composition.
1. `group_by` must support one or more fields.
1. Aggregate filters after grouping must be expressed via `having`.
1. Builder output must be deterministic and preserve the order in which clauses
   were provided.

Recommended builder shape:

```python
soql = (
    SOQLBuilder()
    .select("Industry", "COUNT(Id) total")
    .from_("Account")
    .where_equals("IsDeleted", False)
    .where_any(
        [
            ("BillingCountry", "=", "NL"),
            ("BillingCountry", "=", "BE"),
        ]
    )
    .group_by("Industry")
    .having("COUNT(Id) > 10")
    .order_by("total", direction="DESC")
    .order_by("Industry", direction="ASC")
    .limit(200)
    .build()
)
```

Expected query shape:

```sql
SELECT Industry, COUNT(Id) total
FROM Account
WHERE IsDeleted = false AND (BillingCountry = 'NL' OR BillingCountry = 'BE')
GROUP BY Industry
HAVING COUNT(Id) > 10
ORDER BY total DESC, Industry ASC
LIMIT 200
```

## Normative examples

### 1. Global query service with raw SOQL

```python
query_svc = SalesforceQueryService(client)
page = query_svc.query("SELECT Id FROM Account LIMIT 200")
```

### 2. Object query service with default select behavior

```python
obj_query = SalesforceObjectQueryService(client, object_name="Lead")
# When select is omitted, default select set is applied (minimum: Id).
records = obj_query.query_all(where={"Email": "john@example.com"})
```

### 3. Safe template + params execution

```python
query_svc = SalesforceQueryService(client)
records = query_svc.query_all(
    template="SELECT Id, Email FROM Lead WHERE Email = {email}",
    params={"email": "john@example.com"},
)
```

### 4. Pagination behavior

```python
# Lazy page iteration:
for page in query_svc.query_all_iter(
    "SELECT Id, Name FROM Account ORDER BY CreatedDate DESC"
):
    for record in page.records:
        process(record)

# Object-scoped eager list:
records = obj_query.list(where={"Email": "john@example.com"}, page_size=500)
```

______________________________________________________________________

## Consequences

### Positive

- Preserves full flexibility for advanced and org-specific SOQL.
- Improves ergonomics for day-to-day query construction.
- Keeps backward compatibility for existing query consumers.
- Aligns with composition over inheritance in the project architecture.
- Sets secure query construction as the default behavior.
- Clarifies service ownership and prevents cross-service endpoint overlap.
- Improves maintainability through explicit module-level separation.

### Neutral

- Two query authoring styles will coexist (raw and builder).
- Documentation must clearly position when to use each style.

### Negative / Trade-offs

- The builder cannot cover every advanced SOQL feature without growing complex.
- A dual-path API increases surface area and therefore maintenance scope.
- Security validation and escaping introduce additional implementation and test
  complexity.
- No field validation in v1 means field mistakes are detected by upstream API
  responses instead of preflight checks.

______________________________________________________________________

## Alternatives considered

### Raw SOQL only

Keep only `query(soql)` and avoid a builder.

Rejected because common query tasks become repetitive and error-prone, reducing
developer ergonomics.

### Builder only

Require all queries to go through a structured builder.

Rejected because advanced and org-specific query needs often require direct
SOQL control.

### Subclass-per-object pattern

Model queries via dedicated object-specific query subclasses.

Rejected as the primary pattern due to boilerplate growth and reduced
maintainability for broad object coverage.

______________________________________________________________________

## References

- ADR-0001 — Architecture Principles
- ADR-0002 — Layered Architecture
- ADR-0009 — Service Layer
- SF-0002 — SObject API facade ergonomics
- SF-0004 — Salesforce Search Capability Design
