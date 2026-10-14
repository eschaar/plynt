"""Salesforce JWT bearer auth middleware."""

from __future__ import annotations

import time
from typing import Any, cast
from urllib.parse import urlsplit

# The ``salesforce`` extra declares PyJWT as a required dependency.
import jwt as pyjwt

from plynt.connectors.salesforce.auth.mixins import (
    _SalesforceInstanceUrlAsyncMixin,
    _SalesforceInstanceUrlSyncMixin,
)
from plynt.http.middleware.auth import (
    AsyncOAuth2JWTBearerMiddleware,
    OAuth2JWTBearerMiddleware,
)

_JWT_MAX_EXP_SECONDS = 300  # Salesforce hard limit


def _build_jwt_assertion(
    client_id: str,
    username: str,
    audience: str,
    private_key: str | bytes,
    exp_seconds: int,
) -> str:
    """Return a signed RS256 JWT assertion for the Salesforce JWT Bearer flow."""
    payload = {
        "iss": client_id,
        "sub": username,
        "aud": audience,
        "exp": int(time.time()) + exp_seconds,
    }
    token = cast(Any, pyjwt.encode(payload, private_key, algorithm="RS256"))
    if isinstance(token, str):
        return token
    if isinstance(token, bytes):
        return token.decode("utf-8")
    raise TypeError("PyJWT encode returned an unexpected token type")


def _audience_from_token_url(token_url: str) -> str:
    """Return the scheme + host of ``token_url`` for use as JWT ``aud``."""
    parts = urlsplit(token_url)
    return f"{parts.scheme}://{parts.netloc}"


class SalesforceJWTBearerAuthMiddleware(
    _SalesforceInstanceUrlSyncMixin,
    OAuth2JWTBearerMiddleware,
):
    """Salesforce OAuth2 JWT Bearer auth middleware (sync).

    Authenticates using a signed JWT assertion (RS256) instead of a shared
    secret. The JWT is built fresh on each token fetch and signed with the
    caller-supplied RSA private key. Salesforce verifies the signature
    against a certificate registered in the connected app or external client
    app.

    This is the recommended flow for server-to-server integrations. It is
    mandatory for orgs created Summer '23 or later where the
    Username-Password flow is blocked by default.

    All token lifecycle concerns (caching, lock, 401 invalidate-retry) are
    inherited from ``OAuth2AuthMiddlewareBase``. The Salesforce
    ``instance_url`` is extracted and cached alongside the access token via
    ``_SalesforceInstanceUrlSyncMixin``.

    Sandbox support: point ``token_url`` at
    ``https://test.salesforce.com/services/oauth2/token``; the JWT ``aud``
    is derived automatically from the host in ``token_url``.

    Args:
        client_id: Consumer key of the connected app or external client app.
        username: Salesforce username to authenticate as (must be
            pre-authorised in the connected app).
        private_key: RSA private key as a PEM-encoded string or bytes.
            Keep this value secret — load it from an environment variable
            or a secret manager, never hard-code it.
        token_url: Full URL of the Salesforce token endpoint, e.g.
            ``"https://login.salesforce.com/services/oauth2/token"``.
        jwt_exp_seconds: Lifetime of each JWT assertion in seconds.
            Default: 180. Must be between 1 and 300 (Salesforce hard limit).
        token_retry_policy: Optional retry policy for the token endpoint.
        ttl_leeway: Seconds subtracted from ``expires_in`` for early token
            refresh (default: 30).
        token_cache: Optional ``CacheBackend`` for token storage.

    Example::

        from plynt.http.transport import HttpxSyncTransport
        from plynt.connectors.salesforce.auth import SalesforceJWTBearerAuthMiddleware
        from plynt.connectors.salesforce.client import SalesforceAPIClient

        private_key = open("private_key.pem").read()

        auth = SalesforceJWTBearerAuthMiddleware(
            client_id="3MVG9...",
            username="integration@myorg.com",
            private_key=private_key,
            token_url="https://login.salesforce.com/services/oauth2/token",
        )
        transport = HttpxSyncTransport(middlewares=[auth])
        client = SalesforceAPIClient(auth=auth, transport=transport)

    """

    def __init__(
        self,
        *,
        client_id: str,
        username: str,
        private_key: str | bytes,
        token_url: str,
        jwt_exp_seconds: int = 180,
        **kwargs: Any,
    ) -> None:
        """Initialize SalesforceJWTBearerAuthMiddleware."""
        if not 1 <= jwt_exp_seconds <= _JWT_MAX_EXP_SECONDS:
            raise ValueError(
                f"jwt_exp_seconds must be between 1 and {_JWT_MAX_EXP_SECONDS}, "
                f"got {jwt_exp_seconds}."
            )
        self._client_id = client_id
        self._username = username
        self._private_key = private_key
        self._jwt_exp_seconds = jwt_exp_seconds
        self._audience = _audience_from_token_url(token_url)
        super().__init__(
            token_url=token_url,
            cache_key_material=f"{token_url}:{client_id}:{username}",
            assertion_factory=lambda: _build_jwt_assertion(
                client_id=self._client_id,
                username=self._username,
                audience=self._audience,
                private_key=self._private_key,
                exp_seconds=self._jwt_exp_seconds,
            ),
            **kwargs,
        )

    def _on_response(self, data: dict[str, Any]) -> None:
        """Extract and cache instance_url alongside the access token."""
        instance_url = self._extract_instance_url(data)
        super()._on_response(data)
        self._instance_url = instance_url


class AsyncSalesforceJWTBearerAuthMiddleware(
    _SalesforceInstanceUrlAsyncMixin,
    AsyncOAuth2JWTBearerMiddleware,
):
    """Salesforce OAuth2 JWT Bearer auth middleware (async).

    Async counterpart of ``SalesforceJWTBearerAuthMiddleware``. Uses
    ``asyncio.Lock`` and ``HttpxAsyncTransport`` internally so the token
    endpoint request never blocks the event loop.

    See ``SalesforceJWTBearerAuthMiddleware`` for full documentation on
    parameters and usage.

    Args:
        client_id: Consumer key of the connected app or external client app.
        username: Salesforce username to authenticate as.
        private_key: RSA private key as a PEM-encoded string or bytes.
        token_url: Full URL of the Salesforce token endpoint.
        jwt_exp_seconds: Lifetime of each JWT assertion in seconds
            (default: 180; max: 300).
        token_retry_policy: Optional retry policy for the token endpoint.
        ttl_leeway: Seconds subtracted from ``expires_in`` for early refresh.
        token_cache: Optional ``CacheBackend`` for token storage.

    """

    def __init__(
        self,
        *,
        client_id: str,
        username: str,
        private_key: str | bytes,
        token_url: str,
        jwt_exp_seconds: int = 180,
        **kwargs: Any,
    ) -> None:
        """Initialize AsyncSalesforceJWTBearerAuthMiddleware."""
        if not 1 <= jwt_exp_seconds <= _JWT_MAX_EXP_SECONDS:
            raise ValueError(
                f"jwt_exp_seconds must be between 1 and {_JWT_MAX_EXP_SECONDS}, "
                f"got {jwt_exp_seconds}."
            )
        self._client_id = client_id
        self._username = username
        self._private_key = private_key
        self._jwt_exp_seconds = jwt_exp_seconds
        self._audience = _audience_from_token_url(token_url)
        super().__init__(
            token_url=token_url,
            cache_key_material=f"{token_url}:{client_id}:{username}",
            assertion_factory=lambda: _build_jwt_assertion(
                client_id=self._client_id,
                username=self._username,
                audience=self._audience,
                private_key=self._private_key,
                exp_seconds=self._jwt_exp_seconds,
            ),
            **kwargs,
        )

    def _on_response(self, data: dict[str, Any]) -> None:
        """Extract and cache instance_url alongside the access token."""
        instance_url = self._extract_instance_url(data)
        super()._on_response(data)
        self._instance_url = instance_url
