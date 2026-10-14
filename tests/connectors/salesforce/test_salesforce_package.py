"""Tests for public package exports in ``plynt.connectors.salesforce``."""

import importlib

from plynt.connectors.salesforce.facade import (
    AsyncSalesforceAPIFacade,
    SalesforceAPIFacade,
)
from plynt.connectors.salesforce.helpers import (
    build_select_soql,
    validate_salesforce_id,
)
from plynt.connectors.salesforce.models import SalesforceGlobalDescribeResponse
from plynt.connectors.salesforce.query import (
    AsyncSalesforceQueryService,
    SalesforceQueryService,
)


class TestSalesforcePackage:
    """Verify package-level exports and import behavior."""

    def test_package_exports_critical_stable_names(self) -> None:
        """Verify critical public names are exported by the package."""
        module = importlib.import_module("plynt.connectors.salesforce")

        expected_critical_exports = {
            "AsyncSalesforceAPIFacade",
            "AsyncSalesforceQueryService",
            "SalesforceAPIFacade",
            "SalesforceGlobalDescribeResponse",
            "SalesforceQueryService",
            "build_select_soql",
            "validate_salesforce_id",
        }

        assert expected_critical_exports.issubset(set(module.__all__))

    def test_package_reexports_critical_objects(self) -> None:
        """Verify critical package-level re-exports for stable entry points."""
        module = importlib.import_module("plynt.connectors.salesforce")

        assert module.AsyncSalesforceAPIFacade is AsyncSalesforceAPIFacade
        assert module.AsyncSalesforceQueryService is AsyncSalesforceQueryService
        assert module.SalesforceAPIFacade is SalesforceAPIFacade
        assert (
            module.SalesforceGlobalDescribeResponse is SalesforceGlobalDescribeResponse
        )
        assert module.SalesforceQueryService is SalesforceQueryService
        assert module.build_select_soql is build_select_soql
        assert module.validate_salesforce_id is validate_salesforce_id
