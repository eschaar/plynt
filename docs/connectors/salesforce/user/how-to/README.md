# Salesforce — How-to guides

## Authentication

- [Authenticate with JWT Bearer](authenticate.md#jwt-bearer-flow-recommended)
  — recommended for all new orgs; no shared secret
- [Authenticate with Client Credentials](authenticate.md#client-credentials-flow)
  — simpler machine-to-machine; uses a shared secret
- [Authenticate with Username/Password](authenticate.md#usernamepassword-flow-legacy)
  — legacy flow for older orgs
- [Inject a session token](authenticate.md#session-token-edge-case)
  — when token management happens outside Plynth

## Data operations

- [Query records with SOQL](query-records.md) — single page, paginated,
  incremental (updated-since)
- [Create, update, and delete SObject records](sobject-crud.md) — CRUD,
  upsert, external ID, describe, deleted/updated tracking
- [Search with SOSL](search.md) — full-text and quick search
- [Run Bulk API operations](bulk.md) — ingest and query large data volumes
- [Use composite and batch requests](use-composite.md) — multiple sub-requests
  in a single round-trip

## AI and agents

- [Use the Agentforce API](use-agent-api.md) — start sessions, send messages,
  stream responses, submit feedback
- [Use the Salesforce Models API](use-models-api.md) — chat completions,
  text generation, embeddings (Einstein)

## Resilience and observability

- [Add resilience with circuit breaking](resilience.md) — protect against
  Salesforce downtime and observe quota usage
- [Deploy the CDC subscriber in Kubernetes](deploy-cdc.md) — checkpoint
  backend, graceful shutdown, and consumer topology

## Errors

- [Handle Salesforce errors](handle-errors.md) — catch typed exceptions,
  inspect error codes and fields
