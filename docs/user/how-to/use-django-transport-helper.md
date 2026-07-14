# How to build a transport from Django settings

Use `transport_from_django_settings(...)` when your service keeps external API
config in Django `settings.py` and you want first-party plynth wiring for auth,
response caching, and retry behavior.

## Install extras

```bash
pip install "plynth[django,httpx]"
```

## Configure Django settings blocks

Define one mapping for your upstream API settings and one or more cache aliases.

```python
# settings.py
EXTERNAL_API = {
    "BASE_URL": "https://api.example.com",
    "TIMEOUT_CONNECT": 3.0,
    "TIMEOUT_READ": 15.0,
    "MAX_ATTEMPTS": 3,
    "CLIENT_ID": "${EXTERNAL_API_CLIENT_ID}",
    "CLIENT_SECRET": "${EXTERNAL_API_CLIENT_SECRET}",
    "TOKEN_URL": "https://auth.example.com/oauth/token",
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "django-default",
    },
    "plynth_responses": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/2",
    },
    "plynth_tokens": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/3",
    },
}
```

## Define typed plynth settings

Create a typed `HTTPSettings` subclass for your Django settings block.

```python
from plynth.http.auth import OAuth2ClientCredentialsConfig
from plynth.http.settings import HTTPSettings


class ExternalAPISettings(HTTPSettings):
    client_id: str = ""
    client_secret: str = ""
    token_url: str = ""

    @property
    def auth(self) -> OAuth2ClientCredentialsConfig | None:
        if not self.client_id or not self.client_secret or not self.token_url:
            return None
        return OAuth2ClientCredentialsConfig(
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_url=self.token_url,
        )
```

## Build transport from Django settings

```python
from plynth.adapters.django.transport import transport_from_django_settings
from plynth.middleware.logging import LoggingMiddleware

transport = transport_from_django_settings(
    "EXTERNAL_API",
    ExternalAPISettings,
    response_cache_alias="plynth_responses",
    auth_cache_alias="plynth_tokens",
    middlewares=[LoggingMiddleware()],
)
```

Middleware order in the helper is:

1. your custom `middlewares`
1. auth middleware from `settings.auth` (optional)
1. `CacheMiddleware` for `response_cache_alias` (optional)
1. `RetryMiddleware` from `settings.retry` or `MAX_ATTEMPTS`

## Use with APIClient

```python
from plynth.http.client import APIClient

client = APIClient(base_url="https://api.example.com", transport=transport)
response = client.get("/products")
response.raise_for_status()
```

## Logging with Django LOGGING

Plynth uses Python logging, so standard Django `LOGGING` config applies.

```python
# settings.py
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "plynth": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "plynth.http.transport": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
```

See [How to configure logging](configure-logging.md) for structured output,
throttling, and exception filters.

## Proxy and security middleware notes

When running behind ingress or reverse proxies, Django middleware and settings
determine trusted scheme and host values. Keep these aligned with outbound
plynth behavior:

1. Configure trusted proxy headers in Django (for example
   `SECURE_PROXY_SSL_HEADER`) so request scheme is accurate.
1. Prefer fixed upstream `BASE_URL` values from settings; do not derive them
   from inbound request host headers.
1. Forward only the headers you explicitly trust when using DRF header
   propagation.

This keeps callback links, tracing headers, and auth context predictable across
environments.
