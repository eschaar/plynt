"""Shared fixtures for tests/http."""

from __future__ import annotations

import json

import pytest

from plynt.base.request import Request
from plynt.base.response import Response
from plynt.base.transport import AsyncTransport, SyncTransport
from plynt.http.auth import OAuth2ClientCredentialsConfig
from plynt.http.settings import HTTPSettings

__all__: list[str] = ["_OAuthTestSettings"]

# ---------------------------------------------------------------------------
# Dummy OAuth2 settings - used by test_auth.py and test_settings.py.
# ---------------------------------------------------------------------------

DUMMY_CLIENT_ID = "test-client-id"
DUMMY_CLIENT_SECRET = "test-client-secret"
DUMMY_TOKEN_URL = "https://auth.example.test/token"

# Credential constants for bearer and basic auth tests.
DUMMY_BEARER_TOKEN = "test-bearer-token"
DUMMY_BASIC_USERNAME = "test-basic-user"
DUMMY_BASIC_PASSWORD = "test-basic-pass"

# Token value returned by the fake token endpoint.
DUMMY_ACCESS_TOKEN = "dummy-access-token"


class _OAuthTestSettings(HTTPSettings):
    """Settings subclass exposing OAuth2 credential fields (for middleware tests).

    Declares ``client_id``, ``client_secret``, and ``token_url`` as
    pydantic fields so middleware tests can access them by attribute.
    """

    client_id: str = DUMMY_CLIENT_ID
    client_secret: str = DUMMY_CLIENT_SECRET
    token_url: str = DUMMY_TOKEN_URL

    @property
    def auth(self) -> OAuth2ClientCredentialsConfig:
        """Return auth."""
        return OAuth2ClientCredentialsConfig(
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_url=self.token_url,
        )


class _FakeTokenTransport(SyncTransport):
    """Simulates an OAuth2 token endpoint with a configurable response."""

    def __init__(
        self,
        token: str = DUMMY_ACCESS_TOKEN,
        expires_in: int = 3600,
        status: int = 200,
    ) -> None:
        """Initialize _FakeTokenTransport."""
        self._body = json.dumps(
            {"access_token": token, "expires_in": expires_in}
        ).encode()
        self._status = status
        self.calls: int = 0

    def send(self, request: Request) -> Response:
        """Return send."""
        self.calls += 1
        return Response(status_code=self._status, content=self._body)


class _FakeAsyncTokenTransport(AsyncTransport):
    """Simulates an async OAuth2 token endpoint with a configurable response."""

    def __init__(
        self,
        token: str = DUMMY_ACCESS_TOKEN,
        expires_in: int = 3600,
        status: int = 200,
    ) -> None:
        """Initialize _FakeAsyncTokenTransport."""
        self._body = json.dumps(
            {"access_token": token, "expires_in": expires_in}
        ).encode()
        self._status = status
        self.calls: int = 0

    async def send(self, request: Request) -> Response:
        """Return send."""
        self.calls += 1
        return Response(status_code=self._status, content=self._body)


@pytest.fixture()
def oauth_settings() -> _OAuthTestSettings:
    """Return settings with dummy OAuth2 credentials (used by middleware tests).

    Exposes ``client_id``, ``client_secret``, and ``token_url`` as
    pydantic fields so tests can access them as attributes when
    constructing middleware directly.
    """
    return _OAuthTestSettings()


@pytest.fixture()
def token_transport() -> _FakeTokenTransport:
    """Fake token endpoint that returns ``DUMMY_ACCESS_TOKEN``."""
    return _FakeTokenTransport()


@pytest.fixture()
def async_token_transport() -> _FakeAsyncTokenTransport:
    """Fake async token endpoint that returns ``DUMMY_ACCESS_TOKEN``."""
    return _FakeAsyncTokenTransport()
