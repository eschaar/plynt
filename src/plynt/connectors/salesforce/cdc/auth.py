"""Auth metadata resolution helpers for Salesforce CDC."""

from __future__ import annotations

from inspect import isawaitable
from typing import Any

from plynt.connectors.salesforce.cdc.models import SalesforceCDCAuthMetadata

__all__ = ["AsyncSalesforceCDCAuthMetadataProvider"]


# pylint: disable=too-few-public-methods
class AsyncSalesforceCDCAuthMetadataProvider:
    """Adapt existing async Salesforce auth middleware to CDC metadata."""

    def __init__(
        self,
        auth: Any,
        *,
        tenant_id: str | None = None,
        tenant_id_provider: Any | None = None,
    ) -> None:
        """Initialize provider dependencies.

        Args:
            auth: Async Salesforce auth middleware or session auth object.
            tenant_id: Static tenant ID to include in Pub/Sub metadata.
            tenant_id_provider: Optional async or sync callable returning the
                Salesforce org or tenant identifier.

        """
        self._auth = auth
        self._tenant_id = tenant_id
        self._tenant_id_provider = tenant_id_provider

    async def __call__(self) -> SalesforceCDCAuthMetadata:
        """Resolve access token, instance URL, and tenant ID for CDC calls."""
        return SalesforceCDCAuthMetadata(
            access_token=await self._resolve_access_token(),
            instance_url=await self._resolve_instance_url(),
            tenant_id=await self._resolve_tenant_id(),
        )

    async def _resolve_access_token(self) -> str:
        """Resolve the current bearer token from the auth middleware."""
        token = getattr(self._auth, "_token", None)
        if isinstance(token, str) and token:
            return token

        get_token_header = getattr(self._auth, "_get_token_header", None)
        if callable(get_token_header):
            header = get_token_header()
            if isawaitable(header):
                header = await header
            if isinstance(header, dict):
                authorization = header.get("Authorization")
                if isinstance(authorization, str) and authorization.startswith(
                    "Bearer "
                ):
                    return authorization.removeprefix("Bearer ")

        raise RuntimeError(
            "Salesforce CDC auth metadata provider could not resolve an access token"
        )

    async def _resolve_instance_url(self) -> str:
        """Resolve the Salesforce instance URL from the auth middleware."""
        get_instance_url = getattr(self._auth, "get_instance_url", None)
        if callable(get_instance_url):
            value = get_instance_url()
            if isawaitable(value):
                value = await value
            if isinstance(value, str) and value:
                return value.rstrip("/")

        instance_url = getattr(self._auth, "instance_url", None)
        if isinstance(instance_url, str) and instance_url:
            return instance_url.rstrip("/")

        raise RuntimeError(
            "Salesforce CDC auth metadata provider could not resolve an instance URL"
        )

    async def _resolve_tenant_id(self) -> str:
        """Resolve the Salesforce tenant ID from explicit config or a provider."""
        if isinstance(self._tenant_id, str) and self._tenant_id:
            return self._tenant_id

        tenant_id_provider = self._tenant_id_provider
        if callable(tenant_id_provider):
            value = tenant_id_provider()
            if isawaitable(value):
                value = await value
            if isinstance(value, str) and value:
                return value

        raise RuntimeError(
            "Salesforce CDC auth metadata provider requires a tenant ID or provider"
        )
