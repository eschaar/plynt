# Installation and extras

Plynth uses optional extras to keep the core dependency surface minimal.
Supported environments are Linux with Python 3.11, 3.12, 3.13, and 3.14.
Other combinations are outside the tested contract.

## Extras

| Extra        | Purpose                                                       |
| ------------ | ------------------------------------------------------------- |
| `httpx`      | Built-in sync and async HTTP transport using `httpx2`         |
| `grpc`       | Async gRPC transport, with gRPC and protobuf runtimes         |
| `salesforce` | Salesforce HTTP APIs, signing, models, and Avro decoding      |
| `django`     | Django settings, cache, and HTTP transport adapters           |
| `drf`        | Django REST Framework adapter, including Django support       |
| `fastapi`    | FastAPI lifespan, dependency, header, and error adapters      |
| `test`       | pytest, coverage, async testing, and HTTP recording utilities |
| `dev`        | Test, lint, type-check, build, and pinned codegen tools       |

There is no `oauth`, `llm`, or `soap` extra. Generic OAuth2 helpers are
included in the package; concrete HTTP calls need `httpx` or a caller-supplied
transport. The LLM connector uses the HTTP installation profile.

## Install examples

```bash
# Core only: use a caller-supplied transport
pip install plynth

# HTTP and LLM provider adapters
pip install "plynth[httpx]"

# Salesforce REST, Bulk, and AI
pip install "plynth[salesforce]"

# Experimental Salesforce CDC, including Avro decoding
pip install "plynth[grpc,salesforce]"

# Framework adapters
pip install "plynth[django]"
pip install "plynth[drf]"
pip install "plynth[fastapi]"
```

Core-only installations preserve package imports. Constructing the built-in
HTTP transport without `httpx2` raises an actionable dependency error.

## CDC runtime compatibility

The vendored Pub/Sub messages require `grpcio>=1.83.1,<2` and
`protobuf>=7.35.1,<8`. The Salesforce extra includes `fastavro>=1.13.1,<2`.
Upgrading from older gRPC or protobuf versions requires resolving those
dependencies together; run `python -m pip check` afterward.

The Salesforce extra also requires `PyJWT>=2.15.1,<3` to exclude affected
signing-library versions identified during hardening. Development tooling
sets security floors for urllib3 and virtualenv; neither becomes a core
runtime dependency.

These minima are smoke-tested independently of the development generator.
No code generation runs during installation or package import.
See [ADR-0031](../../architecture/adr/0031-experimental-release-installation-contract.md).

Keep the installer itself current. The development and distribution gates
bootstrap `pip>=26.2,<27`; this is tooling, not a Plynth runtime dependency:

```bash
python -m pip install --upgrade "pip>=26.2,<27"
```

## Development install

From the checkout:

```bash
make install
make check
```

The development bootstrap includes every implemented runtime extra so
optional adapters are not silently skipped. Without `make`, use:

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade "pip>=26.2,<27"
.venv/bin/python -m pip install -e \
  ".[dev,httpx,grpc,salesforce,django,drf,fastapi]"
```

The `dev` extra alone installs tooling, not every framework or connector.
The canonical development command deliberately composes runtime extras.

## Experimental distribution checks

The Distribution workflow builds a wheel from the source distribution and
installs it in fresh environments for core, HTTP, gRPC, CDC, Django, DRF,
and FastAPI. It also checks the CDC runtime minima. The full test matrix
exercises all implemented runtime extras on Linux Python 3.11-3.14.

CDC still needs real Salesforce-org validation, including replay cursor
fidelity. A local distribution passing these checks is not a production
readiness claim.
