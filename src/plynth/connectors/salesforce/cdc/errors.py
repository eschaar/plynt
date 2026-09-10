"""Error types for Salesforce CDC subscribe orchestration."""

from __future__ import annotations

__all__ = [
    "SalesforceCDCGapError",
    "SalesforceCDCOverflowError",
    "SalesforceCDCReplayInvalidError",
]


class SalesforceCDCGapError(RuntimeError):
    """Raised when Salesforce reports a replay gap in the CDC stream."""


class SalesforceCDCOverflowError(RuntimeError):
    """Raised when Salesforce reports an overflow event in the CDC stream."""


class SalesforceCDCReplayInvalidError(RuntimeError):
    """Raised when Salesforce rejects a replay cursor as no longer valid.

    Salesforce retains CDC/platform events for 72 hours. Resuming from a
    replay ID outside that window (or otherwise invalid) fails the Subscribe
    RPC with an INVALID_ARGUMENT status rather than delivering a partial or
    flagged response. Retrying immediately with the same cursor will fail
    again identically, so this is not treated as a transient, reconnectable
    error. Callers must decide how to resync: resubscribe with
    ``replay_preset=EARLIEST`` (only recovers events still in the 72h
    window) or trigger a full reconciliation of the affected object(s)
    against Salesforce, since data older than the retention window is gone
    from the event bus itself and cannot be recovered from CDC alone.
    """
