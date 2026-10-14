# pyright: reportPrivateUsage=false
"""VCR smoke tests for Salesforce Models and Agent APIs.

These tests are separate from the generic connector smoke suite so they
produce dedicated cassette files and can be validated independently.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from plynt.base.response import StreamingResponse
from plynt.connectors.salesforce.auth import SalesforcePasswordAuthMiddleware
from plynt.connectors.salesforce.client import SalesforceAPIClient
from plynt.connectors.salesforce.facade import SalesforceAPIFacade
from plynt.http.errors import ForbiddenError, NotFoundError
from plynt.http.transport import HttpxSyncTransport
from plynt.testsupport.vcr import (
    DeterministicCassettePathResolver,
    VCRMiddleware,
    VCRMode,
    VCRSettings,
)
from tests.connectors.salesforce.conftest import (
    DUMMY_CLIENT_ID,
    DUMMY_CLIENT_SECRET,
    DUMMY_PASSWORD,
    DUMMY_TOKEN_URL,
    DUMMY_USERNAME,
)

_SMOKE_TOKEN_URL = os.getenv("RECORD_TOKEN_URL", DUMMY_TOKEN_URL)
_SMOKE_CLIENT_ID = os.getenv("RECORD_CLIENT_ID", DUMMY_CLIENT_ID)
_SMOKE_CLIENT_SECRET = os.getenv("RECORD_CLIENT_SECRET", DUMMY_CLIENT_SECRET)
_SMOKE_USERNAME = os.getenv("RECORD_USERNAME", DUMMY_USERNAME)
_SMOKE_PASSWORD = os.getenv("RECORD_PASSWORD", DUMMY_PASSWORD)
_SMOKE_SECURITY_TOKEN = os.getenv("RECORD_SECURITY_TOKEN", "")
_SMOKE_AGENT_ID = os.getenv("RECORD_AGENT_ID") or os.getenv("SF_AGENT_ID")

_PATH_ONLY: tuple[str, ...] = ("method", "scheme", "host", "port", "path")

_CASSETTE_ROOT = Path("tests/_mock/cassettes")
_RESOLVER = DeterministicCassettePathResolver(cassette_root=_CASSETTE_ROOT)


def _vcr_mode() -> VCRMode:
    """Return NEW_EPISODES when RECORD=1, otherwise NONE (replay only)."""
    return VCRMode.NEW_EPISODES if os.getenv("RECORD") == "1" else VCRMode.NONE


def _vcr_settings(*, path_only: bool = False) -> VCRSettings:
    """Build VCR settings with strict replay matching defaults."""
    match_on = (
        _PATH_ONLY
        if path_only
        else ("method", "scheme", "host", "port", "path", "query")
    )
    return VCRSettings(
        mode=_vcr_mode(),
        match_on=match_on,
        filter_headers=(("Authorization", None), ("authorization", None)),
    )


def _facade(cassette_path: Path, *, path_only: bool = False) -> SalesforceAPIFacade:
    """Build a facade backed by VCR middleware for record and replay modes."""
    mw = VCRMiddleware(
        cassette_path=str(cassette_path),
        settings=_vcr_settings(path_only=path_only),
    )
    auth = SalesforcePasswordAuthMiddleware(
        client_id=_SMOKE_CLIENT_ID,
        client_secret=_SMOKE_CLIENT_SECRET,
        token_url=_SMOKE_TOKEN_URL,
        username=_SMOKE_USERNAME,
        password=_SMOKE_PASSWORD,
        security_token=_SMOKE_SECURITY_TOKEN,
    )
    auth._transport = HttpxSyncTransport(middlewares=[mw])  # pylint: disable=protected-access

    transport = HttpxSyncTransport(middlewares=[mw, auth])
    client = SalesforceAPIClient(auth=auth, transport=transport)
    return SalesforceAPIFacade(client)


def _cassette(request: pytest.FixtureRequest) -> Path:
    """Resolve deterministic cassette path for the current test node."""
    path = _RESOLVER.from_node_id(request.node.nodeid)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class TestSalesforceAIVCRSmoke:
    """Smoke tests for Salesforce-hosted Models and Agent API calls."""

    pytestmark = pytest.mark.external

    def test_models_generate_text(self, request: pytest.FixtureRequest) -> None:
        """Models generate_text returns typed output for a minimal prompt."""
        try:
            result = (
                _facade(_cassette(request))
                .models()
                .generate_text(
                    "Reply with one short word: ok",
                    max_tokens=8,
                )
            )
        except (NotFoundError, ForbiddenError):
            pytest.skip("Models API is not enabled for this Salesforce org")

        assert result.id
        assert result.text.strip()

    def test_models_generate_chat(self, request: pytest.FixtureRequest) -> None:
        """Models generate_chat returns at least one choice message."""
        try:
            result = (
                _facade(_cassette(request))
                .models()
                .generate_chat(
                    [{"role": "user", "content": "Reply with: hello"}],
                    max_tokens=16,
                    stream=False,
                )
            )
        except (NotFoundError, ForbiddenError):
            pytest.skip("Models API is not enabled for this Salesforce org")

        if isinstance(result, StreamingResponse):
            pytest.fail("Expected non-streaming chat response")

        assert result.id
        assert len(result.choices) >= 1
        first_choice = result.choices[0]
        assert isinstance(first_choice, dict)
        message = first_choice.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            assert isinstance(content, str)
            assert content.strip()
        else:
            text = first_choice.get("text")
            assert isinstance(text, str)
            assert text.strip()

    def test_agent_session_message_and_end(
        self,
        request: pytest.FixtureRequest,
    ) -> None:
        """Agent lifecycle smoke test: start session, message, and end session."""
        if _SMOKE_AGENT_ID is None and _vcr_mode() is VCRMode.NEW_EPISODES:
            pytest.skip("Set RECORD_AGENT_ID or SF_AGENT_ID to record agent smoke")

        cassette_path = _cassette(request)
        if _vcr_mode() is VCRMode.NONE and not cassette_path.exists():
            pytest.skip(
                "No agent cassette recorded yet; run with RECORD=1 and RECORD_AGENT_ID"
            )

        facade = _facade(cassette_path, path_only=True)
        session = facade.agent().start_session(agent_id=_SMOKE_AGENT_ID or "agent-id")
        assert session.session_id

        reply = facade.agent().send_message(session.session_id, "Reply with: hi")
        assert reply.session_id == session.session_id
        if reply.output_text is not None:
            assert reply.output_text.strip()
        else:
            # Some orgs return non-standard payload fields; accept any
            # non-empty message-like extra value for smoke validation.
            extras = reply.model_dump(by_alias=True)
            fallback = (
                extras.get("content") or extras.get("messages") or extras.get("text")
            )
            assert fallback

        end_ack = facade.agent().end_session(session.session_id)
        assert end_ack.session_id == session.session_id
