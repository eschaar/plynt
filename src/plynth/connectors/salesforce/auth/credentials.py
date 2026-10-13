"""Salesforce client credentials auth middleware."""

from __future__ import annotations

from typing import Any

from plynth.connectors.salesforce.auth.mixins import (
    _SalesforceInstanceUrlAsyncMixin,
    _SalesforceInstanceUrlSyncMixin,
)
from plynth.http.middleware.auth import (
    AsyncOAuth2ClientCredentialsMiddleware,
    OAuth2ClientCredentialsMiddleware,
)


class SalesforceClientCredentialsAuthMiddleware(
    _SalesforceInstanceUrlSyncMixin,
    OAuth2ClientCredentialsMiddleware,
):
    """OAuth2 auth middleware for the Salesforce Platform API.

    Extends ``OAuth2AuthMiddleware`` to extract and cache the
    ``instance_url`` field from the Salesforce token response. The instance
    URL identifies the org-specific Salesforce host (e.g.
    ``"https://myorg.my.salesforce.com"``) and is required as the base URL
    for all REST API calls.

    ``instance_url`` and the access token share the same expiry and lock, so
    both are always in sync. Calling ``_invalidate()`` causes both to be
    re-fetched on the next request.
    """

    def _on_response(self, data: dict[str, Any]) -> None:
        """Extract and cache instance_url alongside the access token."""
        instance_url = self._extract_instance_url(data)
        super()._on_response(data)
        self._instance_url = instance_url


class AsyncSalesforceClientCredentialsAuthMiddleware(
    _SalesforceInstanceUrlAsyncMixin,
    AsyncOAuth2ClientCredentialsMiddleware,
):
    """Async OAuth2 auth middleware for the Salesforce Platform API.

    Async counterpart of ``SalesforceClientCredentialsAuthMiddleware``. Uses
    ``asyncio.Lock`` and ``HttpxAsyncTransport`` internally so the token
    endpoint is never called on a blocking thread.

    Extends ``AsyncOAuth2ClientCredentialsMiddleware`` to extract and cache
    the ``instance_url`` field from the Salesforce token response alongside
    the access token. Both are invalidated together on token expiry or a 401.
    """

    def _on_response(self, data: dict[str, Any]) -> None:
        """Extract and cache instance_url alongside the access token."""
        instance_url = self._extract_instance_url(data)
        super()._on_response(data)
        self._instance_url = instance_url
