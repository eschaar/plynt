# Framework adapters

Adapters are optional extensions of the generic client library. Framework
configuration, request lifecycles, dependency injection, and framework-specific
error responses belong here, not in the core user guides.

## Guides

- [Django](django/README.md): settings, caches, and transport wiring.
- [Django REST Framework](django/drf/README.md): views and serializer patterns.
- [FastAPI](fastapi/README.md): application lifespan and dependencies.

## Capabilities

| Adapter | Lifecycle boundary | Transport/client DI | Service DI | Header propagation | Error mapping | Sync | Async |
| ------- | ------------------ | ------------------- | ---------- | ------------------ | ------------- | ---- | ----- |
| Django  | Request/view scope | Via helper function | N/A        | N/A                | N/A           | Yes  | Yes   |
| DRF     | Request lifecycle  | Yes                 | Yes        | Yes                | Yes           | Yes  | Yes   |
| FastAPI | ASGI lifespan      | Yes                 | Yes        | Yes                | Yes           | Yes  | Yes   |

See the [generic user documentation](../user/README.md) for shared contracts and
the [installation reference](../user/reference/installation.md) for extras.
