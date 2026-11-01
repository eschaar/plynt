# Configure FastAPI error envelopes

Pass an envelope callable when installing plynt exception handlers:

```python
from collections.abc import Mapping
from fastapi import FastAPI
from plynt.adapters.fastapi import (
    RequestIDMiddleware,
    install_plynt_exception_handlers,
)
from plynt.base import default_error_envelope


def envelope(
    error: Exception, status_code: int, request_id: str | None
) -> Mapping[str, object]:
    return {
        **default_error_envelope(error, status_code, request_id),
        "request_id": request_id,
    }


api = FastAPI()
install_plynt_exception_handlers(api, envelope=envelope)
app = RequestIDMiddleware(api)
```

Configure routes and dependencies on `api` and serve the wrapped `app`.
See [request-ID middleware](use-request-id-middleware.md) for policy and ordering.
Without an active scope, the envelope receives `None`; mapping never creates IDs.

The callable receives the original exception, existing mapped status, and
scoped ID. It changes the payload only, not the response status. Both
`create_plynt_exception_handler` and `map_exception_to_fastapi_response` also
accept `envelope=` for direct configuration.

Installation registers handlers for plynt `BaseError` and `HttpStatusError`,
not every exception. Native FastAPI validation and HTTP exception handlers
remain unchanged. Applications can register the handler factory for additional
exception types if they deliberately want broader coverage.

Without a custom callable, existing `message`/`code` payloads are preserved.
`include_details=True` retains the default-payload detail opt-in, including
fallback; custom callables own their entire payload.

Callback failures or invalid JSON output log a safe error and use the default
envelope. See the
[core envelope contract](../../user/how-to/handle-errors.md#build-an-external-error-envelope)
for validation and information-exposure responsibilities.

To publish a tracker's event ID, read `get_error_event_id(error)` in the custom
callable and include it only when present. See
[reporting and event IDs](../../user/how-to/report-errors.md#opt-in-to-event-ids-in-responses).
The receipt follows the exact exception, including from sync workerthreads;
default responses never include it.
