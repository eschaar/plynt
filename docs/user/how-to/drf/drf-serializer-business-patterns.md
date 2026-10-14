# DRF serializer and business-layer patterns

Use these patterns when DRF endpoints call upstream services through plynt.
The goal is to keep API contracts stable, business logic testable, and views
small.

## Why this split works

1. Serializers define and enforce request and response contracts.
1. Business layer owns orchestration, filtering, enrichment, and policy rules.
1. Plynt clients focus on transport, auth, retry, and middleware.
1. Views coordinate the flow and return HTTP responses.
1. Async variants keep the same layering; only the view method, plynt client,
   and transport path switch to async.

## Pattern 1: Thin view with application service

Use this as the default pattern.

When to use:

- One endpoint calls one or more upstream services.
- The endpoint has non-trivial business rules.

Implementation:

1. Validate input with an input serializer.
1. Pass validated data into an application service.
1. Let the service call plynt clients and compose domain output.
1. Serialize output with an output serializer.

Benefits:

- View methods stay short.
- Business logic is unit testable without DRF request objects.
- API contract remains explicit and versionable.

## Pattern 2: Query object and orchestrator

Use this when query parameters grow and filtering logic is complex.

When to use:

- Many optional filters and sort options.
- Shared filtering rules across multiple endpoints.

Implementation:

1. Input serializer validates query params.
1. Build a small query object from validated data.
1. Orchestrator executes upstream calls based on the query object.
1. Return normalized output DTO for response serialization.

Benefits:

- Avoids passing loose dictionaries through many layers.
- Makes filter behavior deterministic and easy to test.

## Pattern 3: Aggregator service for fan-out calls

Use this when one API response combines data from multiple backends.

When to use:

- Endpoint needs product, pricing, and availability in one response.
- Upstreams have different response shapes.

Implementation:

1. Aggregator service receives plynt clients.
1. Fetch data from each upstream.
1. Normalize upstream models to internal structures.
1. Merge and filter combined result.
1. Return a single response DTO for serializer output.

Benefits:

- Keeps integration complexity out of views.
- Makes fallback logic and partial-result strategy explicit.

## Pattern 4: Anti-corruption mapper

Use this when upstream payloads are unstable or inconsistent.

When to use:

- Upstream fields change often.
- Different providers model the same concept differently.

Implementation:

1. Keep mapper functions in the business layer.
1. Map each upstream payload into a stable internal DTO.
1. Never expose upstream field names directly in output serializers.

Benefits:

- Protects your public API from upstream churn.
- Makes provider migration safer.

## Pattern 5: Policy object for eligibility rules

Use this when many conditional business checks determine visibility.

When to use:

- Feature flags and entitlement checks.
- Tenant or market-specific business policies.

Implementation:

1. Build a policy object from request context and config.
1. Apply policy in application service after data retrieval.
1. Return only policy-approved data for serialization.

Benefits:

- Centralizes rule logic.
- Improves readability and change safety.

## Reference skeleton

```python
from dataclasses import dataclass
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


@dataclass(frozen=True)
class ProductQuery:
    tenant_id: str
    include_inactive: bool


class ProductOrchestrator:
    def __init__(self, catalog_client) -> None:
        self._catalog = catalog_client

    def execute(self, query: ProductQuery) -> dict:
        response = self._catalog.get(
            "/products",
            params={
                "tenant_id": query.tenant_id,
                "include_inactive": query.include_inactive,
            },
        )
        response.raise_for_status()
        payload = response.json()

        items = []
        for item in payload.get("items", []):
            if item.get("active") or query.include_inactive:
                items.append(item)

        return {"items": items, "total": len(items)}


class ProductListView(PlyntServiceMixin, APIView):
    settings_name = "EXTERNAL_API"
    settings_class = ExternalAPISettings
    service_factories = {
        "catalog": build_catalog_service,
    }

    def get(self, request):
        serializer = ProductQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        query = ProductQuery(**serializer.validated_data)
        orchestrator = ProductOrchestrator(self.get_client("catalog"))
        result = orchestrator.execute(query)

        output = ProductListResponseSerializer(result)
        return Response(output.data)
```

## Testing guidance by layer

1. Serializer tests:
   validate required fields, defaults, and field-level errors.
1. Business-layer tests:
   mock plynt clients and verify filtering, enrichment, and policy behavior.
1. View tests:
   verify serializer integration, HTTP status codes, and response shape.

## Common mistakes

- Putting filtering and enrichment directly inside view methods.
- Returning raw upstream JSON without output serializer validation.
- Coupling serializer fields to upstream field names.
- Mixing transport concerns into business services.

## Decision checklist

Use this quick checklist per endpoint:

1. Is input fully validated by serializer before service calls?
1. Is business logic in a dedicated service or orchestrator?
1. Is output always serialized by an explicit response serializer?
1. Are upstream payloads normalized before response mapping?
1. Are tests split across serializer, service, and view layers?

## Suggested file layout

Use a predictable package layout so teams can navigate layers quickly.

```text
my_feature/
    api/
        serializers.py
        views.py
    services/
        orchestrators.py
        mappers.py
        policies.py
    tests/
        test_serializers.py
        test_orchestrators.py
        test_views.py
```

Mapping guidance:

1. Keep DRF contract code in api/serializers.py and api/views.py.
1. Keep orchestration and enrichment logic in services/orchestrators.py.
1. Keep provider-to-domain translation in services/mappers.py.
1. Keep eligibility and rule checks in services/policies.py.
