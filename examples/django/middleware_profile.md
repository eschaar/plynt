# Django middleware profile example

Use this checklist-style snippet to keep inbound Django middleware behavior
aligned with outbound plynth calls.

```python
from plynth.adapters.django.drf.views import (
    PlynthServiceMixin,
    RequestHeadersConfig,
)


class ExampleView(PlynthServiceMixin):
    request_headers = RequestHeadersConfig(
        enabled=True,
        mapping={
            "X-Request-Id": "X-Request-Id",
            "X-Correlation-Id": "X-Correlation-Id",
            "traceparent": "traceparent",
            "tracestate": "tracestate",
        },
        blocked={"authorization", "cookie"},
    )
```

## Notes

1. Keep request-header forwarding explicit and minimal.
1. Do not derive outbound base URLs from inbound host headers.
1. Keep Django response caching and plynth upstream caching separate.
