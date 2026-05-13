"""Lookup service category definitions."""

from __future__ import annotations

from enum import StrEnum


class LookupType(StrEnum):
    """Supported lookup service categories."""

    RECORD_TYPE = "record_type"
    USER = "user"
    PRICEBOOK = "pricebook"
    QUEUE = "queue"
    PROFILE = "profile"
