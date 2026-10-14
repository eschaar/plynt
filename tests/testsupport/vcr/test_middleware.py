from __future__ import annotations

from pathlib import Path

import pytest

from plynt.base.request import Request as PlyntRequest
from plynt.base.response import Response as PlyntResponse
from plynt.testsupport.vcr import (
    AsyncVCRMiddleware,
    StateTrackingMode,
    StateTrackingSettings,
    VCRMiddleware,
    VCRMissError,
    VCRMode,
    VCRSession,
    VCRSettings,
    use_vcr,
)
from tests.testsupport.vcr._helpers import AsyncResponder, SyncResponder, req, resp


class TestVCRMiddleware:
    """Test suite for VCRMiddleware."""

    def test_replay_raises_when_no_match(self, tmp_path: Path) -> None:
        """Validate replay raises when no match."""
        middleware = VCRMiddleware(
            cassette_path=str(tmp_path / "missing.yaml"),
            settings=VCRSettings(mode=VCRMode.NONE),
        )

        with pytest.raises(VCRMissError):
            middleware.handle(
                req("GET", "https://example.test/items/1"),
                lambda _: resp(200, b"{}"),
            )

    def test_replay_succeeds_for_existing_cassette(self, tmp_path: Path) -> None:
        """Validate replay succeeds for existing cassette."""
        cassette_path = tmp_path / "once.yaml"
        record_settings = VCRSettings(mode=VCRMode.NEW_EPISODES)
        record_mw = VCRMiddleware(
            cassette_path=str(cassette_path), settings=record_settings
        )
        record_mw.handle(
            req("GET", "https://example.test/items/1"),
            SyncResponder([resp(200, b"recorded")]),
        )

        replay_mw = VCRMiddleware(
            cassette_path=str(cassette_path),
            settings=VCRSettings(mode=VCRMode.NONE),
        )
        replayed = replay_mw.handle(
            req("GET", "https://example.test/items/1"),
            lambda _: resp(500, b"should not be called"),
        )
        assert replayed.content == b"recorded"

    def test_record_then_replay_sync(self, tmp_path: Path) -> None:
        """Validate record then replay sync."""
        cassette_path = tmp_path / "sync.yaml"
        settings = VCRSettings(mode=VCRMode.NEW_EPISODES)
        middleware = VCRMiddleware(cassette_path=str(cassette_path), settings=settings)
        responder = SyncResponder([resp(200, b"first")])

        first = middleware.handle(req("GET", "https://example.test/items/1"), responder)
        assert first.content == b"first"
        assert responder.calls == 1

        second = middleware.handle(
            req("GET", "https://example.test/items/1"),
            responder,
        )
        assert second.content == b"first"
        assert responder.calls == 1

    async def test_record_then_replay_async(self, tmp_path: Path) -> None:
        """Validate record then replay async."""
        cassette_path = tmp_path / "async.yaml"
        settings = VCRSettings(mode=VCRMode.NEW_EPISODES)
        middleware = AsyncVCRMiddleware(
            cassette_path=str(cassette_path),
            settings=settings,
        )
        responder = AsyncResponder([resp(200, b"first")])

        first = await middleware.handle(
            req("GET", "https://example.test/items/1"),
            responder,
        )
        assert first.content == b"first"
        assert responder.calls == 1

        second = await middleware.handle(
            req("GET", "https://example.test/items/1"),
            responder,
        )
        assert second.content == b"first"
        assert responder.calls == 1

    def test_state_tracking_off_keeps_stale_replay(self, tmp_path: Path) -> None:
        """Validate state tracking off keeps stale replay."""
        cassette_path = tmp_path / "stale.yaml"
        settings = VCRSettings(
            mode=VCRMode.NEW_EPISODES,
            state_tracking=StateTrackingSettings(mode=StateTrackingMode.OFF),
        )
        middleware = VCRMiddleware(cassette_path=str(cassette_path), settings=settings)
        responder = SyncResponder(
            [resp(200, b"before-update"), resp(204, b""), resp(200, b"after-update")]
        )

        first_read = middleware.handle(
            req("GET", "https://example.test/object/1"),
            responder,
        )
        _ = middleware.handle(
            req("PATCH", "https://example.test/object/1", content=b'{"name":"new"}'),
            responder,
        )
        second_read = middleware.handle(
            req("GET", "https://example.test/object/1"),
            responder,
        )

        assert first_read.content == b"before-update"
        assert second_read.content == b"before-update"
        assert responder.calls == 2

    def test_state_tracking_resource_avoids_stale_replay(self, tmp_path: Path) -> None:
        """Validate state tracking resource avoids stale replay."""
        cassette_path = tmp_path / "fresh.yaml"
        settings = VCRSettings(
            mode=VCRMode.NEW_EPISODES,
            state_tracking=StateTrackingSettings(mode=StateTrackingMode.RESOURCE),
        )
        middleware = VCRMiddleware(cassette_path=str(cassette_path), settings=settings)
        responder = SyncResponder(
            [resp(200, b"before-update"), resp(204, b""), resp(200, b"after-update")]
        )

        first_read = middleware.handle(
            req("GET", "https://example.test/object/1"),
            responder,
        )
        _ = middleware.handle(
            req("PATCH", "https://example.test/object/1", content=b'{"name":"new"}'),
            responder,
        )
        second_read = middleware.handle(
            req("GET", "https://example.test/object/1"),
            responder,
        )

        assert first_read.content == b"before-update"
        assert second_read.content == b"after-update"
        assert responder.calls == 3

    def test_injected_session_is_used(self, tmp_path: Path) -> None:
        """Validate injected session is used."""
        cassette_path = tmp_path / "injected.yaml"
        settings = VCRSettings(mode=VCRMode.PASSTHROUGH)
        injected = VCRSession(cassette_path=str(cassette_path), settings=settings)
        middleware = VCRMiddleware(settings=settings, session=injected)
        responder = SyncResponder([resp(200, b"ok")])

        result = middleware.handle(req("GET", "https://example.test/"), responder)

        assert result.content == b"ok"

    def test_active_vcr_session_is_used_by_middleware(self, tmp_path: Path) -> None:
        """Validate active vcr session is used by middleware."""
        settings = VCRSettings(mode=VCRMode.PASSTHROUGH)
        middleware = VCRMiddleware(
            cassette_path=str(tmp_path / "unused.yaml"),
            settings=settings,
        )
        responder = SyncResponder([resp(200, b"active")])

        with use_vcr(cassette_path=str(tmp_path / "active.yaml"), settings=settings):
            result = middleware.handle(req("GET", "https://example.test/"), responder)

        assert result.content == b"active"

    def test_sync_passthrough_calls_next_handler(self, tmp_path: Path) -> None:
        """Validate sync passthrough calls next handler."""
        settings = VCRSettings(mode=VCRMode.PASSTHROUGH)
        middleware = VCRMiddleware(
            cassette_path=str(tmp_path / "passthrough.yaml"), settings=settings
        )
        responder = SyncResponder([resp(200, b"live")])

        result = middleware.handle(req("GET", "https://example.test/"), responder)

        assert result.content == b"live"
        assert responder.calls == 1

    async def test_async_passthrough_calls_next_handler(self, tmp_path: Path) -> None:
        """Validate async passthrough calls next handler."""
        settings = VCRSettings(mode=VCRMode.PASSTHROUGH)
        middleware = AsyncVCRMiddleware(
            cassette_path=str(tmp_path / "pass-async.yaml"), settings=settings
        )
        responder = AsyncResponder([resp(200, b"async-live")])

        result = await middleware.handle(req("GET", "https://example.test/"), responder)

        assert result.content == b"async-live"
        assert responder.calls == 1

    async def test_async_replay_raises_when_no_match(self, tmp_path: Path) -> None:
        """Validate async replay raises when no match."""
        cassette_path = tmp_path / "missing-async.yaml"
        settings = VCRSettings(mode=VCRMode.NONE)
        middleware = AsyncVCRMiddleware(
            cassette_path=str(cassette_path), settings=settings
        )

        async def dummy_handler(request: PlyntRequest) -> PlyntResponse:
            """Return dummy handler."""
            raise AssertionError("should not be called")

        with pytest.raises(VCRMissError):
            await middleware.handle(
                req("GET", "https://example.test/items/1"), dummy_handler
            )

    def test_failed_mutation_does_not_bump_revision(self, tmp_path: Path) -> None:
        """Validate failed mutation does not bump revision."""
        cassette_path = tmp_path / "failed-mutation.yaml"
        settings = VCRSettings(
            mode=VCRMode.NEW_EPISODES,
            state_tracking=StateTrackingSettings(mode=StateTrackingMode.RESOURCE),
        )
        middleware = VCRMiddleware(cassette_path=str(cassette_path), settings=settings)
        responder = SyncResponder([resp(200, b"initial"), resp(400, b"bad-request")])

        first = middleware.handle(req("GET", "https://example.test/obj/1"), responder)
        _ = middleware.handle(
            req("PATCH", "https://example.test/obj/1", content=b"{}"), responder
        )
        second = middleware.handle(req("GET", "https://example.test/obj/1"), responder)

        assert first.content == b"initial"
        assert second.content == b"initial"  # revision not bumped; replayed
        assert responder.calls == 2

    def test_custom_matchers_are_registered_and_used(self, tmp_path: Path) -> None:
        """Validate custom matchers are registered and used."""
        cassette_path = tmp_path / "custom-matchers.yaml"

        def always_match(r1: object, r2: object) -> None:
            """Return always match."""
            pass

        settings = VCRSettings(
            mode=VCRMode.NEW_EPISODES,
            match_on=("method", "scheme", "host", "port", "path", "custom_match"),
            custom_matchers={"custom_match": always_match},
        )
        middleware = VCRMiddleware(cassette_path=str(cassette_path), settings=settings)
        responder = SyncResponder([resp(200, b"custom")])

        first = middleware.handle(req("GET", "https://example.test/cm"), responder)
        second = middleware.handle(req("GET", "https://example.test/cm"), responder)

        assert first.content == b"custom"
        assert second.content == b"custom"
        assert responder.calls == 1

    def test_request_params_are_merged_into_query(self, tmp_path: Path) -> None:
        """Validate request params are merged into query."""
        cassette_path = tmp_path / "params.yaml"
        settings = VCRSettings(mode=VCRMode.NEW_EPISODES)
        middleware = VCRMiddleware(cassette_path=str(cassette_path), settings=settings)
        responder = SyncResponder([resp(200, b"ok")])

        request = PlyntRequest(
            method="GET",
            url="https://example.test/search",
            params={"q": "hello"},
        )
        result = middleware.handle(request, responder)

        assert result.content == b"ok"
        assert responder.calls == 1

    def test_global_state_tracking_bumps_across_resources(self, tmp_path: Path) -> None:
        """Validate global state tracking bumps across resources."""
        cassette_path = tmp_path / "global.yaml"
        settings = VCRSettings(
            mode=VCRMode.NEW_EPISODES,
            state_tracking=StateTrackingSettings(mode=StateTrackingMode.GLOBAL),
        )
        middleware = VCRMiddleware(cassette_path=str(cassette_path), settings=settings)
        responder = SyncResponder(
            [resp(200, b"before"), resp(201, b""), resp(200, b"after")]
        )

        first = middleware.handle(req("GET", "https://example.test/a"), responder)
        _ = middleware.handle(
            req("POST", "https://example.test/b", content=b"{}"), responder
        )
        second = middleware.handle(req("GET", "https://example.test/a"), responder)

        assert first.content == b"before"
        assert second.content == b"after"  # global revision bumped by POST on /b
        assert responder.calls == 3

    def test_replay_preserves_response_headers(self, tmp_path: Path) -> None:
        """Validate replay preserves response headers."""
        cassette_path = tmp_path / "headers.yaml"
        settings = VCRSettings(mode=VCRMode.NEW_EPISODES)
        middleware = VCRMiddleware(cassette_path=str(cassette_path), settings=settings)
        response_with_headers = PlyntResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            content=b"{}",
        )
        responder = SyncResponder([response_with_headers])
        middleware.handle(req("GET", "https://example.test/data"), responder)

        replayed = middleware.handle(req("GET", "https://example.test/data"), responder)
        assert replayed.headers.get("Content-Type") == "application/json"

    async def test_state_tracking_resource_async(self, tmp_path: Path) -> None:
        """Validate state tracking resource async."""
        cassette_path = tmp_path / "async_tracking.yaml"
        settings = VCRSettings(
            mode=VCRMode.NEW_EPISODES,
            state_tracking=StateTrackingSettings(mode=StateTrackingMode.RESOURCE),
        )
        middleware = AsyncVCRMiddleware(
            cassette_path=str(cassette_path), settings=settings
        )
        responder = AsyncResponder(
            [resp(200, b"before"), resp(204, b""), resp(200, b"after")]
        )

        first = await middleware.handle(
            req("GET", "https://example.test/obj/1"), responder
        )
        await middleware.handle(
            req("PATCH", "https://example.test/obj/1", content=b'{"x":1}'), responder
        )
        second = await middleware.handle(
            req("GET", "https://example.test/obj/1"), responder
        )

        assert first.content == b"before"
        assert second.content == b"after"
        assert responder.calls == 3
