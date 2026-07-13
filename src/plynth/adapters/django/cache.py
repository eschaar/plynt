"""Django cache backend bridge for plynth cache middleware."""

from __future__ import annotations

import base64
import binascii
import importlib
import math
from collections.abc import Mapping
from typing import Any

from plynth.base.cache import CacheBackend
from plynth.base.request import Request
from plynth.base.response import Response

__all__ = ["DjangoCacheBackend"]


class DjangoCacheBackend:
    """Adapt ``django.core.cache`` aliases to the plynth ``CacheBackend`` API.

    ``Response`` values are stored in an explicit schema-marked representation
    so cache contents remain versionable and safe to deserialize across
    deployments.
    """

    _SCHEMA_VERSION = 1
    _RESPONSE_MARKER = "plynth.response"

    def __init__(self, alias: str = "default") -> None:
        """Create a backend wrapper for one Django cache alias.

        Args:
            alias: Django cache alias key from ``django.core.cache.caches``.

        Raises:
            ImportError: If Django is unavailable in the runtime environment.
            KeyError: If the requested alias does not exist.

        """
        self.alias = alias
        self._cache = self._resolve_cache(alias)

    def get(self, key: str, default: Any = None) -> Any:
        """Return one cache value, deserializing ``Response`` payloads safely."""
        value = self._cache.get(key, default)
        if not isinstance(value, Mapping):
            return value

        if not self._is_response_payload(value):
            return value

        response = self._deserialize_response(value)
        return default if response is None else response

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store one value and map plynth TTL semantics onto Django timeout."""
        stored_value = (
            self._serialize_response(value) if isinstance(value, Response) else value
        )
        self._cache.set(key, stored_value, timeout=self._django_timeout(ttl))

    def delete(self, key: str) -> None:
        """Delete one value by key."""
        self._cache.delete(key)

    def clear(self) -> None:
        """Clear all values from the underlying alias."""
        self._cache.clear()

    @staticmethod
    def cache_key(request: Request) -> str:
        """Build the canonical cache key using the shared core helper."""
        return CacheBackend.cache_key(request)

    @staticmethod
    def _resolve_cache(alias: str) -> Any:
        """Return the Django cache backend object for one alias."""
        try:
            django_cache_module = importlib.import_module("django.core.cache")
        except ImportError as exc:
            raise ImportError(
                "Django is required for DjangoCacheBackend. "
                "Install plynth with the 'django' extra."
            ) from exc

        caches = django_cache_module.caches
        alias_error_types: tuple[type[BaseException], ...] = (KeyError,)
        invalid_cache_backend_error = getattr(
            django_cache_module,
            "InvalidCacheBackendError",
            None,
        )
        if isinstance(invalid_cache_backend_error, type) and issubclass(
            invalid_cache_backend_error, Exception
        ):
            alias_error_types = (KeyError, invalid_cache_backend_error)

        try:
            return caches[alias]
        except alias_error_types as exc:
            raise KeyError(f"Unknown Django cache alias: {alias!r}") from exc

    @classmethod
    def _is_response_payload(cls, payload: Mapping[str, Any]) -> bool:
        """Return whether the mapping looks like a stored plynth ``Response``."""
        return payload.get("kind") == cls._RESPONSE_MARKER

    @classmethod
    def _serialize_response(cls, response: Response) -> dict[str, Any]:
        """Serialize a neutral ``Response`` into an explicit cache payload."""
        return {
            "schema_version": cls._SCHEMA_VERSION,
            "kind": cls._RESPONSE_MARKER,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content_b64": base64.b64encode(response.content).decode("ascii"),
        }

    @classmethod
    def _deserialize_response(cls, payload: Mapping[str, Any]) -> Response | None:
        """Deserialize one cache payload into ``Response`` or ``None`` on failure."""
        if payload.get("schema_version") != cls._SCHEMA_VERSION:
            return None

        status_code = payload.get("status_code")
        headers = payload.get("headers")
        content_b64 = payload.get("content_b64")

        if not isinstance(status_code, int):
            return None
        if not isinstance(headers, Mapping):
            return None
        if not isinstance(content_b64, str):
            return None

        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in headers.items()
        ):
            return None

        try:
            content = base64.b64decode(content_b64.encode("ascii"), validate=True)
        except (binascii.Error, ValueError):
            return None

        return Response(
            status_code=status_code,
            headers=dict(headers),
            content=content,
        )

    @staticmethod
    def _django_timeout(ttl: float | None) -> int | None:
        """Translate plynth TTL seconds into Django cache timeout semantics."""
        if ttl is None:
            return None
        return max(0, math.ceil(ttl))
