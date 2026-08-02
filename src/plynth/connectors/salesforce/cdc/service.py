"""Async Salesforce CDC contract skeleton."""

from __future__ import annotations

from collections.abc import AsyncIterator

from plynth.connectors.salesforce.cdc.models import (
    SalesforceCDCEvent,
    SalesforceCDCSubscribeRequest,
)

__all__ = ["AsyncSalesforceCDCSubscriber"]


class _UnimplementedCDCStream(AsyncIterator[SalesforceCDCEvent]):
    """Raise a clear error when CDC iteration is attempted."""

    def __aiter__(self) -> _UnimplementedCDCStream:
        return self

    async def __anext__(self) -> SalesforceCDCEvent:
        raise NotImplementedError(
            "Salesforce CDC subscription transport is not implemented yet"
        )


# pylint: disable=too-few-public-methods
class AsyncSalesforceCDCSubscriber:
    """Define the async Salesforce CDC subscription contract."""

    async def subscribe(
        self,
        request: SalesforceCDCSubscribeRequest,
    ) -> AsyncIterator[SalesforceCDCEvent]:
        """Return the CDC stream contract for a subscription request."""
        del request
        return _UnimplementedCDCStream()
