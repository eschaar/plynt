# SF-0002: Salesforce facade ergonomics

- Status: Accepted
- Date: 2026-03-18

## Context

The Salesforce integration already has a clean split between auth,
client, and service layers. Users asked for ergonomic entrypoints without
collapsing this architecture or moving business logic into the connector.

The facade started as an object-level convenience layer, but it has since
become the stable composition surface for the current shipped service
families.

## Decision

Introduce thin facade classes that only compose existing services:

- `SalesforceAPIFacade`
- `AsyncSalesforceAPIFacade`

Both expose the current thin service factories, returning the appropriate
typed service and nothing more:

- `sobject(object_name, ...)`
- `utility(...)`
- `query(...)`
- `object_query(object_name, ...)`
- `search(...)`
- `bulk(...)`
- `composite(...)`
- `apex_rest(...)`
- `metadata(...)`
- `identity_access(...)`
- `lookup(...)`

Each method composes the corresponding service layer and must not implement
workflow logic, policy decisions, or business-specific orchestration.

## Consequences

Positive:

- Improves discoverability and day-to-day ergonomics.
- Keeps transport, auth, and error handling in existing layers.
- Preserves sync/async parity by design.
- Gives callers a single, consistent entrypoint for all shipped service
  families.

Negative:

- Adds one more public entrypoint to document and maintain.
- Broadens the facade surface area over time, requiring careful documentation
  discipline.

## Notes

This ADR does not change core abstractions or dependency structure.
It is scoped to the Salesforce integration module.

Related capability-specific additions are documented in SF-0003, SF-0004,
SF-0005, SF-0007, SF-0008, and SF-0009.
