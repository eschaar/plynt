# DRF serializer and orchestrator view example

Use this snippet as a copy-paste baseline when you want request/response
serializers and a separate business orchestration layer.

```python
from dataclasses import dataclass
from typing import ClassVar, cast

from rest_framework import serializers
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


@dataclass(frozen=True)
class ProductQuery:
    tenant_id: str
    include_inactive: bool


def build_catalog_service(transport: SyncTransport) -> APIClient:
    return APIClient(base_url="https://api.example.com", transport=transport)


class ProductOrchestrator:
    def __init__(self, catalog_client: APIClient) -> None:
        self._catalog = catalog_client

    def execute(self, query: ProductQuery) -> dict:
        upstream = self._catalog.get(
            "/products",
            params={
                "tenant_id": query.tenant_id,
                "include_inactive": query.include_inactive,
            },
        )
        upstream.raise_for_status()
        payload = upstream.json()

        items = []
        for item in payload.get("items", []):
            if item.get("active") or query.include_inactive:
                items.append(item)

        return {"items": items, "total": len(items)}


class ProductListView(PlynthServiceMixin, APIView):
    settings_name = "EXTERNAL_API"
    settings_class = ExternalAPISettings
    service_factories: ClassVar = {
        "catalog": build_catalog_service,
    }

    def get_catalog_client(self) -> APIClient:
        return cast(APIClient, self.get_client("catalog"))

    def get(self, request) -> Response:
        query_serializer = ProductQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        query = ProductQuery(**query_serializer.validated_data)
        result = ProductOrchestrator(self.get_catalog_client()).execute(query)

        response_serializer = ProductListResponseSerializer(result)
        return Response(response_serializer.data)
```

## Notes

1. Keep serializer logic focused on API contract validation and shaping.
1. Keep filtering and enrichment rules in the orchestrator.
1. Keep upstream transport/auth/cache concerns in plynth configuration.
