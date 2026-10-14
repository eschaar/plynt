"""Reusable class-based VCR matchers for testsupport."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NormalizedJSONBodyMatcher:
    """Matcher that compares JSON request bodies semantically.

    - Dict key order does not matter.
    - List order: significant by default; set ``sort_lists=True`` to ignore it.
    - For non-JSON content types, falls back to VCR's body matcher.
    """

    sort_lists: bool = False

    @staticmethod
    def _header_value(headers: Any, key: str) -> str:
        """Handle header value."""
        value = headers.get(key) if hasattr(headers, "get") else None
        if isinstance(value, list):
            return str(value[0]) if value else ""
        return str(value or "")

    def _content_type(self, request: Any) -> str:
        """Handle content type."""
        headers = getattr(request, "headers", {})
        for name in ("Content-Type", "content-type"):
            value = self._header_value(headers, name).lower()
            if value:
                return value
        return ""

    @staticmethod
    def _decode_json(body: bytes | str | None) -> Any:
        """Handle decode json."""
        if body is None or body == b"" or body == "":
            return None
        if isinstance(body, bytes):
            payload = body.decode("utf-8")
        else:
            payload = body
        return json.loads(payload)

    def _normalize(self, value: Any) -> Any:
        """Handle normalize."""
        if isinstance(value, dict):
            return {k: self._normalize(v) for k, v in sorted(value.items())}
        if isinstance(value, list):
            normalized = [self._normalize(item) for item in value]
            if self.sort_lists:
                return sorted(
                    normalized,
                    key=lambda item: json.dumps(item, sort_keys=True),
                )
            return normalized
        return value

    def match(self, r1: Any, r2: Any) -> None:
        """Compare two VCR requests by JSON body semantics."""
        if "application/json" not in self._content_type(r1):
            from vcr.matchers import body as body_matcher

            body_matcher(r1, r2)
            return

        b1 = self._normalize(self._decode_json(getattr(r1, "body", None)))
        b2 = self._normalize(self._decode_json(getattr(r2, "body", None)))
        if b1 != b2:
            msg = f"JSON body mismatch: {b1!r} != {b2!r}"
            raise AssertionError(msg)


@dataclass(frozen=True)
class ProxyAwarePathMatcher:
    """Matcher that tolerates proxy-prefixed URL/path representations."""

    @staticmethod
    def _plain_equal(r1: Any, r2: Any) -> bool:
        """Handle plain equal."""
        return getattr(r1, "url", "") == getattr(r2, "url", "") or getattr(
            r1, "uri", ""
        ) == getattr(r2, "uri", "")

    @staticmethod
    def _path_equal(r1: Any, r2: Any) -> bool:
        """Handle path equal."""
        r1_path = str(getattr(r1, "path", "") or "")
        if r1_path:
            match = re.search(r"^(//[^/]+)(/.*)", r1_path)
            if match and match.lastindex == 2:
                r1_path = match.group(2)
        return r1_path == str(getattr(r2, "path", "") or "")

    @staticmethod
    def _proxy_env_equal(r1: Any, r2: Any) -> bool:
        """Handle proxy env equal."""
        proxy = (
            os.environ.get("HTTP_PROXY")
            or os.environ.get("http_proxy")
            or os.environ.get("HTTPS_PROXY")
            or os.environ.get("https_proxy")
        )
        if not proxy:
            return False

        r1_url = str(getattr(r1, "url", "") or "")
        r2_url = str(getattr(r2, "url", "") or "")
        r1_clean = re.sub(r"http[s]?://(http[s]?://)", r"\1", r1_url.replace(proxy, ""))
        r2_clean = re.sub(r"http[s]?://(http[s]?://)", r"\1", r2_url.replace(proxy, ""))
        return r1_clean == r2_clean

    @classmethod
    def match(cls, r1: Any, r2: Any) -> None:
        """Compare two VCR requests with proxy-aware path tolerance."""
        if (
            cls._plain_equal(r1, r2)
            or cls._path_equal(r1, r2)
            or cls._proxy_env_equal(r1, r2)
        ):
            return
        msg = "proxy_aware_path mismatch"
        raise AssertionError(msg)


class VCRMatcherLibrary:
    """Factory helpers for registering class-based matcher callables."""

    @staticmethod
    def as_dict() -> dict[str, Any]:
        """Return built-in matcher map ready for VCRSettings.custom_matchers."""
        return {
            "json_body": NormalizedJSONBodyMatcher().match,
            "proxy_aware_path": ProxyAwarePathMatcher.match,
        }
