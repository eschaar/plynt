"""VCR-backed middleware adapters for sync and async transport pipelines."""

from __future__ import annotations

import threading
from pathlib import Path

from plynt.base.middleware import NextAsyncHandler, NextSyncHandler
from plynt.base.request import Request
from plynt.base.response import Response
from plynt.testsupport.vcr.config import VCRSettings
from plynt.testsupport.vcr.session import (
    VCRSession,
    get_active_vcr_session,
)


class _VCRMiddlewareBase:
    """Shared init and thread-safe session resolution for VCR middleware."""

    def __init__(
        self,
        *,
        cassette_path: str | None = None,
        cassette_root: Path | str = Path("tests/_mock/cassettes"),
        cassette_extension: str = ".yaml",
        node_id: str | None = None,
        settings: VCRSettings,
        session: VCRSession | None = None,
    ) -> None:
        """Initialize _VCRMiddlewareBase."""
        self._cassette_path = cassette_path
        self._cassette_root = cassette_root
        self._cassette_extension = cassette_extension
        self._node_id = node_id
        self._settings = settings
        self._session = session
        self._owned_session: VCRSession | None = None
        self._session_lock = threading.Lock()

    def _resolve_session(self) -> VCRSession:
        """Handle resolve session."""
        if self._session is not None:
            return self._session
        active = get_active_vcr_session()
        if active is not None:
            return active
        with self._session_lock:
            if self._owned_session is None:
                self._owned_session = VCRSession(
                    cassette_path=self._cassette_path,
                    cassette_root=self._cassette_root,
                    cassette_extension=self._cassette_extension,
                    node_id=self._node_id,
                    settings=self._settings,
                )
        return self._owned_session


class VCRMiddleware(_VCRMiddlewareBase):
    """Sync middleware that delegates handling to a VCR session."""

    def handle(self, request: Request, next_handler: NextSyncHandler) -> Response:
        """Replay or record a request based on configured mode."""
        return self._resolve_session().handle_sync(request, next_handler)


class AsyncVCRMiddleware(_VCRMiddlewareBase):
    """Async middleware that delegates handling to a VCR session."""

    async def handle(
        self,
        request: Request,
        next_handler: NextAsyncHandler,
    ) -> Response:
        """Replay or record a request based on configured mode."""
        return await self._resolve_session().handle_async(request, next_handler)
