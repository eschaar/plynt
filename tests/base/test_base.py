"""Tests for plynth.base.transport (SyncTransport and AsyncTransport)."""

import json

import pytest

from plynth.base.request import Request
from plynth.base.response import Response
from plynth.base.transport import AsyncTransport, SyncTransport


class FakeSyncTransport(SyncTransport):
    """Minimal concrete sync transport for testing."""

    def send(self, request: Request) -> Response:
        """Return send."""
        return Response(status_code=200, content=b'{"ok": true}')


class FakeAsyncTransport(AsyncTransport):
    """Minimal concrete async transport for testing."""

    async def send(self, request: Request) -> Response:
        """Return send."""
        return Response(status_code=200, content=b'{"ok": true}')


class TestSyncTransport:
    """Test suite for SyncTransport."""

    def test_is_abstract(self) -> None:
        """Validate is abstract."""
        with pytest.raises(TypeError):
            SyncTransport()  # type: ignore[abstract]

    def test_concrete_subclass_is_instantiable(self) -> None:
        """Validate concrete subclass is instantiable."""
        transport = FakeSyncTransport()
        assert isinstance(transport, SyncTransport)

    def test_send_returns_response(self) -> None:
        """Validate send returns response."""
        transport = FakeSyncTransport()
        request = Request(method="GET", url="https://example.com")
        response = transport.send(request)
        assert response.status_code == 200
        assert json.loads(response.content) == {"ok": True}

    def test_subclass_without_send_is_abstract(self) -> None:
        """Validate subclass without send is abstract."""

        class IncompleteTransport(SyncTransport):
            """Represent IncompleteTransport."""

            pass

        with pytest.raises(TypeError):
            IncompleteTransport()  # type: ignore[abstract]


class TestAsyncTransport:
    """Test suite for AsyncTransport."""

    def test_is_abstract(self) -> None:
        """Validate is abstract."""
        with pytest.raises(TypeError):
            AsyncTransport()  # type: ignore[abstract]

    def test_concrete_subclass_is_instantiable(self) -> None:
        """Validate concrete subclass is instantiable."""
        transport = FakeAsyncTransport()
        assert isinstance(transport, AsyncTransport)

    async def test_send_returns_response(self) -> None:
        """Validate send returns response."""
        transport = FakeAsyncTransport()
        request = Request(method="GET", url="https://example.com")
        response = await transport.send(request)
        assert response.status_code == 200
        assert json.loads(response.content) == {"ok": True}

    def test_subclass_without_send_is_abstract(self) -> None:
        """Validate subclass without send is abstract."""

        class IncompleteTransport(AsyncTransport):
            """Represent IncompleteTransport."""

            pass

        with pytest.raises(TypeError):
            IncompleteTransport()  # type: ignore[abstract]
