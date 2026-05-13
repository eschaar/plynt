# ADR-0009: Service Layer

## Status

Accepted

## Context

The layer ordering documented in ADR-0002 ends with a __Service Layer__ that
sits above the Client Layer (ADR-0008). Services are the business-specific entry
points that translate between API endpoints and the application's own model
objects.

The `plynth` core package can provide generic, abstract base classes
(`HTTPService`, `APIService`) that define the structural contract for services
and eliminate boilerplate across downstream implementations. Business-specific
service logic, response models, and error mapping belong in separate packages.

## Decision

### Generic service base classes in the core

The `plynth` package ships two pairs of base classes for the Service Layer.
They mirror the Client Layer hierarchy (`HTTPClient` / `APIClient`) exactly:

__`HTTPService`__ — base for services backed by a raw `HTTPClient`:

```python
from plynth.http.client import HTTPClient
from plynth.http.renderer import Renderer

class HTTPService:
    def __init__(self, client: HTTPClient, renderer: Renderer | None = None) -> None:
        self._client = client
        self._renderer = renderer
```

__`APIService(HTTPService)`__ — base for services backed by an `APIClient` (JSON REST):

```python
from plynth.http.client import APIClient
from plynth.http.renderer import JSONRenderer, Renderer
from plynth.http.service import HTTPService

class APIService(HTTPService):
    def __init__(self, client: APIClient, renderer: Renderer | None = None) -> None:
        super().__init__(client, renderer=renderer or JSONRenderer())
```

`APIService` extends `HTTPService`, mirroring how `APIClient` extends
`HTTPClient`. This hierarchy means:

- `HTTPService` handles raw HTTP; the renderer is optional (no default).
- `APIService` handles JSON REST APIs; the renderer defaults to `JSONRenderer`
  so subclasses do not need to wire it themselves unless they need a custom
  encoder (e.g. `SalesforceRenderer` for datetime/Decimal/UUID support).

Both accept the matching client variant via constructor injection and provide
`self._client` and `self._renderer` as the two access points for outgoing calls
and body serialisation within the service.

Async variants (`AsyncHTTPService`, `AsyncAPIService`) mirror this design,
accepting `AsyncHTTPClient` and `AsyncAPIClient` respectively.

### Business-specific services extend these base classes

Downstream packages extend `HTTPService` or `APIService` and add their own
endpoint methods:

```python
from plynth.http.service import APIService
from plynth.http.client import APIClient

class ProductService(APIService):
    def get_product(self, product_id: str) -> Product:
        resp = self._client.get(f"/products/{product_id}")
        return Product.model_validate_json(resp.content)

    def create_product(self, data: dict) -> Product:
        resp = self._client.post("/products", content=self._renderer.render(data))
        return Product.model_validate_json(resp.content)
```

`APIService` provides `self._renderer` pre-wired with `JSONRenderer`, so
`self._renderer.render(data)` works without any extra setup.

### Request body serialisation via Renderer

Services that send request bodies must not hard-code serialisation logic
inside endpoint methods. Instead, `self._renderer` is called explicitly at
the point where the body is produced:

```python
from plynth.http.service import APIService

class WidgetService(APIService):
    def create_widget(self, data: dict) -> Widget:
        body = self._renderer.render(data)   # → bytes (JSONRenderer by default)
        resp = self._client.post("/widgets", content=body)
        return Widget.model_validate_json(resp.content)
```

The division of responsibility across the layers is:

| Concern                           | Handled by                          |
| --------------------------------- | ----------------------------------- |
| Serialise Python object → `bytes` | `Renderer` (in Service)             |
| `Content-Type` / `Accept` headers | `APIClient` (always, every request) |
| Send `bytes` over the wire        | `Transport`                         |

`JSONRenderer` (the built-in implementation) produces UTF-8 JSON bytes.
Custom renderers (form, XML, msgpack, etc.) implement the `Renderer` protocol
and are injected at construction time. The service layer never needs to know
which encoding format is in use.

### Services return domain models, not Response objects

A service method receives a `Response` from the client and converts it into a
domain model before returning. Raw `Response` objects must never leak out of
the service boundary.

### Services own their error mapping

When an `HttpStatusError` raised by `APIClient` has business-specific meaning,
the service catches it and re-raises a domain-level exception:

```python
from plynth.http.errors import NotFoundError as HttpNotFoundError

def get_product(self, product_id: str) -> Product:
    try:
        resp = self._client.get(f"/products/{product_id}")
    except HttpNotFoundError:
        raise ProductNotFoundError(product_id=product_id)
    return Product.model_validate_json(resp.content)
```

Generic HTTP errors (e.g., `UnauthorizedError`, `InternalServerError`) may be
allowed to propagate unchanged if the caller is expected to handle them.

### Settings injection

Services receive their client from the outside (constructor injection).
The client is itself constructed with settings from `ApiSettings` (ADR-0004).
Services must not create their own clients internally or read environment
variables directly.

### Sync and async symmetry

Where both sync and async variants of a service are needed, they are
implemented as separate classes (`ProductService`, `AsyncProductService`) that
extend the matching base (`APIService`, `AsyncAPIService`). Business logic
shared between the two must be extracted into pure functions or model methods
that contain no I/O.

## Placement in the Codebase

The generic base classes live in `plynth`:

```text
src/plynth/
  http/
    service.py   ← HTTPService, AsyncHTTPService,
                   APIService, AsyncAPIService
```

Business-specific service implementations belong in separate, business-specific
packages:

```text
plynth-acme/
  src/
    plynth_acme/
      services/
        product.py   ← ProductService(APIService)
        order.py     ← OrderService(APIService)
      models/
        product.py   ← Product (Pydantic model)
        order.py     ← Order
      errors.py      ← Domain-level exceptions
      settings.py    ← AcmeSettings(ApiSettings)
```

## Consequences

- Downstream services inherit a consistent structure and constructor signature
  without any boilerplate beyond their own endpoint methods.
- The base classes act as lightweight structural interfaces, making services
  easy to mock and test.
- The `plynth` core remains free of business-specific logic while still providing
  useful scaffolding for service authors.
- Sync and async variants are provided without duplicating business logic.
