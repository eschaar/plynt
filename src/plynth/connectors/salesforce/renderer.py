"""Request body renderer for the Salesforce Platform REST API.

Provides ``SalesforceRenderer``, which serialises Python objects to UTF-8
JSON bytes suitable for Salesforce REST API request bodies.

Datetime, Decimal, and UUID serialisation is provided by
``plynth.http.renderer.ExtendedJSONRenderer``. This renderer adds only the
Salesforce-specific concern: ``SObjectPayload`` instances are converted via
``to_payload()`` before encoding, which applies ``serialization_alias``
mappings and excludes ``None`` fields.

Reference: ADR-0009 (Renderer protocol)
"""

from __future__ import annotations

import json
from typing import Any

from plynth.connectors.salesforce.models import SObjectPayload
from plynth.http.renderer import _ExtendedJSONEncoder

__all__ = ["SalesforceRenderer"]


class SalesforceRenderer:
    """Renders Salesforce SObject payloads to UTF-8-encoded JSON bytes.

    Accepts either a plain ``dict`` (keys are Salesforce field API names) or
    an ``SObjectPayload`` instance. ``SObjectPayload`` inputs are first
    converted via ``to_payload()``, which applies ``serialization_alias``
    mappings and excludes ``None`` fields.

    Datetime, Decimal, and UUID values are serialised by ``ExtendedJSONEncoder``.

    Satisfies the ``plynth.http.renderer.Renderer`` protocol and can be
    injected in place of ``JSONRenderer`` wherever a ``Renderer`` is expected.

    Example::

        from plynth.connectors.salesforce.renderer import SalesforceRenderer

        renderer = SalesforceRenderer()
        body = renderer.render({"Name": "ACME Corp", "CreatedDate": date.today()})
        # → b'{"Name": "ACME Corp", "CreatedDate": "2026-03-15"}'

    """

    def render(self, data: dict[str, Any] | SObjectPayload) -> bytes:
        """Serialise *data* to UTF-8-encoded JSON bytes.

        Args:
            data: Either a plain dict with Salesforce field API names as keys,
                or an ``SObjectPayload`` instance. ``SObjectPayload`` inputs
                are converted via ``to_payload()`` before encoding.

        """
        payload: dict[str, Any] = (
            data.to_payload() if isinstance(data, SObjectPayload) else data
        )
        return json.dumps(payload, cls=_ExtendedJSONEncoder).encode()
