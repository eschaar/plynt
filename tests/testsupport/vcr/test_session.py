"""Unit tests for session-level private helpers."""

from __future__ import annotations

from plynt.base.request import Request
from plynt.base.response import Response
from plynt.testsupport.vcr.config import StateTrackingMode, StateTrackingSettings
from plynt.testsupport.vcr.session import (
    _from_vcr_response,
    _maybe_pretty_json_body,
    _state_key,
    _to_vcr_response,
)


class TestFromVCRResponse:
    """Test suite for FromVCRResponse."""

    def test_list_header_value_is_decoded(self) -> None:
        """Validate list header value is decoded."""
        payload = {
            "status": {"code": 200, "message": "OK"},
            "headers": {"Content-Type": ["application/json"]},
            "body": {"string": b"{}"},
        }
        result = _from_vcr_response(payload)
        assert result.status_code == 200
        assert result.headers["Content-Type"] == "application/json"

    def test_empty_list_header_value_gives_empty_string(self) -> None:
        """Validate empty list header value gives empty string."""
        payload = {
            "status": {"code": 200, "message": "OK"},
            "headers": {"X-Empty": []},
            "body": {"string": b"{}"},
        }
        result = _from_vcr_response(payload)
        assert result.headers["X-Empty"] == ""

    def test_non_list_header_value_is_decoded(self) -> None:
        """Validate non list header value is decoded."""
        payload = {
            "status": {"code": 200, "message": "OK"},
            "headers": {"X-Custom": "raw-string"},
            "body": {"string": b"{}"},
        }
        result = _from_vcr_response(payload)
        assert result.headers["X-Custom"] == "raw-string"

    def test_str_body_is_encoded_to_bytes(self) -> None:
        """Validate str body is encoded to bytes."""
        payload = {
            "status": {"code": 200, "message": "OK"},
            "headers": {},
            "body": {"string": "hello"},
        }
        result = _from_vcr_response(payload)
        assert result.content == b"hello"


class TestStateKeyHelper:
    """Test suite for StateKeyHelper."""

    def test_global_mode_returns_global_key(self) -> None:
        """Validate global mode returns global key."""
        tracking = StateTrackingSettings(mode=StateTrackingMode.GLOBAL)
        request = Request(method="GET", url="https://example.test/resource")
        assert _state_key(request, tracking) == "__global__"

    def test_off_mode_returns_off_key(self) -> None:
        """Validate off mode returns off key."""
        tracking = StateTrackingSettings(mode=StateTrackingMode.OFF)
        request = Request(method="GET", url="https://example.test/resource")
        assert _state_key(request, tracking) == "__off__"


class TestMaybePrettyJsonBody:
    """Test suite for _maybe_pretty_json_body helper behavior."""

    def test_invalid_json_returns_original_bytes(self) -> None:
        """Keep the original payload when JSON parsing fails."""
        raw = b"{not valid json}"
        assert _maybe_pretty_json_body(raw, "application/json") == raw

    def test_invalid_utf8_returns_original_bytes(self) -> None:
        """Keep the original payload when UTF-8 decoding fails."""
        raw = b"\xff\xfe\xfa"
        assert _maybe_pretty_json_body(raw, "application/json") == raw


class TestToVCRResponse:
    """Test suite for _to_vcr_response helper behavior."""

    def test_maps_response_to_vcr_payload(self) -> None:
        """Map status, headers, and body fields into vcrpy payload shape."""
        response = Response(
            status_code=200,
            headers={"Content-Type": "application/json"},
            content=b'{"ok": true}',
        )

        payload = _to_vcr_response(response)

        assert payload["status"]["code"] == 200
        assert payload["headers"] == {"Content-Type": ["application/json"]}
        assert isinstance(payload["body"]["string"], str)
