"""HTTP-specific response primitive.

``HttpResponse`` extends the protocol-agnostic ``Response`` (from
``plynt.core.response``) with two groups of additions:

1. **Request context** — ``method`` and ``url`` from the originating request,
   so that ``raise_for_status()`` can produce richer ``HttpStatusError`` instances.

2. **Body decoding** — convenience members that decode ``content`` (raw bytes)
   without requiring callers to import ``json`` or inspect headers manually:

   - ``encoding`` (property) — the charset from the ``Content-Type`` header,
     lowercased. Defaults to ``"utf-8"`` when absent.
   - ``text`` (property) — ``content`` decoded with ``encoding``.
   - ``json(**kwargs)`` — body decoded as JSON via ``json.loads(self.text)``.
     Accepts the same keyword arguments as ``json.loads()``.

Note: ``encoding``, ``text``, and ``json()`` are intentionally placed on
``HttpResponse`` — an HTTP-layer class — and not on the protocol-agnostic
``Response`` in ``plynt.core.response``. The core response carries only raw
bytes; format-specific decoding belongs at the HTTP layer.

``Response`` and ``ResponseProtocol`` live in ``plynt.core.response`` and
are re-exported here for convenience.
"""

from __future__ import annotations

import json as _json
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from plynt.base.response import Response, ResponseProtocol
from plynt.http.errors import HttpStatusError

__all__ = ["HttpResponse", "Response", "ResponseProtocol"]


@dataclass
class HttpResponse(Response):
    """HTTP response carrier with request context.

    Extends ``Response`` with the originating request's method and URL,
    enabling richer error messages and logging when ``raise_for_status()``
    is called. The raw library response is available via ``_raw``.

    Convenience properties ``text`` and ``encoding``, and the method
    ``json()``, decode the response body without requiring the caller to
    manually inspect headers or call ``json.loads``.

    Attributes:
        status_code: HTTP status code (e.g. ``200``, ``404``).
        headers: Response headers as a plain dict.
        content: Raw response body as bytes.
        _raw: The original library response object, for internal use and
            debugging only (e.g. ``httpx2.Response``). Cast to the expected
            type when needed.
        method: HTTP method of the originating request (e.g. ``"GET"``).
        url: URL of the originating request.

    Example:
        resp = HttpResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            content=b'{"id": 1}',
            method="GET",
            url="https://api.example.com/items/1",
        )
        data = resp.json()  # {"id": 1}

    """

    method: str = ""
    url: str = ""

    @property
    def encoding(self) -> str:
        """Character set from the ``Content-Type`` header, lowercased.

        Falls back to ``"utf-8"`` when no ``charset`` parameter is present.

        Example:
            Content-Type: application/json; charset=iso-8859-1
            → "iso-8859-1"

        """
        content_type = self.headers.get("content-type", "")
        for part in content_type.split(";"):
            part = part.strip()
            if part.lower().startswith("charset="):
                return part[8:].strip().strip('"').lower()
        return "utf-8"

    @property
    def text(self) -> str:
        """Response body decoded to a string using ``encoding``."""
        return self.content.decode(self.encoding)

    def json(self, **kwargs: Any) -> Any:
        """Decode the response body as JSON.

        Args:
            **kwargs: Forwarded verbatim to ``json.loads()`` (e.g.
                ``object_pairs_hook``, ``parse_float``).

        Returns:
            The parsed JSON value (dict, list, str, int, float, bool, or None).

        Raises:
            json.JSONDecodeError: If the body is not valid JSON.

        """
        return _json.loads(self.text, **kwargs)

    def raise_for_status(self) -> None:
        """Raise an ``HttpStatusError`` if the HTTP status indicates failure.

        Includes the request method and URL in the error for useful logging
        and debugging.

        Raises:
            HttpStatusError: If the status code is 4xx or 5xx.

        """
        if self.status_code >= HTTPStatus.BAD_REQUEST:
            raise HttpStatusError(
                status_code=self.status_code,
                method=self.method,
                url=self.url,
            )
