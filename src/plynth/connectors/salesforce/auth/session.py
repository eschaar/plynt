"""Salesforce session auth middleware."""

from __future__ import annotations

from plynth.http.middleware.auth import (
    AsyncBearerTokenAuthMiddleware,
    BearerTokenAuthMiddleware,
)


class SalesforceSessionAuthMiddleware(BearerTokenAuthMiddleware):
    """Attach an externally managed Salesforce access token to requests.

    Use this middleware when your application lifecycle already handles token
    acquisition and refresh, and only needs Plynth to inject the bearer token
    and route calls to the right Salesforce ``instance_url``.
    """

    def __init__(self, *, access_token: str, instance_url: str) -> None:
        """Initialize SalesforceSessionAuthMiddleware."""
        super().__init__(access_token)
        self._instance_url = instance_url.rstrip("/")

    @property
    def instance_url(self) -> str:
        """Return the Salesforce instance URL for the current session token."""
        return self._instance_url


class AsyncSalesforceSessionAuthMiddleware(AsyncBearerTokenAuthMiddleware):
    """Async middleware for externally managed Salesforce session tokens."""

    def __init__(self, *, access_token: str, instance_url: str) -> None:
        """Initialize AsyncSalesforceSessionAuthMiddleware."""
        super().__init__(access_token)
        self._instance_url = instance_url.rstrip("/")

    async def get_instance_url(self) -> str:
        """Return the Salesforce instance URL for the current session token."""
        return self._instance_url
