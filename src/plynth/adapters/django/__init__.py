"""Django framework adapter surface for Plynth.

This package is the Django-core adapter boundary. It will expose helpers for
loading typed plynth settings from Django settings, reusing Django cache
aliases, and constructing plynth transports from Django-native configuration.

DRF-specific helpers live under ``plynth.adapters.django.drf`` so Django-core
users do not need Django REST Framework installed.
"""

from plynth.adapters.django.cache import DjangoCacheBackend
from plynth.adapters.django.settings import from_django_settings
from plynth.adapters.django.transport import (
    async_transport_from_django_settings,
    transport_from_django_settings,
)

__all__ = [
    "DjangoCacheBackend",
    "async_transport_from_django_settings",
    "from_django_settings",
    "transport_from_django_settings",
]
