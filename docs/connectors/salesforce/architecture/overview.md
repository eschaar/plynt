# Salesforce Connector Architecture Overview

This document describes the architecture of the Salesforce connector in plynt.

## Purpose

The connector validates plynt core abstractions against a complex real-world
API surface while staying framework-agnostic and extractable.

## Architectural Position

The REST connector sits above `plynt.http` and reuses core layers:

1. service layer for Salesforce endpoint operations,
1. API client layer for HTTP request dispatch and typed errors,
1. transport + middleware for cross-cutting behavior (auth, retry, cache,
   circuit breaker, rate limiting, logging).

The connector must not bypass these abstractions.

The experimental CDC package uses a separate async gRPC path under
[SF-0013](adr/sf-0013-salesforce-eventing-architecture.md) and
[ADR-0030](../../../architecture/adr/0030-grpc-protocol-boundary.md).
The vendored Pub/Sub adapter wraps a caller-supplied async gRPC channel.
It does not dispatch through the REST client or reuse HTTP auth middleware.

## Module Structure

Current package focus under `src/plynt/connectors/salesforce/`:

- `auth/` for Salesforce-specific auth middleware wrappers,
- `bulk/` for Bulk API 2.0 flows,
- `cdc/` for async Pub/Sub subscriptions, Avro decoding, field bitmap
  expansion, replay checkpoints, and bounded reconnect,
- `composite.py` for composite, batch, and tree primitives,
- `identity/` for generic identity access primitives,
- `lookup/` for reusable lookup conveniences,
- `metadata.py` for Metadata REST deploy flows,
- `query/` for SOQL and pagination,
- `search.py` for SOSL search,
- `sobject/` for core SObject operations,
- `utility.py` for limits, versions, objects, and tooling helpers,
- `facade.py` for ergonomic service composition.

## CDC Runtime Boundary

1. Resolve Salesforce auth metadata through an explicit metadata provider.
1. Open a bidirectional subscription through the Pub/Sub adapter.
1. Fetch and cache Avro schemas, decode payloads, and expand header bitmaps.
1. Yield typed events and request the next batch after consumption.
1. Resume reconnects from the last delivered event, not a batch-end cursor.
1. With checkpointing enabled, persist progress when the caller advances
   the iterator; close and shutdown also flush the last delivered cursor.

Consumers own idempotency, durable event handling, snapshot reconciliation,
and checkpoint backend durability. Flow control, replay, and decoding remain
connector-local rather than generic gRPC contracts.

Install `plynt[grpc,salesforce]`: protocol runtimes belong to `grpc`, while
Avro belongs to `salesforce`, as defined in
[ADR-0031](../../../architecture/adr/0031-experimental-release-installation-contract.md).
See the [CDC deployment guide](../user/how-to/deploy-cdc.md) for wiring and
the current initial-load and replay limitations.

## Design Constraints

- Keep connector logic generic and policy-neutral.
- Keep business-specific orchestration out of connector core.
- Keep sync/async parity for REST capabilities; CDC is explicitly async-only.
- Keep extraction feasibility to a standalone package.

## ADRs

Connector architecture decisions are captured in:

- [Salesforce ADR Index](adr/README.md)

## Status Notes

- Salesforce ADRs `sf-0001` through `sf-0013` are present.
- SF-0012 remains Proposed; package extraction is not approved.
- CDC is implemented but experimental. Real-org authentication, schemas,
  long-running lifecycle, and opaque replay-ID fidelity remain unverified.
- Future capability additions should append a new sequential `sf-xxxx` ADR.
