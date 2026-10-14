"""Tests for FastAPI service dependency helper."""

# pyright: reportUntypedFunctionDecorator=false

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

import pytest

pytest.importorskip("fastapi")

import plynt.adapters.fastapi.services as fastapi_services
from plynt.adapters.fastapi import (
    PlyntLifespan,
    build_service_dependencies,
    get_service,
)

fastapi = __import__("fastapi")
fastapi_testclient = __import__("fastapi.testclient", fromlist=["TestClient"])

FastAPI = fastapi.FastAPI
Depends = fastapi.Depends
TestClient = fastapi_testclient.TestClient


@dataclass
class _Service:
    """Simple service test double with one transport reference."""

    transport: object


class _Transport:
    """Transport test double that supports async shutdown."""

    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


@dataclass
class _OtherService:
    """Second service test double used for bundled dependency checks."""

    transport: object


class TestFastAPIServiceHelper:
    """Validate request-level service construction and caching behavior."""

    def test_service_dependency_caches_by_service_name(self) -> None:
        """Resolve service once when request-level caching is enabled."""
        transport = _Transport()
        build_count = {"count": 0}

        def _factory(bound_transport: object) -> _Service:
            build_count["count"] += 1
            return _Service(transport=bound_transport)

        app = FastAPI(lifespan=PlyntLifespan({"backend": lambda: transport}))

        service_dep = Depends(
            get_service(
                "backend_service",
                transport_name="backend",
                factory=_factory,
            )
        )

        @app.get("/probe")  # type: ignore
        async def probe(
            first: _Service = service_dep,
            second: _Service = service_dep,
        ) -> dict[str, bool | int]:
            return {
                "same_instance": first is second,
                "same_transport": first.transport is transport,
                "build_count": build_count["count"],
            }

        with TestClient(app) as client:
            response = client.get("/probe")

        assert response.status_code == 200
        assert response.json() == {
            "same_instance": True,
            "same_transport": True,
            "build_count": 1,
        }

    def test_service_dependency_without_cache_rebuilds(self) -> None:
        """Build service each time when request-level cache is disabled."""
        transport = _Transport()
        build_count = {"count": 0}

        def _factory(bound_transport: object) -> _Service:
            build_count["count"] += 1
            return _Service(transport=bound_transport)

        app = FastAPI(lifespan=PlyntLifespan({"backend": lambda: transport}))

        service_dependency = get_service(
            "backend_service",
            transport_name="backend",
            factory=_factory,
            cache=False,
        )
        first_dep = Depends(service_dependency, use_cache=False)
        second_dep = Depends(service_dependency, use_cache=False)

        @app.get("/probe")  # type: ignore
        async def probe(
            first: _Service = first_dep,
            second: _Service = second_dep,
        ) -> dict[str, bool | int]:
            return {
                "same_instance": first is second,
                "build_count": build_count["count"],
            }

        with TestClient(app) as client:
            response = client.get("/probe")

        assert response.status_code == 200
        assert response.json() == {
            "same_instance": False,
            "build_count": 2,
        }

    def test_build_service_dependencies_returns_named_dependencies(self) -> None:
        """Create multiple named dependencies that share one transport."""
        transport = _Transport()

        app = FastAPI(lifespan=PlyntLifespan({"backend": lambda: transport}))

        deps = build_service_dependencies(
            transport_name="backend",
            factories={
                "orders_service": lambda bound_transport: _Service(
                    transport=bound_transport
                ),
                "tickets_service": lambda bound_transport: _OtherService(
                    transport=bound_transport
                ),
            },
        )
        orders_dep = Depends(deps["orders_service"])
        tickets_dep = Depends(deps["tickets_service"])

        @app.get("/bundle")  # type: ignore
        async def bundle(
            orders: _Service = orders_dep,
            tickets: _OtherService = tickets_dep,
        ) -> dict[str, bool]:
            return {
                "orders_bound": orders.transport is transport,
                "tickets_bound": tickets.transport is transport,
            }

        with TestClient(app) as client:
            response = client.get("/bundle")

        assert response.status_code == 200
        assert response.json() == {
            "orders_bound": True,
            "tickets_bound": True,
        }

    def test_service_dependency_direct_calls_use_internal_cache(self) -> None:
        """Use request-state cache on repeated direct dependency invocation."""
        transport = _Transport()
        build_count = {"count": 0}

        def _factory(bound_transport: object) -> _Service:
            build_count["count"] += 1
            return _Service(transport=bound_transport)

        dependency = get_service(
            "backend_service",
            transport_name="backend",
            factory=_factory,
        )

        request = SimpleNamespace(
            state=SimpleNamespace(),
            app=SimpleNamespace(
                state=SimpleNamespace(_plynt_transports={"backend": transport})
            ),
        )

        first = dependency(cast(Any, request))
        second = dependency(cast(Any, request))

        assert first is second
        assert build_count["count"] == 1

    def test_service_dependency_requires_request_app_state(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Raise clear error when request does not expose state."""
        monkeypatch.setattr(
            fastapi_services,
            "get_transport",
            lambda _name: lambda _request: object(),
        )

        dependency = get_service(
            "backend_service",
            transport_name="backend",
            factory=lambda transport: _Service(transport=transport),
        )
        bad_request = SimpleNamespace(app=SimpleNamespace(state=None), state=None)

        with pytest.raises(RuntimeError, match=r"request object must expose \.state"):
            dependency(cast(Any, bad_request))
