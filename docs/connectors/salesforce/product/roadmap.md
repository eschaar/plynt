# Salesforce Integration: Architecture & Roadmap

## Purpose

Build a framework-agnostic integration with Salesforce, located under
`src/plynth/connectors/salesforce/`. Extraction to a standalone package is
explicitly deferred until after multiple stable plynth releases are live and
multiple connectors exist.

## Structure

Current module layout:

- `sobject/`: Generic SalesforceObjectService (CRUD, describe, layout,
  deleted/updated window, external ID)
- `utility.py`: SalesforceUtilityService (limits, tooling execute)
- `search.py`: SalesforceSearchService (SOSL search, quick search)
- `composite.py`: SalesforceCompositeService (composite, batch, tree)
- `query/`: SalesforceQueryService (SOQL execution, pagination)
- `facade.py`: SalesforceAPIFacade (high-level facade over all services)
- `auth/`: Authentication middlewares (OAuth2 password, client credentials)
- `client.py`: SalesforceAPIClient (base URL, API version, auth injection)
- `models/`: Typed response models
- `settings.py`: Pydantic-settings-based configuration
- `renderer.py`: JSON renderer with Salesforce-compatible encoding
- `errors.py`: Typed error hierarchy (maps Salesforce error payloads)
- `constants.py`: Shared literals and defaults

## Implemented Capabilities

The following are implemented and covered by tests:

- **SObject CRUD**: create, get, update, delete, upsert,
  get/list-by-external-id
- **SObject metadata**: describe, available layouts, deleted/updated windows
- **SOQL queries**: execute with pagination support (query, query_more,
  query_all, include_deleted via `queryAll`)
- **SOSL search**: search and quick_search with typed `SalesforceSearchResponse`
- **SOSL/SOQL helpers**: `escape_sosl`, `format_soql`, `build_select_soql`,
  `is_salesforce_id`, `validate_salesforce_id`
- **Utility endpoints**: limits (typed), tooling execute
- **Observability**: API usage parsing from `Sforce-Limit-Info`
- **Developer experience**: lookup registry, helper builders, REST/Apex
  passthrough entry points
- **Lookup conveniences**: Queue and Profile lookup services
  (`SalesforceQueueLookupService`, `SalesforceProfileLookupService`,
  and async counterparts) — list, get-by-name, get-by-developer-name
- **Incremental query helper**: `query_updated_since()` on
  `SalesforceObjectQueryService` / `AsyncSalesforceObjectQueryService`
  — timezone-aware datetime validation, configurable timestamp field,
  composable WHERE and ORDER BY
- **Composite primitives**: composite, batch, tree request/response models
- **Objects catalog**: `objects()` (`GET /sobjects/`) with typed
  `SalesforceGlobalDescribeResponse`
- **Facade**: SalesforceAPIFacade / AsyncSalesforceAPIFacade
- **Authentication**: OAuth2 password flow, OAuth2 client credentials flow
- **Error handling**: typed error mapping from Salesforce payloads (SF-0001)
- **Sync and async**: full parity for all implemented capabilities

## Salesforce REST Capability Overview

This matrix consolidates the connector direction in one place.
It is intentionally generic and aligned with common Salesforce REST
integration capabilities seen across mature client libraries and service
integration implementations.

### Status Legend

- **Done**: implemented and supported now.
- **Planned**: intended roadmap item.
- **Deferred**: intentionally postponed until explicit activation criteria are met.
- **Conditional**: only implement when repeated demand appears.
- **Out of Scope**: intentionally excluded from generic core.

| Capability Domain                          | Typical REST API Scope                                                | Plynth Status | Support Policy                     | ADR     | Notes                                                                                         |
| ------------------------------------------ | --------------------------------------------------------------------- | ------------- | ---------------------------------- | ------- | --------------------------------------------------------------------------------------------- |
| Authentication and session handling        | OAuth token endpoint, bearer token usage, externally managed sessions | Done          | Maintain                           | SF-0006 | OAuth client credentials, OAuth password (legacy), JWT bearer, direct token/session injection |
| API version discovery                      | `GET /services/data/`                                                 | Done          | Maintain                           | —       | Optional dynamic version selection with cache                                                 |
| SObject data operations                    | `/sobjects/{Object}` and related record endpoints                     | Done          | Maintain                           | —       | CRUD, upsert, external ID flows, describe, layout, deleted and updated windows                |
| Query operations                           | `/query`, `/queryAll`, pagination cursors                             | Done          | Maintain                           | SF-0003 | SOQL execution, query_more, query_more_from_id, typed query responses                         |
| Search operations                          | `/search`, `/parameterizedSearch`                                     | Done          | Maintain                           | SF-0004 | SOSL search, quick search, escape helpers                                                     |
| Utility and org introspection              | `/limits`, `/sobjects`, `/tooling/*`                                  | Done          | Maintain                           | —       | Limits, API usage parsing, object catalog, tooling execute                                    |
| Observability                              | Response headers and usage telemetry (`Sforce-Limit-Info`)            | Done          | Maintain                           | —       | Typed API usage parsing and exposure via limits context                                       |
| Developer experience (DX)                  | Lookup and helper abstractions for safer usage                        | Done          | Maintain                           | SF-0002 | Enum-based lookup registry, query helpers, escape hatch convenience                           |
| Generic lookup helpers                     | Composite of query and object endpoints                               | Done          | Deferred expansion                 | —       | RecordType, User, Pricebook, Queue, Profile lookup services via enum-based registry           |
| Apex REST passthrough                      | `/apexrest/*`                                                         | Done          | Maintain                           | —       | Dedicated sync and async service entry points                                                 |
| Bulk data processing                       | Bulk API v2 ingest and query resources                                | Done          | v2-first                           | SF-0005 | Bulk API v1 remains excluded by default                                                       |
| Metadata deployment (REST)                 | `/metadata/deployRequest` operations                                  | Done          | Maintain                           | SF-0008 | Start deploy, status polling, quick deploy, cancel, wait helpers, sync and async parity       |
| Composite request orchestration            | `/composite/*`, `/composite/tree/*`, `/composite/batch/*`             | Done          | Maintain                           | SF-0007 | Generic composite primitives for request minimization and transactional orchestration         |
| Identity access primitives (generic)       | User, PermissionSetAssignment, PermissionSetGroupAssignment endpoints | Done          | Deferred expansion                 | SF-0009 | Policy-neutral user retrieval/listing, assignment create/delete, and user active toggle       |
| Event streaming (CDC / Pub-Sub)            | Salesforce Pub/Sub API over gRPC                                      | Deferred      | ADR-required before implementation | —       | Requires gRPC transport design alignment and an accepted capability ADR                       |
| Upstream rate governance                   | Client-side throttling, quota backpressure, and pacing                | Deferred      | Core middleware first              | —       | Prefer shared core middleware policy over connector-specific throttling logic                 |
| GraphQL API                                | Flexible query interface: `/graphql` POST with queries and mutations  | Conditional   | Implement on repeated demand       | —       | Alternative to REST; no core plynth changes required; complements SOQL/SOSL queries           |
| Generative AI — Models API                 | `/einstein/platform/v1` chat, text, embeddings inference              | Planned       | Streaming support first            | —       | Generate Chat, Text, Embeddings with feedback loop; depends on ADR-0017 implementation        |
| Generative AI — Agent API                  | `/einstein/ai-agent/v1` agent session and message orchestration       | Planned       | Streaming support first            | —       | Session lifecycle, sync/streaming messaging, feedback; depends on ADR-0017 implementation     |
| Metadata retrieval and catalog (SOAP-only) | `retrieve`, `listMetadata`, `describeMetadata` (SOAP Metadata API)    | Out of Scope  | Re-evaluate with SOAP core support | —       | Not available via REST-only connector scope                                                   |
| Business-specific contrib layers           | Business-specific wrappers on top of generic connector                | Out of Scope  | Keep in consumer layer             | —       | Protects framework-agnostic, reusable connector core                                          |

### ADR Coverage Notes

Rows with `—` in the ADR column intentionally rely on existing policy and
scope boundaries rather than a dedicated Salesforce capability ADR.

- API version discovery: covered by connector layering rules and kept as an
  internal client concern.
- Utility and observability behavior: covered by existing shipped REST
  surface and core observability/retry policies.
- CDC / Pub-Sub: blocked until a dedicated accepted ADR is written for the
  capability and transport contract.
- Upstream rate governance: delegated to shared core middleware decisions,
  not connector-local behavior.
- GraphQL API: no core plynth changes required; standard HTTP POST + JSON
  response handling suffice. Implement only on repeated demand to avoid
  over-engineering before consumer needs are clear.
- Generative AI (Models + Agent API): both depend on **ADR-0017 streaming
  response support** to fully realize streaming message and inference use cases.
  Sync variants are feasible without streaming but limit real-time UX.
- SOAP metadata and business-specific contrib layers: explicitly out of scope
  by connector policy.

## Strategic Review: AI API Integration

**Decision:** Salesforce Models API and Agent API are classified as **Planned**
items (not Conditional or Deferred). This reflects three strategic factors:

1. **Salesforce product direction:** Agentforce is central to Salesforce's AI
   narrative. Models and Agent APIs are the programmatic entry points. Supporting
   them positions plynth as a natural choice for Salesforce AI workloads.

1. **Streaming blocker:** Both APIs achieve their best UX with streaming support
   (ADR-0017). Streaming is therefore elevated to a critical blocker for the
   entire AI roadmap. This is correct because streaming support (item 3) unlocks
   *five downstream items*: Models API, Agent API, gRPC transport, CDC/Pub-Sub,
   and the LLM connector.

1. **Scope boundary:** Models and Agent APIs are Salesforce-specific orchestration
   layers, not generic connectors. They belong here, not in a future LLM adapter.
   Generic LLM support (OpenAI, etc.) remains a separate concern in the core
   `plynth.connectors.llm` module.

**Implication:** Streaming support (ADR-0017) adoption is now front-and-center
in core roadmap prioritization.

**Roadmap note:**

- Salesforce Models API and Agent API can be developed in parallel with the
  generic LLM connector, but the two tracks must stay independent.
- Do not make either connector depend on the other; only share neutral core
  streaming and transport capabilities.
- Salesforce-specific AI orchestration stays in the Salesforce connector,
  while generic provider-agnostic AI abstractions belong in `plynth.connectors.llm`.

## Priorities

Near-term priority order for REST capability growth:

1. Defer identity primitive expansion until recurring generic demand is proven.
1. Defer lookup expansion until recurring generic demand is proven.
1. Defer query-helper expansion until recurring generic demand is proven.

Activation criteria for deferred expansion:

- At least two independent consumer use cases need the same primitive.
- At least three repeated call-sites show the same integration pattern.
- No org-specific policy, role mapping, or naming assumptions are needed.
- The behavior can be expressed with existing generic primitives.

## Scope Boundaries

- Plynth Salesforce connector remains **REST-first**.
- SOAP metadata capabilities stay outside scope until core SOAP transport
  exists.
- Business-specific logic remains outside generic connector core.

## Implementation Notes and Decisions

This section keeps the key technical context behind the matrix so the roadmap
stays actionable for engineering decisions.

### API Version Discovery

- `versions()` is available on the utility service (`GET /services/data/`).
- If `api_version` is not set, the client can resolve the latest available
  version dynamically.

Architecture notes:

- Discovery belongs in the client layer, not middleware.
- Discovery should run once per client lifecycle and be cacheable.
- The first authenticated call can require two requests
  (version discovery plus actual endpoint call).

### Authentication Direction

- Support modern and legacy org setups through multiple auth patterns:
  client credentials, JWT bearer, and direct token/session injection.
- Username/password remains available for compatibility with legacy orgs,
  but should not receive net-new feature investment.

### Query and Utility Direction

- Keep query ergonomics practical:
  `query_all`, `query_more_from_id`, and lightweight SOQL builders.
- Expand builder patterns only when repeated real use cases are observed.
- Keep utility endpoints focused on operational value:
  limits, object catalog, tooling execute, and API usage parsing.

### Identity Access Direction

- Keep identity access primitives policy-neutral and low-level.
- Support generic operations only: user retrieval/listing, permission set
  assignment create/delete, permission set group assignment create/delete,
  and user active-flag update.
- Keep password reset logic, role-policy mapping, and org-specific
  provisioning flows in consuming applications.

### Metadata REST Deploy Scope

Plynth supports the REST deploy pipeline through
`/metadata/deployRequest` operations:

- `POST /metadata/deployRequest` to start a deploy from a ZIP package.
- `GET /metadata/deployRequest/{id}` to poll status
  (`includeDetails=true` when needed).
- `POST /metadata/deployRequest/{validatedId}` for quick deploy.
- `PATCH /metadata/deployRequest/{id}` to cancel in-progress deploys.

Supporting expectations:

- Wait helpers for terminal status with timeout behavior.
- Typed models for deploy status and details.
- Typed error mapping for failed deploy paths.
- Sync and async parity.

Out-of-scope in the current REST-first connector:

- SOAP metadata-only operations such as `retrieve`, `listMetadata`, and
  `describeMetadata`.

See [SF-0008](../architecture/adr/sf-0008-metadata-rest-deploy.md) for the decision record.

### Composite REST Primitives

Plynth exposes the Salesforce composite REST primitives without embedding
business workflows in the connector.

Supported building blocks:

- `composite(...)` for chained subrequests with `referenceId` linking.
- `batch(...)` for grouped REST requests.
- `tree(...)` for hierarchical parent/child creates.

Example flow (consumer-level orchestration):

1. Create an Account in the first subrequest.
1. Reference the returned Account id in the next subrequest to create a
   Contact or Opportunity.
1. Keep domain-specific decisions, such as which objects to create and when,
   in the consuming application.

This keeps the connector generic while still making composite a first-class
building block for higher-level flows.

See [SF-0007](../architecture/adr/sf-0007-composite-rest-primitives.md) for the decision
record.

### Backlog Focus

- Identity primitive expansion remains deferred and pattern-driven.
- Lookup expansion remains deferred and pattern-driven.
- Query-helper expansion remains deferred and pattern-driven.
- Package extraction stays in backlog for later versions; not targeted for
  the first live releases.

## Extraction Notes

This integration is intentionally kept extractable, but extraction is not
planned for the first live versions.
Execution starts only when both conditions are met:

- multiple stable plynth versions are live in production
- multiple connectors are shipped and maintained in-repo

See [extraction-plan.md](extraction-plan.md)
for sequencing and packaging details.

## Principles

- All code under `src/plynth/connectors/salesforce/`
- No business-specific or org-specific logic in the core package
- Extractable architecture, with package extraction deferred to later versions
- Use Plynth core abstractions (Service, Transport, Middleware)
- Focus on testability and extensibility
- Framework-agnostic: no Django/FastAPI/Flask imports in this module
- No business- or org-specific convenience services in the generic connector;
  these belong in the consuming application layer
