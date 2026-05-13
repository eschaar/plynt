"""Shared test fixtures and mock helpers for the plynth test suite."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from plynth.base.response import Response
from plynth.base.transport import AsyncTransport, SyncTransport
from plynth.http.client import APIClient, AsyncAPIClient, AsyncHTTPClient, HTTPClient
from plynth.testsupport.vcr import (
    StateTrackingMode,
    StateTrackingSettings,
    VCRMode,
    VCRSettings,
    build_cassette_path,
)

# ---------------------------------------------------------------------------
# Mock transports
# ---------------------------------------------------------------------------


class MockSyncTransport(SyncTransport):
    """Sync transport stub backed by a ``MagicMock``.

    Args:
        status_code: Status code the mock will return. Defaults to 200.
        content: Response body the mock will return. Defaults to ``b""``.
    """

    send: MagicMock = None  # type: ignore[assignment]

    def __init__(self, status_code: int = 200, content: bytes = b"") -> None:
        """Initialize MockSyncTransport."""
        self.send = MagicMock(
            return_value=Response(status_code=status_code, content=content)
        )


class MockAsyncTransport(AsyncTransport):
    """Async transport stub backed by an ``AsyncMock``.

    Args:
        status_code: Status code the mock will return. Defaults to 200.
        content: Response body the mock will return. Defaults to ``b""``.
    """

    send: AsyncMock = None  # type: ignore[assignment]

    def __init__(self, status_code: int = 200, content: bytes = b"") -> None:
        """Initialize MockAsyncTransport."""
        self.send = AsyncMock(
            return_value=Response(status_code=status_code, content=content)
        )


# ---------------------------------------------------------------------------
# Client fixtures
# ---------------------------------------------------------------------------

BASE_URL = "https://api.example.com"


@pytest.fixture
def vcr_cassette_path(request: pytest.FixtureRequest) -> Path:
    """Global default deterministic cassette path.

    Each test gets a deterministic cassette file using a short, normalized
    suite/module/class/test path.
    """
    node_id = request.node.nodeid
    cassette_root = Path(__file__).resolve().parent / "_mock" / "cassettes"
    return build_cassette_path(node_id, cassette_root, extension=".yaml")


@pytest.fixture
def vcr_settings() -> VCRSettings:
    """Global default VCR settings.

    Suites may override this fixture in local ``conftest.py`` files.
    """
    return VCRSettings(
        mode=VCRMode.NONE,
        state_tracking=StateTrackingSettings(mode=StateTrackingMode.RESOURCE),
    )


@pytest.fixture
def sync_transport() -> MockSyncTransport:
    """A default-200 sync transport mock."""
    return MockSyncTransport()


@pytest.fixture
def async_transport() -> MockAsyncTransport:
    """A default-200 async transport mock."""
    return MockAsyncTransport()


@pytest.fixture
def http_client(sync_transport: MockSyncTransport) -> HTTPClient:
    """A default ``HTTPClient`` wired to a 200 sync transport mock."""
    return HTTPClient(base_url=BASE_URL, transport=sync_transport)


@pytest.fixture
def async_http_client(async_transport: MockAsyncTransport) -> AsyncHTTPClient:
    """A default ``AsyncHTTPClient`` wired to a 200 async transport mock."""
    return AsyncHTTPClient(base_url=BASE_URL, transport=async_transport)


@pytest.fixture
def api_client(sync_transport: MockSyncTransport) -> APIClient:
    """A default ``APIClient`` wired to a 200 sync transport mock."""
    return APIClient(base_url=BASE_URL, transport=sync_transport)


@pytest.fixture
def async_api_client(async_transport: MockAsyncTransport) -> AsyncAPIClient:
    """A default ``AsyncAPIClient`` wired to a 200 async transport mock."""
    return AsyncAPIClient(base_url=BASE_URL, transport=async_transport)
