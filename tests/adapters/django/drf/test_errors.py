"""Tests for ``plynth.adapters.django.drf.errors``."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import plynth.adapters.django.drf.errors as drf_errors
from plynth.base.errors import InvalidInputError
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
            drf_errors.importlib,
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
            drf_errors.importlib,
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

        monkeypatch.setattr(drf_errors.importlib, "import_module", _import_module)

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

        monkeypatch.setattr(drf_errors.importlib, "import_module", _import_module)

        response = drf_errors.plynth_exception_handler(RuntimeError("boom"), {})

        assert response is fallback
