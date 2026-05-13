"""Shared demo logic for the Salesforce quickstart examples.

Not intended to be run directly — imported by ``client_credentials.py``
and ``username_password.py``.
"""

from __future__ import annotations

import logging
from typing import Any

from plynth.connectors.salesforce.facade import (
    AsyncSalesforceAPIFacade,
    SalesforceAPIFacade,
)
from plynth.connectors.salesforce.settings import SalesforceSettings


def configure_logging() -> None:
    """Enable DEBUG logging for Plynth to show auth and transport activity."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    # Suppress noisy httpx/httpcore transport loggers.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def run_demo(
    facade: SalesforceAPIFacade,
    settings: SalesforceSettings,
    *,
    search_term: str = "Inc",
) -> None:
    """Execute the standard demo sequence against an authenticated facade."""
    utility = facade.utility(api_version=settings.api_version)
    query_svc = facade.query(api_version=settings.api_version)
    account_svc = facade.sobject("Account", api_version=settings.api_version)

    # --- 0. Available API versions ------------------------------------------
    print("=" * 60)
    print("AVAILABLE API VERSIONS")
    print("=" * 60)
    api_versions = utility.versions()
    for v in api_versions[-5:]:  # show only the 5 most recent
        print(f"  {v.version:<8} {v.label}")
    if api_versions:
        print(f"  -> Latest: {api_versions[-1].version}")

    # --- 1. Org limits ------------------------------------------------------
    print()
    print("=" * 60)
    print("ORG LIMITS")
    print("=" * 60)
    limits = utility.limits()
    for name, limit in sorted(limits.items()):
        used = limit.max_value - limit.remaining
        pct = (used / limit.max_value * 100) if limit.max_value else 0
        print(f"  {name:<45} {used:>8} / {limit.max_value:<8}  ({pct:.1f}%)")

    # --- 2. Account SObject description (schema) ----------------------------
    print()
    print("=" * 60)
    print("ACCOUNT SOBJECT — describe()")
    print("=" * 60)
    meta: dict[str, Any] = account_svc.describe()
    fields = meta.get("fields", [])
    print(f"  Label       : {meta.get('label', 'Account')}")
    print(f"  Fields      : {len(fields)}")
    print(f"  Createable  : {meta.get('createable')}")
    print(f"  Queryable   : {meta.get('queryable')}")
    if fields:
        standard = [f["name"] for f in fields if not f["name"].endswith("__c")][:10]
        print(f"  First fields: {', '.join(standard)}")

    # --- 3. SOQL query — first 5 Accounts -----------------------------------
    print()
    print("=" * 60)
    print("SOQL: SELECT Id, Name FROM Account LIMIT 5")
    print("=" * 60)
    result = query_svc.query("SELECT Id, Name FROM Account LIMIT 5")
    print(f"  Total matched : {result.total_size}")
    print(f"  Done          : {result.done}")
    print()
    for record in result.records:
        print(f"  {record.get('Id')}  {record.get('Name')}")

    # --- 4. SOSL quick search -----------------------------------------------
    print()
    print("=" * 60)
    print(f"SOSL: FIND {{{search_term}}} IN NAME FIELDS RETURNING Account(Id, Name)")
    print("=" * 60)
    search_result = utility.search(
        f"FIND {{{search_term}}} IN NAME FIELDS RETURNING Account(Id, Name) LIMIT 5"
    )
    print(f"  Hits : {len(search_result.search_records)}")
    print()
    for found_rec in search_result.search_records:
        print(f"  [{found_rec.sobject_type}]  {found_rec.id}  {found_rec['Name']}")

    print()
    print("Done.")


async def run_async_demo(
    facade: AsyncSalesforceAPIFacade,
    settings: SalesforceSettings,
    *,
    search_term: str = "Inc",
) -> None:
    """Async variant — mirrors run_demo() using the async facade."""
    utility = facade.utility(api_version=settings.api_version)
    query_svc = facade.query(api_version=settings.api_version)
    account_svc = facade.sobject("Account", api_version=settings.api_version)

    # --- 0. Available API versions ------------------------------------------
    print("=" * 60)
    print("AVAILABLE API VERSIONS  (async)")
    print("=" * 60)
    api_versions = await utility.versions()
    for v in api_versions[-5:]:  # show only the 5 most recent
        print(f"  {v.version:<8} {v.label}")
    if api_versions:
        print(f"  -> Latest: {api_versions[-1].version}")

    # --- 1. Org limits ------------------------------------------------------
    print()
    print("=" * 60)
    print("ORG LIMITS  (async)")
    print("=" * 60)
    limits = await utility.limits()
    for name, limit in sorted(limits.items()):
        used = limit.max_value - limit.remaining
        pct = (used / limit.max_value * 100) if limit.max_value else 0
        print(f"  {name:<45} {used:>8} / {limit.max_value:<8}  ({pct:.1f}%)")

    # --- 2. Account SObject description (schema) ----------------------------
    print()
    print("=" * 60)
    print("ACCOUNT SOBJECT — describe()  (async)")
    print("=" * 60)
    meta: dict[str, Any] = await account_svc.describe()
    fields = meta.get("fields", [])
    print(f"  Label       : {meta.get('label', 'Account')}")
    print(f"  Fields      : {len(fields)}")
    print(f"  Createable  : {meta.get('createable')}")
    print(f"  Queryable   : {meta.get('queryable')}")
    if fields:
        standard = [f["name"] for f in fields if not f["name"].endswith("__c")][:10]
        print(f"  First fields: {', '.join(standard)}")

    # --- 3. SOQL query — first 5 Accounts -----------------------------------
    print()
    print("=" * 60)
    print("SOQL: SELECT Id, Name FROM Account LIMIT 5  (async)")
    print("=" * 60)
    result = await query_svc.query("SELECT Id, Name FROM Account LIMIT 5")
    print(f"  Total matched : {result.total_size}")
    print(f"  Done          : {result.done}")
    print()
    for record in result.records:
        print(f"  {record.get('Id')}  {record.get('Name')}")

    # --- 4. SOSL quick search -----------------------------------------------
    print()
    print("=" * 60)
    print(
        f"SOSL: FIND {{{search_term}}} IN NAME FIELDS RETURNING Account(Id, Name)"
        "  (async)"
    )
    print("=" * 60)
    search_result = await utility.search(
        f"FIND {{{search_term}}} IN NAME FIELDS RETURNING Account(Id, Name) LIMIT 5"
    )
    print(f"  Hits : {len(search_result.search_records)}")
    print()
    for hit in search_result.search_records:
        print(f"  [{hit.sobject_type}]  {hit.id}  {hit['Name']}")

    print()
    print("Done.")
