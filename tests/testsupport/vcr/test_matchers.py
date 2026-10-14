from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from plynt.testsupport.vcr.matchers import (
    NormalizedJSONBodyMatcher,
    ProxyAwarePathMatcher,
    VCRMatcherLibrary,
)


def _request(
    *,
    url: str,
    uri: str | None = None,
    path: str | None = None,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> SimpleNamespace:
    """Handle request."""
    return SimpleNamespace(
        url=url,
        uri=uri or url,
        path=path,
        headers=headers or {},
        body=body,
    )


class TestNormalizedJSONBodyMatcher:
    """Test suite for NormalizedJSONBodyMatcher."""

    def test_json_key_order_ignored_by_default(self) -> None:
        """Validate json key order ignored by default."""
        r1 = _request(
            url="https://example.test/orders",
            headers={"Content-Type": "application/json"},
            body=b'{"meta": {"a": 1, "b": 2}, "ids": [1, 2, 3]}',
        )
        r2 = _request(
            url="https://example.test/orders",
            headers={"Content-Type": "application/json"},
            body=b'{"ids": [1, 2, 3], "meta": {"b": 2, "a": 1}}',
        )
        NormalizedJSONBodyMatcher().match(r1, r2)

    def test_json_list_order_significant_by_default(self) -> None:
        """Validate json list order significant by default."""
        r1 = _request(
            url="https://example.test/orders",
            headers={"Content-Type": "application/json"},
            body=b'{"ids": [3, 2, 1]}',
        )
        r2 = _request(
            url="https://example.test/orders",
            headers={"Content-Type": "application/json"},
            body=b'{"ids": [1, 2, 3]}',
        )
        with pytest.raises(AssertionError, match="JSON body mismatch"):
            NormalizedJSONBodyMatcher().match(r1, r2)

    def test_json_list_order_ignored_when_sort_lists_true(self) -> None:
        """Validate json list order ignored when sort lists true."""
        r1 = _request(
            url="https://example.test/orders",
            headers={"Content-Type": "application/json"},
            body=b'{"ids": [3, 2, 1], "meta": {"a": 1, "b": 2}}',
        )
        r2 = _request(
            url="https://example.test/orders",
            headers={"Content-Type": "application/json"},
            body=b'{"meta": {"b": 2, "a": 1}, "ids": [1, 2, 3]}',
        )
        NormalizedJSONBodyMatcher(sort_lists=True).match(r1, r2)

    def test_json_semantic_mismatch_raises(self) -> None:
        """Validate json semantic mismatch raises."""
        r1 = _request(
            url="https://example.test/orders",
            headers={"Content-Type": "application/json"},
            body=b'{"ids": [1, 2, 3]}',
        )
        r2 = _request(
            url="https://example.test/orders",
            headers={"Content-Type": "application/json"},
            body=b'{"ids": [1, 2, 4]}',
        )
        with pytest.raises(AssertionError, match="JSON body mismatch"):
            NormalizedJSONBodyMatcher().match(r1, r2)

    def test_non_json_falls_back_to_vcr_body_matcher(self) -> None:
        """Validate non json falls back to vcr body matcher."""
        r1 = _request(
            url="https://example.test/orders",
            headers={"Content-Type": "text/plain"},
            body=b"payload-a",
        )
        r2 = _request(
            url="https://example.test/orders",
            headers={"Content-Type": "text/plain"},
            body=b"payload-b",
        )
        with pytest.raises(AssertionError):
            NormalizedJSONBodyMatcher().match(r1, r2)

    def test_vcr_list_style_header_is_used_for_content_type(self) -> None:
        # VCR internally stores headers as {name: [value]} dicts.
        """Validate vcr list style header is used for content type."""
        r1: Any = SimpleNamespace(
            url="https://example.test/",
            uri="https://example.test/",
            path=None,
            headers={"Content-Type": ["application/json"]},
            body=b'{"x": 1}',
        )
        r2: Any = SimpleNamespace(
            url="https://example.test/",
            uri="https://example.test/",
            path=None,
            headers={"Content-Type": ["application/json"]},
            body=b'{"x": 1}',
        )
        NormalizedJSONBodyMatcher().match(r1, r2)

    def test_no_content_type_falls_back_to_vcr_body_matcher_and_matches(self) -> None:
        # No Content-Type → _content_type returns "" → body_matcher used → L36, L67
        """Validate no content type falls back to vcr body matcher and matches."""
        r1 = _request(url="https://example.test/", headers={}, body=None)
        r2 = _request(url="https://example.test/", headers={}, body=None)
        NormalizedJSONBodyMatcher().match(r1, r2)

    def test_json_body_none_matches_none(self) -> None:
        # body=None with JSON content-type → _decode_json returns None → L41
        """Validate json body none matches none."""
        r1 = _request(
            url="https://example.test/",
            headers={"Content-Type": "application/json"},
            body=None,
        )
        r2 = _request(
            url="https://example.test/",
            headers={"Content-Type": "application/json"},
            body=None,
        )
        NormalizedJSONBodyMatcher().match(r1, r2)

    def test_json_str_body_is_parsed_and_matched(self) -> None:
        # str body → _decode_json's str branch → L45
        """Validate json str body is parsed and matched."""
        r1 = _request(
            url="https://example.test/",
            headers={"Content-Type": "application/json"},
            body=b'{"k": 1}',
        )
        r2: Any = SimpleNamespace(
            url="https://example.test/",
            uri="https://example.test/",
            path=None,
            headers={"Content-Type": "application/json"},
            body='{"k": 1}',
        )
        NormalizedJSONBodyMatcher().match(r1, r2)


class TestProxyAwarePathMatcher:
    """Test suite for ProxyAwarePathMatcher."""

    def test_plain_url_match_passes(self) -> None:
        """Validate plain url match passes."""
        r1 = _request(url="https://example.test/a")
        r2 = _request(url="https://example.test/a")
        ProxyAwarePathMatcher.match(r1, r2)

    def test_proxy_prefixed_path_match_passes(self) -> None:
        """Validate proxy prefixed path match passes."""
        r1 = _request(
            url="https://proxy.test/https://example.test/service",
            path="//proxy.test/service",
        )
        r2 = _request(
            url="https://example.test/service",
            path="/service",
        )
        ProxyAwarePathMatcher.match(r1, r2)

    def test_proxy_env_match_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Validate proxy env match passes."""
        monkeypatch.setenv("HTTP_PROXY", "http://proxy.internal")
        # _plain_equal: different URLs → False
        # _path_equal: explicit different paths → False
        # _proxy_env_equal: after removing proxy prefix, URLs match → True (L106-110)
        r1 = _request(
            url="http://proxy.internalhttp://api.example.test/data",
            path="/proxy-path",
        )
        r2 = _request(
            url="http://api.example.test/data",
            path="/data",
        )
        ProxyAwarePathMatcher.match(r1, r2)

    def test_mismatch_raises(self) -> None:
        """Validate mismatch raises."""
        r1 = _request(url="https://example.test/a", path="/a")
        r2 = _request(url="https://example.test/b", path="/b")
        with pytest.raises(AssertionError, match="proxy_aware_path mismatch"):
            ProxyAwarePathMatcher.match(r1, r2)


class TestVCRMatcherLibrary:
    """Test suite for VCRMatcherLibrary."""

    def test_library_contains_expected_matchers(self) -> None:
        """Validate library contains expected matchers."""
        matchers = VCRMatcherLibrary.as_dict()
        assert "json_body" in matchers
        assert "proxy_aware_path" in matchers

    def test_library_values_are_callable(self) -> None:
        """Validate library values are callable."""
        matchers = VCRMatcherLibrary.as_dict()
        assert callable(matchers["json_body"])
        assert callable(matchers["proxy_aware_path"])
