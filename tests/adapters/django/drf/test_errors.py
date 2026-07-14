"""Tests for ``plynth.adapters.django.drf.errors``."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

import pytest

import plynth.adapters.django.drf.errors as drf_errors
from plynth.base.errors import (
    ConfigurationError,
    DependencyUnavailableError,
    FeatureDisabledError,
    InvalidInputError,
    OperationFailedError,
    StreamInterruptedError,
)
from plynth.http.errors import NotFoundError


class TestBuildErrorPayload:
    """Verify safe payload generation from plynth and generic exceptions."""

    def test_builds_payload_from_plynth_error_without_details_by_default(self) -> None:
        """Exclude details unless explicitly requested."""
        exc = InvalidInputError("bad request", details={"field": ["required"]})

        payload = drf_errors.build_error_payload(exc)

        assert payload == {"message": "bad request", "code": "INVALID_INPUT"}

    def test_builds_payload_with_details_when_enabled(self) -> None:
        """Include details when explicitly enabled."""
        exc = InvalidInputError("bad request", details={"field": ["required"]})

        payload = drf_errors.build_error_payload(exc, include_details=True)

        assert payload["details"] == {"field": ["required"]}

    def test_builds_fallback_payload_for_non_plynth_exception(self) -> None:
        """Return generic safe payload for unknown exceptions."""
        payload = drf_errors.build_error_payload(RuntimeError("boom"))

        assert payload == {
            "message": "Internal server error",
            "code": "INTERNAL_SERVER_ERROR",
        }


class TestMapExceptionToDrfResponse:
    """Verify response mapping status and payload behavior."""

    def test_maps_http_status_error_status_code(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Use HTTP status code from HttpStatusError subclasses."""

        class _FakeResponse:
            def __init__(self, data: dict[str, Any], *, status: int) -> None:
                self.data = data
                self.status_code = status

        monkeypatch.setattr(
            importlib,
            "import_module",
            lambda name: (
                SimpleNamespace(Response=_FakeResponse)
                if name == "rest_framework.response"
                else (_ for _ in ()).throw(AssertionError(name))
            ),
        )

        response = drf_errors.map_exception_to_drf_response(NotFoundError("missing"))

        assert response.status_code == 404
        assert response.data["message"] == "missing"

    def test_maps_unknown_exception_to_500(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fallback to status 500 for non-HTTP exceptions."""

        class _FakeResponse:
            def __init__(self, data: dict[str, Any], *, status: int) -> None:
                self.data = data
                self.status_code = status

        monkeypatch.setattr(
            importlib,
            "import_module",
            lambda name: (
                SimpleNamespace(Response=_FakeResponse)
                if name == "rest_framework.response"
                else (_ for _ in ()).throw(AssertionError(name))
            ),
        )

        response = drf_errors.map_exception_to_drf_response(RuntimeError("boom"))

        assert response.status_code == 500
        assert response.data["code"] == "INTERNAL_SERVER_ERROR"

    def test_maps_invalid_input_error_to_400(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Map plynth invalid input errors to HTTP 400."""

        class _FakeResponse:
            def __init__(self, data: dict[str, Any], *, status: int) -> None:
                self.data = data
                self.status_code = status

        monkeypatch.setattr(
            importlib,
            "import_module",
            lambda name: (
                SimpleNamespace(Response=_FakeResponse)
                if name == "rest_framework.response"
                else (_ for _ in ()).throw(AssertionError(name))
            ),
        )

        response = drf_errors.map_exception_to_drf_response(
            InvalidInputError("bad request")
        )

        assert response.status_code == 400
        assert response.data["code"] == "INVALID_INPUT"

    def test_maps_dependency_unavailable_error_to_503(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Map dependency unavailability to HTTP 503."""

        class _FakeResponse:
            def __init__(self, data: dict[str, Any], *, status: int) -> None:
                self.data = data
                self.status_code = status

        monkeypatch.setattr(
            importlib,
            "import_module",
            lambda name: (
                SimpleNamespace(Response=_FakeResponse)
                if name == "rest_framework.response"
                else (_ for _ in ()).throw(AssertionError(name))
            ),
        )

        response = drf_errors.map_exception_to_drf_response(
            DependencyUnavailableError("upstream down")
        )

        assert response.status_code == 503
        assert response.data["code"] == "DEPENDENCY_UNAVAILABLE"

    def test_maps_feature_disabled_error_to_503(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Map feature availability failures to HTTP 503."""

        class _FakeResponse:
            def __init__(self, data: dict[str, Any], *, status: int) -> None:
                self.data = data
                self.status_code = status

        monkeypatch.setattr(
            importlib,
            "import_module",
            lambda name: (
                SimpleNamespace(Response=_FakeResponse)
                if name == "rest_framework.response"
                else (_ for _ in ()).throw(AssertionError(name))
            ),
        )

        response = drf_errors.map_exception_to_drf_response(
            FeatureDisabledError("maintenance window")
        )

        assert response.status_code == 503
        assert response.data["code"] == "FEATURE_DISABLED"

    def test_maps_operation_failed_error_to_422(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Map generic operation failures to HTTP 422."""

        class _FakeResponse:
            def __init__(self, data: dict[str, Any], *, status: int) -> None:
                self.data = data
                self.status_code = status

        monkeypatch.setattr(
            importlib,
            "import_module",
            lambda name: (
                SimpleNamespace(Response=_FakeResponse)
                if name == "rest_framework.response"
                else (_ for _ in ()).throw(AssertionError(name))
            ),
        )

        response = drf_errors.map_exception_to_drf_response(
            OperationFailedError("business rule failed")
        )

        assert response.status_code == 422
        assert response.data["code"] == "OPERATION_FAILED"

    def test_maps_transport_error_to_502(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Map transport failures to HTTP 502."""

        class _FakeResponse:
            def __init__(self, data: dict[str, Any], *, status: int) -> None:
                self.data = data
                self.status_code = status

        monkeypatch.setattr(
            importlib,
            "import_module",
            lambda name: (
                SimpleNamespace(Response=_FakeResponse)
                if name == "rest_framework.response"
                else (_ for _ in ()).throw(AssertionError(name))
            ),
        )

        response = drf_errors.map_exception_to_drf_response(
            StreamInterruptedError("upstream stream broke")
        )

        assert response.status_code == 502
        assert response.data["code"] == "STREAM_INTERRUPTED"

    def test_maps_configuration_error_to_500(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Keep server configuration errors on HTTP 500."""

        class _FakeResponse:
            def __init__(self, data: dict[str, Any], *, status: int) -> None:
                self.data = data
                self.status_code = status

        monkeypatch.setattr(
            importlib,
            "import_module",
            lambda name: (
                SimpleNamespace(Response=_FakeResponse)
                if name == "rest_framework.response"
                else (_ for _ in ()).throw(AssertionError(name))
            ),
        )

        response = drf_errors.map_exception_to_drf_response(
            ConfigurationError("missing service endpoint")
        )

        assert response.status_code == 500
        assert response.data["code"] == "CONFIGURATION_ERROR"

    def test_maps_subclass_of_invalid_input_error_to_400(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Apply parent class mapping to BaseError subclasses."""

        class _CustomInvalidInputError(InvalidInputError):
            pass

        class _FakeResponse:
            def __init__(self, data: dict[str, Any], *, status: int) -> None:
                self.data = data
                self.status_code = status

        monkeypatch.setattr(
            importlib,
            "import_module",
            lambda name: (
                SimpleNamespace(Response=_FakeResponse)
                if name == "rest_framework.response"
                else (_ for _ in ()).throw(AssertionError(name))
            ),
        )

        response = drf_errors.map_exception_to_drf_response(
            _CustomInvalidInputError("bad request")
        )

        assert response.status_code == 400


class TestPlynthExceptionHandler:
    """Verify DRF-first fallback behavior of plynth exception handler."""

    def test_returns_drf_default_response_when_available(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Prefer DRF default handler output when it handles the exception."""
        sentinel = object()

        def _import_module(name: str) -> Any:
            if name == "rest_framework.views":
                return SimpleNamespace(exception_handler=lambda exc, context: sentinel)
            raise AssertionError(name)

        monkeypatch.setattr(importlib, "import_module", _import_module)

        response = drf_errors.plynth_exception_handler(RuntimeError("boom"), {})

        assert response is sentinel

    def test_falls_back_to_plynth_mapping_when_drf_returns_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Use mapped plynth response when DRF does not handle exception."""
        fallback = object()

        monkeypatch.setattr(
            drf_errors,
            "map_exception_to_drf_response",
            lambda exc: fallback,
        )

        def _import_module(name: str) -> Any:
            if name == "rest_framework.views":
                return SimpleNamespace(exception_handler=lambda exc, context: None)
            raise AssertionError(name)

        monkeypatch.setattr(importlib, "import_module", _import_module)

        response = drf_errors.plynth_exception_handler(RuntimeError("boom"), {})

        assert response is fallback
