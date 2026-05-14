# Salesforce Connector Architecture Overview

This document describes the architecture of the Salesforce connector in plynth.

## Purpose

The connector validates plynth core abstractions against a complex real-world
API surface while staying framework-agnostic and extractable.

## Architectural Position

The connector sits above `plynth.http` and reuses core layers:

1. service layer for Salesforce endpoint operations,
1. API client layer for HTTP request dispatch and typed errors,
1. transport + middleware for cross-cutting behavior (auth, retry, cache,
   circuit breaker, rate limiting, logging).

The connector must not bypass these abstractions.

## Module Structure

Current package focus under `src/plynth/connectors/salesforce/`:

- `auth/` for Salesforce-specific auth middleware wrappers,
- `bulk/` for Bulk API 2.0 flows,
- `composite.py` for composite, batch, and tree primitives,
- `identity/` for generic identity access primitives,
- `lookup/` for reusable lookup conveniences,
- `metadata.py` for Metadata REST deploy flows,
- `query/` for SOQL and pagination,
- `search.py` for SOSL search,
- `sobject/` for core SObject operations,
- `utility.py` for limits, versions, objects, and tooling helpers,
- `facade.py` for ergonomic service composition.

## Design Constraints

- Keep connector logic generic and policy-neutral.
- Keep business-specific orchestration out of connector core.
- Keep sync/async parity for shipped capabilities.
- Keep extraction feasibility to a standalone package.

## ADRs

Connector architecture decisions are captured in:

- [Salesforce ADR Index](adr/README.md)

## Status Notes

- Core Salesforce capability ADRs `sf-0001` through `sf-0010` are present.
- Future capability additions should append a new sequential `sf-xxxx` ADR.
