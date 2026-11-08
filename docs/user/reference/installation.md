# Installation and extras

Plynt uses optional extras to keep the core dependency surface minimal.
Supported environments are Linux with Python 3.12, 3.13, 3.14, and 3.15. Python
3.14 is the development default; Python 3.15 remains fully tested. Other
combinations are outside the tested contract.

## Extras

| Extra        | Purpose                                                        |
| ------------ | -------------------------------------------------------------- |
| `httpx`      | Built-in sync and async HTTP transport using `httpx2`          |
| `grpc`       | Async gRPC transport, with gRPC and protobuf runtimes          |
| `salesforce` | Salesforce HTTP APIs, signing, models, and Avro decoding       |
| `django`     | Django settings, cache, and HTTP transport adapters            |
| `drf`        | Django REST Framework adapter, including Django support        |
| `fastapi`    | FastAPI lifespan, dependency, header, and error adapters       |
| `sentry`     | Optional reporting using an application-initialized Sentry SDK |
| `test`       | pytest, coverage, async testing, and HTTP recording utilities  |
| `dev`        | Test, lint, type-check, build, and pinned codegen tools        |

There is no `oauth`, `llm`, or `soap` extra. Generic OAuth2 helpers are included
in the package; concrete HTTP calls need `httpx` or a caller-supplied transport.
The LLM connector uses the HTTP installation profile.

## Install examples

```bash
# Core only: use a caller-supplied transport
pip install plynt

# Built-in HTTP transport
pip install "plynt[httpx]"

# Async gRPC transport
pip install "plynt[grpc]"
```

Core-only installations preserve package imports. Constructing the built-in HTTP
transport without `httpx2` raises an actionable dependency error.

The HTTP extras require `httpx2>=2.13.1`. For extension installation and runtime
migration instructions, see:

- [Framework adapters](../../adapters/README.md)
- [Connector documentation](../../connectors/)
- [Sentry integration](../../integrations/sentry.md)

### Migration from Python 3.11

This is a breaking installation-contract change under
[ADR-0034](../../architecture/adr/0034-django-6-support.md). Python 3.11 is no
longer supported. Upgrade the interpreter first, preferably to Python 3.14, and
recreate the development `.venv` rather than reusing an environment with an
older Python. Framework-specific migration instructions live in the adapter
guides.

## gRPC runtime compatibility

The gRPC extra requires `grpcio>=1.85.1,<2` and `protobuf>=7.35.1,<8`. Resolve
these dependencies together and run `python -m pip check` after upgrading. The
development generator is pinned to `grpcio-tools==1.85.1`. The generated gRPC
stub enforces the gRPC runtime floor; regenerated protobuf checks continue to
require protobuf 7.35.1. Routine refresh policy and validation gates are in
[ADR-0044](../../architecture/adr/0044-grpc-toolchain-upgrade-policy.md).
Consumers do not need the development-only generator.

Keep the installer itself current. The development and distribution gates
bootstrap `pip>=26.2,<27`; this is tooling, not a Plynt runtime dependency:

```bash
python -m pip install --upgrade "pip>=26.2,<27"
```

## Development install

From the checkout:

```bash
make install
make check
```

The development bootstrap includes every implemented runtime extra so optional
adapters are not silently skipped. Without `make`, use:

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade "pip>=26.2,<27"
.venv/bin/python -m pip install -e \
  ".[dev,httpx,grpc,salesforce,django,drf,fastapi,sentry]"
```

The `dev` extra alone installs tooling, not every framework or connector. The
canonical development command deliberately composes runtime extras.

## Experimental distribution checks

The Distribution workflow builds a wheel from the source distribution and
installs it in fresh environments for core, HTTP, gRPC, CDC, Django, DRF, and
FastAPI, and Sentry. It also checks the CDC runtime minima. The full test matrix exercises
all implemented runtime extras on Linux Python 3.12-3.15.

These checks verify installation boundaries, not correctness against an external
provider. Connector-specific readiness evidence lives with each connector.
