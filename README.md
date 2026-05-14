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
- [Salesforce Integration Guide](docs/connectors/salesforce/README.md)

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

```bash
pip install plynth
```

Current status:

- GitHub releases exist for `0.1.0` (core baseline), `0.2.0` (Salesforce connector), and `0.2.1`.
- Release automation is enabled via release-please.
- PyPI publish uses OIDC and is guarded by `ENABLE_PYPI_PUBLISH` in CI.

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

- Logging and observability (`plynth.middleware.logging`)
- Framework adapters — Django and FastAPI extras
- Built-in cache backends (`plynth[cache]`)
- Async OAuth2 (`AsyncOAuth2ClientCredentials`)
- Salesforce client implementation (REST, SOQL, Bulk, Pub/Sub CDC) —
  reference implementation and integration test for plynth, later extracted
  into a standalone `plynth-salesforce` package

______________________________________________________________________

## Philosophy

Plynth follows a simple rule:

> If it’s not essential for the foundation, it doesn’t belong here.

______________________________________________________________________

## License

MIT
