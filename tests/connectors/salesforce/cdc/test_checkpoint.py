"""Focused tests for Salesforce CDC checkpoint store primitives."""

from __future__ import annotations

from typing import Any

import pytest

from plynth.cache import LocMemCache
from plynth.connectors.salesforce.cdc.checkpoint import (
    CacheSalesforceCDCCheckpointStore,
    InMemorySalesforceCDCCheckpointStore,
    SalesforceCDCCheckpointStore,
)


class TestSalesforceCDCCheckpointStore:
    """Verify incomplete explicitly inherited stores fail on persistence calls"""

    @pytest.mark.parametrize(
        ("method", "arguments"),
        [
            ("load", ("/data/AccountChangeEvent",)),
            ("save", ("/data/AccountChangeEvent", 42)),
            ("delete", ("/data/AccountChangeEvent",)),
        ],
    )
    def test_unimplemented_operation_raises(
        self, method: str, arguments: tuple[str | int, ...]
    ) -> None:
        class IncompleteStore(SalesforceCDCCheckpointStore):
            pass

        store_type: type[Any] = IncompleteStore
        store = store_type()

        with pytest.raises(NotImplementedError):
            getattr(store, method)(*arguments)


class TestInMemorySalesforceCDCCheckpointStore:
    """Verify local development checkpoint storage behavior."""

    def test_load_save_and_delete(self) -> None:
        """Persist one replay cursor and remove it again."""
        store = InMemorySalesforceCDCCheckpointStore()

        assert store.load("/data/AccountChangeEvent") is None

        store.save("/data/AccountChangeEvent", 42)

        assert store.load("/data/AccountChangeEvent") == 42

        store.delete("/data/AccountChangeEvent")

        assert store.load("/data/AccountChangeEvent") is None


class TestCacheSalesforceCDCCheckpointStore:
    """Verify checkpoint persistence through the generic cache backend."""

    def test_load_save_and_delete(self) -> None:
        """Round-trip a replay cursor through ``LocMemCache``."""
        store = CacheSalesforceCDCCheckpointStore(LocMemCache())

        assert store.load("/data/AccountChangeEvent") is None

        store.save("/data/AccountChangeEvent", 99)

        assert store.load("/data/AccountChangeEvent") == 99

        store.delete("/data/AccountChangeEvent")

        assert store.load("/data/AccountChangeEvent") is None
