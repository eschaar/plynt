"""Tests for ``plynth.adapters.django.transport`` placeholders."""

import importlib


class TestTransportFromDjangoSettings:
    """Verify placeholder behavior for transport factory."""

    def test_placeholder_transport_helper_raises_not_implemented(self) -> None:
        """Verify transport helper raises until WP4 implementation lands."""
        module = importlib.import_module("plynth.adapters.django.transport")

        try:
            module.transport_from_django_settings("SERVICE", object)
        except NotImplementedError as exc:
            assert "planned but not implemented yet" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("Expected NotImplementedError")
