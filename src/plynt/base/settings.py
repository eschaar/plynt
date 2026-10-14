"""Core settings base class for Plynt.

Defines the minimal ``Settings`` base that all service-specific
settings classes must inherit from. This class contains only
universal configuration (debug flag and .env support). Protocol- or
service-specific fields belong in subclasses.

The three-layer settings hierarchy (ADR-0004):

- ``plynt.base.settings.Settings`` — universal base (debug + .env)
- ``plynt.http.settings.HTTPSettings`` — HTTP transport fields
- ``plynt.http.settings.ApiSettings`` — REST/OAuth2 API fields

Example::

    from plynt.http.settings import ApiSettings
    from pydantic_settings import SettingsConfigDict

    class CustomerServiceSettings(ApiSettings):
        model_config = SettingsConfigDict(
            env_prefix="CUSTOMER_",
            env_file=".env",
        )

    settings = CustomerServiceSettings()
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "SettingsConfigDict"]


class Settings(BaseSettings):
    """Minimal base settings class for Plynt.

    Provides ``.env`` file support and UTF-8 encoding out of the box.
    Defines only ``debug`` — all other fields belong in subclasses.

    Subclasses can use ``env_prefix`` in their own ``model_config``
    to avoid environment variable collisions between services.

    Configuration is read from both environment variables and a ``.env``
    file (if present). Environment variables always take precedence.
    A missing ``.env`` file is silently ignored.
    """

    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
