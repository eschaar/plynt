"""Focused tests for Salesforce CDC checkpoint store primitives."""

from __future__ import annotations

from plynth.cache import LocMemCache
from plynth.connectors.salesforce.cdc.checkpoint import (
    CacheBackendSalesforceCDCCheckpointStore,
    InMemorySalesforceCDCCheckpointStore,
)


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


class TestCacheBackendSalesforceCDCCheckpointStore:
    """Verify checkpoint persistence through the generic cache backend."""

    def test_load_save_and_delete(self) -> None:
        """Round-trip a replay cursor through ``LocMemCache``."""
        store = CacheBackendSalesforceCDCCheckpointStore(LocMemCache())

        assert store.load("/data/AccountChangeEvent") is None

        store.save("/data/AccountChangeEvent", 99)

        assert store.load("/data/AccountChangeEvent") == 99

        store.delete("/data/AccountChangeEvent")

        assert store.load("/data/AccountChangeEvent") is None
