"""Django framework adapter surface for Plynt.

This package is the Django-core adapter boundary. It will expose helpers for
loading typed plynt settings from Django settings, reusing Django cache
aliases, and constructing plynt transports from Django-native configuration.

DRF-specific helpers live under ``plynt.adapters.django.drf`` so Django-core
users do not need Django REST Framework installed.
"""

from plynt.adapters.django.cache import DjangoCacheBackend
from plynt.adapters.django.settings import from_django_settings
from plynt.adapters.django.transport import (
    async_transport_from_django_settings,
    transport_from_django_settings,
)

__all__ = [
    "DjangoCacheBackend",
    "async_transport_from_django_settings",
    "from_django_settings",
    "transport_from_django_settings",
]
