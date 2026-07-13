"""DRF header propagation placeholders for Plynth.

Concrete DRF behavior will be added in WP6.
"""

from __future__ import annotations

from typing import Any

__all__ = ["build_request_header_middleware"]


def build_request_header_middleware(
    request: object,
    headers: dict[str, str] | None = None,
) -> Any:  # pragma: no cover - placeholder until WP6
    """Placeholder DRF request-header propagation helper.

    The implementation is intentionally deferred to WP6. This placeholder keeps
    the DRF import surface stable while WP1 establishes package structure.
    """
    del request, headers
    raise NotImplementedError(
        "build_request_header_middleware is planned but not implemented yet"
    )
