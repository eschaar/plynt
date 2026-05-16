"""Tests for Salesforce throttle signal normalization.

Validates that Salesforce-specific response shapes — the ``Sforce-Limit-Info``
quota header and the ``REQUEST_LIMIT_EXCEEDED`` 429 body — are correctly
normalized into generic ``ThrottleSignal`` instances by the connector-level
helper ``_salesforce_quota_signal`` and the shared ``_extract_throttle_signal``
middleware function.
"""

# pylint: disable=protected-access
from __future__ import annotations

import json

from plynth.base.response import Response
from plynth.connectors.salesforce.utility import _salesforce_quota_signal
from plynth.middleware.throttle import _extract_throttle_signal

# ---------------------------------------------------------------------------
# Salesforce quota-exhaustion signal normalization
# ---------------------------------------------------------------------------


class TestSalesforceQuotaSignal:
    """Tests for _salesforce_quota_signal normalization from Sforce-Limit-Info."""

    def test_quota_exhausted_returns_detected_signal(self) -> None:
        """Quota exhausted (used == limit) produces a detected ThrottleSignal."""
        response = Response(
            status_code=200,
            headers={"Sforce-Limit-Info": "api-usage=5000000/5000000"},
            content=b"",
        )
        signal = _salesforce_quota_signal(response)
        assert signal is not None
        assert signal.detected is True

    def test_quota_over_limit_returns_detected_signal(self) -> None:
        """used > limit (edge case) also produces a detected signal."""
        response = Response(
            status_code=200,
            headers={"Sforce-Limit-Info": "api-usage=5000001/5000000"},
            content=b"",
        )
        signal = _salesforce_quota_signal(response)
        assert signal is not None
        assert signal.detected is True

    def test_quota_not_exhausted_returns_none(self) -> None:
        """Quota not yet exhausted (used < limit) returns None."""
        response = Response(
            status_code=200,
            headers={"Sforce-Limit-Info": "api-usage=4999999/5000000"},
            content=b"",
        )
        assert _salesforce_quota_signal(response) is None

    def test_quota_well_below_limit_returns_none(self) -> None:
        """Low API usage returns None (not detected)."""
        response = Response(
            status_code=200,
            headers={"Sforce-Limit-Info": "api-usage=1/5000000"},
            content=b"",
        )
        assert _salesforce_quota_signal(response) is None

    def test_missing_sforce_limit_info_returns_none(self) -> None:
        """Absent Sforce-Limit-Info header returns None."""
        response = Response(status_code=200, headers={}, content=b"")
        assert _salesforce_quota_signal(response) is None

    def test_sforce_limit_info_header_case_insensitive(self) -> None:
        """Sforce-Limit-Info is matched case-insensitively."""
        response = Response(
            status_code=200,
            headers={"sforce-limit-info": "api-usage=5000000/5000000"},
            content=b"",
        )
        signal = _salesforce_quota_signal(response)
        assert signal is not None
        assert signal.detected is True

    def test_zero_limit_returns_none(self) -> None:
        """A zero limit is treated as an unusable quota — returns None."""
        response = Response(
            status_code=200,
            headers={"Sforce-Limit-Info": "api-usage=0/0"},
            content=b"",
        )
        assert _salesforce_quota_signal(response) is None

    def test_multiple_chunks_in_header_detects_exhaustion(self) -> None:
        """Multiple comma-separated Sforce-Limit-Info chunks are parsed correctly."""
        response = Response(
            status_code=200,
            headers={"Sforce-Limit-Info": "api-usage=5000000/5000000, extra=1/2"},
            content=b"",
        )
        signal = _salesforce_quota_signal(response)
        assert signal is not None
        assert signal.detected is True


# ---------------------------------------------------------------------------
# Generic signal extraction with Salesforce response shapes
# ---------------------------------------------------------------------------


class TestExtractThrottleSignalSalesforceShapes:
    """Tests for _extract_throttle_signal using Salesforce-shaped responses.

    Validates that standard signals sent by the Salesforce platform are
    normalized correctly by the shared middleware extraction logic.
    """

    def test_salesforce_429_request_limit_exceeded_is_detected(self) -> None:
        """Salesforce 429 REQUEST_LIMIT_EXCEEDED response is detected as throttle."""
        body = json.dumps(
            [
                {
                    "errorCode": "REQUEST_LIMIT_EXCEEDED",
                    "message": "TotalRequests Limit exceeded.",
                }
            ]
        ).encode()
        response = Response(
            status_code=429,
            headers={"Retry-After": "300"},
            content=body,
        )
        signal = _extract_throttle_signal(response)
        assert signal.detected is True
        assert signal.retry_after_seconds == 300.0

    def test_salesforce_429_without_retry_after_still_detected(self) -> None:
        """Salesforce 429 without Retry-After is still a detected throttle signal."""
        body = json.dumps(
            [
                {
                    "errorCode": "REQUEST_LIMIT_EXCEEDED",
                    "message": "TotalRequests Limit exceeded.",
                }
            ]
        ).encode()
        response = Response(status_code=429, headers={}, content=body)
        signal = _extract_throttle_signal(response)
        assert signal.detected is True
        assert signal.retry_after_seconds is None

    def test_salesforce_503_with_retry_after_is_detected(self) -> None:
        """Salesforce 503 with Retry-After is treated as a throttle signal."""
        response = Response(
            status_code=503,
            headers={"Retry-After": "60"},
            content=b"Service Unavailable",
        )
        signal = _extract_throttle_signal(response)
        assert signal.detected is True
        assert signal.retry_after_seconds == 60.0

    def test_salesforce_503_without_retry_after_is_not_detected(self) -> None:
        """Salesforce 503 without Retry-After is a server error, not throttle."""
        response = Response(
            status_code=503,
            headers={},
            content=b"Service Unavailable",
        )
        signal = _extract_throttle_signal(response)
        assert signal.detected is False

    def test_salesforce_429_with_ratelimit_reset_header(self) -> None:
        """X-RateLimit-Reset on a Salesforce 429 is captured as reset_at_seconds."""
        response = Response(
            status_code=429,
            headers={"Retry-After": "120", "X-RateLimit-Reset": "1748100000"},
            content=b"",
        )
        signal = _extract_throttle_signal(response)
        assert signal.detected is True
        assert signal.retry_after_seconds == 120.0
        assert signal.reset_at_seconds == 1_748_100_000.0

    def test_sforce_limit_info_alone_is_not_detected_by_generic_extractor(self) -> None:
        """Sforce-Limit-Info exhaustion requires _salesforce_quota_signal.

        The generic _extract_throttle_signal does not read Sforce-Limit-Info.
        Callers that want to detect Salesforce quota exhaustion must use
        _salesforce_quota_signal in addition to _extract_throttle_signal.
        """
        response = Response(
            status_code=200,
            headers={"Sforce-Limit-Info": "api-usage=5000000/5000000"},
            content=b"",
        )
        generic_signal = _extract_throttle_signal(response)
        salesforce_signal = _salesforce_quota_signal(response)

        assert generic_signal.detected is False
        assert salesforce_signal is not None
        assert salesforce_signal.detected is True
