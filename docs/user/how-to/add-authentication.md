# How to add authentication

Plynt supports five authentication mechanisms via typed config objects.
Pass a config to `auth_from_config()` to get the corresponding middleware,
or pass it to `HTTPSettings.auth` to wire it automatically via
`from_settings()`.

## OAuth2 Client Credentials (machine-to-machine)

The standard flow for server-to-server integrations. Exchanges a
`client_id` and `client_secret` for an access token. Tokens are refreshed
automatically when they expire.

```python
from plynt.http.auth import OAuth2ClientCredentialsConfig, auth_from_config
from plynt.http.transport import HttpxSyncTransport

auth = auth_from_config(
    OAuth2ClientCredentialsConfig(
        client_id="my-client-id",
        client_secret="my-client-secret",
        token_url="https://auth.example.com/oauth/token",
        ttl_leeway=60,  # refresh 60 seconds before expiry
    )
)
transport = HttpxSyncTransport(middlewares=[auth])
```

### Via settings

```python
from plynt.http.settings import HTTPSettings
from plynt.http.auth import OAuth2ClientCredentialsConfig
from pydantic_settings import SettingsConfigDict


class MySettings(HTTPSettings):
    model_config = SettingsConfigDict(env_prefix="MY_", env_file=".env")
    client_id: str = ""
    client_secret: str = ""

    @property
    def auth(self):
        if not self.client_id:
            return None
        return OAuth2ClientCredentialsConfig(
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_url="https://auth.example.com/oauth/token",
        )


settings = MySettings()
transport = HttpxSyncTransport.from_settings(settings)
```

## Bearer token (static API key)

For APIs that use a fixed token or API key in the `Authorization` header.

```python
from plynt.http.auth import BearerAuthConfig, auth_from_config

auth = auth_from_config(BearerAuthConfig(token="my-api-key"))
transport = HttpxSyncTransport(middlewares=[auth])
```

The token is sent as `Authorization: Bearer <token>` on every request.

## HTTP Basic authentication

```python
from plynt.http.auth import BasicAuthConfig, auth_from_config

auth = auth_from_config(BasicAuthConfig(username="alice", password="hunter2"))
transport = HttpxSyncTransport(middlewares=[auth])
```

## OAuth2 JWT Bearer (RFC 7523)

For flows where you sign a JWT assertion and exchange it for an access
token. You provide a factory callable that generates the signed JWT.

```python
from plynt.http.auth import OAuth2JWTBearerConfig, auth_from_config


def build_assertion() -> str:
    # Sign and return a JWT here using PyJWT or cryptography
    return "<signed-jwt>"


auth = auth_from_config(
    OAuth2JWTBearerConfig(
        token_url="https://auth.example.com/oauth/token",
        assertion_factory=build_assertion,
        cache_key_material="issuer:service-account",
    )
)
transport = HttpxSyncTransport(middlewares=[auth])
```

## OAuth2 Resource Owner Password Credentials (legacy)

For legacy APIs that require a username and password. This flow is
deprecated by most modern APIs.

```python
from plynt.http.auth import OAuth2PasswordConfig, auth_from_config

auth = auth_from_config(
    OAuth2PasswordConfig(
        client_id="my-client-id",
        client_secret="my-client-secret",
        token_url="https://auth.example.com/oauth/token",
        username="alice",
        password="hunter2",
    )
)
transport = HttpxSyncTransport(middlewares=[auth])
```

## Token caching

OAuth2 flows cache the token in memory by default. Pass a `CacheBackend`
to cache across processes or persist tokens in Redis:

```python
import redis
from plynt.cache import RedisCache
from plynt.http.auth import OAuth2ClientCredentialsConfig, auth_from_config

redis_client = redis.Redis(host="localhost")
cache = RedisCache(redis_client, prefix="tokens:")

auth = auth_from_config(
    OAuth2ClientCredentialsConfig(
        client_id="...",
        client_secret="...",
        token_url="...",
    ),
    cache=cache,
)
```

## Async

Use `async_auth_from_config()` instead of `auth_from_config()`:

```python
from plynt.http.auth import async_auth_from_config

auth = async_auth_from_config(OAuth2ClientCredentialsConfig(...))
```

Use the result with `HttpxAsyncTransport`.

## Reference

See [Auth configs reference](../reference/auth-configs.md) for all fields
of each config class.
