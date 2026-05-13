"""Typed configuration for VCR-backed testsupport."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

HeaderRule = tuple[str, str | None]
MatcherFunc = Callable[[object, object], None]


class VCRMissError(RuntimeError):
    """Raised when replay mode cannot find a matching interaction."""


class VCRMode(StrEnum):
    """Supported replay/record modes for VCR-backed middleware."""

    NONE = "none"
    ONCE = "once"
    NEW_EPISODES = "new_episodes"
    ALL = "all"
    PASSTHROUGH = "passthrough"


class StateTrackingMode(StrEnum):
    """State tracking strategy for anti-stale matching."""

    OFF = "off"
    RESOURCE = "resource"
    GLOBAL = "global"


@dataclass(frozen=True)
class StateTrackingSettings:
    """State tracking settings for anti-stale matching."""

    mode: StateTrackingMode = StateTrackingMode.OFF
    revision_header_name: str = "X-Plynth-State-Revision"
    mutating_methods: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})
    success_status_min: int = 200
    success_status_max: int = 299


@dataclass(frozen=True)
class VCRSettings:
    """Typed VCR middleware settings."""

    mode: VCRMode = VCRMode.NONE
    match_on: tuple[str, ...] = (
        "method",
        "scheme",
        "host",
        "port",
        "path",
        "query",
        "body",
    )
    filter_headers: tuple[HeaderRule, ...] = ()
    decode_compressed_response: bool = True
    allow_playback_repeats: bool = False
    custom_matchers: dict[str, MatcherFunc] = field(default_factory=dict)
    state_tracking: StateTrackingSettings = field(default_factory=StateTrackingSettings)
