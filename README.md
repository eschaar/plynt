# Plynth

Plynth is a modular, framework-agnostic Python library for building external API clients and services.

The name *plynth* is inspired by a **plinth** in architecture:

> the solid base a structure stands on.

Plynth aims to be exactly that - a stable, minimal layer for long-lived, maintainable integrations with external HTTP APIs.

______________________________________________________________________

## Project Goal

Plynth provides a reusable foundation for creating Python clients and services
that communicate with external HTTP APIs. It is designed to be:

- **Framework-agnostic** (works with FastAPI, Django, Starlette, or stand-alone)
- **Modular** (install only what you need)
- **Sync + Async** (single codebase, no duplication)
- **Minimal core dependencies**
- **ORM-like developer experience for APIs**

See [docs/architecture/adr/0001-architecture-principles.md](docs/architecture/adr/0001-architecture-principles.md)
for the full architecture principles and
[docs/architecture/adr/0002-layered-architecture.md](docs/architecture/adr/0002-layered-architecture.md)
for the conceptual layers.

______________________________________________________________________

## What Plynth Is

Plynth provides core building blocks for API clients and service layers, focusing on:

- clear structure
- predictable behavior
- minimal magic
- explicit configuration

Plynth is not a web framework and does not replace tools like FastAPI, Flask,
or Django. Instead, it complements them as a foundation for external service integration.

______________________________________________________________________

## What Plynth Is Not

Plynth intentionally avoids:

- tight coupling to any web framework
- heavy abstractions
- hidden lifecycle behavior
- opinionated application structure

If you want a batteries-included framework, Plynth is probably not what you’re looking for.

______________________________________________________________________

## Documentation

- [Architecture Overview](docs/architecture/overview.md)
- [Architecture ADR Index](docs/architecture/adr/README.md)
- [Architecture Principles](docs/architecture/adr/0001-architecture-principles.md)
- [Layered Architecture](docs/architecture/adr/0002-layered-architecture.md)
- [Dependency Policy](docs/architecture/adr/0003-dependency-policy.md)
- [Product Vision](docs/product/vision.md)
- [Product Requirements](docs/product/requirements.md)
- [Product Roadmap](docs/product/roadmap.md)
- [Generic LLM Connector Guide](docs/connectors/llm/README.md)
- [Salesforce Integration Guide](docs/connectors/salesforce/README.md)
- [Contributing](CONTRIBUTING.md)

______________________________________________________________________

## Intended Use Cases

- Microservices
- Internal APIs
- Platform / shared service libraries
- Long-running backend services
- Teams that want consistency without lock-in

______________________________________________________________________

## Project Status

Plynth is currently in early development (0.x).

APIs may change while the foundation is being shaped. Stability guarantees will come with a 1.0 release.

______________________________________________________________________

## Installation

Requires **Python 3.11 or later**.

```bash
pip install plynth
```

Optional extras:

```bash
pip install "plynth[httpx]"       # httpx2 transport backend
pip install "plynth[salesforce]"  # Salesforce REST connector
```

### Canonical extras matrix

| Extra        | Installs                                | Typical use                                       |
| ------------ | --------------------------------------- | ------------------------------------------------- |
| `httpx`      | `httpx2` transport backend              | Core HTTP transport for sync and async clients    |
| `django`     | Django adapter support + `httpx2`       | Django integration helpers and cache adapters     |
| `drf`        | DRF adapter support + Django + `httpx2` | DRF service mixins and exception mapping patterns |
| `fastapi`    | FastAPI adapter support + `httpx2`      | FastAPI dependency wiring for plynth clients      |
| `salesforce` | Salesforce connector dependencies       | Typed Salesforce REST APIs, bulk, and AI services |

### Public API surface

Plynth treats package exports in `plynth.base` and `plynth.http` as the main
public contract boundaries for core usage.

- Prefer importing from these package roots instead of internal submodules.
- Internal module paths may evolve as long as public exports remain compatible.
- Compatibility and deprecation policy is defined in [ADR-0027](docs/architecture/adr/0027-public-api-compatibility-and-deprecation-policy.md).

______________________________________________________________________

## Authentication

Plynth supports typed auth configuration via `settings.auth`.

Supported config types:

- `BearerAuthConfig`
- `BasicAuthConfig`
- `OAuth2ClientCredentialsConfig`
- `OAuth2JWTBearerConfig` (RFC 7523)
- `OAuth2PasswordConfig` (legacy)

JWT Bearer in core is dependency-light:

- The core middleware handles the OAuth2 token lifecycle.
- JWT signing is supplied via `assertion_factory`.
- You can use any signing implementation that returns a non-empty JWT string.

Example using typed settings + JWT Bearer:

```python
from plynth.http.auth import AuthConfig, OAuth2JWTBearerConfig
from plynth.http.settings import HTTPSettings


def build_assertion() -> str:
    # Use your own signer implementation (PyJWT, jose, HSM client, etc.).
    return "<signed-jwt>"


class MySettings(HTTPSettings):
    @property
    def auth(self) -> AuthConfig | None:
        return OAuth2JWTBearerConfig(
            token_url="https://auth.example.com/oauth/token",
            assertion_factory=build_assertion,
            cache_key_material="my-issuer:service-account",
            scope="api.read api.write",
            ttl_leeway=30,
        )
```

For Salesforce-specific JWT claim construction and signing guidance, see
[docs/connectors/salesforce/README.md](docs/connectors/salesforce/README.md)
and [docs/connectors/salesforce/architecture/adr/sf-0006-jwt-bearer-auth.md](docs/connectors/salesforce/architecture/adr/sf-0006-jwt-bearer-auth.md).

______________________________________________________________________

## Roadmap

See [docs/product/roadmap.md](docs/product/roadmap.md) for the full roadmap, including what
is implemented, what is planned, and what is explicitly out of scope.

High-level planned areas:

- Framework adapters (Django, FastAPI, Flask)
- gRPC transport (`plynth[grpc]`) as foundation for Salesforce Pub/Sub CDC
- SOAP transport (`plynth[soap]`) as long-term extension

Shipped connector highlights:

- Generic AI / LLM connector (`plynth.connectors.llm`) with neutral request,
  completion, and streaming chunk contract models.

______________________________________________________________________

## Philosophy

Plynth follows a simple rule:

> If it’s not essential for the foundation, it doesn’t belong here.

______________________________________________________________________

## License

MIT
