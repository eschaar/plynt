"""Shared constants and helpers for the Salesforce integration."""

from __future__ import annotations

import re
from collections.abc import Awaitable
from typing import Any

__all__ = [
    "DEFAULT_API_VERSION",
    "SALESFORCE_ID_RE",
    "resolve_async_api_version",
    "resolve_sync_api_version",
]

# Default Salesforce REST API version used when none is specified.
DEFAULT_API_VERSION = "59.0"

# Salesforce record IDs are always alphanumeric, exactly 15 (case-sensitive)
# or 18 characters (case-insensitive, with a 3-character checksum suffix).
SALESFORCE_ID_RE = re.compile(r"^[a-zA-Z0-9]{15}(?:[a-zA-Z0-9]{3})?$")


def resolve_sync_api_version(client: Any, api_version: str | None) -> str:
    """Resolve the Salesforce API version for sync services.

    Resolution order:
    1. Explicit ``api_version`` argument when provided.
    2. ``client.api_version`` when available and non-empty.
    3. ``DEFAULT_API_VERSION``.

    """
    if api_version:
        return api_version
    client_version = getattr(client, "api_version", None)
    if isinstance(client_version, str) and client_version:
        return client_version
    return DEFAULT_API_VERSION


async def resolve_async_api_version(client: Any, api_version: str | None) -> str:
    """Resolve the Salesforce API version for async services.

    Resolution order:
    1. Explicit ``api_version`` argument when provided.
    2. ``await client.get_api_version()`` when available.
    3. ``client.api_version`` when available and non-empty.
    4. ``DEFAULT_API_VERSION``.

    """
    if api_version:
        return api_version

    getter = getattr(client, "get_api_version", None)
    if callable(getter):
        maybe_version = getter()
        if isinstance(maybe_version, Awaitable):
            resolved = await maybe_version
            if isinstance(resolved, str) and resolved:
                return resolved

    client_version = getattr(client, "api_version", None)
    if isinstance(client_version, str) and client_version:
        return client_version
    return DEFAULT_API_VERSION
