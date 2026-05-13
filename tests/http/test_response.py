"""Tests for plynth.http.response.HttpResponse."""

from __future__ import annotations

import json

import pytest

from plynth.http.errors import HttpStatusError
from plynth.http.response import HttpResponse


class TestHttpResponseEncoding:
    """Tests for ``HttpResponse.encoding``."""

    def test_defaults_to_utf8_when_no_header(self) -> None:
        """Validate defaults to utf8 when no header."""
        resp = HttpResponse(status_code=200)
        assert resp.encoding == "utf-8"

    def test_defaults_to_utf8_when_no_charset_in_content_type(self) -> None:
        """Validate defaults to utf8 when no charset in content type."""
        resp = HttpResponse(
            status_code=200,
            headers={"content-type": "application/json"},
        )
        assert resp.encoding == "utf-8"

    def test_reads_charset_from_content_type(self) -> None:
        """Validate reads charset from content type."""
        resp = HttpResponse(
            status_code=200,
            headers={"content-type": "application/json; charset=iso-8859-1"},
        )
        assert resp.encoding == "iso-8859-1"

    def test_lowercases_charset(self) -> None:
        """Validate lowercases charset."""
        resp = HttpResponse(
            status_code=200,
            headers={"content-type": "text/html; charset=UTF-8"},
        )
        assert resp.encoding == "utf-8"

    def test_strips_quotes_from_charset(self) -> None:
        """Validate strips quotes from charset."""
        resp = HttpResponse(
            status_code=200,
            headers={"content-type": 'text/plain; charset="utf-8"'},
        )
        assert resp.encoding == "utf-8"

    def test_handles_charset_before_other_params(self) -> None:
        """Validate handles charset before other params."""
        resp = HttpResponse(
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8; boundary=something"},
        )
        assert resp.encoding == "utf-8"

    def test_handles_charset_after_other_params(self) -> None:
        """Validate handles charset after other params."""
        resp = HttpResponse(
            status_code=200,
            headers={"content-type": "text/html; boundary=something; charset=utf-8"},
        )
        assert resp.encoding == "utf-8"


class TestHttpResponseText:
    """Tests for ``HttpResponse.text``."""

    def test_decodes_utf8_content(self) -> None:
        """Validate decodes utf8 content."""
        resp = HttpResponse(status_code=200, content=b"hello world")
        assert resp.text == "hello world"

    def test_decodes_unicode_content(self) -> None:
        """Validate decodes unicode content."""
        payload = "héllo wörld"
        resp = HttpResponse(
            status_code=200,
            headers={"content-type": "text/plain; charset=utf-8"},
            content=payload.encode("utf-8"),
        )
        assert resp.text == payload

    def test_decodes_with_explicit_charset(self) -> None:
        """Validate decodes with explicit charset."""
        payload = "café"
        resp = HttpResponse(
            status_code=200,
            headers={"content-type": "text/plain; charset=iso-8859-1"},
            content=payload.encode("iso-8859-1"),
        )
        assert resp.text == payload

    def test_empty_body_returns_empty_string(self) -> None:
        """Validate empty body returns empty string."""
        resp = HttpResponse(status_code=204)
        assert resp.text == ""


class TestHttpResponseJson:
    """Tests for ``HttpResponse.json()``."""

    def test_parses_json_object(self) -> None:
        """Validate parses json object."""
        resp = HttpResponse(
            status_code=200,
            content=b'{"id": 1, "name": "test"}',
        )
        assert resp.json() == {"id": 1, "name": "test"}

    def test_parses_json_list(self) -> None:
        """Validate parses json list."""
        resp = HttpResponse(status_code=200, content=b"[1, 2, 3]")
        assert resp.json() == [1, 2, 3]

    def test_parses_json_primitives(self) -> None:
        """Validate parses json primitives."""
        assert HttpResponse(status_code=200, content=b"true").json() is True
        assert HttpResponse(status_code=200, content=b"null").json() is None
        assert HttpResponse(status_code=200, content=b"42").json() == 42

    def test_parses_json_with_unicode(self) -> None:
        """Validate parses json with unicode."""
        payload = {"message": "héllo"}
        resp = HttpResponse(
            status_code=200,
            headers={"content-type": "application/json; charset=utf-8"},
            content=json.dumps(payload).encode("utf-8"),
        )
        assert resp.json() == payload

    def test_accepts_json_loads_kwargs(self) -> None:
        """Validate accepts json loads kwargs."""
        from collections import OrderedDict

        resp = HttpResponse(status_code=200, content=b'{"b": 2, "a": 1}')
        result = resp.json(object_pairs_hook=OrderedDict)
        assert list(result.keys()) == ["b", "a"]

    def test_raises_on_invalid_json(self) -> None:
        """Validate raises on invalid json."""
        resp = HttpResponse(status_code=200, content=b"not-json")
        with pytest.raises(json.JSONDecodeError):
            resp.json()

    def test_raises_on_empty_body(self) -> None:
        """Validate raises on empty body."""
        resp = HttpResponse(status_code=200, content=b"")
        with pytest.raises(json.JSONDecodeError):
            resp.json()


class TestHttpResponseRaiseForStatus:
    """Tests for ``HttpResponse.raise_for_status()``."""

    @pytest.mark.parametrize("status_code", [200, 201, 204, 301, 304])
    def test_does_not_raise_for_success(self, status_code: int) -> None:
        """Validate does not raise for success."""
        resp = HttpResponse(status_code=status_code, method="GET", url="/")
        resp.raise_for_status()  # must not raise

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422, 500, 503])
    def test_raises_http_status_error_for_failure(self, status_code: int) -> None:
        """Validate raises http status error for failure."""
        resp = HttpResponse(
            status_code=status_code,
            method="GET",
            url="https://api.example.com/items",
        )
        with pytest.raises(HttpStatusError) as exc_info:
            resp.raise_for_status()
        assert exc_info.value.status_code == status_code

    def test_error_includes_method_and_url(self) -> None:
        """Validate error includes method and url."""
        resp = HttpResponse(
            status_code=404,
            method="DELETE",
            url="https://api.example.com/items/99",
        )
        with pytest.raises(HttpStatusError) as exc_info:
            resp.raise_for_status()
        err = exc_info.value
        assert err.method == "DELETE"
        assert err.url == "https://api.example.com/items/99"
