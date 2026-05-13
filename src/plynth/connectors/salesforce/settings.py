"""Salesforce-specific settings for Plynth.

Extends ``ApiSettings`` with fields required to connect to the Salesforce
Platform REST API. Use this as the base class for any Salesforce integration
settings.

Environment variable prefix convention: use ``SF_`` (or a more specific
prefix such as ``ACME_SF_``) so that Salesforce credentials are clearly
separated from other service configuration.

The ``instance_url`` field is optional when using ``SalesforceAPIClient`` with
``SalesforceClientCredentialsAuthMiddleware``: the client resolves the org-specific
host automatically from the OAuth2 token response. Set ``instance_url`` only
if you manage the base URL yourself (e.g. with a plain ``APIClient``).

Example ``.env``::

    SF_CLIENT_ID=3MVG9...
    SF_CLIENT_SECRET=abc123
    SF_TOKEN_URL=https://login.salesforce.com/services/oauth2/token
    SF_API_VERSION=62.0

Example usage with automatic ``instance_url`` resolution::

    from plynth.http.transport import HttpxSyncTransport
    from plynth.connectors.salesforce.auth import (
        SalesforceClientCredentialsAuthMiddleware,
    )
    from plynth.connectors.salesforce.client import SalesforceAPIClient
    from plynth.connectors.salesforce.facade import SObjectAPIFacade
    from plynth.connectors.salesforce.settings import SalesforceSettings
    from pydantic_settings import SettingsConfigDict

    class MySalesforceSettings(SalesforceSettings):
        model_config = SettingsConfigDict(
            env_prefix="SF_",
            env_file=".env",
        )

    settings = MySalesforceSettings()
    auth = SalesforceClientCredentialsAuthMiddleware(
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        token_url=settings.token_url,
    )
    transport = HttpxSyncTransport(middlewares=[auth])
    client = SalesforceAPIClient(auth=auth, transport=transport)
    facade = SObjectAPIFacade(client)
    svc = facade.sobject("Account", api_version=settings.api_version)

"""

from __future__ import annotations

from plynth.http.settings import ApiSettings

__all__ = ["SalesforceSettings"]


class SalesforceSettings(ApiSettings):
    """Settings for the Salesforce Platform REST API.

    Extends ``ApiSettings`` with Salesforce-specific fields.  Credential
    fields (``client_id``, ``client_secret``, ``token_url``) are declared
    here; wire them manually to
    ``SalesforceClientCredentialsAuthMiddleware`` (or
    pass to ``auth_from_config()``) when constructing the transport.

    Attributes:
        instance_url: The org-specific Salesforce host (e.g.
            ``"https://myorg.my.salesforce.com"``). Not needed when using
            ``SalesforceAPIClient`` with
            ``SalesforceClientCredentialsAuthMiddleware``,
            which resolves the instance URL automatically from the OAuth2 token
            response. Provide it only when using a plain ``APIClient``.
        api_version: Salesforce REST API version to target. When left empty
            (default), services resolve the latest version lazily from
            ``GET /services/data/``. Set explicitly to pin a fixed version.
            Format: ``"<major>.<minor>"`` (e.g. ``"62.0"``).
        client_id: OAuth2 client identifier. Read from env.
        client_secret: OAuth2 client secret. Read from env.
        token_url: Full URL of the OAuth2 token endpoint.
        username: Username for OAuth2 Password grant. Optional when using
            Client Credentials flow.
        password: Password for OAuth2 Password grant. Optional when using
            Client Credentials flow.
        security_token: Salesforce security token appended to the password
            for orgs without IP allowlisting. Optional. When set, it is
            concatenated with ``password`` inside
            ``SalesforcePasswordAuthMiddleware`` before the token request.

    """

    instance_url: str = ""
    api_version: str = ""
    client_id: str = ""
    client_secret: str = ""
    token_url: str = ""
    username: str = ""
    password: str = ""
    security_token: str = ""
