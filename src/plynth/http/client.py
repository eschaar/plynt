"""Generic and REST API HTTP clients.

``HTTPClient`` is a thin layer above a transport. It owns:

- base URL composition
- default request headers (merged per call)
- convenience methods for each HTTP verb

It does not parse response bodies, raise on status codes, or perform
authentication. Those concerns belong in ``APIClient`` or higher layers.

``APIClient`` extends ``HTTPClient`` with conventions specific to JSON REST
APIs:

- Sends ``Content-Type: application/json`` and ``Accept: application/json``
  by default on every request.
- Raises a typed ``HttpStatusError`` subclass (via ``match_error()``) for
    4xx and 5xx responses by default.
- Supports ``raw=True`` on ``request()`` to bypass typed error raising when
    callers need direct access to upstream status and headers.

To keep responsibility boundaries clear, ``raw`` exists only on
``APIClient`` and ``AsyncAPIClient``. ``HTTPClient`` and ``AsyncHTTPClient``
already return raw transport responses. Their verb methods forward
``**kwargs`` to ``request()`` so extended options added by subclasses (such
as ``raw``) work without duplicating verb methods in each subclass.

Inject a ``SyncTransport`` or ``AsyncTransport`` to control the underlying
HTTP library. Use ``HTTPClient`` directly when you need raw ``Response``
objects without any JSON or error-mapping logic.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from plynth.base.request import Request
from plynth.base.response import AsyncStreamingResponse, Response, StreamingResponse
from plynth.base.transport import AsyncTransport, SyncTransport

__all__ = ["APIClient", "AsyncAPIClient", "AsyncHTTPClient", "HTTPClient"]

_JSON_HEADERS: dict[str, str] = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}


class HTTPClient:
    """Synchronous HTTP client with convenience methods for each HTTP verb.

    Composes a base URL and default headers with each outgoing request.
    The actual I/O is delegated to the injected ``SyncTransport``.

    Example:
        transport = HttpxSyncTransport()
        client = HTTPClient(
            base_url="https://api.example.com",
            transport=transport,
            headers={"User-Agent": "my-app/1.0"},
        )
        resp = client.get("/items")

    """

    def __init__(
        self,
        base_url: str,
        transport: SyncTransport,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize HTTPClient."""
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._default_headers: dict[str, str] = headers or {}

    def _build_request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
        stream: bool = False,
    ) -> Request:
        """Build a request by merging the base URL, default headers,
        and call-level overrides.
        """
        merged_headers = {**self._default_headers, **(headers or {})}
        return Request(
            method=method,
            url=f"{self._base_url}/{path.lstrip('/')}",
            headers=merged_headers,
            params=params or {},
            content=content,
            stream=stream,
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> Response:
        """Send an HTTP request and return the raw response."""
        req = self._build_request(
            method,
            path,
            headers=headers,
            params=params,
            content=content,
        )
        return self._transport.send(req)

    def get(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Response:
        """Send a GET request.

        Extra keyword arguments are forwarded to ``request()``. This allows
        subclasses to expose additional options without redefining verb
        methods.

        """
        return self.request(
            "GET",
            path,
            headers=headers,
            params=params,
            **kwargs,
        )

    def post(
        self,
        path: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Response:
        """Send a POST request.

        Extra keyword arguments are forwarded to ``request()``.

        """
        return self.request(
            "POST",
            path,
            headers=headers,
            params=params,
            content=content,
            **kwargs,
        )

    def put(
        self,
        path: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Response:
        """Send a PUT request.

        Extra keyword arguments are forwarded to ``request()``.

        """
        return self.request(
            "PUT",
            path,
            headers=headers,
            params=params,
            content=content,
            **kwargs,
        )

    def patch(
        self,
        path: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Response:
        """Send a PATCH request.

        Extra keyword arguments are forwarded to ``request()``.

        """
        return self.request(
            "PATCH",
            path,
            headers=headers,
            params=params,
            content=content,
            **kwargs,
        )

    def delete(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Response:
        """Send a DELETE request.

        Extra keyword arguments are forwarded to ``request()``.

        """
        return self.request(
            "DELETE",
            path,
            headers=headers,
            params=params,
            **kwargs,
        )

    def stream(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> StreamingResponse:
        """Send a streaming HTTP request and return a streaming response.

        The response body is not buffered. Callers must iterate over lines
        or bytes using iter_lines() or iter_bytes(), and close the response
        when done (via context manager or explicit close()) (ADR-0017, Step B).

        Args:
            method: HTTP method (e.g. "GET", "POST").
            path: Request path; merged with base_url.
            headers: Additional request headers; merged with defaults.
            params: Query string parameters.
            content: Request body as bytes.

        Returns:
            A StreamingResponse opened for iteration.

        Example:
            with client.stream("GET", "/data") as resp:
                for line in resp.iter_lines():
                    ...

        """
        req = self._build_request(
            method,
            path,
            headers=headers,
            params=params,
            content=content,
            stream=True,
        )
        resp = self._transport.send(req)
        if not isinstance(resp, StreamingResponse):
            raise TypeError(
                "Sync transport returned non-streaming response for "
                "Request.stream=True; expected StreamingResponse, got "
                f"{type(resp).__name__}"
            )
        return resp


class AsyncHTTPClient:
    """Asynchronous HTTP client with convenience methods for each HTTP verb.

    Async equivalent of ``HTTPClient``. Delegates I/O to an injected
    ``AsyncTransport``.

    Example:
        transport = HttpxAsyncTransport()
        client = AsyncHTTPClient(
            base_url="https://api.example.com",
            transport=transport,
        )
        resp = await client.get("/items")

    """

    def __init__(
        self,
        base_url: str,
        transport: AsyncTransport,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize AsyncHTTPClient."""
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._default_headers: dict[str, str] = headers or {}

    def _build_request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
        stream: bool = False,
    ) -> Request:
        """Build a request by merging the base URL, default headers,
        and call-level overrides.
        """
        merged_headers = {**self._default_headers, **(headers or {})}
        return Request(
            method=method,
            url=f"{self._base_url}/{path.lstrip('/')}",
            headers=merged_headers,
            params=params or {},
            content=content,
            stream=stream,
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> Response:
        """Send an HTTP request asynchronously and return the raw response."""
        req = self._build_request(
            method,
            path,
            headers=headers,
            params=params,
            content=content,
        )
        return await self._transport.send(req)

    async def get(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Response:
        """Send a GET request.

        Extra keyword arguments are forwarded to ``request()``. This allows
        subclasses to expose additional options without redefining verb
        methods.

        """
        return await self.request(
            "GET",
            path,
            headers=headers,
            params=params,
            **kwargs,
        )

    async def post(
        self,
        path: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Response:
        """Send a POST request.

        Extra keyword arguments are forwarded to ``request()``.

        """
        return await self.request(
            "POST",
            path,
            headers=headers,
            params=params,
            content=content,
            **kwargs,
        )

    async def put(
        self,
        path: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Response:
        """Send a PUT request.

        Extra keyword arguments are forwarded to ``request()``.

        """
        return await self.request(
            "PUT",
            path,
            headers=headers,
            params=params,
            content=content,
            **kwargs,
        )

    async def patch(
        self,
        path: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Response:
        """Send a PATCH request.

        Extra keyword arguments are forwarded to ``request()``.

        """
        return await self.request(
            "PATCH",
            path,
            headers=headers,
            params=params,
            content=content,
            **kwargs,
        )

    async def delete(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Response:
        """Send a DELETE request.

        Extra keyword arguments are forwarded to ``request()``.

        """
        return await self.request(
            "DELETE",
            path,
            headers=headers,
            params=params,
            **kwargs,
        )

    async def stream(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> AsyncStreamingResponse:
        """Send an async streaming HTTP request and return a streaming response.

        The response body is not buffered. Callers must iterate asynchronously
        over lines or bytes using aiter_lines() or aiter_bytes(), and close
        the response when done (via async context manager or aclose())
        (ADR-0017, Step B).

        Args:
            method: HTTP method (e.g. "GET", "POST").
            path: Request path; merged with base_url.
            headers: Additional request headers; merged with defaults.
            params: Query string parameters.
            content: Request body as bytes.

        Returns:
            An AsyncStreamingResponse opened for async iteration.

        Example:
            async with client.stream("GET", "/data") as resp:
                async for line in resp.aiter_lines():
                    ...

        """
        req = self._build_request(
            method,
            path,
            headers=headers,
            params=params,
            content=content,
            stream=True,
        )
        resp = await self._transport.send(req)
        if not isinstance(resp, AsyncStreamingResponse):
            raise TypeError(
                "Async transport returned non-streaming response for "
                "Request.stream=True; expected AsyncStreamingResponse, got "
                f"{type(resp).__name__}"
            )
        return resp


class APIClient(HTTPClient):
    """Synchronous REST API client with JSON defaults and structured errors.

    Extends ``HTTPClient`` by:

    - Merging ``Content-Type: application/json`` and
      ``Accept: application/json`` into every request.
    - Raising a typed ``HttpStatusError`` subclass for 4xx/5xx responses
      via ``match_error()``, so callers receive ``NotFoundError``,
      ``UnauthorizedError``, etc. instead of checking status codes manually.

    Example:
        client = APIClient(
            base_url="https://api.example.com/v1",
            transport=HttpxSyncTransport(),
        )
        resp = client.get("/products/1")  # raises NotFoundError on 404

    """

    def __init__(
        self,
        base_url: str,
        transport: SyncTransport,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize APIClient."""
        merged = {**_JSON_HEADERS, **(headers or {})}
        super().__init__(base_url, transport, headers=merged)

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
        """Send a request and raise a typed error on 4xx/5xx responses.

        Args:
            method: HTTP method.
            path: Request path.
            raw: When true, bypass typed status errors and return the raw
                response for all status codes.
            headers: Additional request headers.
            params: Query string parameters.
            content: Request body.

        Returns:
            The transport response. With ``raw=False`` this is 1xx-3xx only.
            With ``raw=True`` this may be any HTTP status.

        Raises:
            HttpStatusError: Typed subclass for the specific status code
                (e.g. ``NotFoundError`` for 404, ``UnauthorizedError`` for
                401). Falls back to plain ``HttpStatusError`` for unknown
                codes.

        """
        from plynth.http.errors import match_error

        resp = super().request(
            method,
            path,
            headers=headers,
            params=params,
            content=content,
        )
        if not raw and resp.status_code >= HTTPStatus.BAD_REQUEST:
            err = match_error(
                resp.status_code,
                method=method,
                url=f"{self._base_url}/{path.lstrip('/')}",
            )
            err.attach_response(resp)
            raise err
        return resp

    def stream(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> StreamingResponse:
        """Send a streaming request and raise a typed error on 4xx/5xx status.

        Returns the response immediately *before* consuming the body.
        Callers must close the response on the success path after finishing
        iteration. On 4xx/5xx responses, the client closes the response
        before raising the error to allow proper resource cleanup
        (ADR-0017, Step B).

        Returns:
            A StreamingResponse (status 1xx-3xx) opened for iteration.

        Raises:
            HttpStatusError: Typed subclass for 4xx/5xx responses after the
                client closes the response.

        """
        from plynth.http.errors import match_error

        resp = super().stream(
            method,
            path,
            headers=headers,
            params=params,
            content=content,
        )
        if resp.status_code >= HTTPStatus.BAD_REQUEST:
            resp.close()
            err = match_error(
                resp.status_code,
                method=method,
                url=f"{self._base_url}/{path.lstrip('/')}",
            )
            err.attach_response(resp)
            raise err
        return resp


class AsyncAPIClient(AsyncHTTPClient):
    """Asynchronous REST API client with JSON defaults and structured errors.

    Async equivalent of ``APIClient``.

    Example:
        client = AsyncAPIClient(
            base_url="https://api.example.com/v1",
            transport=HttpxAsyncTransport(),
        )
        resp = await client.get("/products/1")  # raises NotFoundError on 404

    """

    def __init__(
        self,
        base_url: str,
        transport: AsyncTransport,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize AsyncAPIClient."""
        merged = {**_JSON_HEADERS, **(headers or {})}
        super().__init__(base_url, transport, headers=merged)

    async def request(
        self,
        method: str,
        path: str,
        *,
        raw: bool = False,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> Response:
        """Send a request asynchronously and raise a typed error on 4xx/5xx.

        Args:
            method: HTTP method.
            path: Request path.
            raw: When true, bypass typed status errors and return the raw
                response for all status codes.
            headers: Additional request headers.
            params: Query string parameters.
            content: Request body.

        Returns:
            The transport response. With ``raw=False`` this is 1xx-3xx only.
            With ``raw=True`` this may be any HTTP status.

        Raises:
            HttpStatusError: Typed subclass for the specific status code.

        """
        from plynth.http.errors import match_error

        resp = await super().request(
            method,
            path,
            headers=headers,
            params=params,
            content=content,
        )
        if not raw and resp.status_code >= HTTPStatus.BAD_REQUEST:
            err = match_error(
                resp.status_code,
                method=method,
                url=f"{self._base_url}/{path.lstrip('/')}",
            )
            err.attach_response(resp)
            raise err
        return resp

    async def stream(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> AsyncStreamingResponse:
        """Send an async streaming request and raise a typed error on 4xx/5xx.

        Returns the response immediately *before* consuming the body.
        Callers must close the response on the success path after finishing
        iteration. On 4xx/5xx responses, the client closes the response
        before raising the error to allow proper resource cleanup
        (ADR-0017, Step B).

        Returns:
            An AsyncStreamingResponse (status 1xx-3xx) opened for iteration.

        Raises:
            HttpStatusError: Typed subclass for 4xx/5xx responses after the
                client closes the response.

        """
        from plynth.http.errors import match_error

        resp = await super().stream(
            method,
            path,
            headers=headers,
            params=params,
            content=content,
        )
        if resp.status_code >= HTTPStatus.BAD_REQUEST:
            await resp.aclose()
            err = match_error(
                resp.status_code,
                method=method,
                url=f"{self._base_url}/{path.lstrip('/')}",
            )
            err.attach_response(resp)
            raise err
        return resp
