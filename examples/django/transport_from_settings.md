# Django transport from settings example

Use this snippet as a copy-paste starting point for building a transport
through `transport_from_django_settings` or
`async_transport_from_django_settings`.

Run this from a Django-aware runtime (for example `manage.py shell`) so
`django.conf.settings` and `django.core.cache` are available.

```python
from __future__ import annotations

from plynt.adapters.django.transport import (
    async_transport_from_django_settings,
    transport_from_django_settings,
)
from plynt.http.auth import OAuth2ClientCredentialsConfig
from plynt.http.settings import HTTPSettings
from plynt.middleware.logging import AsyncLoggingMiddleware, LoggingMiddleware


class ExternalAPISettings(HTTPSettings):
    """Typed settings model for one upstream API block in Django settings."""

    client_id: str = ""
    client_secret: str = ""
    token_url: str = ""

    @property
    def auth(self) -> OAuth2ClientCredentialsConfig | None:
        """Return OAuth2 config only when credentials are present."""
        if not self.client_id or not self.client_secret or not self.token_url:
            return None
        return OAuth2ClientCredentialsConfig(
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_url=self.token_url,
        )


def build_transport() -> object:
    """Build a sync transport from Django settings and cache aliases."""
    return transport_from_django_settings(
        "EXTERNAL_API",
        ExternalAPISettings,
        response_cache_alias="plynt_responses",
        auth_cache_alias="plynt_tokens",
        middlewares=[LoggingMiddleware()],
    )


def build_async_transport() -> object:
    """Build an async transport from Django settings and cache aliases."""
    return async_transport_from_django_settings(
        "EXTERNAL_API",
        ExternalAPISettings,
        response_cache_alias="plynt_responses",
        auth_cache_alias="plynt_tokens",
        middlewares=[AsyncLoggingMiddleware()],
    )
```

## Notes

1. `EXTERNAL_API` must exist in Django settings with keys expected by
   `ExternalAPISettings`.
1. Use `build_async_transport()` only from async Django request paths under
   ASGI.
1. Keep the middleware list focused and deterministic; ordering affects
   request and response behavior.
