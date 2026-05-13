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
- Calls ``raise_for_status()`` after every response, which raises a typed
  ``HttpStatusError`` subclass (via ``match_error()``) for 4xx and 5xx
  responses.

Inject a ``SyncTransport`` or ``AsyncTransport`` to control the underlying
HTTP library. Use ``HTTPClient`` directly when you need raw ``Response``
objects without any JSON or error-mapping logic.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from plynth.base.request import Request
from plynth.base.response import Response
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
    ) -> Response:
        """Send a GET request."""
        return self.request("GET", path, headers=headers, params=params)

    def post(
        self,
        path: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Response:
        """Send a POST request."""
        return self.request(
            "POST", path, headers=headers, params=params, content=content
        )

    def put(
        self,
        path: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Response:
        """Send a PUT request."""
        return self.request(
            "PUT", path, headers=headers, params=params, content=content
        )

    def patch(
        self,
        path: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Response:
        """Send a PATCH request."""
        return self.request(
            "PATCH", path, headers=headers, params=params, content=content
        )

    def delete(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Response:
        """Send a DELETE request."""
        return self.request("DELETE", path, headers=headers, params=params)


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
    ) -> Response:
        """Send a GET request."""
        return await self.request("GET", path, headers=headers, params=params)

    async def post(
        self,
        path: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Response:
        """Send a POST request."""
        return await self.request(
            "POST", path, headers=headers, params=params, content=content
        )

    async def put(
        self,
        path: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Response:
        """Send a PUT request."""
        return await self.request(
            "PUT", path, headers=headers, params=params, content=content
        )

    async def patch(
        self,
        path: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Response:
        """Send a PATCH request."""
        return await self.request(
            "PATCH", path, headers=headers, params=params, content=content
        )

    async def delete(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Response:
        """Send a DELETE request."""
        return await self.request("DELETE", path, headers=headers, params=params)


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
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> Response:
        """Send a request and raise a typed error on 4xx/5xx responses.

        Returns:
            The raw transport response (status 1xx-3xx).

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
        if resp.status_code >= HTTPStatus.BAD_REQUEST:
            err = match_error(
                resp.status_code,
                method=method,
                url=f"{self._base_url}/{path.lstrip('/')}",
            )
            err._response = resp
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
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> Response:
        """Send a request asynchronously and raise a typed error on 4xx/5xx.

        Returns:
            The raw transport response (status 1xx-3xx).

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
        if resp.status_code >= HTTPStatus.BAD_REQUEST:
            err = match_error(
                resp.status_code,
                method=method,
                url=f"{self._base_url}/{path.lstrip('/')}",
            )
            err._response = resp
            raise err
        return resp
