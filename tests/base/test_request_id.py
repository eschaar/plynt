"""Verify request ID validation and execution-context isolation"""

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from typing import cast
from uuid import UUID

import pytest

from plynt.base import RequestIDPolicy, get_request_id


class TestRequestIDPolicy:
    def test_default_generator_returns_uuid_hex(self) -> None:
        policy = RequestIDPolicy()
        request_id = policy.resolve()

        assert len(request_id) == 32
        assert UUID(hex=request_id).version == 4
        assert policy.header_name == "X-Request-ID"

    @pytest.mark.parametrize("incoming", ["a", "Abc-123_foo.bar:42", "a" * 128])
    def test_valid_inbound_id_is_retained(self, incoming: str) -> None:
        assert RequestIDPolicy().resolve(incoming) == incoming

    @pytest.mark.parametrize(
        "incoming",
        [None, "", "a" * 129, "a b", "a\r\nb", "a\n", "a\tb", "é", "a/b"],
    )
    def test_invalid_inbound_id_is_replaced(self, incoming: str | None) -> None:
        policy = RequestIDPolicy(generator=lambda: "replacement")

        assert policy.resolve(incoming) == "replacement"

    def test_untrusted_inbound_id_is_replaced(self) -> None:
        policy = RequestIDPolicy(trust_inbound=False, generator=lambda: "replacement")

        assert policy.resolve("valid") == "replacement"

    def test_custom_max_length_and_header_name(self) -> None:
        policy = RequestIDPolicy(
            max_length=3, header_name="X-Correlation-ID", generator=lambda: "new"
        )

        assert policy.resolve("abc") == "abc"
        assert policy.resolve("abcd") == "new"
        assert policy.header_name == "X-Correlation-ID"

    @pytest.mark.parametrize("header_name", ["", "A B", "X:ID", "X\nID", "é"])
    def test_invalid_header_configuration_raises(self, header_name: str) -> None:
        with pytest.raises(ValueError, match="header name"):
            RequestIDPolicy(header_name=header_name)

    @pytest.mark.parametrize("max_length", [0, -1])
    def test_non_positive_max_length_raises(self, max_length: int) -> None:
        with pytest.raises(ValueError, match="max_length"):
            RequestIDPolicy(max_length=max_length)

    def test_non_callable_generator_raises(self) -> None:
        with pytest.raises(TypeError, match="callable"):
            RequestIDPolicy(generator=cast(Callable[[], str], None))

    @pytest.mark.parametrize("value", ["", "a b", "a" * 129, None, 123])
    def test_invalid_generated_id_raises_without_echoing_value(
        self, value: object
    ) -> None:
        policy = RequestIDPolicy(generator=cast(Callable[[], str], lambda: value))

        with pytest.raises(
            ValueError, match="generator must return a valid request ID"
        ):
            policy.resolve()

    def test_generator_failure_propagates(self) -> None:
        error = RuntimeError("Generator unavailable")

        def generate() -> str:
            raise error

        with pytest.raises(RuntimeError) as caught:
            RequestIDPolicy(generator=generate).resolve()

        assert caught.value is error

    def test_nested_scope_restores_prior_id(self) -> None:
        policy = RequestIDPolicy()
        assert get_request_id() is None

        with policy.scope("outer") as request_id:
            assert request_id == "outer"
            assert get_request_id() == "outer"
            with policy.scope("inner"):
                assert get_request_id() == "inner"
            assert get_request_id() == "outer"

        assert get_request_id() is None

    def test_scope_resets_after_failure(self) -> None:
        with pytest.raises(RuntimeError):
            with RequestIDPolicy().scope("request"):
                raise RuntimeError("Request failed")

        assert get_request_id() is None

    def test_threads_need_explicit_context_copy(self) -> None:
        with ThreadPoolExecutor(max_workers=1) as executor:
            with RequestIDPolicy().scope("parent"):
                assert executor.submit(get_request_id).result() is None
                context = copy_context()
                assert executor.submit(context.run, get_request_id).result() == "parent"

            assert executor.submit(get_request_id).result() is None

    @pytest.mark.asyncio
    async def test_concurrent_tasks_have_isolated_ids(self) -> None:
        policy = RequestIDPolicy()

        async def request(value: str) -> str | None:
            with policy.scope(value):
                await asyncio.sleep(0)
                return get_request_id()

        with policy.scope("parent"):
            first, second = await asyncio.gather(request("first"), request("second"))
            assert first == "first"
            assert second == "second"
            assert get_request_id() == "parent"

        assert get_request_id() is None
