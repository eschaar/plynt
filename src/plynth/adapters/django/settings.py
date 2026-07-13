"""Load typed plynth settings objects from Django settings mappings."""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from typing import Any, Generic, TypeVar

from pydantic_settings import BaseSettings

__all__ = ["from_django_settings"]

SettingsT = TypeVar("SettingsT", bound=BaseSettings)


class _DjangoSettingsLoader(Generic[SettingsT]):
    """Load one typed settings object from a Django settings container."""

    def __init__(
        self,
        name: str,
        settings_class: type[SettingsT],
        *,
        settings_obj: object | None = None,
    ) -> None:
        if not isinstance(settings_class, type) or not issubclass(
            settings_class, BaseSettings
        ):
            raise TypeError("settings_class must be a BaseSettings subclass")

        self._name = name
        self._settings_class = settings_class
        self._settings_obj = settings_obj

    def load(self) -> SettingsT:
        """Build the target settings object from the configured source."""
        payload = self._read_mapping()
        normalized_payload = self._normalize_keys(payload)
        return self._settings_class(**normalized_payload)

    def _read_mapping(self) -> Mapping[str, Any]:
        """Return the named Django settings block as a mapping."""
        settings_obj = self._settings_obj or _load_default_settings_object()

        try:
            raw_value = getattr(settings_obj, self._name)
        except AttributeError as exc:
            raise KeyError(
                f"Django settings object has no setting named {self._name!r}"
            ) from exc

        if not isinstance(raw_value, Mapping):
            raise TypeError(
                f"Django setting {self._name!r} must be a mapping, "
                f"got {type(raw_value).__name__}"
            )

        return raw_value

    def _normalize_keys(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Map uppercase Django-style keys onto known plynth field names."""
        normalized: dict[str, Any] = {}
        field_names = set(self._settings_class.model_fields)

        for key, value in payload.items():
            if isinstance(key, str) and key in field_names:
                normalized[key] = value

        for key, value in payload.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"Django setting {self._name!r} must use only string keys"
                )

            lowered_key = key.lower()
            if lowered_key in field_names:
                normalized.setdefault(lowered_key, value)

        return normalized


def _load_default_settings_object() -> object:
    """Resolve ``django.conf.settings`` lazily."""
    try:
        django_conf = importlib.import_module("django.conf")
    except ImportError as exc:  # pragma: no cover - exercised without Django extra
        raise ImportError(
            "Django is required when settings_obj is not provided. "
            "Install plynth with the 'django' extra or pass settings_obj explicitly."
        ) from exc

    return django_conf.settings


def from_django_settings(
    name: str,
    settings_class: type[SettingsT],
    *,
    settings_obj: object | None = None,
) -> SettingsT:
    """Return a typed plynth settings object from a Django settings mapping.

    Args:
        name: Attribute name on the Django settings object.
        settings_class: Target plynth settings class to instantiate.
        settings_obj: Optional settings-like object used instead of
            ``django.conf.settings``.

    """
    return _DjangoSettingsLoader(
        name,
        settings_class,
        settings_obj=settings_obj,
    ).load()
