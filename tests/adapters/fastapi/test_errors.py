"""Tests for FastAPI error mapping and exception handlers."""

# pyright: reportUntypedFunctionDecorator=false

from __future__ import annotations

import json

import pytest

fastapi = pytest.importorskip("fastapi")
fastapi_testclient = pytest.importorskip("fastapi.testclient")

from plynt.adapters.fastapi.errors import (  # noqa: E402
    build_error_payload,
    install_plynt_exception_handlers,
    map_exception_to_fastapi_response,
)
from plynt.base.errors import BaseError, InvalidInputError  # noqa: E402
from plynt.http.errors import NotFoundError  # noqa: E402

FastAPI = fastapi.FastAPI
TestClient = fastapi_testclient.TestClient


class TestFastAPIErrorHelpers:
    """Validate FastAPI adapter error mapping behaviors."""

    def test_map_exception_uses_http_status_for_http_errors(self) -> None:
        """Map HttpStatusError subclasses using their HTTP status code."""
        response = map_exception_to_fastapi_response(
            NotFoundError(method="GET", url="/items/1")
        )

        assert response.status_code == 404
        payload = json.loads(response.body)
        assert payload["code"] == "NOT_FOUND"

    def test_map_exception_uses_base_error_status_mapping(self) -> None:
        """Map known BaseError subclasses to stable API status codes."""
        response = map_exception_to_fastapi_response(
            InvalidInputError(details={"field": "name"}),
            include_details=True,
        )

        assert response.status_code == 400
        payload = json.loads(response.body)
        assert payload["code"] == "INVALID_INPUT"
        assert payload["details"] == {"field": "name"}

    def test_build_error_payload_for_generic_exception(self) -> None:
        """Return safe generic payload for non-plynt exceptions."""
        payload = build_error_payload(RuntimeError("boom"))
        assert payload == {
            "message": "Internal server error",
            "code": "INTERNAL_SERVER_ERROR",
        }

    def test_install_exception_handlers_on_fastapi_app(self) -> None:
        """Install plynt handlers and map exceptions into JSON responses."""
        app = FastAPI()
        install_plynt_exception_handlers(app, include_details=True)

        @app.get("/boom")  # type: ignore
        async def boom() -> dict[str, str]:
            raise InvalidInputError(details={"field": "tenant_id"})

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/boom")

        assert response.status_code == 400
        assert response.json() == {
            "message": "Invalid input data",
            "code": "INVALID_INPUT",
            "details": {"field": "tenant_id"},
        }

    def test_map_exception_uses_500_for_unmapped_base_error(self) -> None:
        """Fallback to 500 when BaseError subclass has no explicit mapping."""

        class _CustomBaseError(BaseError):
            code = "CUSTOM_BASE"
            message = "custom"

        response = map_exception_to_fastapi_response(_CustomBaseError())
        assert response.status_code == 500

    def test_install_handlers_requires_add_exception_handler(self) -> None:
        """Raise clear error for app-like objects without handler API."""
        with pytest.raises(RuntimeError, match="add_exception_handler"):
            install_plynt_exception_handlers(object())
