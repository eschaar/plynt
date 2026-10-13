# Architecture Overview

This document describes the current architecture of plynth at a high level and
links to the ADR set for decision-level detail.

## Purpose

Plynth is a framework-agnostic API client foundation. It separates generic
transport and middleware concerns from protocol-specific implementations and
domain connectors.

## Layer Model

Plynth uses a layered model where responsibility is explicit and composable:

1. Request layer (`plynth.base.request`)
1. Transport layer (`plynth.base.transport`, `plynth.http.transport`)
1. Response layer (`plynth.base.response`, `plynth.http.response`)
1. Client layer (`plynth.http.client`)
1. Service layer (`plynth.http.service` and connector services)

Core abstractions live in `plynth.base` and are protocol-agnostic.
HTTP-specific implementations live in `plynth.http`.
Business connectors (for example Salesforce) live in `plynth.connectors.*`.

## Connector vs Adapter

Use these terms consistently:

- **Connector**: domain-facing integration surface for an external platform.
  A connector owns domain models and service orchestration for that platform.
  Examples: `plynth.connectors.salesforce`, `plynth.connectors.llm`.
- **Adapter**: interface translation component between two boundaries.
  Adapters translate payloads, framework contracts, or transport concerns.

Typical placement:

- Framework adapters live near core boundaries.
- Provider adapters can live inside a connector when one connector supports
  multiple providers under a shared contract.

Current FastAPI adapter capabilities include:

1. lifespan-based transport lifecycle management,
1. dependency factories for transport/client/service resolution,
1. bundled service-dependency helpers for router setup,
1. request-header propagation helpers,
1. plynth exception-to-JSON response mapping helpers.

## Framework Adapter Capability Matrix

This matrix summarizes the currently shipped adapter surface.

| Adapter          | Lifecycle boundary | Transport/client DI | Service DI | Header propagation | Error mapping | Sync | Async |
| ---------------- | ------------------ | ------------------- | ---------- | ------------------ | ------------- | ---- | ----- |
| Django core      | Request/view scope | Via helper function | N/A        | N/A                | N/A           | Yes  | Yes   |
| Django DRF layer | Request lifecycle  | Yes                 | Yes        | Yes                | Yes           | Yes  | Yes   |
| FastAPI adapter  | ASGI lifespan      | Yes                 | Yes        | Yes                | Yes           | Yes  | Yes   |

## Runtime Flow

A typical request path is:

1. Service method composes endpoint input and serializes body via renderer.
1. Client builds a `Request` and delegates to the injected transport.
1. Transport executes the middleware chain and performs network I/O.
1. Client applies protocol conventions (for API clients: typed error mapping).
1. Service maps response to domain models.

## Middleware Chain

The middleware model is chain-of-responsibility (`handle(request, next)`),
implemented in base transport classes.

Canonical order:

1. Cache middleware (outermost)
1. Auth middleware
1. Circuit breaker middleware
1. Rate limit middleware
1. Retry middleware (innermost above I/O)

This keeps cross-cutting behavior reusable and explicit.

## Sync and Async Strategy

Sync and async variants share architecture and naming patterns. I/O mode is a
transport concern, while service/domain semantics stay execution-model agnostic.

## Configuration Strategy

Configuration is typed and environment-driven through settings classes.
HTTP settings can wire auth and cache configuration into transport factories.
No framework-specific configuration logic is allowed in the core package.

## Experimental Release Boundary

Salesforce CDC composes `plynth[grpc,salesforce]`: gRPC and protobuf stay in
the protocol extra, while Avro decoding belongs to the Salesforce extra.
The core remains free of those runtime dependencies.

Full tests exercise all implemented extras. Separate clean wheel installation
tests verify that each documented profile works without development tooling.
The wheel is built from the source distribution, not from an editable install.
Codegen is pinned and compared against committed output.

CDC remains experimental pending validation against a real Salesforce org.
See [ADR-0031](adr/0031-experimental-release-installation-contract.md) for the
installation and acceptance contract.

## ADRs

Architecture decisions are captured in ADRs under `docs/architecture/adr/`.
Use the ADR index for status and scope:

- [ADR Index](adr/README.md)
