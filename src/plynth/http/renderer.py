"""Request body renderer protocol and built-in implementations.

A ``Renderer`` serialises Python objects into ``bytes`` for use as an HTTP
request body. Renderers are injected into services to keep encoding logic
(JSON, form, XML, etc.) out of endpoint methods.

Reference: ADR-0009
"""

from __future__ import annotations

import datetime
import decimal
import json
import uuid
from typing import Any, Protocol, runtime_checkable

__all__ = ["ExtendedJSONRenderer", "JSONRenderer", "Renderer"]


@runtime_checkable
class Renderer(Protocol):
    """Protocol for request body serialisers.

    Implement this to provide a custom encoding format (form, XML, msgpack,
    etc.). The returned bytes are passed directly as the ``content`` argument
    to the HTTP client.
    """

    def render(self, data: Any) -> bytes:
        """Serialise ``data`` to bytes.

        Args:
            data: The Python object to serialise.

        Returns:
            The serialised body as bytes.

        """
        ...  # pragma: no cover


class JSONRenderer:
    """Renders Python objects as UTF-8-encoded JSON bytes.

    Example::

        renderer = JSONRenderer()
        body = renderer.render({"key": "value"})
        # b'{"key": "value"}'
    """

    def render(self, data: Any) -> bytes:
        """Serialise ``data`` to JSON bytes.

        Args:
            data: The Python object to serialise (must be JSON-serialisable).

        Returns:
            UTF-8-encoded JSON bytes.

        """
        return json.dumps(data).encode()


class _ExtendedJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles common stdlib types the built-in encoder cannot.

    Supported types beyond the ``json`` default:

    - ``datetime.datetime``, ``datetime.date``,
      ``datetime.time`` → ISO 8601 string via ``isoformat()``
    - ``decimal.Decimal`` → string (preserves precision, avoids float
      rounding)
    - ``uuid.UUID`` → canonical hyphenated string
    """

    def default(self, o: Any) -> Any:
        """Return default."""
        if isinstance(o, (datetime.datetime, datetime.date, datetime.time)):
            return o.isoformat()
        if isinstance(o, decimal.Decimal):
            return str(o)
        if isinstance(o, uuid.UUID):
            return str(o)
        return super().default(o)


class ExtendedJSONRenderer:
    """JSON renderer with support for common Python stdlib types.

    Extends ``JSONRenderer`` by handling types that the built-in
    ``json`` module cannot serialise: ``datetime.datetime``,
    ``datetime.date``, ``datetime.time``,
    ``decimal.Decimal``, and ``uuid.UUID``.

    Satisfies the ``Renderer`` protocol and can be used as a drop-in
    replacement for ``JSONRenderer`` wherever richer type support is
    needed.

    Example::

        from plynth.http.renderer import ExtendedJSONRenderer

        renderer = ExtendedJSONRenderer()
        body = renderer.render({"amount": Decimal("9.99"), "ts": datetime.now()})
        # b'{"amount": "9.99", "ts": "2026-03-22T14:00:00"}'

    """

    def render(self, data: Any) -> bytes:
        """Serialise ``data`` to UTF-8-encoded JSON bytes.

        Args:
            data: The Python object to serialise.

        Returns:
            UTF-8-encoded JSON bytes.

        """
        return json.dumps(data, cls=_ExtendedJSONEncoder).encode()
