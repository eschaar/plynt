# How to use Plynt in DRF views

Use `PlyntServiceMixin` or `AsyncPlyntServiceMixin` to build one plynt
transport per DRF view instance and expose named upstream services in a
predictable way.

This adapter is meant for service-to-service backend calls from DRF views,
not as an ORM replacement. The view remains the orchestration boundary:

1. Read and validate inbound HTTP input.
1. Call one or more upstream backend services through plynt clients.
1. Map upstream responses into stable API responses for your own consumers.

## Support matrix

Use this matrix as the current support boundary for Django and DRF view types.

| Surface           | Sync | Async   | Status            | Notes                                                                                                                    |
| ----------------- | ---- | ------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Django views      | Yes  | Yes     | Supported         | Use `transport_from_django_settings(...)` or `async_transport_from_django_settings(...)` directly in plain Django views. |
| DRF `APIView`     | Yes  | Yes     | Supported         | Use `PlyntServiceMixin` for sync handlers and `AsyncPlyntServiceMixin` for explicit async handlers under ASGI.           |
| DRF generic views | Yes  | Partial | Not yet supported | Sync usage can compose existing helpers, but async generic-view support is not a first-class validated slice yet.        |
| DRF viewsets      | Yes  | Partial | Not yet supported | Sync usage works with `PlyntServiceMixin`; async viewset support is intentionally not claimed as first-class yet.        |

Practical rule:

1. Use plain Django views when you want minimal framework coupling.
1. Use DRF `APIView` when you want serializer-driven API contracts over upstream backends.
1. Treat async generic views and async viewsets as future work unless you are ready to validate runtime behavior yourself.

## Install extras

```bash
pip install "plynt[drf]"
```

## Configure Django settings

```python
# settings.py
EXTERNAL_API = {
    "BASE_URL": "https://api.example.com",
    "MAX_ATTEMPTS": 3,
    "CLIENT_ID": "${EXTERNAL_API_CLIENT_ID}",
    "CLIENT_SECRET": "${EXTERNAL_API_CLIENT_SECRET}",
    "TOKEN_URL": "https://auth.example.com/oauth/token",
}

CACHES = {
    "plynt_responses": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/2",
    },
    "plynt_tokens": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/3",
    },
}
```

## Create typed settings and service factory

```python
from plynt.http.auth import OAuth2ClientCredentialsConfig
from plynt.http.client import APIClient
from plynt.http.settings import HTTPSettings


class ExternalAPISettings(HTTPSettings):
    client_id: str = ""
    client_secret: str = ""
    token_url: str = ""

    @property
    def auth(self) -> OAuth2ClientCredentialsConfig | None:
        if not self.client_id or not self.client_secret or not self.token_url:
            return None
        return OAuth2ClientCredentialsConfig(
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_url=self.token_url,
        )


def build_catalog_service(transport):
    return APIClient(base_url="https://api.example.com", transport=transport)


def build_pricing_service(transport):
    return APIClient(base_url="https://pricing.example.com", transport=transport)
```

## Use `PlyntServiceMixin` in APIView/ViewSet

```python
from rest_framework.response import Response
from rest_framework.views import APIView

from plynt.adapters.django.drf.views import (
    CacheAliasesConfig,
    PlyntServiceMixin,
    RequestHeadersConfig,
)


class ProductListView(PlyntServiceMixin, APIView):
    settings_name = "EXTERNAL_API"
    settings_class = ExternalAPISettings
    cache_aliases = CacheAliasesConfig(
        response="plynt_responses",
        auth="plynt_tokens",
    )
    request_headers = RequestHeadersConfig(enabled=True)
    service_factories = {
        "catalog": build_catalog_service,
    }

    def get(self, request):
        catalog = self.get_client("catalog")
        upstream = catalog.get("/products")
        upstream.raise_for_status()
        return Response(upstream.json())
```

`get_client("catalog")` is a convenience alias for
`get_service("catalog")`. Both are lazy and cached per view instance.

## Use `AsyncPlyntServiceMixin` in async APIView

Use the async mixin for ASGI-native DRF views that call async plynt clients or
services.

```python
from rest_framework.response import Response
from rest_framework.views import APIView

from plynt.adapters.django.drf.views import (
    AsyncPlyntServiceMixin,
    CacheAliasesConfig,
    RequestHeadersConfig,
)
from plynt.http.client import AsyncAPIClient


def build_async_catalog_service(transport):
    return AsyncAPIClient(base_url="https://api.example.com", transport=transport)


class AsyncProductListView(AsyncPlyntServiceMixin, APIView):
    settings_name = "EXTERNAL_API"
    settings_class = ExternalAPISettings
    cache_aliases = CacheAliasesConfig(
        response="plynt_responses",
        auth="plynt_tokens",
    )
    request_headers = RequestHeadersConfig(enabled=True)
    service_factories = {
        "catalog": build_async_catalog_service,
    }

    async def get(self, request):
        catalog = self.get_client("catalog")
        upstream = await catalog.get("/products")
        upstream.raise_for_status()
        return Response(upstream.json())
```

Keep the first async DRF slice limited to thin `APIView` handlers. Do not treat
generic views and viewsets as async-ready by default.

## Serializer-first flow with business logic

In most DRF services, you should still use serializers for request and response
contracts. Plynt handles backend transport concerns, while serializers keep
your public API stable and explicit.

Recommended layering:

1. Input serializer validates and normalizes request data.
1. A business service orchestrates filtering, enrichment, and extra lookups.
1. Plynt clients call upstream backends.
1. Output serializer shapes your external response contract.

Example structure:

```python
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from plynt.adapters.django.drf.views import PlyntServiceMixin


class ProductQuerySerializer(serializers.Serializer):
    tenant_id = serializers.CharField()
    include_inactive = serializers.BooleanField(required=False, default=False)


class ProductItemSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    active = serializers.BooleanField()


class ProductListResponseSerializer(serializers.Serializer):
    items = ProductItemSerializer(many=True)
    total = serializers.IntegerField()


class ProductOrchestrator:
    def __init__(self, catalog_client, pricing_client) -> None:
        self._catalog = catalog_client
        self._pricing = pricing_client

    def execute(self, *, tenant_id: str, include_inactive: bool) -> dict:
        catalog_resp = self._catalog.get(
            "/products",
            params={"tenant_id": tenant_id, "include_inactive": include_inactive},
        )
        catalog_resp.raise_for_status()
        catalog_data = catalog_resp.json()

        # Business logic: enrich and filter data before returning it
        enriched = []
        for item in catalog_data.get("items", []):
            if item.get("active") or include_inactive:
                enriched.append(item)

        return {"items": enriched, "total": len(enriched)}


class ProductListView(PlyntServiceMixin, APIView):
    settings_name = "EXTERNAL_API"
    settings_class = ExternalAPISettings
    service_factories = {
        "catalog": build_catalog_service,
        "pricing": build_pricing_service,
    }

    def get(self, request):
        query = ProductQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        orchestrator = ProductOrchestrator(
            catalog_client=self.get_client("catalog"),
            pricing_client=self.get_client("pricing"),
        )
        result = orchestrator.execute(**query.validated_data)

        output = ProductListResponseSerializer(result)
        return Response(output.data)
```

This pattern keeps views thin, serializers authoritative for API contracts,
and business rules grouped in one testable unit.

For additional design variants, see
[DRF serializer and business-layer patterns](drf-serializer-business-patterns.md).

## ViewSet example

```python
from rest_framework import mixins, viewsets
from rest_framework.response import Response

from plynt.adapters.django.drf.views import PlyntServiceMixin


class ProductViewSet(
    PlyntServiceMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    settings_name = "EXTERNAL_API"
    settings_class = ExternalAPISettings
    request_headers = RequestHeadersConfig(enabled=True)
    service_factories = {
        "catalog": build_catalog_service,
    }

    def list(self, request, *args, **kwargs):
        catalog = self.get_client("catalog")
        upstream = catalog.get("/products")
        upstream.raise_for_status()
        return Response(upstream.json())
```

The mixin cache scope is per view instance, so transports and services are not
shared across different requests.

## Propagate request headers to outbound calls

Use `build_request_header_middleware(...)` or
`build_async_request_header_middleware(...)` when correlation headers from the
incoming DRF request should be forwarded upstream.

```python
from plynt.adapters.django.drf.headers import build_request_header_middleware

middleware = build_request_header_middleware(request)
```

For async middleware chains:

```python
from plynt.adapters.django.drf.headers import build_async_request_header_middleware

middleware = build_async_request_header_middleware(request)
```

Default forwarded headers:

1. `X-Request-Id`
1. `X-Correlation-Id`
1. `traceparent`
1. `tracestate`

You can pass an explicit outbound-to-inbound mapping:

```python
build_request_header_middleware(
    request,
    headers={"X-Upstream-Tenant": "X-Tenant-Id"},
)
```

Set a single class-level config when using automatic propagation:

```python
class ProductListView(PlyntServiceMixin, APIView):
    request_headers = RequestHeadersConfig(
        enabled=True,
        mapping={"X-Upstream-Tenant": "X-Tenant-Id"},
        blocked={"authorization", "cookie"},
    )
```

`request_headers.blocked` is optional. When omitted, the default
sensitive-header denylist from the adapter is used.

## DRF exception mapping for plynt errors

Use the provided exception handler to map unhandled plynt exceptions to
safe DRF JSON responses.

```python
# settings.py
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "plynt.adapters.django.drf.errors.plynt_exception_handler",
}
```

Behavior:

1. DRF default exception handler runs first.
1. If DRF returns `None`, plynt mapping returns a safe error payload.
1. `HttpStatusError` subclasses keep their status code.
1. Core plynt domain and transport errors map to stable HTTP statuses:
   `InvalidInputError` -> `400`, `OperationFailedError` -> `422`,
   `TransportError`/`StreamInterruptedError` -> `502`, and dependency or
   feature availability issues -> `503`.
1. Unknown exceptions still map to HTTP 500.

## Sensitive header safety

`build_request_header_middleware(...)` blocks sensitive header names by
default, even when they are present in custom mappings:

1. `Authorization`
1. `Proxy-Authorization`
1. `Cookie`
1. `Set-Cookie`
1. `X-Api-Key`

This keeps authentication/session data from being forwarded accidentally.
Only override this when there is an explicit security review for your flow.

## Logging and correlation alignment

For end-to-end observability, use the same correlation identifiers in inbound
Django/DRF logs and outbound plynt logs:

1. `X-Request-Id`
1. `X-Correlation-Id`
1. `traceparent`
1. `tracestate`

Enable `request_headers = RequestHeadersConfig(enabled=True)` when these
headers are set by Django
middleware at request ingress.
