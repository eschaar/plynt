"""Error types for Salesforce CDC subscribe orchestration."""

from __future__ import annotations

from plynth.base.errors import OperationFailedError

__all__ = [
    "SalesforceCDCGapError",
    "SalesforceCDCOverflowError",
    "SalesforceCDCReplayInvalidError",
]


class SalesforceCDCGapError(OperationFailedError):
    """Raised when Salesforce reports a replay gap in the CDC stream."""

    code = "SALESFORCE_CDC_GAP"
    message = "Salesforce CDC stream reported a replay gap"


class SalesforceCDCOverflowError(OperationFailedError):
    """Raised when Salesforce reports an overflow event in the CDC stream."""

    code = "SALESFORCE_CDC_OVERFLOW"
    message = "Salesforce CDC stream reported an overflow event"


class SalesforceCDCReplayInvalidError(OperationFailedError):
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

    code = "SALESFORCE_CDC_REPLAY_INVALID"
    message = "Salesforce CDC replay cursor is no longer valid"
