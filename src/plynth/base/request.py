"""Transport-layer request primitive.

``Request`` is a library-agnostic data carrier for outgoing HTTP requests.
It does not depend on any HTTP library and can be used with any HTTP
transport implementation.

Example:
    req = Request(
        method="POST",
        url="https://api.example.com/items",
        headers={"Authorization": "Bearer ..."},
        params={"q": "search"},
        content=b'{"foo": "bar"}',
    )

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["Request"]


@dataclass
class Request:
    """Represents an outgoing HTTP request.

    Attributes:
        method: HTTP method (e.g. ``"GET"``, ``"POST"``).
        url: Fully qualified URL string.
        headers: Request headers as a plain dict.
        params: Query string parameters as a plain dict.
        content: Raw request body as bytes, or ``None`` for bodyless requests.
        timeout: Per-request read timeout in seconds. When set, overrides
            the transport-level timeout configured via
            ``HTTPSettings.timeout_read``. When ``None`` (default), the
            transport's configured timeout applies unchanged.
            (ADR-0005-A1)

    Example:
        req = Request(
            method="POST",
            url="https://api.example.com/items",
            headers={"Authorization": "Bearer ..."},
            params={"q": "search"},
            content=b'{"foo": "bar"}',
        )

    """

    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    content: bytes | None = None
    timeout: float | None = None
