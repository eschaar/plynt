"""Tests for Salesforce connector constants and version resolver helpers."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any

from plynt.connectors.salesforce.constants import (
    DEFAULT_API_VERSION,
    resolve_async_api_version,
    resolve_sync_api_version,
)


class _SyncClient:
    """Minimal sync client stub exposing api_version."""

    def __init__(self, api_version: Any) -> None:
        self.api_version = api_version


class _AsyncClient:
    """Minimal async client stub for async version resolution tests."""

    def __init__(
        self,
        *,
        getter_return: Awaitable[str] | str | None = None,
        api_version: Any = None,
    ) -> None:
        self.api_version = api_version
        self._getter_return = getter_return

    def get_api_version(self) -> Awaitable[str] | str | None:
        """Return a configured value used by resolve_async_api_version tests."""
        return self._getter_return


class TestResolveSyncApiVersion:
    """Validate sync API version resolution order."""

    def test_uses_explicit_argument_first(self) -> None:
        """Validate explicit api_version takes precedence."""
        client = _SyncClient(api_version="58.0")

        resolved = resolve_sync_api_version(client, "60.0")

        assert resolved == "60.0"

    def test_uses_client_api_version_when_explicit_not_set(self) -> None:
        """Validate client.api_version is used when explicit value is absent."""
        client = _SyncClient(api_version="58.0")

        resolved = resolve_sync_api_version(client, None)

        assert resolved == "58.0"

    def test_falls_back_to_default_version(self) -> None:
        """Validate fallback to default when no usable version exists."""
        client = _SyncClient(api_version="")

        resolved = resolve_sync_api_version(client, None)

        assert resolved == DEFAULT_API_VERSION


class TestResolveAsyncApiVersion:
    """Validate async API version resolution order."""

    async def test_uses_explicit_argument_first(self) -> None:
        """Validate explicit api_version takes precedence over client values."""
        client = _AsyncClient(getter_return="63.0", api_version="62.0")

        resolved = await resolve_async_api_version(client, "64.0")

        assert resolved == "64.0"

    async def test_uses_async_getter_when_available(self) -> None:
        """Validate awaited get_api_version result is preferred when non-empty."""

        async def _version() -> str:
            return "63.0"

        client = _AsyncClient(getter_return=_version(), api_version="62.0")

        resolved = await resolve_async_api_version(client, None)

        assert resolved == "63.0"

    async def test_falls_back_to_client_api_version_when_getter_not_usable(
        self,
    ) -> None:
        """Validate fallback to client.api_version when getter returns non-awaitable."""
        client = _AsyncClient(getter_return="not-awaitable", api_version="62.0")

        resolved = await resolve_async_api_version(client, None)

        assert resolved == "62.0"

    async def test_falls_back_to_default_when_no_sources_available(self) -> None:
        """Validate final fallback to default when no version source is usable."""
        client = _AsyncClient(getter_return=None, api_version="")

        resolved = await resolve_async_api_version(client, None)

        assert resolved == DEFAULT_API_VERSION
