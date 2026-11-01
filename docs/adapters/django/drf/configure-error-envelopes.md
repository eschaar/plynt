# Configure DRF error envelopes

The default `plynt_exception_handler` keeps existing `message`/`code` payloads.
To opt into a custom envelope, expose an application handler:

```python
from collections.abc import Mapping
from typing import Any
from plynt.adapters.django.drf.errors import plynt_exception_handler
from plynt.base import default_error_envelope


def envelope(
    error: Exception, status_code: int, request_id: str | None
) -> Mapping[str, object]:
    payload = default_error_envelope(error, status_code, request_id)
    return {**payload, "request_id": request_id}


def exception_handler(exc: Exception, context: dict[str, Any]) -> Any:
    return plynt_exception_handler(exc, context, envelope=envelope)
```

Select that handler in Django settings:

```python
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "myapp.errors.exception_handler",
}
```

Install [Django request-ID middleware](../use-request-id-middleware.md) to
provide the scoped ID. Without an active scope, the callable receives `None`;
exception mapping never generates an ID.

The adapter supplies the existing mapped status and exception to the callable,
then builds a DRF response. The envelope changes only the payload, not the
response status. For direct mapping, pass `envelope=` to
`map_exception_to_drf_response`.

DRF's default handler still runs first. Native DRF errors, including validation
errors, retain their own payloads and do not invoke the custom envelope.
The custom format applies only when DRF returns `None` and plynt maps the error.
An application requiring one format for all DRF errors must also handle native
responses in its application wrapper.

Custom output is validated by the shared
[core envelope builder](../../../user/how-to/handle-errors.md#build-an-external-error-envelope).
Callback failures and invalid output produce safe error logging and the default
payload. `include_details=True` on the handler or mapping helper preserves the
existing default-payload opt-in, including fallback; custom envelopes own their
entire payload. Only include details that are safe to expose.

To publish a tracker's event ID, read `get_error_event_id(error)` in the custom
callable and include it only when present. See
[reporting and event IDs](../../../user/how-to/report-errors.md#opt-in-to-event-ids-in-responses).
The receipt belongs to the exact exception; default responses never include it.
