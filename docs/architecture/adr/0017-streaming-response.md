# ADR-0017: Streaming Response Support (SSE / chunked HTTP)

## Status

Accepted

## Context

Plynth's current `Response` model is a fully-buffered data carrier:

```python
@dataclass
class Response:
    status_code: int
    headers: dict[str, str]
    content: bytes = b""   # entire body in memory before the caller sees it
```

`_send_once()` in `HttpxSyncTransport` and `HttpxAsyncTransport` calls
`client.request()`, which blocks until the full response body has been
downloaded and stored in memory. This is correct and efficient for standard
JSON REST APIs.

It is insufficient for **streaming HTTP responses**, the most important
examples being:

- **Server-Sent Events (SSE)** — used by AI completion APIs (OpenAI,
  Anthropic, Gemini, and others) to stream generated tokens to the caller
  as they are produced. The connection stays open for the duration of
  generation (potentially tens of seconds) and the caller must consume
  `data:` lines incrementally to display output or measure time-to-first-
  token.
- **Long-running chunked downloads** — large file or bulk data exports where
  buffering the full body in memory would be prohibitive.
- **Salesforce Pub/Sub / Change Data Capture** — while ultimately gRPC-based,
  the pattern is the same: the caller iterates over a stream of events rather
  than receiving a single complete response.

httpx2 already supports streaming natively via its `client.stream()` context
manager, which keeps the connection open and exposes `iter_lines()`,
`iter_bytes()`, and `aiter_lines()` / `aiter_bytes()`. The gap is entirely
inside plynth — the `Response` contract and the middleware chain assume a
complete buffered body.

### Why the middleware chain does not need to be fundamentally changed

The transport middleware chain follows a chain-of-responsibility pattern
(ADR-0013):

```python
def handle(self, request: Request, next_handler: NextHandler) -> Response:
    ...
```

All middleware fires during `handle()`. By the time a `Response` is returned
to the caller the chain is complete. Crucially, **the body is not part of the
chain** — middleware manipulates request headers and may inspect response
headers, but it does not read `content`. A `StreamingResponse` can satisfy
the same `ResponseProtocol` structural interface with `content = b""`, while
exposing iterators that the caller drives *after* the chain has fully
unwound.

This means:

- Auth, header injection, and retry middleware are entirely unaffected.
- Logging middleware logs the status code and headers as usual; it cannot
  log the body (there is none yet), which is expected and acceptable.
- Cache middleware must detect a `StreamingResponse` and skip caching.
- Retry middleware can retry on connection errors before streaming starts
  (before the first byte of the body arrives). Once streaming has begun, a
  retry is not possible without restarting from scratch, which the caller
  must handle explicitly.

## Decision

### 1. `Request.stream` flag

Add an opt-in `stream: bool = False` field to `Request` (ADR-0005).
Non-streaming callers are entirely unaffected.

```python
request = Request("GET", url, stream=True)
```

### 2. `StreamingResponse` — a `Response` subclass

Introduce `StreamingResponse` in `plynth.base.response`. It satisfies
`ResponseProtocol` with `content = b""` and adds iteration:

```python
@dataclass
class StreamingResponse(Response):
    """Response whose body is consumed by the caller via iteration.

    ``content`` is always ``b""``. Use ``iter_lines()`` or ``iter_bytes()``
    to read the body.
    """

    def iter_lines(self) -> Iterator[str]: ...
    def iter_bytes(self) -> Iterator[bytes]: ...
    def close(self) -> None: ...

    def __enter__(self) -> StreamingResponse: ...
    def __exit__(self, *args: object) -> None: ...
```

The async variant:

```python
@dataclass
class AsyncStreamingResponse(Response):
    async def aiter_lines(self) -> AsyncIterator[str]: ...
    async def aiter_bytes(self) -> AsyncIterator[bytes]: ...
    async def aclose(self) -> None: ...

    async def __aenter__(self) -> AsyncStreamingResponse: ...
    async def __aexit__(self, *args: object) -> None: ...
```

Both hold a reference to the underlying `httpx2.Response` (via `_raw`) and
delegate iteration to httpx2's own streaming primitives.

### 3. `_send_once()` branches on `request.stream`

```python
def _send_once(self, request: Request) -> Response:
    if request.stream:
        return self._send_stream(request)   # uses client.stream()
    ...                                     # existing path unchanged
```

`_send_stream()` opens the httpx2 stream context, reads headers, and wraps the
open response in a `StreamingResponse`. The connection remains open; the
caller is responsible for closing it.

### 4. Caller usage

```python
with transport.send(Request("GET", url, stream=True)) as response:
    for line in response.iter_lines():
        if line.startswith("data: "):
          chunk = json.loads(line[6:])
            print(chunk["choices"][0]["delta"]["content"], end="", flush=True)
```

Async:

```python
async with transport.send(Request("GET", url, stream=True)) as response:
    async for line in response.aiter_lines():
        ...
```

### 5. Middleware adaptations

| Middleware          | Change required                                                          |
| ------------------- | ------------------------------------------------------------------------ |
| `AuthMiddleware`    | None — only touches request headers                                      |
| `HeaderMiddleware`  | None — only touches request headers                                      |
| `RetryMiddleware`   | None for pre-stream connection errors; no retry once streaming has begun |
| `LoggingMiddleware` | Log `<-- {status} {method} {url} (streaming)` — omit body logging        |
| `CacheMiddleware`   | Skip cache read and write when `isinstance(response, StreamingResponse)` |

### 6. Module location

- `StreamingResponse` / `AsyncStreamingResponse` live in
  `plynth.base.response`, exported from `plynth.base`.
- `_send_stream()` is a private method on `HttpxSyncTransport` /
  `HttpxAsyncTransport`.
- No new public classes in `plynth.http` — streaming is exposed through the
  same `transport.send()` entry point.

### 7. No new runtime dependencies

httpx2 already supports streaming. This ADR introduces no new dependencies.

## Consequences

### Positive

- AI API integrations (SSE-based streaming completions) become possible
  without workarounds.
- Large chunked downloads no longer require full in-memory buffering.
- The existing middleware chain, auth flows, service layer, and all current
  tests are unaffected. This is an additive change.
- The programming model is consistent with the existing non-streaming API —
  the same `transport.send()` entry point, opt-in via `Request.stream`.

### Negative / trade-offs

- Streaming responses require explicit resource management by the caller
  (`with` / `async with`). This is an intentional trade-off — the same
  contract httpx2 itself uses.

- `CacheMiddleware` and `LoggingMiddleware` require small stream-aware
  adaptations. This couples them lightly to `StreamingResponse`.

- **Middleware is fully unwound before the body is consumed.** Any problem
  that arises during iteration — a network reset, a connection drop, an
  embedded error chunk signalling auth expiry or rate limiting — is not
  visible to middleware. It is the service layer's responsibility to handle
  these.

  In practice this is not a significant limitation because:

  - HTTP-level errors (401, 429, 5xx) appear in the status line, which
    arrives *before* the stream starts. Middleware handles these as normal,
    before `StreamingResponse` is returned.
  - Embedded application-level errors (e.g. an AI API writing
    `{"error": {...}}` as a stream chunk) must be parsed by the service
    layer anyway — the service layer is already iterating and interpreting
    every chunk. Error detection and typed exception mapping naturally
    belong there.
  - Network errors during iteration (connection reset, read timeout) surface
    as transport exceptions. The **client layer** (ADR-0008) is the correct
    place to catch and map these to `StreamInterruptedError` — consistent
    with how `raise_for_status()` already maps HTTP errors at the client
    layer before they reach the service layer. The service layer never sees
    raw httpx2 types.

  An alternative design — ASGI-style iterator-wrapping middleware — would
  allow middleware to intercept chunks. That design is significantly more
  complex and would require changing the ADR-0013 Protocol contract. It is
  not warranted by these use cases. If future usage patterns show a genuine
  need, a new ADR should be raised before any implementation.

- Retry on a partially-consumed stream is not possible without restarting
  from scratch. The service layer controls this decision because it alone
  knows whether a restart is safe (idempotent) and what to do with already-
  consumed output.

### Layer responsibilities for streaming

The existing layer separation (ADR-0002) maps cleanly onto streaming:

| Layer         | Responsibility                                                                                                                                                                                                           |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Transport** | Opens the stream via `client.stream()`; returns `StreamingResponse` with status + headers populated; connection stays open                                                                                               |
| **Client**    | Calls `raise_for_status()` before returning (HTTP-level errors, 401/429/5xx, handled here as normal); exposes a `stream()` method; wraps `iter_lines()` to catch transport exceptions and raise `StreamInterruptedError` |
| **Service**   | Calls `self._client.stream()`; owns the chunk-parsing loop; detects API-level embedded errors in chunks and raises typed domain exceptions (e.g. `RateLimitError`); never sees raw httpx2 types                          |
| **Caller**    | Iterates the typed stream returned by the service; handles domain exceptions; decides whether to restart                                                                                                                 |

This mirrors non-streaming exactly — the client already absorbs
`raise_for_status()` so the service layer never deals with raw HTTP errors.
Streaming extends that contract: the client also absorbs raw transport
iterator exceptions, and the service absorbs embedded application errors.

A `StreamService` / `AsyncStreamService` base class in `plynth.http` remains a
possible future enhancement for reducing integration boilerplate.

### Implemented follow-up

The original proposal listed two follow-ups that are now implemented:

- `StreamInterruptedError` exists in `plynth.base.errors`.
- Client-layer `stream()` methods are available on `HTTPClient`,
  `AsyncHTTPClient`, `APIClient`, and `AsyncAPIClient` with close-before-raise
  behavior on 4xx/5xx responses.

### Still out of scope

- `StreamService` / `AsyncStreamService` base classes in `plynth.http`.
- **WebSockets** — full-duplex persistent connections. Different protocol
  model; the middleware chain contract does not apply. Requires a separate ADR
  and likely a dedicated transport.
- **gRPC** — different protocol stack (HTTP/2 + protobuf). ADR-0006
  anticipated this via direct `SyncTransport` / `AsyncTransport` subclassing.
  Requires a dedicated `GrpcAsyncTransport` ADR.
- **Service-layer streaming helpers** — SSE parsing, event model, typed token
  models. These belong in integration modules (e.g. `plynth[openai]`), not
  in the transport base.
