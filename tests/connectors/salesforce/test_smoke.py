# pyright: reportPrivateUsage=false
"""VCR cassette smoke tests for the Salesforce integration.

These tests mirror the demo flow in ``examples/salesforce/_demo.py``:
versions → limits → SOQL query → SOSL quick-search.

How to use
----------
**Replay (default — no credentials needed)**::

    pytest tests/connectors/salesforce/test_smoke.py

Cassettes stored under ``tests/_mock/cassettes/`` are committed to the repo and
replayed without any real HTTP calls.  This works in CI out of the box.

**Record against a real Salesforce org**::

    RECORD=1 pytest tests/connectors/salesforce/test_smoke.py

Before recording, set real credentials through ``RECORD_*`` environment
variables. VCR will make live HTTP calls and overwrite the cassettes.
After recording, anonymise sensitive values in the recorded cassette files
including browser cookies, record IDs, and matching record URLs. Preserve
consistent synthetic IDs across responses and clear those environment
variables before committing.

Cassette layout
---------------
Cassettes are stored at a deterministic path derived from the test node id::

    tests/_mock/cassettes/connectors/salesforce/smoke/salesforcevcrsmoke/
        <test_name>__<hash>.yaml

This matches the default ``DeterministicCassettePathResolver`` root
(``tests/_mock/cassettes``).

.. note::
    Sensitive data (``Authorization`` headers, access tokens) are
    filtered by ``VCRSettings.filter_headers`` before the cassette is
    written to disk.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from plynt.connectors.salesforce.auth import SalesforcePasswordAuthMiddleware
from plynt.connectors.salesforce.client import SalesforceAPIClient
from plynt.connectors.salesforce.facade import SalesforceAPIFacade
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

# ---------------------------------------------------------------------------
# Smoke settings
#
# For RECORD=1: fill in real credentials.  After recording:
#   1. Anonymise cassettes (replace the real org hostname, ``access_token``,
#      and credentials from the token request body with placeholder values).
#   2. Revert any RECORD_* env vars to the shared dummy defaults.
# For replay: credentials are not used.  ``instance_url`` is derived from
# the OAuth2 token response stored in the cassette.
# ---------------------------------------------------------------------------

_SMOKE_TOKEN_URL = os.getenv("RECORD_TOKEN_URL", DUMMY_TOKEN_URL)
_SMOKE_CLIENT_ID = os.getenv("RECORD_CLIENT_ID", DUMMY_CLIENT_ID)
_SMOKE_CLIENT_SECRET = os.getenv("RECORD_CLIENT_SECRET", DUMMY_CLIENT_SECRET)
_SMOKE_USERNAME = os.getenv("RECORD_USERNAME", DUMMY_USERNAME)
_SMOKE_PASSWORD = os.getenv("RECORD_PASSWORD", DUMMY_PASSWORD)
_SMOKE_SECURITY_TOKEN = os.getenv("RECORD_SECURITY_TOKEN", "")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Match on method + path only — used for endpoints that include dynamic
# query parameters (q=SOQL/SOSL) so the cassette matches regardless of
# the exact query string.
_PATH_ONLY: tuple[str, ...] = ("method", "scheme", "host", "port", "path")

_CASSETTE_ROOT = Path("tests/_mock/cassettes")
_RESOLVER = DeterministicCassettePathResolver(cassette_root=_CASSETTE_ROOT)


def _vcr_mode() -> VCRMode:
    """Return NEW_EPISODES when RECORD=1, otherwise NONE (replay only)."""
    return VCRMode.NEW_EPISODES if os.getenv("RECORD") == "1" else VCRMode.NONE


def _vcr_settings(*, path_only: bool = False) -> VCRSettings:
    """Handle vcr settings."""
    match_on = (
        _PATH_ONLY
        if path_only
        else ("method", "scheme", "host", "port", "path", "query")
    )
    return VCRSettings(
        mode=_vcr_mode(),
        match_on=match_on,
        # Scrub auth headers so tokens are never written to the cassette.
        filter_headers=(("Authorization", None), ("authorization", None)),
    )


def _facade(cassette_path: Path, *, path_only: bool = False) -> SalesforceAPIFacade:
    """Build a ``SalesforceAPIFacade`` whose transport is backed by VCR.

    Both record and replay modes use ``SalesforceAPIClient`` + auth.  The
    auth middleware's own token-endpoint transport is also routed through VCR
    so that ``instance_url`` is always derived from the OAuth2 response stored
    in the cassette, not from a hardcoded configuration value.

    **Record mode** (``RECORD=1``):
        Real credentials can be supplied through ``RECORD_*`` env vars. VCR records
        the token exchange and all subsequent API calls into the cassette.
        After recording, anonymise the cassettes and revert the credentials.

    **Replay mode** (default):
        No credentials needed.  VCR replays the token exchange (providing
        ``instance_url``) and all API calls.  Tests are skipped when no
        cassettes exist yet.
    """
    cassette = str(cassette_path)
    settings = _vcr_settings(path_only=path_only)
    # Both the auth token-endpoint transport and the main API transport
    # are routed through a VCRMiddleware pointing to the same cassette.
    # Interactions are matched by content, so the token POST and the
    # API GET are replayed/recorded independently.
    mw = VCRMiddleware(cassette_path=cassette, settings=settings)

    auth = SalesforcePasswordAuthMiddleware(
        client_id=_SMOKE_CLIENT_ID,
        client_secret=_SMOKE_CLIENT_SECRET,
        token_url=_SMOKE_TOKEN_URL,
        username=_SMOKE_USERNAME,
        password=_SMOKE_PASSWORD,
        security_token=_SMOKE_SECURITY_TOKEN,
    )
    # Route the auth token exchange through VCR so instance_url is derived
    # from the cassette response, not from a hardcoded configuration value.
    auth._transport = HttpxSyncTransport(middlewares=[mw])  # pylint: disable=protected-access

    if _vcr_mode() is VCRMode.NONE and not any(_CASSETTE_ROOT.rglob("*.yaml")):
        pytest.skip(
            "No cassettes recorded yet. Run with RECORD=1: "
            "RECORD=1 pytest tests/connectors/salesforce/test_smoke.py"
        )

    transport = HttpxSyncTransport(middlewares=[mw, auth])
    client = SalesforceAPIClient(auth=auth, transport=transport)
    return SalesforceAPIFacade(client)


def _cassette(request: pytest.FixtureRequest) -> Path:
    """Resolve the cassette path for the current test node."""
    path = _RESOLVER.from_node_id(request.node.nodeid)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSalesforceVCRSmoke:
    """Test suite for SalesforceVCRSmoke."""

    def test_versions(self, request: pytest.FixtureRequest) -> None:
        """GET /services/data/ → list[SalesforceApiVersion]."""
        versions = _facade(_cassette(request)).utility().versions()

        assert len(versions) >= 1
        assert all(v.version for v in versions)

    def test_limits(self, request: pytest.FixtureRequest) -> None:
        """GET /services/data/v{api}/limits → SalesforceLimitsResponse."""
        limits = _facade(_cassette(request)).utility().limits()

        assert len(limits) > 0
        assert "DailyApiRequests" in limits
        assert limits["DailyApiRequests"].max_value > 0

    def test_query_accounts(self, request: pytest.FixtureRequest) -> None:
        """SOQL SELECT against Account → SalesforceQueryResponse."""
        result = (
            _facade(_cassette(request), path_only=True)
            .query()
            .query("SELECT Id, Name FROM Account LIMIT 5")
        )

        assert result.total_size >= 0
        assert isinstance(result.done, bool)
        assert isinstance(result.records, list)

    def test_quick_search(self, request: pytest.FixtureRequest) -> None:
        """SOSL quick_search → SalesforceSearchResponse with typed records."""
        result = (
            _facade(_cassette(request), path_only=True).search().quick_search("Inc")
        )

        assert isinstance(result.search_records, list)
        for record in result.search_records:
            assert record.sobject_type
            assert record["Id"]

    def test_objects_catalog(self, request: pytest.FixtureRequest) -> None:
        """GET /sobjects/ exposes a non-empty global object catalog."""
        result = _facade(_cassette(request)).utility().objects()

        assert len(result.sobjects) > 0
        assert any(obj.name == "Account" for obj in result.sobjects)

    def test_query_org_metadata(self, request: pytest.FixtureRequest) -> None:
        """SOQL on Organization returns a minimal non-destructive metadata row."""
        result = (
            _facade(_cassette(request), path_only=True)
            .query()
            .query("SELECT Id, Name FROM Organization LIMIT 1")
        )

        assert result.total_size >= 1
        assert isinstance(result.records[0]["Id"], str)
        assert isinstance(result.records[0]["Name"], str)


class TestSalesforceCassettePrivacy:
    """Check committed Salesforce recordings use synthetic identifiers"""

    @pytest.mark.parametrize(
        "cassette_path",
        sorted(Path("tests/_mock/cassettes/connectors/salesforce").rglob("*.yaml")),
        ids=lambda path: path.name,
    )
    def test_browser_ids_are_redacted(self, cassette_path: Path) -> None:
        contents = cassette_path.read_text(encoding="utf-8")

        assert all(
            value == "REDACTED_BROWSER_ID"
            for value in re.findall(r"BrowserId=([^;\s]+)", contents)
        )

    @pytest.mark.parametrize(
        "cassette_name",
        ["query_accounts__58b98669.yaml", "quick_search__1101ee82.yaml"],
    )
    def test_record_ids_and_urls_use_synthetic_ids(self, cassette_name: str) -> None:
        cassette_path = (
            Path("tests/_mock/cassettes/connectors/salesforce/smoke/salesforcevcrsmoke")
            / cassette_name
        )
        contents = cassette_path.read_text(encoding="utf-8")
        record_ids = re.findall(r'"Id": "([^"]+)"', contents)
        url_ids = re.findall(r"/sobjects/[^/\" ]+/([A-Za-z0-9]+)", contents)

        assert record_ids
        assert url_ids
        assert set(record_ids) == set(url_ids)
        assert all(
            re.fullmatch(r"(?:001|00O|0PL)0{11}[1-5](?:AAA|EAA|GAA)", record_id)
            for record_id in record_ids
        )
