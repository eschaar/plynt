# Use request IDs in Django

Install `plynt[django]` and add `RequestIDMiddleware` before
`CommonMiddleware` and response-cache middleware:

```python
MIDDLEWARE = [
    "plynt.adapters.django.RequestIDMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Other application middleware follows.
]
```

The middleware accepts a valid inbound `X-Request-ID` or generates a UUID hex
value. It scopes that ID around the response handler, then echoes it on the
response. It supports both sync and async Django handlers without forcing an
execution-mode conversion.

Read the ID in views or application code with `plynt.base.get_request_id()`.
Enable outbound propagation and logging separately as described in the
[core request-ID guide](../../user/how-to/use-request-id-context.md).

## Ordering and response behavior

Putting the middleware before `CommonMiddleware` ensures `APPEND_SLASH`
redirects carry the ID. It does not change paths or Django's slash settings.
Early responses and Django-generated error responses also carry the ID.

The response header is always set to the current scoped ID, replacing stale
values from downstream handlers or response caches. Put it before response
cache middleware so a cached response cannot supply another request's ID.

A redirect and its subsequent request are separate requests. They retain
the same ID only if the caller sends it again; plynt does not manage redirects
or workflow correlation.

The context is restored after the handler returns or raises, including async
cancellation. Sync views adapted by Django under ASGI receive copied context.
Deferred streaming-body iteration and background work after the response
handler finishes are outside this scope.

## Configure a policy

For a custom header, generator, or inbound trust policy, expose a middleware
factory in the application:

```python
from collections.abc import Awaitable, Callable
from django.http import HttpRequest
from django.http.response import HttpResponseBase
from django.utils.decorators import sync_and_async_middleware
from plynt.adapters.django import RequestIDMiddleware
from plynt.base import RequestIDPolicy


@sync_and_async_middleware
def request_ids(
    get_response: Callable[
        [HttpRequest], HttpResponseBase | Awaitable[HttpResponseBase]
    ],
) -> RequestIDMiddleware:
    return RequestIDMiddleware(
        get_response,
        policy=RequestIDPolicy(trust_inbound=False),
    )
```

Use `"myapp.middleware.request_ids"` in `MIDDLEWARE` instead of the default
class path. The decorator declares both execution modes to Django. Django
supports these factories directly; no plugin registry is needed.

The default trusts valid inbound IDs. Use `trust_inbound=False` for
internet-facing services that should always generate their own ID. Request IDs
are correlation values, never authentication or idempotency keys.

This middleware does not change DRF error envelopes. Use
[DRF envelope configuration](drf/configure-error-envelopes.md) to include the ID
in error payloads.
