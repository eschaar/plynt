# DRF exception handler setup example

Use this snippet to enable safe, consistent DRF error responses for unhandled
plynth exceptions.

```python
# settings.py
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "plynth.adapters.django.drf.errors.plynth_exception_handler",
}
```

Optional view-level include-details toggle example:

```python
from plynth.adapters.django.drf.errors import map_exception_to_drf_response


def custom_exception_handler(exc, context):
    # Example: include details in non-production only
    include_details = False
    response = map_exception_to_drf_response(exc, include_details=include_details)
    return response
```

## Notes

1. Keep `include_details=False` for production by default.
1. Avoid returning internal stack traces or sensitive context.
1. Use structured logging for diagnostics instead of exposing internals.
