"""Focused tests for gRPC errors and interceptor protocol contracts."""

from __future__ import annotations

from typing import cast

import pytest

from plynth.grpc.errors import GrpcStatusError
from plynth.grpc.handler import GrpcCall
from plynth.grpc.interceptor import AsyncGrpcInterceptor


class TestGrpcErrorContract:
    """Verify gRPC error contract behavior."""

    def test_status_error_preserves_method(self) -> None:
        """Validate method is preserved for downstream diagnostics."""
        error = GrpcStatusError(
            "failure",
            status_code=14,
            method="/svc.v1.Health/Check",
        )

        assert error.method == "/svc.v1.Health/Check"


class TestGrpcInterceptorContract:
    """Verify interceptor protocol primitives."""

    def test_call_dataclass_defaults_timeout_to_none(self) -> None:
        """Validate GrpcCall timeout default for call envelopes."""
        call = GrpcCall(method="/svc.v1.Health/Check", request={}, metadata={})

        assert call.timeout is None

    @pytest.mark.asyncio
    async def test_protocol_handle_stub_raises_not_implemented(self) -> None:
        """Validate protocol stub behavior when invoked directly."""

        async def _next_handler(call: GrpcCall) -> object:
            return {"method": call.method}

        with pytest.raises(NotImplementedError):
            await AsyncGrpcInterceptor.handle(
                cast(AsyncGrpcInterceptor, object()),
                GrpcCall(method="/svc.v1.Health/Check", request={}, metadata={}),
                _next_handler,
            )
