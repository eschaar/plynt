"""Tests for FastAPI error mapping and exception handlers."""

# pyright: reportUntypedFunctionDecorator=false

from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

fastapi = pytest.importorskip("fastapi")
fastapi_testclient = pytest.importorskip("fastapi.testclient")

from plynt.adapters.fastapi import RequestIDMiddleware  # noqa: E402
from plynt.adapters.fastapi.errors import (  # noqa: E402
    build_error_payload,
    create_plynt_exception_handler,
    install_plynt_exception_handlers,
    map_exception_to_fastapi_response,
)
from plynt.base import (  # noqa: E402
    Request,
    RequestIDPolicy,
    Response,
    default_error_envelope,
    get_error_event_id,
    get_request_id,
)
from plynt.base.errors import BaseError, InvalidInputError  # noqa: E402
from plynt.http.errors import NotFoundError  # noqa: E402
from plynt.middleware import (  # noqa: E402
    AsyncErrorReportingMiddleware,
    ErrorReportingMiddleware,
)

FastAPI = fastapi.FastAPI
TestClient = fastapi_testclient.TestClient


class TestFastAPIErrorHelpers:
    @pytest.mark.parametrize("async_endpoint", [False, True])
    def test_reported_event_reaches_envelope_from_worker_or_async_endpoint(
        self, async_endpoint: bool
    ) -> None:
        class Reporter:
            def report(
                self, exc: Exception, context: Mapping[str, object]
            ) -> str | None:
                return "tracker-event"

            async def areport(
                self, exc: Exception, context: Mapping[str, object]
            ) -> str | None:
                return self.report(exc, context)

        def envelope(
            error: Exception, status: int, request_id: str | None
        ) -> Mapping[str, object]:
            payload = default_error_envelope(error, status, request_id)
            event_id = get_error_event_id(error)
            if event_id is not None:
                payload["error_id"] = event_id
            return payload

        def failing(request: Request) -> Response:
            raise InvalidInputError()

        async def async_failing(request: Request) -> Response:
            return failing(request)

        def sync_endpoint() -> None:
            ErrorReportingMiddleware(Reporter()).handle(
                Request("GET", "/upstream"), failing
            )

        async def async_handler() -> None:
            await AsyncErrorReportingMiddleware(Reporter()).handle(
                Request("GET", "/upstream"), async_failing
            )

        def unreported() -> None:
            raise InvalidInputError()

        app = FastAPI()
        install_plynt_exception_handlers(app, envelope=envelope)
        app.get("/reported")(async_handler if async_endpoint else sync_endpoint)
        app.get("/unreported")(unreported)
        with TestClient(RequestIDMiddleware(app)) as client:
            reported = client.get("/reported")
            unreported_response = client.get("/unreported")
        assert reported.status_code == 400
        assert reported.json() == {
            "message": "Invalid input data",
            "code": "INVALID_INPUT",
            "error_id": "tracker-event",
        }
        assert unreported_response.status_code == 400
        assert unreported_response.json() == {
            "message": "Invalid input data",
            "code": "INVALID_INPUT",
        }

    @pytest.mark.parametrize(
        ("error", "status"),
        [
            (InvalidInputError(), 400),
            (NotFoundError(), 404),
            (RuntimeError("private"), 500),
        ],
    )
    def test_custom_envelope_receives_exact_error_status_and_scoped_id(
        self, error: Exception, status: int
    ) -> None:
        def envelope(
            received: Exception, status_code: int, request_id: str | None
        ) -> Mapping[str, object]:
            assert received is error
            return {"status": status_code, "request_id": request_id}

        with RequestIDPolicy().scope("scoped"):
            response = map_exception_to_fastapi_response(error, envelope=envelope)
        assert response.status_code == status
        assert json.loads(response.body) == {"status": status, "request_id": "scoped"}

    @pytest.mark.asyncio
    async def test_handler_factory_passes_missing_context_without_generating_id(
        self,
    ) -> None:
        def envelope(
            error: Exception, status: int, request_id: str | None
        ) -> Mapping[str, object]:
            return {"request_id": request_id}

        handler = create_plynt_exception_handler(envelope=envelope)
        response = await handler(object(), InvalidInputError())
        assert json.loads(response.body) == {"request_id": None}
        assert get_request_id() is None

    @pytest.mark.parametrize("invalid_output", [False, True])
    def test_failed_envelope_uses_safe_logged_fallback(
        self, invalid_output: bool, caplog: pytest.LogCaptureFixture
    ) -> None:
        def failing(
            error: Exception, status: int, request_id: str | None
        ) -> Mapping[str, object]:
            if invalid_output:
                return {"bad": object()}
            raise ValueError("private-callback")

        response = map_exception_to_fastapi_response(
            InvalidInputError(details={"field": "name"}),
            envelope=failing,
            include_details=True,
        )
        assert response.status_code == 400
        assert json.loads(response.body) == {
            "message": "Invalid input data",
            "code": "INVALID_INPUT",
            "details": {"field": "name"},
        }
        assert len(caplog.records) == 1
        assert "private-callback" not in caplog.text

    @pytest.mark.parametrize("async_endpoint", [False, True])
    def test_installed_envelope_and_outer_middleware_share_request_id(
        self, async_endpoint: bool
    ) -> None:
        app = FastAPI()

        def envelope(
            error: Exception, status: int, request_id: str | None
        ) -> Mapping[str, object]:
            return {"status": status, "request_id": request_id}

        install_plynt_exception_handlers(app, envelope=envelope)

        def sync_endpoint() -> None:
            raise InvalidInputError()

        async def async_handler() -> None:
            sync_endpoint()

        app.get("/custom")(async_handler if async_endpoint else sync_endpoint)
        with TestClient(RequestIDMiddleware(app)) as client:
            response = client.get("/custom", headers={"X-Request-ID": "inbound"})
            assert response.status_code == 400
            assert response.json() == {"status": 400, "request_id": "inbound"}
            assert response.headers["X-Request-ID"] == "inbound"

    def test_native_validation_handler_is_not_replaced(self) -> None:
        app = FastAPI()

        def forbidden(
            error: Exception, status: int, request_id: str | None
        ) -> Mapping[str, object]:
            pytest.fail("Native validation must bypass the plynt envelope")

        install_plynt_exception_handlers(app, envelope=forbidden)

        def endpoint(count: int) -> dict[str, int]:
            return {"count": count}

        app.get("/validate")(endpoint)
        with TestClient(app) as client:
            response = client.get("/validate?count=invalid")
        assert response.status_code == 422
        assert "detail" in response.json()

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
