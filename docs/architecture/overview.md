# Architecture Overview

This document describes the current architecture of plynt at a high level and
links to the ADR set for decision-level detail.

## Purpose

Plynt is a framework-agnostic API client foundation. It separates generic
transport and middleware concerns from protocol-specific implementations and
domain connectors.

## System Style

**backend-only** — Plynt is a Python client library and integration foundation;
it provides no first-party user interface.

## Layer Model

Plynt uses a layered model where responsibility is explicit and composable:

1. Request layer (`plynt.base.request`)
1. Transport layer (`plynt.base.transport`, `plynt.http.transport`)
1. Response layer (`plynt.base.response`, `plynt.http.response`)
1. Client layer (`plynt.http.client`)
1. Service layer (`plynt.http.service` and connector services)

Core abstractions live in `plynt.base` and are protocol-agnostic. HTTP-specific
implementations live in `plynt.http`. Business connectors (for example
Salesforce) live in `plynt.connectors.*`.

`plynt.grpc` is a sibling protocol namespace with async transport, client,
settings, errors, interceptors, and protobuf helpers. It does not define
Salesforce replay, checkpoints, Avro decoding, or subscription flow control. See
[ADR-0030](adr/0030-grpc-protocol-boundary.md).

## Connector vs Adapter

Use these terms consistently:

- **Connector**: domain-facing integration surface for an external platform. A
  connector owns domain models and service orchestration for that platform.
  Examples: `plynt.connectors.salesforce`, `plynt.connectors.llm`.
- **Adapter**: interface translation component between two boundaries. Adapters
  translate payloads, framework contracts, or transport concerns.

Typical placement:

- Framework adapters live near core boundaries.
- Provider adapters can live inside a connector when one connector supports
  multiple providers under a shared contract.

Framework-specific capabilities and usage live in the
[adapter documentation](../adapters/README.md).

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

This keeps cross-cutting behavior reusable and explicit. The HTTP middleware
chain is not reused by gRPC; that protocol has its own interceptor and metadata
boundaries.

## Sync and Async Strategy

Sync and async variants share architecture and naming patterns. I/O mode is a
transport concern, while service/domain semantics stay execution-model agnostic.
HTTP capabilities retain sync/async parity. The initial gRPC foundation is
async-only. Connector-specific execution-model support is documented by each
connector.

## Configuration Strategy

Configuration is typed and environment-driven through settings classes. HTTP
settings can wire auth and cache configuration into transport factories. No
framework-specific configuration logic is allowed in the core package.

## Experimental Release Boundary

Protocol and connector runtime dependencies stay behind their respective extras.
The core remains free of those optional dependencies.

Full tests exercise all implemented extras. Separate clean wheel installation
tests verify that each documented profile works without development tooling. The
wheel is built from the source distribution, not from an editable install.
Codegen is pinned and compared against committed output.

Full coverage runs enforce 100% statement coverage in the existing measured
source scope. This is not branch coverage or proof of provider correctness. The
supported Linux Python 3.12-3.15 matrix and installed-wheel checks remain
separate acceptance gates.

Experimental connectors require provider-specific validation beyond local tests.
Their operational requirements are documented with each connector. See
[ADR-0031](adr/0031-experimental-release-installation-contract.md) for the
installation and acceptance contract. The generator refresh and gRPC runtime
alignment are recorded in [ADR-0032](adr/0032-grpc-codegen-version-refresh.md).
Python support, the 3.14 default, and the local `.venv`/pyenv bootstrap are in
[ADR-0033](adr/0033-python-315-support-and-local-pyenv.md). Python 3.11 removal
and Django 6.1 requirements are recorded in
[ADR-0034](adr/0034-django-6-support.md). See the
[current hardening evidence](../releases/2026-10-13-experimental-rc-hardening-evidence.md)
for verified revisions and outstanding checks. Versions and tags are owned by
CI/CD and release-please; passing local gates does not approve publication.

## ADRs

Architecture decisions are captured in ADRs under `docs/architecture/adr/`. Use
the ADR index for status and scope:

- [ADR Index](adr/README.md)
