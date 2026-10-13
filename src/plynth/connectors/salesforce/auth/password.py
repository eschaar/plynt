"""Salesforce password auth middleware."""

from __future__ import annotations

from typing import Any

from plynth.connectors.salesforce.auth.mixins import (
    _SalesforceInstanceUrlAsyncMixin,
    _SalesforceInstanceUrlSyncMixin,
)
from plynth.http.middleware.auth import (
    AsyncOAuth2PasswordMiddleware,
    OAuth2PasswordMiddleware,
)


class SalesforcePasswordAuthMiddleware(
    _SalesforceInstanceUrlSyncMixin,
    OAuth2PasswordMiddleware,
):
    """Salesforce OAuth2 Password middleware with cached ``instance_url``.

    Use this middleware for the OAuth2 Resource Owner Password Credentials
    flow. The middleware captures and caches ``instance_url`` alongside the
    access token, so ``SalesforceAPIClient`` can always target the current
    org-specific host.

    When a ``security_token`` is provided it is automatically appended to
    the password before the token request — matching Salesforce's requirement
    for orgs without IP allowlisting.

    Args:
        security_token: Optional Salesforce security token. When supplied,
            it is appended to ``password`` before the token request. Leave
            empty for orgs with IP allowlisting.

    """

    def __init__(
        self,
        *,
        password: str,
        security_token: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize SalesforcePasswordAuthMiddleware."""
        super().__init__(password=password + security_token, **kwargs)

    def _on_response(self, data: dict[str, Any]) -> None:
        """Extract and cache instance_url alongside the access token."""
        instance_url = self._extract_instance_url(data)
        super()._on_response(data)
        self._instance_url = instance_url


class AsyncSalesforcePasswordAuthMiddleware(
    _SalesforceInstanceUrlAsyncMixin,
    AsyncOAuth2PasswordMiddleware,
):
    """Async Salesforce OAuth2 Password middleware with cached ``instance_url``.

    Async counterpart of ``SalesforcePasswordAuthMiddleware``. Accepts the
    same ``security_token`` argument — when provided it is concatenated with
    *password* before the token request.

    Args:
        security_token: Optional Salesforce security token. When supplied,
            it is appended to ``password`` before the token request. Leave
            empty for orgs with IP allowlisting.

    """

    def __init__(
        self,
        *,
        password: str,
        security_token: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize AsyncSalesforcePasswordAuthMiddleware."""
        super().__init__(password=password + security_token, **kwargs)

    def _on_response(self, data: dict[str, Any]) -> None:
        """Extract and cache instance_url alongside the access token."""
        instance_url = self._extract_instance_url(data)
        super()._on_response(data)
        self._instance_url = instance_url
