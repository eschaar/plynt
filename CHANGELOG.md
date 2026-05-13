# Changelog

All notable changes to this project are documented in this file.

## [0.2.0] - 2026-05-14

### Added

- Salesforce connector package with typed client and service modules.
- Salesforce auth, query, bulk, metadata, identity, composite, and utility APIs.
- Connector-focused tests, smoke coverage, and usage examples.

## [0.1.0] - 2026-05-14

### Added

- Core HTTP foundation with request, response, transport, and middleware layers.
- Cache abstractions and default cache adapters.
- Shared error mapping, retry policies, logging utilities, and VCR test support.
- Project documentation, ADR set, and core test suite.


## v0.2.0 (2026-03-23)

### Features

- **Salesforce**: added `SalesforceSearchRecord` / `SalesforceSearchResponse` typed models for SOSL search results
- **Salesforce**: `SalesforceLimitsResponse` is now dict-like (`keys()`, `values()`, `items()`)
- **Salesforce**: added `security_token` parameter to `SalesforcePasswordAuthMiddleware`
- **Salesforce**: added `SalesforceApiVersion` model and `versions()` endpoint to `UtilityService`
- **Salesforce**: extracted `SalesforceQueryService` from `UtilityService`
- **Logging**: `LoggingMiddleware` / `AsyncLoggingMiddleware` now emit ECS structured fields
  via `extra` (`event.action`, `http.request.method`, `url.full`, `http.response.status_code`,
  `event.duration`)
- **Logging**: `StructuredFormatter` serialises `extra` fields into the JSON payload
- **Logging**: middleware response logs include elapsed time in milliseconds
- **Logging**: transport log lines use arrow convention (`-->` / `<--`)
- **Logging**: auth transport automatically adds `LoggingMiddleware` at DEBUG level for
  token-fetch requests
- **HTTP**: `ExtendedJSONRenderer` extracted into core; `SalesforceRenderer` delegates to it

### Refactors

- `SObjectAPIFacade` renamed to `SalesforceAPIFacade`
- `service.py` renamed to `sobject.py` (and `test_service.py` → `test_sobject.py`)
- Salesforce examples restructured under `examples/salesforce/`
- Default logger name changed from `plynth.middleware.logging` to `plynth.http`

### Documentation

- ADR-0014 updated: ECS field table, arrow convention, `plynth.http` logger hierarchy
- ADR-0017 added: streaming response design
- `ROADMAP.md` updated with short-term priorities and long-term goals
- `docs/connectors/salesforce/` README and ROADMAP added

## v0.1.0 (2026-03-14)

- Initial Release
