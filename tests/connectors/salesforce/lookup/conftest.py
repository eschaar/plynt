"""Shared test helpers for Salesforce lookup services."""

from __future__ import annotations

from plynth.http.client import APIClient, AsyncAPIClient
from tests.conftest import MockAsyncTransport, MockSyncTransport
from tests.connectors.salesforce.conftest import DUMMY_INSTANCE_URL


def make_sync_client(
    *,
    base_url: str = DUMMY_INSTANCE_URL,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[APIClient, MockSyncTransport]:
    """Create a sync APIClient with a mocked transport."""
    transport = MockSyncTransport(status_code=status_code, content=content)
    return APIClient(base_url=base_url, transport=transport), transport


def make_async_client(
    *,
    base_url: str = DUMMY_INSTANCE_URL,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[AsyncAPIClient, MockAsyncTransport]:
    """Create an async APIClient with a mocked transport."""
    transport = MockAsyncTransport(status_code=status_code, content=content)
    return AsyncAPIClient(base_url=base_url, transport=transport), transport
