"""Focused tests for Salesforce CDC auth metadata resolution."""

from __future__ import annotations

import pytest

from plynth.connectors.salesforce.cdc.auth import AsyncSalesforceCDCAuthMetadataProvider


class _FakeAsyncOAuthAuth:
    """Small async auth double exposing the OAuth token-header contract."""

    async def _get_token_header(self) -> dict[str, str]:
        return {"Authorization": "Bearer token-123"}

    async def get_instance_url(self) -> str:
        return "https://example.my.salesforce.com/"


class _FakeAsyncSessionAuth:
    """Small async session-auth double exposing token and instance URL."""

    def __init__(self) -> None:
        self._token = "token-456"

    async def get_instance_url(self) -> str:
        return "https://session.my.salesforce.com"


class TestAsyncSalesforceCDCAuthMetadataProvider:
    """Verify auth middleware adaptation to CDC metadata."""

    @pytest.mark.asyncio
    async def test_resolves_from_async_oauth_auth_and_static_tenant_id(self) -> None:
        """Build CDC metadata from OAuth-style auth middleware."""
        provider = AsyncSalesforceCDCAuthMetadataProvider(
            _FakeAsyncOAuthAuth(),
            tenant_id="00Dxx0000000001",
        )

        metadata = await provider()

        assert metadata.access_token == "token-123"
        assert metadata.instance_url == "https://example.my.salesforce.com"
        assert metadata.tenant_id == "00Dxx0000000001"

    @pytest.mark.asyncio
    async def test_resolves_from_async_session_auth_and_tenant_provider(self) -> None:
        """Build CDC metadata from session-style auth middleware."""

        async def _tenant_id_provider() -> str:
            return "00Dxx0000000002"

        provider = AsyncSalesforceCDCAuthMetadataProvider(
            _FakeAsyncSessionAuth(),
            tenant_id_provider=_tenant_id_provider,
        )

        metadata = await provider()

        assert metadata.access_token == "token-456"
        assert metadata.instance_url == "https://session.my.salesforce.com"
        assert metadata.tenant_id == "00Dxx0000000002"

    @pytest.mark.asyncio
    async def test_fails_clearly_when_access_token_is_unavailable(self) -> None:
        """Raise a clear error when the auth object cannot yield a token."""

        class _BadAuth:
            async def get_instance_url(self) -> str:
                return "https://example.my.salesforce.com"

        provider = AsyncSalesforceCDCAuthMetadataProvider(
            _BadAuth(),
            tenant_id="00Dxx0000000001",
        )

        with pytest.raises(RuntimeError, match="resolve an access token"):
            await provider()

    @pytest.mark.asyncio
    async def test_fails_clearly_when_tenant_id_is_unavailable(self) -> None:
        """Raise a clear error when no tenant ID source is configured."""
        provider = AsyncSalesforceCDCAuthMetadataProvider(_FakeAsyncOAuthAuth())

        with pytest.raises(RuntimeError, match="requires a tenant ID or provider"):
            await provider()
