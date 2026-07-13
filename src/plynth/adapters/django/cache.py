"""Django cache adapter placeholders for Plynth.

Concrete cache-bridge behavior will be added in WP3.
"""

__all__ = ["DjangoCacheBackend"]


class DjangoCacheBackend:  # pragma: no cover - placeholder until WP3
    """Placeholder Django cache backend.

    The implementation is intentionally deferred to WP3. This placeholder keeps
    the package boundary stable while WP1 establishes packaging and import
    surfaces.
    """

    def __init__(self, alias: str = "default") -> None:
        self.alias = alias
        raise NotImplementedError(
            "DjangoCacheBackend is planned but not implemented yet"
        )
