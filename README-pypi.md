# Plynt

Plynt is a modular, framework-agnostic Python library for building external API
clients and services.

Plynt focuses on a stable integration foundation:

- framework-agnostic design
- sync and async support from one codebase
- explicit configuration and minimal hidden behavior
- typed settings and reusable middleware patterns

## Installation

Supports **Python 3.12-3.15 on Linux**. Django/DRF extras require Django 6.1.

```bash
pip install plynt
```

Optional extras:

```bash
pip install "plynt[httpx]"       # httpx2 transport
pip install "plynt[salesforce]"  # Salesforce REST connector
```

### Canonical extras matrix

| Extra        | Installs                                | Typical use                                       |
| ------------ | --------------------------------------- | ------------------------------------------------- |
| `httpx`      | `httpx2` transport backend              | Core HTTP transport for sync and async clients    |
| `grpc`       | gRPC and protobuf runtimes              | Async gRPC clients and transports                 |
| `django`     | Django adapter support + `httpx2`       | Django integration helpers and cache adapters     |
| `drf`        | DRF adapter support + Django + `httpx2` | DRF service mixins and exception mapping patterns |
| `fastapi`    | FastAPI adapter support + `httpx2`      | FastAPI dependency wiring for plynt clients       |
| `salesforce` | HTTP, signing, validation, Avro         | REST, bulk, AI; combine with `grpc` for CDC       |

Install `plynt[grpc,salesforce]` for experimental CDC support, including
vendored Pub/Sub messages and the Avro decoder. Real Salesforce-org validation
is still required before production CDC use.

### Public API surface

Plynt treats package exports in `plynt.base` and `plynt.http` as the main public
contract boundaries for core usage.

- Prefer importing from these package roots instead of internal submodules.
- Internal module paths may evolve as long as public exports remain compatible.
- Compatibility and deprecation policy is defined in
  [ADR-0027](https://github.com/eschaar/plynt/blob/main/docs/architecture/adr/0027-public-api-compatibility-and-deprecation-policy.md).

## Salesforce connector

The optional `plynt[salesforce]` connector provides REST, Bulk, and AI APIs with
sync/async support. Configuration and usage examples live in its own guide.

See the
[Salesforce connector docs](https://github.com/eschaar/plynt/tree/main/docs/connectors/salesforce)
for the full guide including JWT Bearer auth, pagination, bulk ingest, and more.

## Generic LLM connector

The optional LLM connector provides provider-neutral messaging and streaming.
See the
[LLM connector guide](https://github.com/eschaar/plynt/tree/main/docs/connectors/llm)
for models, provider adapters, and usage examples.

## Project Status

Plynt remains in the 0.x release line. Documented APIs follow the compatibility
and deprecation policy in ADR-0027. Current capabilities include HTTP,
middleware, caching, streaming, Salesforce REST/Bulk/AI, LLM provider adapters,
Django/DRF/FastAPI adapters, and async gRPC.

Release acceptance includes distribution and installation checks. Local and CI
tests do not replace validation against real external providers. Non-prerelease
GitHub releases are published to PyPI through trusted publishing after the build
and installed-wheel checks pass.

## Documentation

- [README](https://github.com/eschaar/plynt/blob/main/README.md)
- [Changelog](https://github.com/eschaar/plynt/blob/main/CHANGELOG.md)
- [Architecture ADRs](https://github.com/eschaar/plynt/tree/main/docs/architecture/adr)
- [Framework adapters](https://github.com/eschaar/plynt/tree/main/docs/adapters)
- [LLM connector docs](https://github.com/eschaar/plynt/tree/main/docs/connectors/llm)
- [Salesforce connector docs](https://github.com/eschaar/plynt/tree/main/docs/connectors/salesforce)

## License

MIT
