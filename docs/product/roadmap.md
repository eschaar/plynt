# Plynth — Roadmap

This document tracks what is implemented, what is planned, and what
is deferred. It is a living document: update it alongside ADRs when
decisions are made or scope changes.

Companion product documents:

- [Vision](vision.md)
- [Requirements](requirements.md)

______________________________________________________________________

## Implemented Baseline (through v0.2.1)

### Core abstractions (`plynth.base`)

- `SyncTransport` / `AsyncTransport` ABCs (ADR-0006)
- `BaseSyncTransport` / `BaseAsyncTransport` — compose a middleware chain
  and delegate I/O to `_send_once()` (ADR-0013)
- `Request` / `Response` data carriers (ADR-0005, ADR-0007)
- `StreamingResponse` / `AsyncStreamingResponse` — typed streaming HTTP
  response with `iter_lines()` / `aiter_lines()` and `iter_bytes()` /
  `aiter_bytes()` methods (ADR-0017)
- `StreamInterruptedError` — raised on stream close or interruption (ADR-0017)
- `SyncMiddleware` / `AsyncMiddleware` Protocols (ADR-0013)
- `Cache` Protocol (ADR-0010)
- `RetryPolicy` dataclass (ADR-0012)
- `CircuitBreakerPolicy` dataclass — controls circuit breaker state machine
  (ADR-0019)
- `RateLimitPolicy` dataclass — controls sliding-window rate limiting
  (ADR-0020)
- `Settings` base class — env-driven, pydantic-settings (ADR-0004)
- `BaseError` hierarchy (ADR-0007)

### HTTP transport (`plynth.http`)

- `HttpxSyncTransport` / `HttpxAsyncTransport` — httpx-backed transport
  implementations with full middleware wiring (ADR-0013)
- `HttpxSyncTransport.from_settings()` / `HttpxAsyncTransport.from_settings()`
  — zero-boilerplate environment-driven construction, including auth wiring
  via the `auth` typed config property (ADR-0011) and cache wiring via
  `caches`, `default_cache`, and `default_auth_cache` properties (ADR-0010)
- `HTTPSettings` / `ApiSettings` — structured timeout, proxy, TLS; typed
  `auth` property (ADR-0011) and typed cache properties (`caches`,
  `default_cache`, `default_auth_cache`) for response and token caches
  (ADR-0004, ADR-0010)
- `plynth.http.auth` — typed auth configuration dataclasses
  (`BearerAuthConfig`, `BasicAuthConfig`, `OAuth2ClientCredentialsConfig`,
  `OAuth2JWTBearerConfig`, `OAuth2PasswordConfig`) plus factory functions
  `auth_from_config()` / `async_auth_from_config()` (ADR-0011)
- Auth middleware in `plynth.http.middleware.auth/` (ADR-0011):
  - `BearerTokenAuthMiddleware`, `BasicAuthMiddleware` (sync + async)
  - `OAuth2AuthMiddlewareBase` — abstract base for all OAuth2 flows
  - `OAuth2ClientCredentialsMiddleware` / `AsyncOAuth2ClientCredentialsMiddleware`
    (Client Credentials flow, machine-to-machine)
  - `OAuth2JWTBearerMiddleware` / `AsyncOAuth2JWTBearerMiddleware`
    (JWT Bearer flow)
  - `OAuth2PasswordMiddleware` / `AsyncOAuth2PasswordMiddleware`
    (Resource Owner Password Credentials flow, legacy)
  - `OAuth2AuthMiddleware` / `AsyncOAuth2AuthMiddleware` backward-compat aliases
  - Pluggable token cache: `token_cache=` accepts any `CacheBackend`
    (`LocMemCache` default; `RedisCache` for cross-process sharing)
- `HttpRetryPolicy` — HTTP-aware retry with configurable backoff (ADR-0012)
- `HttpResponse` — encoding detection, `.text`, `.json()` (ADR-0007)
- Streaming HTTP support — `HTTPClient.stream()` / `AsyncHTTPClient.stream()`
  and `APIClient.stream()` / `AsyncAPIClient.stream()` methods for SSE and
  chunked responses (ADR-0017)
- `HttpStatusError` subclasses per HTTP status group (ADR-0007)
- `HTTPClient` / `AsyncHTTPClient` — base URL + verb API (ADR-0008)
- `APIClient` / `AsyncAPIClient` — JSON REST + typed error raising (ADR-0008)
- `HTTPService` / `AsyncHTTPService` — raw HTTP service base (ADR-0009)
- `APIService` / `AsyncAPIService` — JSON REST service base (ADR-0009)
- `JSONRenderer` — JSON body serialiser (ADR-0009)
- `APIErrorMapper` — maps HTTP status codes to typed errors (ADR-0007)

### Middleware (`plynth.middleware`)

- `CacheMiddleware` / `AsyncCacheMiddleware` — opt-in response caching
  (ADR-0010, ADR-0013)
- Typed cache configuration dataclasses: `DummyCacheConfig`,
  `LocMemCacheConfig`, `RedisCacheConfig` (ADR-0010)
- `cache_from_config(config)` — typed factory for `CacheBackend` instances
- `CircuitBreakerMiddleware` / `AsyncCircuitBreakerMiddleware` — configurable
  circuit breaker for detecting and containing cascading failures (ADR-0019)
- `CircuitBreakerPolicy` — typed circuit breaker configuration with
  `failure_threshold`, `recovery_timeout`, `half_open_max_calls` (ADR-0019)
- `CircuitBreakerOpenError` — raised when circuit is open (ADR-0019)
- `RateLimitMiddleware` / `AsyncRateLimitMiddleware` — sliding-window request
  rate limiting (ADR-0020)
- `RateLimitPolicy` — typed rate limit configuration with `max_requests` and
  `window_seconds` (ADR-0020)
- `RateLimitExceededError` — raised when rate limit is exceeded (ADR-0020)
- `RetryMiddleware` / `AsyncRetryMiddleware` — configurable retry with
  exponential backoff (ADR-0012, ADR-0013)
- `LoggingMiddleware` / `AsyncLoggingMiddleware` — INFO-level request /
  response logging, once per logical call outside the retry loop (ADR-0014)
- `HeaderMiddleware` / `AsyncHeaderMiddleware` — inject static or dynamic
  headers on every request (ADR-0015)
- `ThrottleFilter`, `ExceptionInfoFilter`, `PlynthHTTPFilter` — stdlib
  logging filters (ADR-0014)
- `StructuredFormatter` — single-line JSON log output (ADR-0014)
- Opt-in body logging with mandatory credential scrubbing (`log_bodies=True`)
  (ADR-0014)

### Salesforce integration (`plynth.connectors.salesforce`) — partial

- `SalesforceObjectService` / `AsyncSalesforceObjectService` — SObject REST
  operations for sync and async clients, including CRUD, `metadata`,
  `describe`, `describe_layout`, `deleted`, and `updated`
- `SalesforceAPIClient` — extends `APIClient` with dynamic `instance_url`
  resolution from the OAuth2 token response
- `AsyncSalesforceAPIClient` — async client counterpart with dynamic
  `instance_url` resolution
- `SalesforceJWTBearerAuthMiddleware` /
  `AsyncSalesforceJWTBearerAuthMiddleware` — Salesforce-specific JWT Bearer
  auth support
- `SalesforceSessionAuthMiddleware` /
  `AsyncSalesforceSessionAuthMiddleware` — direct session token injection for
  externally managed tokens
- `SalesforceClientCredentialsAuthMiddleware` — extends
  `OAuth2AuthMiddleware` to
  capture and cache `instance_url` alongside the access token
- `SalesforcePasswordAuthMiddleware` and async auth counterparts
- `SalesforceAPIFacade` / `AsyncSalesforceAPIFacade` — ergonomic facade that
  returns object-bound services (ADR: SF-0002)
- `SalesforceCompositeService` / `AsyncSalesforceCompositeService` — typed
  composite, batch, and tree REST operations
- `SalesforceMetadataService` / `AsyncSalesforceMetadataService` — Metadata
  REST deploy helpers
- `SalesforceIdentityAccessService` /
  `AsyncSalesforceIdentityAccessService` — generic user and assignment
  primitives
- `SalesforceUtilityService` / `AsyncSalesforceUtilityService` — `limits()`,
  `versions()`, `objects()`, and `tooling_execute()`
- Lookup conveniences: `SalesforceQueueLookupService`,
  `SalesforceProfileLookupService`, and async counterparts — list,
  get-by-name, get-by-developer-name via enum-based registry
- `query_updated_since()` incremental query helper on
  `SalesforceObjectQueryService` / `AsyncSalesforceObjectQueryService`
- `SalesforceSettings` — extends `ApiSettings` with `instance_url` and
  `api_version` fields
- `SalesforceRenderer` — JSON renderer with `datetime`, `Decimal`, and
  `UUID` support; handles `SObjectPayload` field-name mapping
- `SObjectPayload`, `SObjectCreateResult`, `SObjectError` — typed request /
  response models

### Retry (`plynth.http`)

- `HttpRetryPolicy` — typed retry configuration with `max_attempts`, `backoff_initial`,
  `backoff_multiplier`, `backoff_max`, `retry_on_network_error`, and
  `retryable_status_codes` (defaults expressed as `HTTPStatus` enum values) (ADR-0012)
- `retry` typed property on `HTTPSettings` — overridable in subclasses;
  falls back to `HttpRetryPolicy(max_attempts=self.max_attempts)` (ADR-0012)
- `token_retry_policy` on `OAuth2ClientCredentialsConfig` and `OAuth2PasswordConfig`
  — typed retry for the internal token endpoint transport (ADR-0012)
- `RetryMiddleware` / `AsyncRetryMiddleware` — wired automatically by `from_settings()`
  (ADR-0012, ADR-0013)

### Quality

- Full quality gate required and currently green: formatting, markdown lint,
  linting, type-checking, and test execution
- ruff + mypy enforced via pre-commit
- tox matrix: Python 3.11, 3.12, 3.13, 3.14
- ADR set maintained as the source of architectural truth

______________________________________________________________________

## Release Strategy

Current release history:

1. `0.1.0` core baseline release.
1. `0.2.0` Salesforce connector baseline release.
1. `0.2.1` release process and documentation stabilization release.

Forward path:

1. `0.x` series: complete core + connector scope while preserving
   compatibility where practical.
1. `1.0.0`: stable public milestone after roadmap and ADR readiness gates
   are met.

### Definition of Done: `v0.9.x` (Plynth Core)

- Core API surface frozen for 1.0 preparation.
- ADR set aligned with shipped behavior.
- Full quality gate green (lint, typecheck, tests, coverage).
- Public docs complete for core usage patterns.
- Release automation and versioning policy validated end-to-end.

### Definition of Done: `v1.0.0` (Core + Salesforce)

- Sync and async parity for supported Salesforce features.
- Connector docs and examples usable without internal context.
- Stable error model and retry behavior documented and tested.
- Explicit scope boundaries documented (what is supported vs deferred).
- Public release checklist complete (tests, docs, packaging, changelog).

### Repository History Note

Repository history has already been reset and normalized for the current
public release baseline. Future history rewrites are not part of normal
delivery and should only happen via explicit maintenance decision.

______________________________________________________________________

## Planned

Items are ordered by dependency and priority: core library completeness first,
then integration validation, then framework adapters.

Core streaming support, circuit breaking, and client-side rate limiting are now
implemented. The remaining roadmap items below build on that shipped
foundation rather than block on it.

______________________________________________________________________

### Middleware extensions

**Status:** `HeaderMiddleware`, `Request.timeout`,
`CircuitBreakerMiddleware`, and `RateLimitMiddleware` are implemented.
See [`docs/product/ideas/middleware-extensions.md`](ideas/middleware-extensions.md)
for remaining items.

Extend `plynth.middleware` with additional cross-cutting concerns. Ordered by
priority within this item:

#### 1a. `HeaderMiddleware` (Tier 1 — core, no new dependencies) ✓

Implemented in `plynth.middleware.header`. Injects static or callable-generated
headers; non-overwrite guarantee; documented chain position (ADR-0015).
Covers API key auth use case without a dedicated middleware type.

#### 1b. `Request.timeout` — per-request timeout override ✓

Added `timeout: float | None = None` to `Request` (ADR-0005-A1). When set,
the httpx transport passes it directly to `client.request()`, overriding the
transport-level timeout for that single call. A `TimeoutMiddleware` was
considered and rejected — a plain field on `Request` is simpler and keeps
the override at the call site.

#### 1c. `CircuitBreakerMiddleware` (Tier 1 — core, no new dependencies) ✓

Implemented in `plynth.middleware.circuit_breaker` with sync and async
variants plus typed policy and open-circuit error support (ADR-0019).

Complements `RetryMiddleware` by failing fast when an upstream is
structurally unavailable while still allowing recovery probing.

#### 1d. `RateLimitMiddleware` (Tier 1 — core, no new dependencies) ✓

Implemented in `plynth.middleware.rate_limit` with sync and async variants
plus typed policy and rate-limit exceeded error support (ADR-0020).

Provides client-side pacing to stay within upstream quotas using a core
middleware rather than connector-specific throttling logic.

#### 1e. `TracingMiddleware` — `plynth[otel]` (Tier 2)

OpenTelemetry span per HTTP call, following HTTP semantic conventions. See
[idea](ideas/middleware-extensions.md#tracingmiddleware-plynthotel) for
interface sketch.

**Note:** `opentelemetry-instrumentation-httpx` covers the common tracing
use case without any plynth middleware. This item is only warranted if
consumers need spans scoped to plynth's middleware chain (e.g., latency
measured after auth and retry). Evaluate real demand before writing an ADR.

**Prerequisite:** New ADR. Must live behind `plynth[otel]` extra per ADR-0003.

#### 1f. `MetricsMiddleware` — `plynth[prometheus]` (Tier 2)

Prometheus counters and latency histograms per HTTP call. See
[idea](ideas/middleware-extensions.md#metricsmiddleware-plynthprometheus) for
interface sketch.

**Note:** `opentelemetry-instrumentation-httpx` + an OTel Prometheus exporter
already provides request counts and latency histograms with no plynth-specific
code. A dedicated `MetricsMiddleware` is not needed for the common case; it
would only add value for callers who want Prometheus metrics independent of
OTel. Low priority — evaluate real demand before writing an ADR.

**Prerequisite:** New ADR. Must live behind `plynth[prometheus]` extra per
ADR-0003.

#### 1g. `MockMiddleware` (Tier 3 — test/dev only)

Intercept requests and return pre-configured responses in tests, as a
middleware-level alternative to httpx's `MockTransport`. See
[idea](ideas/middleware-extensions.md#mockmiddleware) for interface sketch.

______________________________________________________________________

### 2. Salesforce integration — remaining work

**Status:** Partially implemented. See "Implemented" section above for what
is already in place. The following items remain.

**Purpose:** Validate plynth against a complex, multi-API external service;
surface gaps in the abstractions; serve as the reference example for writing
plynth-based clients.

**Scope priority:** Focus first on the standard Salesforce Platform REST APIs
(SObject, Query, Bulk, and related standard endpoints). Apex REST remains
available as a generic passthrough use case, while business-specific Apex
workflows stay outside connector core.

#### 2a. Fix `SalesforceObjectService` bug ✓

`SalesforceObjectService` now renders write payloads via
`content=renderer.render(...)` (no `json=` usage on `Request`).

#### 2b. Salesforce error mapping ✓

- Typed exception hierarchy rooted at `SalesforceAPIError`
  (`SalesforceValidationError`, `SalesforceDuplicateError`,
  `SalesforceNotFoundError`, `SalesforceSessionExpiredError`,
  `SalesforcePermissionError`, `SalesforceLockError`)
- `raise_for_salesforce_errors()` helper parses the Salesforce JSON error
  list and raises the appropriate subclass; falls back to `HttpStatusError`
  for non-Salesforce bodies
- Wired into both `SalesforceAPIClient` and `AsyncSalesforceAPIClient`
- ADR: [SF-0001](../connectors/salesforce/architecture/adr/sf-0001-error-mapping.md)

#### 2c. SOQL Query API (`SalesforceQueryService`) ✓

- `/services/data/vX.X/query/` and `/queryMore/` (auto-pagination)
- Typed `QueryResult` envelope (total size, done flag, records list)
- Auto-pagination helper that transparently follows `nextRecordsUrl`
- `query_all()` with `include_deleted` flag

Implementation: dedicated `SalesforceQueryService` on top of
`SalesforceAPIClient`.

Follow-up query ergonomics now implemented:

- `query_more_from_id(...)` on sync + async query services
- `SalesforceObjectQueryService` / `AsyncSalesforceObjectQueryService`
- `build_select_soql(...)` lightweight SOQL SELECT builder helper

#### 2d. Async variants ✓

- `AsyncSalesforceClientCredentialsAuthMiddleware` implemented
- `AsyncSalesforcePasswordAuthMiddleware` implemented
- `AsyncSalesforceAPIClient` and `AsyncSalesforceObjectService` implemented

**Prerequisite:** `AsyncOAuth2AuthMiddleware` implemented (ADR-0011).

#### 2e. Salesforce Bulk API 2.0 (`SalesforceBulkService`) ✓

- Job creation, data upload (CSV), job close, polling, result retrieval
- Async-first (long-running jobs)
- Ingest and query job types

Implementation: `SalesforceBulkService` and `AsyncSalesforceBulkService` in
`plynth.connectors.salesforce.bulk` (ADR SF-0005). Sync + async, full job
lifecycle, exponential-backoff polling, auto-abort on failure, CSV helpers,
`Sforce-Locator` pagination. 69 unit tests.

#### 2f. Salesforce Pub/Sub API — Change Data Capture (deferred)

- gRPC-based streaming API for CDC events
- Protobuf schema resolution via Salesforce Schema Registry
- Async consumer loop

**Note:** This is explicitly gRPC, not HTTP. The transport abstraction is
protocol-agnostic (ADR-0006 allows non-HTTP transports via direct
`SyncTransport` / `AsyncTransport` subclassing). A `GrpcAsyncTransport`
extending `AsyncTransport` directly is the expected approach — no changes to
`BaseSyncTransport` / `BaseAsyncTransport` are needed or expected.

**Prerequisite:** Write an ADR for gRPC transport before implementation.
Defer until REST + Bulk are validated.

#### 2g. Package extraction (`plynth-salesforce`)

Deferred backlog item. Extraction will be considered only after multiple
stable plynth versions are live and multiple connectors are maintained.
Bulk stability remains a prerequisite, but not sufficient on its own.

#### 2h. Apex REST (`apexecute`) for custom org endpoints ✓

- `SalesforceApexRestService` / `AsyncSalesforceApexRestService` implemented
- Exposed through facade via `facade.apex_rest()` /
  `async_facade.apex_rest()`
- Kept intentionally low-level as passthrough operations

Scope note:

- Business-specific Apex orchestration remains outside connector core.

#### 2i. SObject REST parity baseline ✓

The baseline SObject parity surface is implemented in sync and async
services:

- `metadata()` — `GET /sobjects/{Object}/`
- `describe_layout(record_id)` —
  `GET /sobjects/{Object}/describe/layouts/{record_id}`
- `deleted(start, end)` —
  `GET /sobjects/{Object}/deleted/?start=...&end=...`
- `updated(start, end)` —
  `GET /sobjects/{Object}/updated/?start=...&end=...`

Notes:

- `get_by_custom_id(...)` parity is already covered by
  `get_by_external_id(...)`.
- `upload_base64` / `update_base64` / `get_base64` are convenience helpers,
  intentionally left out of the baseline SObject service.

#### 2j. Utility REST endpoints (limits/search/tooling) ✓

- `SalesforceUtilityService` / `AsyncSalesforceUtilityService` implemented
- Endpoint wrappers:
  - `limits()`
  - `versions()`
  - `objects()`
  - `search(sosl)`
  - `quick_search(search_text)`
  - `tooling_execute(action, ...)`
- Exposed through facade via `facade.utility()` / `async_facade.utility()`

Scope note:

- This item is specific to Salesforce Platform REST API utility endpoints.
- It does not include SOAP, Bulk, or Pub/Sub APIs.

#### 2k. Identity access primitives (generic) ✓

- `SalesforceIdentityAccessService` /
  `AsyncSalesforceIdentityAccessService` implemented
- Exposed through facade via `facade.identity_access()` /
  `async_facade.identity_access()`
- Generic primitives only:
  - `get_user(...)`, `list_users(...)`
  - permission set assignment create/delete
  - permission set group assignment create/delete
  - user active-flag update

Scope note:

- Expansion is deferred until recurring generic patterns are proven.
- Org-specific provisioning logic remains outside connector core.

#### 2l. GraphQL API (`/graphql` flexible query interface)

**Status:** Conditional — on repeated demand.

- `SalesforceGraphQLService` / `AsyncSalesforceGraphQLService` — generic
  GraphQL query and mutation execution
- Exposes `query(gql_query, variables=...)` for flexible data retrieval
- Complements REST API (SOQL/SOSL) with alternative query interface
- No core plynth changes required; standard HTTP POST + JSON handling

**Core enablement:** None required. HTTP + JSON middleware already cover it.

**Scope note:**

- Implement only on repeated consumer demand (proven use cases).
- Avoids over-engineering before real need is clear.
- GraphQL schema introspection remains consumer responsibility.

#### 2m. Generative AI — Models REST API

**Status:** Planned — core streaming support is already available.

- `SalesforceModelsService` / `AsyncSalesforceModelsService` — LLM inference
  via Salesforce Einstein Trust Layer
- Exposed through facade via `facade.models()` / `async_facade.models()`
- Endpoints:
  - `generate_chat(...)` — chat completion interface
  - `generate_text(...)` — text generation with prompt
  - `generate_embeddings(...)` — vector embeddings for semantic search
  - `submit_feedback(...)` — feedback loop for inference optimization
- Full sync + async parity

**Core enablement:** Item 3 is already shipped, so streaming chat completions
can build directly on the current response and transport model.

**Scope note:**

- Models API connects plynth to Salesforce's gen-AI strategy (Agentforce).
- Complements LLM connector (item 7) but specific to Salesforce-hosted models.

#### 2n. Generative AI — Agent API

**Status:** Planned — core streaming support is already available.

- `SalesforceAgentService` / `AsyncSalesforceAgentService` — orchestrate
  Salesforce AI agents from external systems
- Exposed through facade via `facade.agent()` / `async_facade.agent()`
- Session lifecycle:
  - `start_session(agent_id, ...)` — initiate agent conversation
  - `send_message(session_id, text, ...)` — sync messaging
  - `send_message_streaming(session_id, text, ...)` — streaming message loop
  - `end_session(session_id)` — cleanup
  - `submit_feedback(...)` — feedback on agent responses
- Full sync + async parity

**Core enablement:** Item 3 is already shipped, so both sync and streaming
message flows can build on the current response and transport model.

**Scope note:**

- Agent API enables external orchestration of Salesforce agents.
- Topics, actions, and agent state remain Salesforce org concerns.
- Complements the LLM connector (item 7) for agent-specific workflows.

______________________________________________________________________

### 3. Streaming response support (SSE / chunked HTTP)

**Status:** Implemented — see [ADR-0017](../architecture/adr/0017-streaming-response.md).

This foundation work is complete and now enables planned higher-level work such
as items 2m, 2n, and 7.

Shipped core capabilities:

- `Request.stream: bool` opt-in flag (no impact on existing callers).
- `StreamingResponse` / `AsyncStreamingResponse` subtypes in
  `plynth.base.response` exposing `iter_lines()` / `aiter_lines()` and byte
  iteration helpers.
- `_send_once()` branches on `request.stream` — uses `httpx.stream()` instead
  of `httpx.request()`.
- `CacheMiddleware` and `LoggingMiddleware` get minor stream-aware
  adaptations; all other middleware and service-layer code is unaffected.
- No new runtime dependencies.

This item no longer blocks roadmap execution; the remaining work is at the
service and connector layer.

______________________________________________________________________

### 4. Framework adapters

**Status:** Not started. Ideas documented in `docs/product/ideas/`.

Deferred until the Salesforce integration (item 2) has validated that the
core abstractions are stable enough. See
[ideas/django-adapter.md](ideas/django-adapter.md),
[ideas/fastapi-adapter.md](ideas/fastapi-adapter.md), and
[ideas/flask-adapter.md](ideas/flask-adapter.md) for design sketches.

#### 4a. Django extra (`plynth[django]`) — [idea](ideas/django-adapter.md)

- `from_django_settings()` factory — reads plynth config from `settings.py`
- Django cache adapter implementing the `Cache` Protocol over `django.core.cache`
- Logging: no adapter needed; documented configuration only

#### 4b. FastAPI extra (`plynth[fastapi]`) — [idea](ideas/fastapi-adapter.md)

- `PlynthLifespan` — handles transport creation and `aclose()` via FastAPI lifespan
- `get_transport()` / `get_client()` — `Depends`-compatible DI factories
- Settings: no adapter needed; `HTTPSettings` subclasses work directly

#### 4c. Flask extra (`plynth[flask]`) — [idea](ideas/flask-adapter.md)

- Low priority — `HttpxSyncTransport.from_settings()` already works without any adapter
- `PlynthFlask` extension — stores transport in `app.extensions`, `init_app()` pattern
- Validate real demand before writing an ADR

**Prerequisite:** Write ADRs for each adapter before implementation.

______________________________________________________________________

### 5. Cache backend documentation

**Status:** Implementation complete. Documentation only remaining.

All cache backends and typed config are implemented. Missing:

- How-to guide for using `RedisCache` with custom SSL options
- How to wrap framework-native caches behind plynth's cache protocol
- How to implement a custom cache backend cleanly

______________________________________________________________________

### 6. gRPC transport (`plynth[grpc]`)

**Status:** Not started. Requires ADR before implementation.

The transport abstraction (ADR-0006) is protocol-agnostic: a `GrpcAsyncTransport`
extending `AsyncTransport` directly is the expected implementation path — no
changes to `BaseSyncTransport` / `BaseAsyncTransport` are needed.

Anticipated scope:

- `GrpcAsyncTransport` — wraps a `grpc.aio` channel; maps plynth `Request` /
  `Response` onto gRPC unary calls.
- Auth: pluggable via gRPC `CallCredentials` (maps to existing auth concepts).
- First use case: Salesforce Pub/Sub API (Change Data Capture, CDC events).
- Protobuf schema resolution and streaming consumer loop are connector-level
  concerns, not transport-level.

**Prerequisite:** New ADR before implementation. Install extra `plynth[grpc]`
per ADR-0003 dependency policy. Defer until Salesforce REST + Bulk are
validated.

______________________________________________________________________

### 7. AI / LLM connector (`plynth.connectors.llm`)

**Status:** Not started. Requires scoping and ADR before implementation.

Plynth's transport and middleware chain is well-suited for LLM API clients:
auth (API key via `BearerTokenAuthMiddleware`), retry, and rate limiting are
already available, and streaming response support is already shipped.

Anticipated scope:

- Generic `LLMService` base on top of `APIService` — handles chat completion
  and streaming endpoints.
- First target: OpenAI-compatible APIs (OpenAI, Azure OpenAI, local
  OpenAI-compatible servers such as Ollama).
- `ChatMessage`, `ChatCompletionRequest`, `ChatCompletionResponse`,
  `StreamingChunk` — typed request/response models.
- SSE line-by-line iteration via `AsyncStreamingResponse.aiter_lines()`.
- Token-bucket rate limiting via `RateLimitMiddleware` (item 1d) — relevant
  for high-throughput inference workloads.

**Prerequisite:**

1. New ADR before implementation.
1. Consider whether this lives in `plynth.connectors.llm` (generic)
   or as a separate `plynth-openai` package from the start.

**Roadmap note:**

- This work can proceed in parallel with Salesforce Models API and Agent API
  as long as the connector implementations remain independent.
- Share only neutral core capabilities such as streaming response support,
  transport primitives, and middleware; do not introduce connector-to-
  connector dependencies.
- If a shared AI abstraction emerges, keep it generic and connector-agnostic
  so that Salesforce-specific behavior stays in the Salesforce connector.

______________________________________________________________________

### 8. SOAP transport (`plynth[soap]`)

**Status:** Not started. Long-term, low priority. Requires ADR before
implementation.

The transport abstraction (ADR-0006) is protocol-agnostic: `SyncTransport` /
`AsyncTransport` define only a `send()` contract and impose no HTTP semantics.
A SOAP transport is therefore architecturally possible without modifying core
abstractions.

Anticipated scope:

- `SoapSyncTransport` / `SoapAsyncTransport` — wrap a Zeep client; map SOAP
  operations onto plynth `Request` / `Response` using a SOAP-specific
  encoding layer (XML envelope, `SOAPAction` header).
- A parallel `SoapRequest` / `SoapResponse` may be needed to carry SOAP
  operation names and XML payloads cleanly, or the existing `Request` fields
  may be reused with documented SOAP conventions.
- Auth: SOAP services typically use the same OAuth2 token as the REST surface
  — existing auth middleware applies via a custom `CallCredentials` adapter.
- First use case: Salesforce Metadata API SOAP-only operations
  (`retrieve()`, `listMetadata()`, `describeMetadata()`). The REST deploy
  pipeline (Slice D) is preferred and does not require this item.
- Zeep 4.x (actively maintained) is the expected underlying library.

**Prerequisite:** New ADR before implementation, covering the `Request` /
`Response` extension model, Zeep integration strategy, and the install extra
`plynth[soap]` per ADR-0003 dependency policy. Defer until gRPC transport
(item 6) has validated the non-HTTP transport pattern.

______________________________________________________________________

### 9. Connector package extraction policy

**Status:** Not started. Backlog — no ADR required to define the policy, but each
extraction requires its own ADR.

As connectors in `plynth.connectors.*` mature, they should be extracted into
standalone packages (`plynth-<name>`) so consumers can install only what they
need. This item tracks the policy and the pending extractions.

**Policy:**

- Each connector package declares `plynth[httpx]` as its only plynth dependency.
- No plynth internals are exposed — public API only.
- Extraction happens after the connector is stable and fully tested inside the
  monorepo.
- A connector-specific ADR is required before extraction (packaging, versioning,
  and release strategy must be decided explicitly).

**Pending extractions (backlog):**

- `plynth.connectors.salesforce` -> `plynth-salesforce`
  Prerequisite: Item 2e stable; multi-version + multi-connector gate.
- `plynth.connectors.llm` (future) -> `plynth-openai` or `plynth-llm`
  Prerequisite: Item 7 implemented.

______________________________________________________________________

## Explicitly Out of Scope

| Item                                           | Reason                                                                                                                                                                                               |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| OAuth2 authorization code flow                 | User-facing browser flow; not machine-to-machine                                                                                                                                                     |
| WebSocket transport                            | Full-duplex persistent connections; protocol model differs from the middleware chain contract; no current use case — requires its own ADR                                                            |
| Request signing (AWS SigV4, etc.)              | Custom `Authenticator` is sufficient; no built-in needed                                                                                                                                             |
| Automatic schema generation                    | Not a client library concern                                                                                                                                                                         |
| ORM-style query builders                       | Too framework-specific                                                                                                                                                                               |
| Core `MetricsMiddleware` / `TracingMiddleware` | OTel auto-instrumentation (`opentelemetry-instrumentation-httpx`) covers the common case without a built-in dependency; optional extras remain open ideas but require an ADR and demonstrated demand |
