"""Runtime smoke tests for FastAPI adapter lifecycle and DI wiring."""

# pyright: reportUntypedFunctionDecorator=false

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

pytest.importorskip("fastapi")

from plynth.adapters.fastapi import (
    PlynthLifespan,
    get_client,
    get_transport,
)
from plynth.base.request import Request
from plynth.base.response import Response
from plynth.base.transport import AsyncTransport

fastapi = __import__("fastapi")
fastapi_testclient = __import__("fastapi.testclient", fromlist=["TestClient"])

FastAPI = fastapi.FastAPI
Depends = fastapi.Depends
TestClient = fastapi_testclient.TestClient


class _FakeAsyncTransport(AsyncTransport):
    """Minimal async transport test double with close tracking."""

    def __init__(self) -> None:
        self.closed = False

    async def send(self, request: Request) -> Response:
        del request
        return Response(status_code=200, headers={}, content=b"{}")

    async def aclose(self) -> None:
        self.closed = True


class _DemoClient:
    """Simple client wrapper used to validate dependency construction."""

    def __init__(self, *, transport: object, service_name: str) -> None:
        self.transport = transport
        self.service_name = service_name


class _FakeSyncTransport:
    """Minimal sync transport test double with close tracking."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _AwaitableCloseTransport:
    """Sync-like transport whose ``close()`` returns an awaitable."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> object:
        async def _finish() -> None:
            self.closed = True

        return _finish()


class TestFastAPILifespan:
    """Validate transport lifecycle semantics for FastAPI adapter."""

    def test_lifespan_registers_transport_and_closes_on_shutdown(self) -> None:
        """Expose one named transport in route and close it at shutdown."""
        transport = _FakeAsyncTransport()

        app = FastAPI(
            lifespan=PlynthLifespan({"salesforce": lambda: transport}),
        )

        @app.get("/probe")  # type: ignore
        async def probe(
            bound_transport: object = Depends(get_transport("salesforce")),
        ) -> dict[str, bool]:
            return {"bound": bound_transport is transport}

        with TestClient(app) as client:
            response = client.get("/probe")
            assert response.status_code == 200
            assert response.json() == {"bound": True}

        assert transport.closed is True

    def test_get_client_dependency_builds_client_with_transport(self) -> None:
        """Build one client instance from request-scoped dependency."""
        transport = _FakeAsyncTransport()

        app = FastAPI(
            lifespan=PlynthLifespan({"salesforce": lambda: transport}),
        )
        client_dependency = Depends(
            get_client("salesforce", _DemoClient, service_name="svc")
        )

        @app.get("/client")  # type: ignore
        async def probe_client(
            client: _DemoClient = client_dependency,
        ) -> dict[str, bool | str]:
            return {
                "transport_bound": client.transport is transport,
                "name": client.service_name,
            }

        with TestClient(app) as test_client:
            response = test_client.get("/client")
            assert response.status_code == 200
            assert response.json() == {
                "transport_bound": True,
                "name": "svc",
            }

    def test_missing_transport_returns_server_error(self) -> None:
        """Return a runtime error when dependency requests unknown transport."""
        app = FastAPI(
            lifespan=PlynthLifespan({"salesforce": _FakeAsyncTransport}),
        )

        @app.get("/missing")  # type: ignore
        async def missing(
            _: object = Depends(get_transport("servicenow")),
        ) -> dict[str, str]:
            return {"ok": "never"}

        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.get("/missing")
            assert response.status_code == 500

    def test_startup_failure_closes_created_transports(self) -> None:
        """Close already-created transports when one startup factory fails."""
        transport = _FakeAsyncTransport()

        def _raise() -> object:
            raise RuntimeError("boom")

        factories: dict[str, Callable[[], object]] = {
            "salesforce": lambda: transport,
            "broken": _raise,
        }

        app = FastAPI(lifespan=PlynthLifespan(factories))

        with pytest.raises(RuntimeError, match="boom"):
            with TestClient(app):
                pass

        assert transport.closed is True

    def test_lifespan_closes_sync_transport_when_present(self) -> None:
        """Close sync transport objects that expose ``close()``."""
        transport = _FakeSyncTransport()

        app = FastAPI(
            lifespan=PlynthLifespan({"salesforce": lambda: transport}),
        )

        @app.get("/probe")  # type: ignore
        async def probe(
            _: object = Depends(get_transport("salesforce")),
        ) -> dict[str, bool]:
            return {"ok": True}

        with TestClient(app) as client:
            response = client.get("/probe")
            assert response.status_code == 200
            assert response.json() == {"ok": True}

        assert transport.closed is True

    def test_lifespan_rejects_empty_transport_mapping(self) -> None:
        """Raise for empty transport factory mapping."""
        with pytest.raises(ValueError, match="must not be empty"):
            PlynthLifespan({})

    def test_lifespan_requires_app_state(self) -> None:
        """Raise when app object does not expose state."""
        lifespan = PlynthLifespan({"salesforce": _FakeAsyncTransport})

        async def _run() -> None:
            async with lifespan(object()):
                pass

        with pytest.raises(RuntimeError, match=r"must expose \.state"):
            asyncio.run(_run())

    def test_dependency_fails_when_transports_not_initialized(self) -> None:
        """Return server error when dependency runs without lifespan setup."""
        app = FastAPI()

        @app.get("/probe")  # type: ignore
        async def probe(
            _: object = Depends(get_transport("salesforce")),
        ) -> dict[str, bool]:
            return {"ok": True}

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/probe")

        assert response.status_code == 500

    def test_lifespan_resolves_async_transport_factory(self) -> None:
        """Accept transport factories that return awaitables."""
        transport = _FakeAsyncTransport()

        async def _build() -> object:
            await asyncio.sleep(0)
            return transport

        app = FastAPI(lifespan=PlynthLifespan({"salesforce": _build}))

        @app.get("/probe")  # type: ignore
        async def probe(
            bound_transport: object = Depends(get_transport("salesforce")),
        ) -> dict[str, bool]:
            return {"bound": bound_transport is transport}

        with TestClient(app) as client:
            response = client.get("/probe")
            assert response.status_code == 200
            assert response.json() == {"bound": True}

    def test_lifespan_awaits_close_return_value_when_awaitable(self) -> None:
        """Await close return value when sync close exposes awaitable work."""
        transport = _AwaitableCloseTransport()
        app = FastAPI(lifespan=PlynthLifespan({"salesforce": lambda: transport}))

        @app.get("/probe")  # type: ignore
        async def probe(
            _: object = Depends(get_transport("salesforce")),
        ) -> dict[str, bool]:
            return {"ok": True}

        with TestClient(app) as client:
            response = client.get("/probe")
            assert response.status_code == 200

        assert transport.closed is True
