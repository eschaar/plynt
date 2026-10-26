"""Verify isolation and lifecycle of deterministic test clocks"""

from __future__ import annotations

import asyncio
import time
from importlib import import_module

import pytest

from tests.conftest import MonotonicClock


class TestMonotonicClock:
    """Verify the shared elapsed-time fixture"""

    def test_starts_at_zero_and_advances(self, monotonic_clock: MonotonicClock) -> None:
        assert monotonic_clock.monotonic() == 0.0
        monotonic_clock.advance(1.5)
        monotonic_clock.advance(0.0)
        assert monotonic_clock.monotonic() == 1.5

    @pytest.mark.parametrize(
        "seconds", [-1.0, float("nan"), float("inf"), float("-inf")]
    )
    def test_rejects_invalid_advances(
        self, monotonic_clock: MonotonicClock, seconds: float
    ) -> None:
        with pytest.raises(ValueError, match="finite and non-negative"):
            monotonic_clock.advance(seconds)
        assert monotonic_clock.monotonic() == 0.0

    def test_binding_restores_module_without_mutating_global_time(self) -> None:
        module = import_module("plynt.cache.locmem")
        original_time = module.time
        original_monotonic = time.monotonic

        with pytest.MonkeyPatch.context() as scoped:
            clock = MonotonicClock(scoped)
            clock.bind("plynt.cache.locmem")
            clock.advance(5.0)
            assert module.time.monotonic() == 5.0
            assert module.time.sleep is time.sleep
            assert time.monotonic is original_monotonic

        assert module.time is original_time
        assert time.monotonic is original_monotonic

    @pytest.mark.asyncio
    async def test_binding_does_not_freeze_asyncio(
        self, monotonic_clock: MonotonicClock
    ) -> None:
        original_monotonic = time.monotonic
        monotonic_clock.bind("plynt.cache.locmem")
        monotonic_clock.advance(1000.0)

        assert time.monotonic is original_monotonic
        await asyncio.wait_for(asyncio.sleep(0), timeout=1.0)
