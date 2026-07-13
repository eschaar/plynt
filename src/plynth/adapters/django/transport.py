"""Django transport helper placeholders for Plynth.

Concrete transport-wiring behavior will be added in WP4.
"""

from __future__ import annotations

from typing import Any

__all__ = ["transport_from_django_settings"]


def transport_from_django_settings(
    name: str,
    settings_class: type[Any],
    *,
    settings_obj: object | None = None,
    response_cache_alias: str | None = None,
    auth_cache_alias: str | None = None,
    middlewares: list[object] | None = None,
) -> Any:  # pragma: no cover - placeholder until WP4
    """Placeholder helper for building a plynth transport from Django config.

    The implementation is intentionally deferred to WP4. This placeholder keeps
    the public import surface stable while WP1 establishes package structure.
    """
    del (
        name,
        settings_class,
        settings_obj,
        response_cache_alias,
        auth_cache_alias,
        middlewares,
    )
    raise NotImplementedError(
        "transport_from_django_settings is planned but not implemented yet"
    )
