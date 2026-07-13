# DRF service view example

Use this snippet as a copy-paste starting point for integrating
`PlynthServiceMixin` in a DRF `APIView`.

```python
from typing import ClassVar, cast

from rest_framework.response import Response
from rest_framework.views import APIView

from plynth.adapters.django.drf.views import PlynthServiceMixin
from plynth.base.transport import SyncTransport
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


def build_catalog_service(transport: SyncTransport) -> APIClient:
    return APIClient(base_url="https://api.example.com", transport=transport)


class ProductListView(PlynthServiceMixin, APIView):
    plynth_settings_name = "EXTERNAL_API"
    plynth_settings_class = ExternalAPISettings
    plynth_response_cache_alias = "plynth_responses"
    plynth_auth_cache_alias = "plynth_tokens"
    plynth_service_factories: ClassVar = {
        "catalog": build_catalog_service,
    }

    def get_catalog_client(self) -> APIClient:
        return cast(APIClient, self.get_client("catalog"))

    def get(self, request) -> Response:
        catalog = self.get_catalog_client()
        upstream = catalog.get("/products")
        upstream.raise_for_status()
        return Response(upstream.json())
```

## Notes

1. Keep business logic outside the view in dedicated service/facade classes.
1. Use the view mainly for request validation, orchestration, and response
   shaping.
1. Configure auth and cache aliases in Django `settings.py`.
