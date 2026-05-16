# ADR-0018: Raw Response Access

## Status

Proposed

## Context

Plynth's `APIClient` and `AsyncAPIClient` (ADR-0008) return raw `Response`
objects on successful responses, but they always raise typed exceptions for
4xx/5xx responses. This makes non-success raw-response inspection possible
only by catching exceptions and extracting the attached response object.

This is the right default for the happy path. However, certain scenarios
require access to the raw response:

- Reading non-body data from a successful response — e.g., `Location`
  headers after a `201 Created`, `ETag` for cache validation, rate-limit
  headers, or `X-Request-Id` for correlation.
- Detecting subtle status codes — e.g., distinguishing `200` from `201` or
  `204` in mutation responses where only the status code carries meaning.
- Escape-hatch integrations — e.g., forwarding upstream headers to a
  calling service or logging the full response for audit purposes.

Currently the alternatives are either catching typed errors and inspecting the
attached response, or bypassing `APIClient` and using `HTTPClient` directly
(losing APIClient defaults such as JSON header conventions and typed mapping).

The need appears across connectors and service layers. It belongs at the
`APIClient` level, not in individual service methods or connector packages.

## Decision

### Approach: opt-in `raw` flag on `APIClient.request()`

Add an optional `raw: bool = False` keyword argument to
`APIClient.request()` (and `AsyncAPIClient.request()`):

```python
def request(
    self,
    method: str,
    path: str,
    *,
    raw: bool = False,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    content: bytes | None = None,
) -> Response:
    ...
```

When `raw=True`:

- `raise_for_status()` is **not** called.
- The `Response` object is returned directly to the caller.
- The caller is responsible for error handling and body parsing.

When `raw=False` (default):

- Existing behaviour is preserved exactly — no breaking change.

The convenience verb methods (`get`, `post`, `put`, `patch`, `delete`)
forward `**kwargs` to `request()`, so `raw=True` propagates naturally:

```python
resp = client.post("/sobjects/Account", content=body, raw=True)
location = resp.headers.get("Location")
```

Trade-off: forwarding `**kwargs` keeps verb methods DRY and avoids duplicate
overrides in subclasses, but it makes verb signatures less explicit about
which subclass-specific options are supported.

### What this is not

- Not a context manager. A flag is simpler, composes cleanly with the
  existing call signature, and avoids leaking connection management into
  the client layer (that concern belongs in ADR-0017 streaming support).
- Not a parallel `raw_request()` method. A single `request()` with an
  opt-in flag keeps the API surface small and avoids duplication.
- Not exposed on `HTTPClient`. `HTTPClient` already returns `Response`
  without calling `raise_for_status()` — it is the raw layer. The gap is
  only in `APIClient`.

## Alternatives Considered

### A: Separate `raw_request()` / `raw_get()` methods

Keeps the typed and raw paths fully separate. Rejected because it doubles
the method surface and forces callers to remember two API shapes.

### B: Context manager (`with client.raw(): ...`)

Allows raw mode for a block of calls. More expressive for multi-call
sequences, but introduces connection-lifecycle semantics that do not belong
at the client layer. Rejected for now; can be layered on top later.

### C: Return a `tuple[Response, T]` always

Provide both the raw response and the parsed model on every call. Rejected
because it breaks all existing call sites and changes the return type
contract for the common case.

### D: Caller uses `HTTPClient` directly

Already possible. Rejected as the primary solution because it loses error
mapping, JSON content type headers, and the `raise_for_status()` contract
that services rely on.

## Impact

### Client layer (`plynth.http.client`)

- `APIClient.request()` and `AsyncAPIClient.request()` gain `raw: bool = False`.
- All existing callers pass no argument and see no behaviour change.
- Convenience methods (`get`, `post`, etc.) must forward `**kwargs`.

### Service layer

- No changes required. Services that want raw access call
  `self._client.request(..., raw=True)` explicitly.
- Connector-level service methods (e.g., Salesforce `sobject.create()`)
  can expose their own `raw: bool = False` parameter and forward it.

### Testing

- Unit tests for `APIClient` and `AsyncAPIClient` must cover the `raw=True`
  branch: verify that `raise_for_status()` is not called and that the
  `Response` is returned directly.
- Existing tests need no changes.

### Breaking changes

None. The flag defaults to `False`, preserving the current contract.

## Connector Impact

Once implemented, any connector service method can expose its own
`raw: bool = False` parameter and forward it to `client.request()`. No
connector-level changes are required to adopt the feature — the client layer
change is sufficient for callers that want to drop down to raw access directly.
