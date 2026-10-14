# DRF service view example

Use this snippet as a copy-paste starting point for integrating
`PlyntServiceMixin` or `AsyncPlyntServiceMixin` in a DRF `APIView`.

```python
from typing import ClassVar, cast

from rest_framework.response import Response
from rest_framework.views import APIView

from plynt.adapters.django.drf.views import (
    AsyncPlyntServiceMixin,
    CacheAliasesConfig,
    PlyntServiceMixin,
)
from plynt.base.transport import AsyncTransport, SyncTransport
from plynt.http.auth import OAuth2ClientCredentialsConfig
from plynt.http.client import APIClient, AsyncAPIClient
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


def build_catalog_service(transport: SyncTransport) -> APIClient:
    return APIClient(base_url="https://api.example.com", transport=transport)


def build_async_catalog_service(transport: AsyncTransport) -> AsyncAPIClient:
    return AsyncAPIClient(base_url="https://api.example.com", transport=transport)


class ProductListView(PlyntServiceMixin, APIView):
    settings_name = "EXTERNAL_API"
    settings_class = ExternalAPISettings
    cache_aliases = CacheAliasesConfig(
        response="plynt_responses",
        auth="plynt_tokens",
    )
    service_factories: ClassVar = {
        "catalog": build_catalog_service,
    }

    def get_catalog_client(self) -> APIClient:
        return cast(APIClient, self.get_client("catalog"))

    def get(self, request) -> Response:
        catalog = self.get_catalog_client()
        upstream = catalog.get("/products")
        upstream.raise_for_status()
        return Response(upstream.json())


class AsyncProductListView(AsyncPlyntServiceMixin, APIView):
    settings_name = "EXTERNAL_API"
    settings_class = ExternalAPISettings
    cache_aliases = CacheAliasesConfig(
        response="plynt_responses",
        auth="plynt_tokens",
    )
    service_factories: ClassVar = {
        "catalog": build_async_catalog_service,
    }

    def get_catalog_client(self) -> AsyncAPIClient:
        return cast(AsyncAPIClient, self.get_client("catalog"))

    async def get(self, request) -> Response:
        catalog = self.get_catalog_client()
        upstream = await catalog.get("/products")
        upstream.raise_for_status()
        return Response(upstream.json())
```

## Notes

1. Keep business logic outside the view in dedicated service/facade classes.
1. Use the view mainly for request validation, orchestration, and response
   shaping.
1. Configure auth and cache aliases in Django `settings.py`.
1. Use `AsyncPlyntServiceMixin` only for explicit async `APIView` handlers
   under ASGI.
