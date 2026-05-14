# SF-0008: Salesforce Metadata REST Deploy

**Date:** 2026-05-10
**Status:** Accepted

## Context

Salesforce exposes part of its Metadata API through REST deploy operations.
That REST surface is sufficient for deploy-focused workflows such as starting
a deploy from a ZIP payload, polling status, performing quick deploy, and
canceling an in-progress deploy.

The connector is REST-first and does not provide SOAP transport. That means
the generic connector should only implement the Metadata REST deploy
primitives that are reachable without SOAP, while keeping SOAP-only catalog
and retrieve operations out of scope until core SOAP support exists.

## Alternatives Considered

### Option 1: Do Nothing

**Description:** Leave metadata deploy unsupported.

**Pros:**

- No additional surface area.

**Cons:**

- Blocks a meaningful Salesforce deployment workflow.
- Forces consumers to implement their own low-level REST handling.

**Why rejected:** Metadata deploy is a core Salesforce REST capability.

### Option 2: Implement SOAP Metadata API

**Description:** Add SOAP transport and expose the full Metadata API,
including retrieve and catalog operations.

**Pros:**

- Broadest feature coverage.

**Cons:**

- Introduces a new transport model and dependency surface.
- Expands the connector beyond the current REST-first architecture.

**Why rejected:** Exceeds the current connector scope and requires a separate
transport decision.

### Option 3: Delay Until a Future SOAP Layer Exists

**Description:** Postpone metadata entirely until SOAP support is available.

**Pros:**

- Avoids partial coverage.

**Cons:**

- Leaves deploy workflows unavailable even though they are REST-capable.

**Why rejected:** The REST deploy subset can be implemented now without SOAP.

## Decision

We will ship the REST-only Metadata deploy subset as a first-class connector
service and keep SOAP-only Metadata API operations out of scope for now.

This gives consumers deploy capability now without forcing a SOAP transport
dependency into the generic connector.

## Rationale

The Metadata deploy flow is useful enough to justify a dedicated service, but
the generic connector should only implement what the REST surface can provide.
That keeps the architecture consistent with the rest of the module: thin
services, typed models, and no business workflow logic.

The deploy subset is also a good fit for sync/async parity and for a small,
typed API surface that can be tested thoroughly. Polling and quick deploy are
transport concerns, not domain workflows.

Keeping SOAP-only operations out of scope prevents accidental expansion into a
new transport stack and preserves the current connector boundary.

## Consequences

### Positive

- Provides REST deploy support immediately.
- Keeps the connector REST-first and dependency-light.
- Maintains a clear boundary between deploy primitives and SOAP-only metadata
  catalog/retrieve operations.

### Negative / Tradeoffs

- Not all Metadata API functionality is available.
- Callers needing retrieve/catalog flows must wait for SOAP support or use a
  different integration path.
- The service adds another public API family to maintain.

### Risks

- Users may assume Metadata REST implies full Metadata API coverage.
  Mitigation: document the SOAP-only exclusions clearly.
- Polling semantics and deploy timing can vary by org size and payload.
  Mitigation: keep timeout and wait behavior explicit in the API.

## Related ADRs

- SF-0001: Salesforce Error Mapping — deploy failures use typed exceptions.
- SF-0002: Salesforce facade ergonomics — exposes the metadata service as a
  thin constructor.
- SF-0005: Salesforce Bulk API 2.0 Service Design — similar long-running job
  lifecycle and polling patterns.
