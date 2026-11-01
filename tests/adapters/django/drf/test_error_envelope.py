"""Verify DRF envelope integration with real responses and request-ID scopes"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

django = pytest.importorskip("django")
pytest.importorskip("rest_framework")

from django.conf import settings  # noqa: E402

if not settings.configured:
    settings.configure(SECRET_KEY="envelope-tests", INSTALLED_APPS=[], MIDDLEWARE=[])
    django.setup()

from django.test import RequestFactory, override_settings  # noqa: E402
from rest_framework.exceptions import ValidationError  # noqa: E402
from rest_framework.renderers import JSONRenderer  # noqa: E402
from rest_framework.request import Request  # noqa: E402
from rest_framework.response import Response  # noqa: E402
from rest_framework.views import APIView  # noqa: E402

from plynt.adapters.django import RequestIDMiddleware  # noqa: E402
from plynt.adapters.django.drf.errors import (  # noqa: E402
    map_exception_to_drf_response,
    plynt_exception_handler,
)
from plynt.base import (  # noqa: E402
    BaseError,
    InvalidInputError,
    RequestIDPolicy,
    default_error_envelope,
    get_error_event_id,
)
from plynt.base import Request as OutboundRequest  # noqa: E402
from plynt.base import Response as OutboundResponse  # noqa: E402
from plynt.http.errors import NotFoundError  # noqa: E402
from plynt.middleware import ErrorReportingMiddleware  # noqa: E402


def custom_envelope(
    error: Exception, status_code: int, request_id: str | None
) -> Mapping[str, object]:
    return {"status": status_code, "request_id": request_id, "code": "CUSTOM"}


def application_exception_handler(exc: Exception, context: dict[str, Any]) -> Any:
    return plynt_exception_handler(exc, context, envelope=custom_envelope)


def _failing_get(self: object, request: Request) -> Response:
    raise InvalidInputError()


_FailingView: Any = type("_FailingView", (APIView,), {"get": _failing_get})


class TestDRFErrorEnvelope:
    @pytest.mark.parametrize("publish_event_id", [False, True])
    def test_reported_exception_reaches_real_view_handler_with_opt_in_id(
        self, publish_event_id: bool
    ) -> None:
        class Reporter:
            def report(
                self, exc: Exception, context: Mapping[str, object]
            ) -> str | None:
                return "drf-event"

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

        def exception_handler(exc: Exception, context: dict[str, Any]) -> Any:
            return plynt_exception_handler(
                exc, context, envelope=envelope if publish_event_id else None
            )

        def failing(request: OutboundRequest) -> OutboundResponse:
            raise InvalidInputError()

        def reported_get(self: object, request: Request) -> Response:
            ErrorReportingMiddleware(Reporter()).handle(
                OutboundRequest("GET", "/upstream"), failing
            )
            pytest.fail("The outbound call must raise")

        view: Any = type(
            "_ReportedView",
            (APIView,),
            {
                "get": reported_get,
                "get_exception_handler": lambda self: exception_handler,
                "authentication_classes": [],
            },
        )
        with override_settings(REST_FRAMEWORK={"UNAUTHENTICATED_USER": None}):
            response = RequestIDMiddleware(view.as_view())(
                RequestFactory().get("/", headers={"X-Request-ID": "inbound"})
            )
        assert isinstance(response, Response)
        response.render()
        expected: dict[str, object] = {
            "message": "Invalid input data",
            "code": "INVALID_INPUT",
        }
        if publish_event_id:
            expected["error_id"] = "drf-event"
        assert response.status_code == 400
        assert response["X-Request-ID"] == "inbound"
        assert json.loads(response.content) == expected

    @pytest.mark.parametrize(
        ("error", "status"),
        [
            (InvalidInputError(), 400),
            (NotFoundError(), 404),
            (RuntimeError("private"), 500),
        ],
    )
    def test_custom_envelope_receives_mapped_status_and_active_id(
        self, error: Exception, status: int
    ) -> None:
        def envelope(
            received: Exception, status_code: int, request_id: str | None
        ) -> Mapping[str, object]:
            assert received is error
            return custom_envelope(received, status_code, request_id)

        with RequestIDPolicy().scope("scoped"):
            response = map_exception_to_drf_response(error, envelope=envelope)
        assert response.status_code == status
        assert response.data == {
            "status": status,
            "request_id": "scoped",
            "code": "CUSTOM",
        }
        response.accepted_renderer = JSONRenderer()
        response.accepted_media_type = "application/json"
        response.renderer_context = {}
        response.render()
        assert json.loads(response.content) == response.data

    def test_missing_context_is_passed_without_generating_id(self) -> None:
        response = map_exception_to_drf_response(
            InvalidInputError(), envelope=custom_envelope
        )
        assert response.data["request_id"] is None

    @pytest.mark.parametrize("invalid_output", [False, True])
    def test_failed_envelope_uses_logged_default_and_preserves_details_option(
        self, invalid_output: bool, caplog: pytest.LogCaptureFixture
    ) -> None:
        def failing(
            error: Exception, status: int, request_id: str | None
        ) -> Mapping[str, object]:
            if invalid_output:
                return {"bad": object()}
            raise ValueError("private-callback")

        response = plynt_exception_handler(
            InvalidInputError(details={"field": "name"}),
            {},
            envelope=failing,
            include_details=True,
        )
        assert response.status_code == 400
        assert response.data == {
            "message": "Invalid input data",
            "code": "INVALID_INPUT",
            "details": {"field": "name"},
        }
        assert len(caplog.records) == 1
        assert "private-callback" not in caplog.text

    def test_drf_native_exception_bypasses_custom_envelope(self) -> None:
        def forbidden(
            error: Exception, status: int, request_id: str | None
        ) -> Mapping[str, object]:
            pytest.fail("DRF-native responses must not invoke the envelope")

        response = plynt_exception_handler(
            ValidationError({"name": ["required"]}), {}, envelope=forbidden
        )
        assert response.status_code == 400
        assert response.data == {"name": ["required"]}

    def test_existing_default_payload_retains_missing_code_behavior(self) -> None:
        response = map_exception_to_drf_response(BaseError("custom"))
        assert response.data == {"message": "custom", "code": "INTERNAL_SERVER_ERROR"}

    def test_configured_handler_and_django_middleware_share_request_id(self) -> None:
        with override_settings(
            REST_FRAMEWORK={
                "EXCEPTION_HANDLER": f"{__name__}.application_exception_handler",
                "DEFAULT_AUTHENTICATION_CLASSES": [],
                "UNAUTHENTICATED_USER": None,
            }
        ):
            middleware = RequestIDMiddleware(_FailingView.as_view())
            response = middleware(
                RequestFactory().get("/", headers={"X-Request-ID": "inbound"})
            )
            assert isinstance(response, Response)
            response.render()
            assert response.status_code == 400
            assert response["X-Request-ID"] == "inbound"
            assert json.loads(response.content) == {
                "status": 400,
                "request_id": "inbound",
                "code": "CUSTOM",
            }
