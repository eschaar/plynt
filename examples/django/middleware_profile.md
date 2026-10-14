# Django middleware profile example

Use this checklist-style snippet to keep inbound Django middleware behavior
aligned with outbound plynt calls.

```python
from plynt.adapters.django.drf.views import (
    PlyntServiceMixin,
    RequestHeadersConfig,
)


class ExampleView(PlyntServiceMixin):
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
1. Keep Django response caching and plynt upstream caching separate.
