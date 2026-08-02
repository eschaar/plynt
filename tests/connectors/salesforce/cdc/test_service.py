"""Tests for the Salesforce CDC subscriber contract."""

from __future__ import annotations

import inspect

import pytest

from plynth.connectors.salesforce.cdc import (
    AsyncSalesforceCDCSubscriber,
    SalesforceCDCSubscribeRequest,
)


class TestAsyncSalesforceCDCSubscriber:
    """Test suite for the async CDC subscriber skeleton."""

    def test_subscribe_contract_accepts_only_generic_request(self) -> None:
        """Keep the async contract focused on a generic subscription request."""
        signature = inspect.signature(AsyncSalesforceCDCSubscriber.subscribe)

        assert list(signature.parameters) == ["self", "request"]
        assert signature.return_annotation is not inspect.Signature.empty

    @pytest.mark.asyncio
    async def test_subscribe_is_placeholder_behavior(self) -> None:
        """Raise a clear placeholder error until transport wiring exists."""
        subscriber = AsyncSalesforceCDCSubscriber()
        stream = await subscriber.subscribe(
            SalesforceCDCSubscribeRequest(channel="/data/AccountChangeEvent")
        )

        with pytest.raises(
            NotImplementedError, match="Salesforce CDC subscription transport"
        ):
            await anext(stream)
