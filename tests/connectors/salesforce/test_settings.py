"""Tests for SalesforceSettings."""

from __future__ import annotations

from plynth.connectors.salesforce.settings import SalesforceSettings
from plynth.http.settings import ApiSettings


class TestSalesforceSettings:
    """Verify defaults, inheritance, and field presence."""

    def test_inherits_from_api_settings(self) -> None:
        """Validate inherits from api settings."""
        assert issubclass(SalesforceSettings, ApiSettings)

    def test_default_api_version_is_empty_for_dynamic_discovery(self) -> None:
        """Validate default api version is empty for dynamic discovery."""
        settings = SalesforceSettings()
        assert settings.api_version == ""

    def test_default_instance_url_is_empty(self) -> None:
        """Validate default instance url is empty."""
        settings = SalesforceSettings()
        assert settings.instance_url == ""

    def test_instance_url_can_be_set(self) -> None:
        """Validate instance url can be set."""
        settings = SalesforceSettings(instance_url="https://myorg.my.salesforce.com")
        assert settings.instance_url == "https://myorg.my.salesforce.com"

    def test_api_version_can_be_overridden(self) -> None:
        """Validate api version can be overridden."""
        settings = SalesforceSettings(api_version="62.0")
        assert settings.api_version == "62.0"

    def test_declares_auth_fields(self) -> None:
        """Validate declares auth fields."""
        settings = SalesforceSettings(
            client_id="my-client",
            client_secret="s3cr3t",
            token_url="https://login.salesforce.com/services/oauth2/token",
            username="user@example.com",
            password="pw",
        )
        assert settings.client_id == "my-client"
        assert settings.client_secret == "s3cr3t"
        assert (
            settings.token_url == "https://login.salesforce.com/services/oauth2/token"
        )
        assert settings.username == "user@example.com"
        assert settings.password == "pw"
