# DRF examples

Runnable snippets and integration patterns for using plynth inside Django REST
Framework views.

## Available examples

- [DRF service view](drf_service_view.md) — configure `PlynthServiceMixin` with
  named upstream service factories, including async `APIView` usage
- [Serializer + business orchestrator view](serializer_orchestrator_view.md) —
  keep serializers as API contracts and place business logic in an orchestrator
- [DRF exception handler setup](exception_handler_setup.md) — map plynth
  exceptions to safe DRF responses

## Prerequisites

1. Install DRF support:

```bash
pip install "plynth[drf]"
```

1. Configure your Django settings block for upstream API credentials.
1. Run snippets from a Django-aware runtime (for example `manage.py shell`).
