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

import inspect
from collections.abc import AsyncIterator, Iterator, Mapping
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Protocol, runtime_checkable

from plynth.base.errors import StatusError

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

    ``content`` is always ``b""``. Read the body through ``iter_bytes()`` or
    ``iter_lines()`` and call ``close()`` when finished (or use ``with``).
    """

    content: bytes = b""

    def _raw_response(self) -> Any:
        """Return the underlying transport response object."""
        if self._raw is None:
            raise RuntimeError("StreamingResponse has no raw response attached")
        return self._raw

    def iter_bytes(self) -> Iterator[bytes]:
        """Yield raw body chunks as bytes."""
        raw = self._raw_response()
        yield from raw.iter_bytes()

    def iter_lines(self) -> Iterator[bytes]:
        """Yield newline-delimited body lines as bytes."""
        buffered = b""
        for chunk in self.iter_bytes():
            buffered += chunk
            while True:
                newline_at = buffered.find(b"\n")
                if newline_at == -1:
                    break
                line = buffered[:newline_at]
                if line.endswith(b"\r"):
                    line = line[:-1]
                yield line
                buffered = buffered[newline_at + 1 :]

        if buffered:
            if buffered.endswith(b"\r"):
                buffered = buffered[:-1]
            yield buffered

    def close(self) -> None:
        """Close the underlying transport response stream."""
        raw = self._raw_response()
        raw.close()

    def __enter__(self) -> StreamingResponse:
        """Enter context manager and return this response."""
        return self

    def __exit__(self, *args: object) -> None:
        """Close the streaming response on context exit."""
        self.close()


@dataclass
class AsyncStreamingResponse(Response):
    """Async response whose body is consumed lazily via async iteration.

    ``content`` is always ``b""``. Read the body through ``aiter_bytes()`` or
    ``aiter_lines()`` and call ``aclose()`` when finished (or use
    ``async with``).
    """

    content: bytes = b""

    def _raw_response(self) -> Any:
        """Return the underlying transport response object."""
        if self._raw is None:
            raise RuntimeError("AsyncStreamingResponse has no raw response attached")
        return self._raw

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        """Yield raw body chunks as bytes."""
        raw = self._raw_response()
        async for chunk in raw.aiter_bytes():
            yield chunk

    async def aiter_lines(self) -> AsyncIterator[bytes]:
        """Yield newline-delimited body lines as bytes."""
        buffered = b""
        async for chunk in self.aiter_bytes():
            buffered += chunk
            while True:
                newline_at = buffered.find(b"\n")
                if newline_at == -1:
                    break
                line = buffered[:newline_at]
                if line.endswith(b"\r"):
                    line = line[:-1]
                yield line
                buffered = buffered[newline_at + 1 :]

        if buffered:
            if buffered.endswith(b"\r"):
                buffered = buffered[:-1]
            yield buffered

    async def aclose(self) -> None:
        """Close the underlying async response stream."""
        raw = self._raw_response()
        close_result = raw.aclose()
        if inspect.isawaitable(close_result):
            await close_result

    async def __aenter__(self) -> AsyncStreamingResponse:
        """Enter async context manager and return this response."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Close the streaming response on async context exit."""
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
