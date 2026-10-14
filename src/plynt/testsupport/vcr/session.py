"""VCR-backed session engine and context/decorator APIs."""

from __future__ import annotations

import contextvars
import inspect
import json
from collections import defaultdict
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qsl, urlencode, urlparse

import vcr
from vcr.request import Request as VCRRequest

from plynt.base.middleware import NextAsyncHandler, NextSyncHandler
from plynt.base.request import Request
from plynt.base.response import Response
from plynt.testsupport.vcr.config import (
    StateTrackingMode,
    StateTrackingSettings,
    VCRMissError,
    VCRMode,
    VCRSettings,
)
from plynt.testsupport.vcr.path import DeterministicCassettePathResolver
from plynt.testsupport.vcr.serializer import (
    READABLE_YAML_SERIALIZER,
    READABLE_YAML_SERIALIZER_NAME,
)


def _normalize_path(url: str) -> str:
    """Return the normalised path component of a URL, with trailing slash removed."""
    parsed = urlparse(url)
    path = parsed.path or "/"
    return path.rstrip("/") or "/"


def _merge_query(
    request: Request,
    *,
    tracking: StateTrackingSettings,
    revision: int,
) -> str:
    """Merge request params and optional VCR revision marker into a query string."""
    parsed = urlparse(request.url)
    pairs = list(parse_qsl(parsed.query, keep_blank_values=True))
    if request.params:
        pairs.extend(
            parse_qsl(
                urlencode(request.params, doseq=True),
                keep_blank_values=True,
            )
        )
    if tracking.mode is not StateTrackingMode.OFF:
        pairs.append(("_plynt_vcr_rev", str(revision)))
    if not pairs:
        return ""
    return urlencode(pairs, doseq=True)


def _state_key(request: Request, tracking: StateTrackingSettings) -> str:
    """Return the state-tracking key for a request based on the configured mode."""
    if tracking.mode is StateTrackingMode.GLOBAL:
        return "__global__"
    if tracking.mode is StateTrackingMode.RESOURCE:
        return _normalize_path(request.url)
    return "__off__"


def _to_vcr_request(
    request: Request,
    *,
    tracking: StateTrackingSettings,
    revision: int,
) -> VCRRequest:
    """Convert a Plynt ``Request`` to a vcrpy ``VCRRequest``."""
    parsed = urlparse(request.url)
    query = _merge_query(request, tracking=tracking, revision=revision)
    uri = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if query:
        uri = f"{uri}?{query}"

    headers = {k: [v] for k, v in request.headers.items()}
    if tracking.mode is not StateTrackingMode.OFF:
        headers[tracking.revision_header_name] = [str(revision)]

    return VCRRequest(
        method=request.method.upper(),
        uri=uri,
        body=request.content,
        headers=headers,
    )


def _from_vcr_response(payload: dict[str, Any]) -> Response:
    """Convert a vcrpy cassette response payload to a Plynt ``Response``."""
    status = payload.get("status", {})
    headers_payload = payload.get("headers", {})
    headers: dict[str, str] = {}
    for key, value in headers_payload.items():
        if isinstance(value, list):
            headers[key] = str(value[0]) if value else ""
        else:
            headers[key] = str(value)

    body = payload.get("body", {}).get("string", b"")
    if isinstance(body, str):
        body_bytes = body.encode("utf-8")
    else:
        body_bytes = bytes(body)

    return Response(
        status_code=int(status.get("code", 200)),
        headers=headers,
        content=body_bytes,
    )


def _maybe_pretty_json_body(content: bytes, content_type: str) -> str | bytes:
    """Pretty-print ``content`` if it is a JSON response body.

    Checks the ``Content-Type`` header first to avoid the cost of parsing
    non-JSON bodies.  Returns the original bytes unchanged when the body is
    not JSON, is empty, or cannot be decoded.
    """
    if "application/json" not in content_type or not content:
        return content
    try:
        return json.dumps(
            json.loads(content.decode("utf-8")),
            indent=2,
            ensure_ascii=False,
        )
    except (ValueError, UnicodeDecodeError):
        return content


def _to_vcr_response(response: Response) -> dict[str, Any]:
    """Convert a Plynt ``Response`` to a vcrpy cassette response payload.

    JSON response bodies are pretty-printed via ``_maybe_pretty_json_body``
    so that recorded cassettes are readable and produce clean diffs.
    """
    content_type = response.headers.get("Content-Type", "")
    return {
        "status": {"code": response.status_code, "message": ""},
        "headers": {k: [v] for k, v in response.headers.items()},
        "body": {"string": _maybe_pretty_json_body(response.content, content_type)},
    }


class VCRSession:
    """State-aware VCR session for sync and async middleware."""

    def __init__(
        self,
        *,
        settings: VCRSettings,
        cassette_path: str | None = None,
        cassette_root: Path | str = Path("tests/_mock/cassettes"),
        cassette_extension: str = ".yaml",
        node_id: str | None = None,
    ) -> None:
        """Initialize VCRSession."""
        resolver = DeterministicCassettePathResolver(
            cassette_root=Path(cassette_root),
            extension=cassette_extension,
        )
        self._cassette_path = str(
            resolver.resolve(cassette_path=cassette_path, node_id=node_id)
        )
        self._settings = settings
        self._state_revisions: dict[str, int] = defaultdict(int)
        self._vcr_instance: vcr.VCR | None = None

    @property
    def cassette_path(self) -> str:
        """Resolved cassette path used by this session."""
        return self._cassette_path

    @property
    def settings(self) -> VCRSettings:
        """Effective settings for this session."""
        return self._settings

    def _current_revision(self, request: Request) -> int:
        """Return the current mutation revision counter for the request's state key."""
        tracking = self._settings.state_tracking
        if tracking.mode is StateTrackingMode.OFF:
            return 0
        return self._state_revisions.get(_state_key(request, tracking), 0)

    def _bump_revision(self, request: Request, response: Response) -> None:
        """Increment the revision counter after a successful mutating request."""
        tracking = self._settings.state_tracking
        if tracking.mode is StateTrackingMode.OFF:
            return
        if request.method.upper() not in tracking.mutating_methods:
            return
        if not (
            tracking.success_status_min
            <= response.status_code
            <= tracking.success_status_max
        ):
            return
        self._state_revisions[_state_key(request, tracking)] += 1

    def _build_vcr(self) -> vcr.VCR:
        """Return the shared vcrpy ``VCR`` instance, creating it on first call."""
        if self._vcr_instance is None:
            instance = vcr.VCR(
                filter_headers=list(self._settings.filter_headers),
                decode_compressed_response=self._settings.decode_compressed_response,
                serializer=READABLE_YAML_SERIALIZER_NAME,
            )
            instance.register_serializer(
                READABLE_YAML_SERIALIZER_NAME,
                READABLE_YAML_SERIALIZER,
            )
            for name, matcher in self._settings.custom_matchers.items():
                instance.register_matcher(name, matcher)
            self._vcr_instance = instance
        return self._vcr_instance

    def handle_sync(self, request: Request, next_handler: NextSyncHandler) -> Response:
        """Handle a sync request with VCR record/replay behavior."""
        if self._settings.mode is VCRMode.PASSTHROUGH:
            response = next_handler(request)
            self._bump_revision(request, response)
            return response

        revision = self._current_revision(request)
        vcr_request = _to_vcr_request(
            request,
            tracking=self._settings.state_tracking,
            revision=revision,
        )

        recorder = self._build_vcr()
        with recorder.use_cassette(
            self._cassette_path,
            record_mode=self._settings.mode.value,
            match_on=list(self._settings.match_on),
            allow_playback_repeats=self._settings.allow_playback_repeats,
        ) as cassette:
            if cassette.can_play_response_for(vcr_request):
                response = _from_vcr_response(cassette.play_response(vcr_request))
            elif cassette.write_protected and self._settings.mode is not VCRMode.ALL:
                msg = f"No VCR interaction for request {vcr_request!r}"
                raise VCRMissError(msg)
            else:
                response = next_handler(request)
                cassette.append(vcr_request, _to_vcr_response(response))

        self._bump_revision(request, response)
        return response

    async def handle_async(
        self,
        request: Request,
        next_handler: NextAsyncHandler,
    ) -> Response:
        """Handle an async request with VCR record/replay behavior."""
        if self._settings.mode is VCRMode.PASSTHROUGH:
            response = await next_handler(request)
            self._bump_revision(request, response)
            return response

        revision = self._current_revision(request)
        vcr_request = _to_vcr_request(
            request,
            tracking=self._settings.state_tracking,
            revision=revision,
        )

        recorder = self._build_vcr()
        with recorder.use_cassette(
            self._cassette_path,
            record_mode=self._settings.mode.value,
            match_on=list(self._settings.match_on),
            allow_playback_repeats=self._settings.allow_playback_repeats,
        ) as cassette:
            if cassette.can_play_response_for(vcr_request):
                response = _from_vcr_response(cassette.play_response(vcr_request))
            elif cassette.write_protected and self._settings.mode is not VCRMode.ALL:
                msg = f"No VCR interaction for request {vcr_request!r}"
                raise VCRMissError(msg)
            else:
                response = await next_handler(request)
                cassette.append(vcr_request, _to_vcr_response(response))

        self._bump_revision(request, response)
        return response


_ACTIVE_VCR: contextvars.ContextVar[VCRSession | None] = contextvars.ContextVar(
    "plynt_active_vcr_session",
    default=None,
)


def get_active_vcr_session() -> VCRSession | None:
    """Return the active VCR session bound by use_vcr, if present."""
    return _ACTIVE_VCR.get()


@contextmanager
def use_vcr(
    *,
    settings: VCRSettings,
    cassette_path: str | None = None,
    cassette_root: Path | str = Path("tests/_mock/cassettes"),
    cassette_extension: str = ".yaml",
    node_id: str | None = None,
) -> Iterator[VCRSession]:
    """Activate a VCR session in the current context."""
    session = VCRSession(
        settings=settings,
        cassette_path=cassette_path,
        cassette_root=cassette_root,
        cassette_extension=cassette_extension,
        node_id=node_id,
    )
    token = _ACTIVE_VCR.set(session)
    try:
        yield session
    finally:
        _ACTIVE_VCR.reset(token)


def with_vcr(
    *,
    settings: VCRSettings,
    cassette_path: str | None = None,
    cassette_root: Path | str = Path("tests/_mock/cassettes"),
    cassette_extension: str = ".yaml",
    node_id: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that executes a callable inside use_vcr."""

    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        """Handle decorator."""
        if inspect.iscoroutinefunction(fn):

            @wraps(fn)
            async def _async_wrapper(*args: object, **kwargs: object) -> Any:
                """Handle async wrapper."""
                with use_vcr(
                    settings=settings,
                    cassette_path=cassette_path,
                    cassette_root=cassette_root,
                    cassette_extension=cassette_extension,
                    node_id=node_id,
                ):
                    return await cast(Awaitable[object], fn(*args, **kwargs))

            return _async_wrapper

        @wraps(fn)
        def _sync_wrapper(*args: object, **kwargs: object) -> Any:
            """Handle sync wrapper."""
            with use_vcr(
                settings=settings,
                cassette_path=cassette_path,
                cassette_root=cassette_root,
                cassette_extension=cassette_extension,
                node_id=node_id,
            ):
                return fn(*args, **kwargs)

        return _sync_wrapper

    return _decorator
