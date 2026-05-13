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

from collections.abc import Mapping
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Protocol, runtime_checkable

from plynth.base.errors import StatusError

__all__ = ["Response", "ResponseProtocol"]


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
