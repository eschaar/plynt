"""Shared Salesforce auth middleware mixins."""

from __future__ import annotations

import time
from typing import Any


# pylint: disable=too-few-public-methods
class _SalesforceInstanceUrlSyncMixin:
    """Shared Salesforce ``instance_url`` behavior for sync OAuth2 middlewares."""

    _lock: Any
    _cache: Any
    _cache_key: str
    _fetch: Any

    def __init__(self, **kwargs: Any) -> None:
        """Initialize _SalesforceInstanceUrlSyncMixin."""
        super().__init__(**kwargs)
        self._instance_url: str | None = None

    @property
    def instance_url(self) -> str:
        """Return the Salesforce instance URL, fetching a token first if needed.

        Triggers a token fetch (and caches the result) if no valid token is
        cached. Thread-safe: shares the parent's lock.

        Returns:
            The org-specific Salesforce host (e.g.
            ``"https://myorg.my.salesforce.com"``).

        Raises:
            RuntimeError: If the token endpoint response did not include an
                ``instance_url`` field.

        """
        with self._lock:
            entry = self._cache.get(self._cache_key)
            if entry is None or time.monotonic() >= entry[1]:
                self._fetch()
            if self._instance_url is None:  # pragma: no cover
                raise RuntimeError(
                    "Token fetched but 'instance_url' was not set. "
                    "Check that _on_response ran successfully."
                )
        return self._instance_url

    def _extract_instance_url(self, data: dict[str, Any]) -> str:
        """Return ``instance_url`` from the token response, raising if absent."""
        instance_url = data.get("instance_url")
        if not isinstance(instance_url, str) or not instance_url:
            raise RuntimeError(
                "Salesforce token response did not include 'instance_url'. "
                "Ensure the connected app/token endpoint returns this field."
            )
        return instance_url


# pylint: disable=too-few-public-methods
class _SalesforceInstanceUrlAsyncMixin:
    """Shared Salesforce ``instance_url`` behavior for async OAuth2 middlewares."""

    _lock: Any
    _cache: Any
    _cache_key: str
    _fetch: Any

    def __init__(self, **kwargs: Any) -> None:
        """Initialize _SalesforceInstanceUrlAsyncMixin."""
        super().__init__(**kwargs)
        self._instance_url: str | None = None

    async def get_instance_url(self) -> str:
        """Return the Salesforce instance URL, fetching a token first if needed.

        Triggers a token fetch (and caches the result) if no valid token is
        cached. Concurrency-safe: shares the parent's asyncio lock.

        Returns:
            The org-specific Salesforce host (e.g.
            ``"https://myorg.my.salesforce.com"``).

        Raises:
            RuntimeError: If the token endpoint response did not include an
                ``instance_url`` field.

        """
        async with self._lock:
            entry = self._cache.get(self._cache_key)
            if entry is None or time.monotonic() >= entry[1]:
                await self._fetch()
            if self._instance_url is None:  # pragma: no cover
                raise RuntimeError(
                    "Token fetched but 'instance_url' was not set. "
                    "Check that _on_response ran successfully."
                )
        return self._instance_url

    def _extract_instance_url(self, data: dict[str, Any]) -> str:
        """Return ``instance_url`` from the token response, raising if absent."""
        instance_url = data.get("instance_url")
        if not isinstance(instance_url, str) or not instance_url:
            raise RuntimeError(
                "Salesforce token response did not include 'instance_url'. "
                "Ensure the connected app/token endpoint returns this field."
            )
        return instance_url
