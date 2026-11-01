# Use request ID context

`RequestIDPolicy` configures request ID validation, generation, and scoped
context using `contextvars`. The policy itself does not read requests, modify endpoints,
or inject headers. Framework-specific wiring is documented in the
[adapter guides](../../adapters/README.md).

```python
from plynt.base import RequestIDPolicy, get_request_id

policy = RequestIDPolicy()
with policy.scope("incoming-id") as request_id:
    assert get_request_id() == request_id
assert get_request_id() is None
```

## Validation and configuration

Incoming IDs may contain ASCII letters, digits, `-`, `_`, `.`, and `:`.
The default maximum is 128 characters. Missing or invalid IDs are replaced
by a UUID hex value without logging or echoing the rejected input.

```python
policy = RequestIDPolicy(
    header_name="X-Request-ID",
    max_length=64,
    trust_inbound=False,
)
```

`X-Request-ID` is the default header name. `header_name` can be changed for
integrations that require a different name; this does not change the scope
or meaning of the ID.

`header_name` is validated configuration for integrations; this core helper
does not access HTTP headers. Set `trust_inbound=False` to generate fresh IDs
even when an inbound ID is valid. IDs are correlation values, not credentials
or idempotency keys.

A custom `generator` must return a valid ID. Invalid output raises `ValueError`
rather than silently substituting another generator. Generator exceptions
propagate unchanged.

## Propagate the ID to upstream calls

Enable propagation explicitly with `request_id_policy` on `HeaderMiddleware`
or `AsyncHeaderMiddleware`:

```python
from plynt.base import Request, RequestIDPolicy
from plynt.middleware.header import HeaderMiddleware
from plynt.http.transport import HttpxSyncTransport

policy = RequestIDPolicy()
with HttpxSyncTransport(
    middlewares=[HeaderMiddleware({}, request_id_policy=policy)]
) as transport:
    with policy.scope("incoming-id"):
        response = transport.send(Request("GET", "https://api.example.com/items"))
```

The middleware reads the active context for each outgoing request. It never
generates an ID outside a scope, and it never replaces an existing request ID
header, comparing names case-insensitively. Explicit configured headers take
precedence over context propagation. Other header injection behavior remains
unchanged.

Place the header middleware before retry middleware so the ID stays the same
throughout retry attempts.

## Include the ID in logs

Attach `RequestIDFilter` to a handler to enrich records from both application
and plynt loggers. Python logger filters do not apply to propagated child
records, so configure this filter on the handler rather than a parent logger.

```python
import logging
from plynt.log import RequestIDFilter, StructuredFormatter

handler = logging.StreamHandler()
handler.addFilter(RequestIDFilter())
handler.setFormatter(StructuredFormatter())
logging.getLogger("plynt").addHandler(handler)
```

The filter sets `record.request_id` to the active scoped ID, or `"-"` when
no scope is active. It never generates an ID or suppresses a record. Existing
`request_id` fields are replaced with the current context, preventing stale IDs.

`StructuredFormatter` includes the field automatically. For plain-text output,
use `logging.Formatter("%(request_id)s %(message)s")` on the filtered handler.
Filtering is opt-in; existing logging configuration remains unchanged.

## Scope and concurrency

The same `with policy.scope(...)` block works in synchronous functions and
async functions. Its ID is restored on exit, including when an exception
propagates. Concurrent asyncio tasks have independent contexts.

The policy object contains reusable configuration, not the active request ID.
The active ID lives in the current execution context and is returned by
`get_request_id()`.

## Request scope versus workflows

One scope represents one inbound request and the upstream calls and log
records produced while handling it. Propagating that ID across these calls
does not guarantee a distinct ID for each HTTP hop: a trusted inbound ID
can be retained.

A workflow containing multiple independent requests or background jobs needs
separate workflow correlation managed by the application. Distributed tracing
can use a trace ID across the workflow and separate spans for individual
operations. Renaming the header to a correlation header does not add workflow
tracking to this policy.

Worker threads do not automatically inherit the caller's context. Use
`contextvars.copy_context()` and execute the worker through its `run` method,
or use `asyncio.to_thread()`, which copies context automatically. Never share
the same copied context between concurrently executing workers.

See [ADR-0040](../../architecture/adr/0040-inbound-request-id-and-error-envelope.md)
for the integration contract. Adapter-specific setup belongs in the
[adapter guides](../../adapters/README.md).
