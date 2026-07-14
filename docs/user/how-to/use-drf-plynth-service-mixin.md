# How to use Plynth in DRF views

Use `PlynthServiceMixin` to build one plynth transport per DRF view instance
and expose named upstream services in a predictable way.

## Install extras

```bash
pip install "plynth[drf]"
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
    "plynth_responses": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/2",
    },
    "plynth_tokens": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/3",
    },
}
```

## Create typed settings and service factory

```python
from plynth.http.auth import OAuth2ClientCredentialsConfig
from plynth.http.client import APIClient
from plynth.http.settings import HTTPSettings


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
```

## Use `PlynthServiceMixin` in APIView/ViewSet

```python
from rest_framework.response import Response
from rest_framework.views import APIView

from plynth.adapters.django.drf.views import PlynthServiceMixin


class ProductListView(PlynthServiceMixin, APIView):
    plynth_settings_name = "EXTERNAL_API"
    plynth_settings_class = ExternalAPISettings
    plynth_response_cache_alias = "plynth_responses"
    plynth_auth_cache_alias = "plynth_tokens"
    plynth_auto_request_headers = True
    plynth_service_factories = {
        "catalog": build_catalog_service,
    }

    def get(self, request):
        catalog = self.get_client("catalog")
        upstream = catalog.get("/products")
        upstream.raise_for_status()
        return Response(upstream.json())
```

`get_client("catalog")` is a convenience alias for
`get_plynth_service("catalog")`. Both are lazy and cached per view instance.

## Propagate request headers to outbound calls

Use `build_request_header_middleware(...)` when correlation headers from the
incoming DRF request should be forwarded upstream.

```python
from plynth.adapters.django.drf.headers import build_request_header_middleware

middleware = build_request_header_middleware(request)
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

Set a class-level mapping when using automatic propagation from the mixin:

```python
class ProductListView(PlynthServiceMixin, APIView):
    plynth_auto_request_headers = True
    plynth_request_header_map = {
        "X-Upstream-Tenant": "X-Tenant-Id",
    }
```

## DRF exception mapping for plynth errors

Use the provided exception handler to map unhandled plynth exceptions to
safe DRF JSON responses.

```python
# settings.py
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "plynth.adapters.django.drf.errors.plynth_exception_handler",
}
```

Behavior:

1. DRF default exception handler runs first.
1. If DRF returns `None`, plynth mapping returns a safe error payload.
1. `HttpStatusError` subclasses keep their status code; other exceptions map
   to HTTP 500.
