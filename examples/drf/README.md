# DRF examples

Runnable snippets and integration patterns for using plynt inside Django REST
Framework views.

## Available examples

- [DRF service view](drf_service_view.md) — configure `PlyntServiceMixin` with
  named upstream service factories, including async `APIView` usage
- [Serializer + business orchestrator view](serializer_orchestrator_view.md) —
  keep serializers as API contracts and place business logic in an orchestrator
- [DRF exception handler setup](exception_handler_setup.md) — map plynt
  exceptions to safe DRF responses

## Prerequisites

1. Install required extras:

```bash
pip install "plynt[drf]"
```

1. Configure your Django settings block for upstream API credentials.
1. Run snippets from a Django-aware runtime (for example `manage.py shell`).

## Validation checklist

- Confirm `PlyntServiceMixin` resolves configured service factories.
- Trigger a mapped plynt exception and verify DRF-safe error output.
- For async snippets, verify view execution without sync/async boundary errors.
