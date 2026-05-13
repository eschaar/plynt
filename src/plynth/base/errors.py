# src/plynth/base/errors.py
"""Plynth Error Contract
====================

This module defines the canonical error model used by Plynth.

Plynth is a foundation library. Errors defined here are:
- transport-agnostic (no HTTP, no framework concepts),
- minimal and explicit,
- stable over time.

--------------------------------------------------------------------------
Canonical Error Shape
--------------------------------------------------------------------------

Every Plynth error can be represented as:

    {
        "message": "Human readable explanation",   # REQUIRED
        "code": "OPTIONAL_MACHINE_CODE",           # OPTIONAL
        "details": { ... }                          # OPTIONAL
    }

Field semantics:

- message (required)
    A human-readable explanation of what went wrong.
    Must be present for every error instance.
    It may be supplied explicitly when raising the error or implicitly
    via a subclass default.

- code (optional)
    A machine-readable identifier (e.g. "INVALID_INPUT").
    Useful for clients, metrics, and documentation.
    Optional by design.

- details (optional)
    Arbitrary structured data (JSON-serializable).
    This is the *single extensibility point* for additional information:
    validation errors, dependency metadata, hints, etc.

--------------------------------------------------------------------------
Design Rules
--------------------------------------------------------------------------

1) message is mandatory per instance
   - If neither an explicit message nor a subclass default exists,
     instantiation fails.

2) code and details are optional
   - Omitted fields are not included in structured output.

3) Exactly ONE extensibility point exists: `details`
   - No separate `context`, `extra`, or similar buckets.

4) `details` is accepted as any Mapping at the boundary
   - Internally it is normalized to a `dict`.
   - This avoids typing/lint issues and clarifies ownership.

5) Transport-specific mapping belongs outside core
   - HTTP status codes, headers, etc. live in an API layer.

This contract is intentionally small and strict to remain stable long-term.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class BaseError(Exception):
    """Canonical base class for all application errors in Plynth.

    - Representation: *what* went wrong (no transport or logic details)
    - Implementation: Python exception with a strict, stable contract

    Subclasses may define class-level defaults:
        - message: str | None
        - code: str | None

    Parameters
    ----------
    message : str | None
        Human-readable explanation. Explicitly provided or from subclass
        default. Required: must never be empty.

    code : str | None
        Machine-readable identifier. Overrides subclass default if given.

    details : Mapping[str, Any] | None
        Structured, JSON-serialisable data. Always normalised to a dict.

    **kwargs
        Extra key-value pairs merged into details. No second extension point.

    """

    # No __slots__: extension is constrained by documentation, type hints,
    # and the explicit contract. This avoids Python conflicts and keeps the
    # contract idiomatic and stable.

    # Subclass defaults (may be overridden per instance)
    message: str | None = None
    code: str | None = None

    # Instance state: stored as dict for clear ownership and stable output
    details: dict[str, Any] | None

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        # Resolve message: explicit argument wins, otherwise subclass default.
        """Initialize BaseError."""
        final_message = message or type(self).message
        if not final_message:
            raise ValueError(f"{self.__class__.__name__} requires a non-empty message")

        self.message = final_message
        self.code = code if code is not None else type(self).code

        # Normalize details:
        # - accept any Mapping at the boundary (e.g. Django ValidationError)
        # - store a concrete dict internally (clear ownership, no lint issues)
        if details or kwargs:
            merged: dict[str, Any] = {}
            if details:
                merged.update(details)
            merged.update(kwargs)
            self.details = merged
        else:
            self.details = None

        # Initialize Exception with the human-readable message
        super().__init__(final_message)

    def to_dict(self) -> dict[str, Any]:
        """Canonical structured representation of the error.

        Optional fields are omitted when not present.
        Subclasses may override to add extra fields, but should call super().to_dict().
        """
        data: dict[str, Any] = {"message": self.message}
        if self.code is not None:
            data["code"] = self.code
        if self.details is not None:
            data["details"] = self.details
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaseError:
        """Reconstruct an error from a dictionary. Ignores unknown fields."""
        message = data.get("message")
        code = data.get("code")
        details = data.get("details")
        return cls(message=message, code=code, details=details)

    def __str__(self) -> str:
        """Return a readable string with class name and message (if present)."""
        if self.message:
            return f"{self.__class__.__name__}: {self.message}"
        return self.__class__.__name__

    def __repr__(self) -> str:
        """Return a string representation of the BaseError instance."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"code={self.code!r}, "
            f"details={self.details!r})"
        )


# ---------------------------------------------------------------------------
# Common derived errors (base)
# ---------------------------------------------------------------------------
# These subclasses are intentionally *declarative*: they only define defaults.
# Behavior is in BaseError. This keeps maintenance low and avoids boilerplate.
# ---------------------------------------------------------------------------


class InvalidInputError(BaseError):
    """Input validation failed.

    Typical use: request data, form data, serializer data, domain validation.
    details commonly contains field-level errors, e.g.
        {"email": ["Invalid email"], "__all__": ["General issue"]}
    """

    code = "INVALID_INPUT"
    message = "Invalid input data"


class OperationFailedError(BaseError):
    """Generic operation failure.

    Use when no more specific code applies, or as a base to refine later.
    """

    code = "OPERATION_FAILED"
    message = "Operation failed"


class FeatureDisabledError(BaseError):
    """A feature is disabled / not available.

    This can represent feature flags, maintenance windows, or disabled endpoints.
    """

    code = "FEATURE_DISABLED"
    message = "Requested feature is disabled"


class DependencyUnavailableError(BaseError):
    """An external dependency is unavailable

    Example: DB down, upstream service unreachable, etc.
    """

    code = "DEPENDENCY_UNAVAILABLE"
    message = "Dependency unavailable"


class ConfigurationError(BaseError):
    """Invalid or inconsistent configuration.

    Example: missing env vars, invalid settings, malformed config files.
    """

    code = "CONFIGURATION_ERROR"
    message = "Invalid configuration"


# ---------------------------------------------------------------------------
# Transport errors
# ---------------------------------------------------------------------------
# Protocol-agnostic errors for the transport layer. Protocol-specific errors
# (HTTP, gRPC, etc.) live in their own modules (e.g. plynth.http.errors).
# ---------------------------------------------------------------------------


class TransportError(BaseError):
    """Base class for all transport-layer errors.

    Raised when sending a request or receiving a response fails at the
    transport level, regardless of protocol (HTTP, gRPC, etc.).
    """

    code = "TRANSPORT_ERROR"
    message = "A transport error occurred"


class StatusError(TransportError):
    """Raised when a response status code indicates failure.

    Protocol-agnostic: for HTTP this means a 4xx or 5xx status code;
    for gRPC this means a non-zero status code. The ``status_code``
    attribute is always available as structured detail.

    Attributes:
        status_code: The status code returned by the remote.

    Example:
        raise StatusError(status_code=404)
        raise StatusError("Account not found", status_code=404)

    """

    code = "STATUS_ERROR"
    message = "Response status indicates failure"

    def __init__(
        self,
        message: str | None = None,
        *,
        status_code: int,
        **kwargs: Any,
    ) -> None:
        """Initialise a StatusError.

        Args:
            message: Human-readable description. Falls back to the class
                default if omitted.
            status_code: Status code returned by the remote (e.g. 404, 500).
            **kwargs: Additional key-value pairs merged into ``details``.

        """
        super().__init__(message, status_code=status_code, **kwargs)
        self.status_code = status_code
