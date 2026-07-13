"""Tests for ``plynth.adapters.django.cache`` placeholders."""

import importlib

import pytest


class TestDjangoCacheBackend:
    """Verify placeholder behavior for ``DjangoCacheBackend``."""

    def test_placeholder_cache_backend_raises_not_implemented(self) -> None:
        """Verify cache backend raises until WP3 implementation lands."""
        module = importlib.import_module("plynth.adapters.django.cache")

        with pytest.raises(
            NotImplementedError, match="planned but not implemented yet"
        ):
            module.DjangoCacheBackend()
