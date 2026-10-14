"""Tests for SalesforceRenderer."""

from __future__ import annotations

import datetime
import decimal
import json

import pytest
from pydantic import Field

from plynt.connectors.salesforce.models import SObjectPayload
from plynt.connectors.salesforce.renderer import SalesforceRenderer


class TestSalesforceRendererWithDict:
    """Smoke tests for plain-dict input.

    Encoding correctness for datetime, Decimal, and UUID is covered by
    ``TestExtendedJSONRenderer`` in ``tests/http/test_service.py``.
    """

    @pytest.fixture
    def renderer(self) -> SalesforceRenderer:
        """Return renderer."""
        return SalesforceRenderer()

    def test_renders_simple_dict(self, renderer: SalesforceRenderer) -> None:
        """Validate renders simple dict."""
        result = renderer.render({"Name": "ACME Corp", "Phone": "+31201234567"})
        assert json.loads(result) == {"Name": "ACME Corp", "Phone": "+31201234567"}

    def test_output_is_bytes(self, renderer: SalesforceRenderer) -> None:
        """Validate output is bytes."""
        assert isinstance(renderer.render({"Name": "ACME"}), bytes)

    def test_output_is_utf8_encoded(self, renderer: SalesforceRenderer) -> None:
        """Validate output is utf8 encoded."""
        assert renderer.render({"Name": "Ünïcödé"}).decode("utf-8")

    def test_extended_types_are_encoded(self, renderer: SalesforceRenderer) -> None:
        """Dict path delegates to ExtendedJSONEncoder (datetime smoke test)."""
        result = renderer.render({"CloseDate": datetime.date(2026, 3, 22)})
        assert json.loads(result) == {"CloseDate": "2026-03-22"}


class TestSalesforceRendererWithSObjectPayload:
    """Verify SObjectPayload inputs are rendered via to_payload()."""

    @pytest.fixture
    def renderer(self) -> SalesforceRenderer:
        """Return renderer."""
        return SalesforceRenderer()

    def test_applies_serialization_alias(self, renderer: SalesforceRenderer) -> None:
        """Validate applies serialization alias."""

        class AccountPayload(SObjectPayload):
            """Represent AccountPayload."""

            name: str = Field(serialization_alias="Name")

        result = renderer.render(AccountPayload(name="ACME Corp"))
        assert json.loads(result) == {"Name": "ACME Corp"}

    def test_excludes_none_fields(self, renderer: SalesforceRenderer) -> None:
        """Validate excludes none fields."""

        class AccountPayload(SObjectPayload):
            """Represent AccountPayload."""

            name: str = Field(serialization_alias="Name")
            phone: str | None = Field(default=None, serialization_alias="Phone")

        result = renderer.render(AccountPayload(name="ACME Corp"))
        parsed = json.loads(result)
        assert "Phone" not in parsed

    def test_includes_set_optional_fields(self, renderer: SalesforceRenderer) -> None:
        """Validate includes set optional fields."""

        class AccountPayload(SObjectPayload):
            """Represent AccountPayload."""

            name: str = Field(serialization_alias="Name")
            phone: str | None = Field(default=None, serialization_alias="Phone")

        result = renderer.render(AccountPayload(name="ACME Corp", phone="+31201234567"))
        assert json.loads(result) == {"Name": "ACME Corp", "Phone": "+31201234567"}

    def test_renders_datetime_field(self, renderer: SalesforceRenderer) -> None:
        """Validate renders datetime field."""

        class OpportunityPayload(SObjectPayload):
            """Represent OpportunityPayload."""

            close_date: datetime.date = Field(serialization_alias="CloseDate")

        result = renderer.render(
            OpportunityPayload(close_date=datetime.date(2026, 3, 15))
        )
        assert json.loads(result) == {"CloseDate": "2026-03-15"}

    def test_renders_decimal_field(self, renderer: SalesforceRenderer) -> None:
        """Validate renders decimal field."""

        class OpportunityPayload(SObjectPayload):
            """Represent OpportunityPayload."""

            amount: decimal.Decimal = Field(serialization_alias="Amount")

        result = renderer.render(OpportunityPayload(amount=decimal.Decimal("9999.99")))
        assert json.loads(result) == {"Amount": "9999.99"}


class TestSalesforceRendererProtocol:
    """Verify SalesforceRenderer satisfies the Renderer protocol."""

    def test_satisfies_renderer_protocol(self) -> None:
        """Validate satisfies renderer protocol."""
        from plynt.http.renderer import Renderer

        assert isinstance(SalesforceRenderer(), Renderer)
