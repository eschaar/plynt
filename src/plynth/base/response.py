"""Protocol-agnostic response primitives.

``Response`` is a minimal data carrier produced by any transport. It holds
the essential raw data (status code, headers, raw body) and raises a
``StatusError`` when the status indicates failure.

``ResponseProtocol`` is a structural interface (``typing.Protocol``) that
any response-like object satisfies if it exposes the right attributes and
``raise_for_status()``. This includes ``httpx.Response``, ``requests.Response``,
and ``plynth.Response`` itself — without any inheritance.

Higher layers (middleware, client, service) should depend on
``ResponseProtocol``, not on any concrete class or HTTP library.
Format-specific parsing (JSON, text) belongs in library adapters or higher
layers, not in this module.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Protocol, runtime_checkable

from plynth.base.errors import StatusError, StreamInterruptedError

__all__ = [
    "AsyncStreamingResponse",
    "Response",
    "ResponseProtocol",
    "StreamingResponse",
]


@dataclass
class Response:
    """Minimal, library-agnostic data carrier for raw transport responses.

    Transports produce ``Response`` instances by mapping the underlying
    library response (e.g. ``httpx.Response``) into this neutral form.
    It holds only the essential raw data and performs no parsing.

    Attributes:
        status_code: Protocol status code (e.g. ``200``, ``404`` for HTTP).
        headers: Response headers as a plain dict.
        content: Raw response body as bytes.
        _raw: The original library-specific response object, for internal
            use and debugging only. Typed as ``object | None`` to stay
            library-agnostic. Cast to the expected type when needed
            (e.g. ``httpx.Response``). Not included in ``repr`` or equality.

    Example:
        resp = Response(status_code=200, content=b'{"ok": true}')
        assert resp.status_code == 200

    """

    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    content: bytes = b""
    _raw: object | None = field(default=None, repr=False, compare=False)

    def raise_for_status(self) -> None:
        """Raise a ``StatusError`` if the response status indicates failure.

        For HTTP transports this means a 4xx or 5xx status code.

        Raises:
            StatusError: If the status code indicates a client or server error.

        """
        if self.status_code >= HTTPStatus.BAD_REQUEST:
            raise StatusError(status_code=self.status_code)


@dataclass
class StreamingResponse(Response):
    """Response whose body is consumed lazily via iteration.

    Holds a reference to the underlying httpx response as an entered
    context manager. The response body is not buffered; instead, callers
    iterate over lines or bytes on demand via ``iter_lines()`` or
    ``iter_bytes()``.

    The connection remains open until ``close()`` is called or the response
    exits its context manager (ADR-0017, Step A).

    Attributes:
        status_code: HTTP response status (e.g. 200, 404).
        headers: Response headers as a mapping.
        content: Always ``b""`` for streaming responses (body not buffered).
        _raw: An entered ``httpx.Response`` object. Call methods on this via
            the public iteration interface (``iter_lines()``, etc.).

    Example::

        resp = client.stream(Request("GET", "https://api.example.com/events"))
        for line in resp.iter_lines():
            if line.startswith("data: "):
                event = json.loads(line[6:])
                print(f"Event: {event}")
        resp.close()

        # Or use as a context manager:
        with client.stream(...) as resp:
            for line in resp.iter_lines():
                ...

    """

    content: bytes = b""

    def _raw_response(self) -> Any:
        """Return the underlying transport response object."""
        if self._raw is None:
            raise RuntimeError(
                "StreamingResponse has no bound raw stream; "
                "ensure transport returns a streaming _raw response"
            )
        return self._raw

    def iter_lines(self) -> Iterator[str]:
        """Yield newline-delimited body lines as text."""
        raw = self._raw_response()

        def _iter_lines() -> Iterator[str]:
            try:
                yield from raw.iter_lines()
            except Exception as exc:
                raise StreamInterruptedError(underlying_error=exc) from exc

        return _iter_lines()

    def iter_bytes(self, chunk_size: int | None = None) -> Iterator[bytes]:
        """Yield raw body chunks as bytes."""
        raw = self._raw_response()

        def _iter_bytes() -> Iterator[bytes]:
            try:
                if chunk_size is not None:
                    yield from raw.iter_bytes(chunk_size)
                    return
                yield from raw.iter_bytes()
            except Exception as exc:
                raise StreamInterruptedError(underlying_error=exc) from exc

        return _iter_bytes()

    def close(self) -> None:
        """Close the underlying transport response stream."""
        raw = self._raw_response()
        raw.close()

    def __enter__(self) -> StreamingResponse:
        """Enter context manager and return this response."""
        return self

    def __exit__(self, *args: object) -> None:
        """Close the streaming response on context exit."""
        if self._raw is not None:
            self.close()


@dataclass
class AsyncStreamingResponse(Response):
    """Async response whose body is consumed lazily via async iteration.

    Holds a reference to the underlying httpx async response as an entered
    context manager. The response body is not buffered; instead, callers
    iterate asynchronously over lines or bytes on demand via ``aiter_lines()``
    or ``aiter_bytes()``.

    The connection remains open until ``aclose()`` is called or the response
    exits its async context manager (ADR-0017, Step A).

    Attributes:
        status_code: HTTP response status (e.g. 200, 404).
        headers: Response headers as a mapping.
        content: Always ``b""`` for streaming responses (body not buffered).
        _raw: An entered ``httpx.AsyncResponse`` object. Call methods on this
            via the public async iteration interface (``aiter_lines()``, etc.).

    Example::

        resp = await client.stream(Request("GET", "https://api.example.com/events"))
        async with resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    print(f"Event: {event}")

    """

    content: bytes = b""

    def _raw_response(self) -> Any:
        """Return the underlying transport response object."""
        if self._raw is None:
            raise RuntimeError(
                "AsyncStreamingResponse has no bound raw stream; "
                "ensure transport returns a streaming _raw response"
            )
        return self._raw

    def aiter_lines(self) -> AsyncIterator[str]:
        """Yield newline-delimited body lines as text."""
        raw = self._raw_response()

        async def _aiter_lines() -> AsyncIterator[str]:
            try:
                async for line in raw.aiter_lines():
                    yield line
            except Exception as exc:
                raise StreamInterruptedError(underlying_error=exc) from exc

        return _aiter_lines()

    def aiter_bytes(self, chunk_size: int | None = None) -> AsyncIterator[bytes]:
        """Yield raw body chunks as bytes."""
        raw = self._raw_response()

        async def _aiter_bytes() -> AsyncIterator[bytes]:
            try:
                iterator = (
                    raw.aiter_bytes(chunk_size)
                    if chunk_size is not None
                    else raw.aiter_bytes()
                )
                async for chunk in iterator:
                    yield chunk
            except Exception as exc:
                raise StreamInterruptedError(underlying_error=exc) from exc

        return _aiter_bytes()

    async def aclose(self) -> None:
        """Close the underlying async response stream."""
        raw = self._raw_response()
        await raw.aclose()

    async def __aenter__(self) -> AsyncStreamingResponse:
        """Enter async context manager and return this response."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Close the streaming response on async context exit."""
        if self._raw is not None:
            await self.aclose()


@runtime_checkable
class ResponseProtocol(Protocol):
    """Structural interface for response-like objects.

    Any object that exposes ``status_code``, ``headers``, ``content``, and
    ``raise_for_status()`` satisfies this protocol — including
    ``httpx.Response``, ``requests.Response``, and ``plynth.Response`` —
    without inheriting from this class.

    Use this protocol as the type annotation in middleware, client, and
    service layers to remain decoupled from any specific transport library.

    Example:
        def handle(response: ResponseProtocol) -> None:
            response.raise_for_status()
            ...

    """

    status_code: int
    headers: Mapping[str, str]
    content: bytes

    def raise_for_status(self) -> None:
        """Raise an exception if the response status indicates failure."""
        ...  # pragma: no cover
