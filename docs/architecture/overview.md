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

`plynth.grpc` is a sibling protocol namespace with async transport, client,
settings, errors, interceptors, and protobuf helpers. It does not define
Salesforce replay, checkpoints, Avro decoding, or subscription flow control.
See [ADR-0030](adr/0030-grpc-protocol-boundary.md).

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

A typical HTTP request path is:

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
The HTTP middleware chain is not reused by gRPC; that protocol has its own
interceptor and metadata boundaries.

## Sync and Async Strategy

Sync and async variants share architecture and naming patterns. I/O mode is a
transport concern, while service/domain semantics stay execution-model agnostic.
HTTP capabilities retain sync/async parity. The initial gRPC foundation and
Salesforce CDC subscriber are async-only; no sync eventing API is promised.

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

Full coverage runs enforce 100% statement coverage in the existing measured
source scope. This is not branch coverage or proof of provider correctness.
The supported Linux Python 3.12-3.15 matrix and installed-wheel checks remain
separate acceptance gates.

CDC remains experimental pending validation of authentication, real schemas,
long-running operation, and opaque replay cursor fidelity against Salesforce.
See [ADR-0031](adr/0031-experimental-release-installation-contract.md) for the
installation and acceptance contract.
The generator refresh and gRPC runtime alignment are recorded in
[ADR-0032](adr/0032-grpc-codegen-version-refresh.md).
Python support, the 3.14 default, and the local `.venv`/pyenv bootstrap are in
[ADR-0033](adr/0033-python-315-support-and-local-pyenv.md).
Python 3.11 removal and Django 6.1 requirements are recorded in
[ADR-0034](adr/0034-django-6-support.md).
See the [current hardening evidence](../releases/2026-10-13-experimental-rc-hardening-evidence.md)
for verified revisions and outstanding checks. Versions and tags are owned
by CI/CD and release-please; passing local gates does not approve publication.

## ADRs

Architecture decisions are captured in ADRs under `docs/architecture/adr/`.
Use the ADR index for status and scope:

- [ADR Index](adr/README.md)
