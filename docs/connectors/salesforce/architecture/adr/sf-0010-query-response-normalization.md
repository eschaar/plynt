# SF-0010 — Salesforce Query Response Normalization

**Status:** Accepted
**Date:** 2026-05-13
**Scope:** `plynt.connectors.salesforce.lookup`, `plynt.connectors.salesforce.identity`, `plynt.connectors.salesforce.query`

______________________________________________________________________

## Context

Salesforce SOQL query responses are expected to follow a standard envelope:

```json
{
  "totalSize": 150,
  "done": true,
  "nextRecordsUrl": null,
  "records": [...]
}
```

However, some Salesforce API endpoints and edge cases return minimal payloads
that may contain only the `records` field:

```json
{
  "records": [...]
}
```

Plynt's `SalesforceQueryResponse` model expects the full envelope
(all four fields) for consistent validation and type safety. Services that
invoke SOQL queries must handle both the standard and minimal cases.

Without normalization, minimal payloads cause validation errors. The service
layer must decide: fail-fast or fill in reasonable defaults?

______________________________________________________________________

## Decision

### 1. Normalize before validation

Query services in the lookup, identity, and query modules will normalize
responses before passing them to `SalesforceQueryResponse.model_validate()`.

Normalization rules (applied to a parsed JSON dict):

1. If `totalSize` is missing, compute it as `len(records)`.
1. If `done` is missing, default to `true` (end of result set).
1. If `nextRecordsUrl` is missing, default to `null` (no pagination).
1. Preserve `records` as-is.

```python
normalized_payload = {
    "totalSize": payload.get("totalSize", len(records)),
    "done": payload.get("done", True),
    "nextRecordsUrl": payload.get("nextRecordsUrl"),
    "records": records,
}
return SalesforceQueryResponse.model_validate(normalized_payload).records
```

### 2. Why normalize before validation

- **Type safety**: Pydantic models require all fields present for strong validation.
- **Consistency**: All query responses follow the same envelope structure.
- **Pagination**: Proper `nextRecordsUrl` handling requires explicit field presence.
- **Backward compatibility**: Minimal payloads from older Salesforce orgs are handled gracefully.

### 3. Implementation locations

This pattern is used in:

- `SalesforceIdentityAccessService._query_records()` (sync)
- `AsyncSalesforceIdentityAccessService._query_records()` (async)
- `SalesforceLookupService._query()` (sync)
- `AsyncSalesforceLookupService._query()` (async)
- `SalesforceQueryService.query()` and related methods

______________________________________________________________________

## Rationale

### Why not skip validation?

Skipping Pydantic validation would lose type safety and make pagination
logic harder to reason about. The cost of normalization is negligible compared
to the HTTP roundtrip.

### Why not use defaults in the model?

`SalesforceQueryResponse` fields are required at the API level, not optional.
Defaults belong in the service layer (where responses are parsed), not in the
schema.

### Why not fail on minimal payloads?

Some Salesforce endpoints intentionally return minimal payloads for performance.
Normalizing gracefully allows us to support a wider range of use cases.

______________________________________________________________________

## Consequences

### Positive

- ✅ All query responses type-check consistently.
- ✅ Pagination state is always explicit (`done` and `nextRecordsUrl`).
- ✅ Edge cases with minimal payloads are handled without exception.
- ✅ Service logic remains decoupled from schema validation details.

### Negative

- ⚠️ Query methods have a small normalization overhead (negligible vs HTTP latency).
- ⚠️ If a query response is missing `records` entirely, validation fails — this is intentional (abort on structural error).

______________________________________________________________________

## References

- **ADR-0013**: HTTP transport layer abstraction
- **Pydantic Docs**: [Model Validation](https://docs.pydantic.dev/latest/concepts/models/#model-validation)
- **Salesforce REST API**: [Query Parameter](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_query.htm)
