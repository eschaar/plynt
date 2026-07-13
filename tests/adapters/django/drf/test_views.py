"""Tests for ``plynth.adapters.django.drf.views`` placeholders."""

import importlib


class TestPlynthServiceMixin:
    """Verify placeholder class surface for DRF view integration."""

    def test_exports_placeholder_mixin(self) -> None:
        """Verify module exposes the placeholder mixin class."""
        module = importlib.import_module("plynth.adapters.django.drf.views")

        assert module.PlynthServiceMixin.__name__ == "PlynthServiceMixin"
