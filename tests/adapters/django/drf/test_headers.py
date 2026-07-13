"""Tests for ``plynth.adapters.django.drf.headers`` placeholders."""

import importlib


class TestBuildRequestHeaderMiddleware:
    """Verify placeholder behavior for header propagation helper."""

    def test_placeholder_header_helper_raises_not_implemented(self) -> None:
        """Verify header helper raises until WP6 implementation lands."""
        module = importlib.import_module("plynth.adapters.django.drf.headers")

        try:
            module.build_request_header_middleware(object())
        except NotImplementedError as exc:
            assert "planned but not implemented yet" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("Expected NotImplementedError")
