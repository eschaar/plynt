# Auth configs reference

Authentication is configured via typed dataclasses and passed to
`auth_from_config()` (sync) or `async_auth_from_config()` (async).

Both functions are in `plynt.http.auth`.

______________________________________________________________________

## BearerAuthConfig

Static token. Sends `Authorization: Bearer <token>` on every request.

| Field   | Type  | Required | Description                 |
| ------- | ----- | -------- | --------------------------- |
| `token` | `str` | yes      | The bearer token or API key |

```python
from plynt.http.auth import BearerAuthConfig, auth_from_config

auth = auth_from_config(BearerAuthConfig(token="my-api-key"))
```

______________________________________________________________________

## BasicAuthConfig

HTTP Basic authentication. Encodes `username:password` in the
`Authorization` header.

| Field      | Type  | Required | Description |
| ---------- | ----- | -------- | ----------- |
| `username` | `str` | yes      | Username    |
| `password` | `str` | yes      | Password    |

```python
from plynt.http.auth import BasicAuthConfig, auth_from_config

auth = auth_from_config(BasicAuthConfig(username="alice", password="hunter2"))
```

______________________________________________________________________

## OAuth2ClientCredentialsConfig

OAuth2 client credentials flow (RFC 6749 §4.4). Exchanges a
`client_id`/`client_secret` for an access token. Tokens are refreshed
automatically on expiry.

| Field           | Type             | Required | Description                                            |
| --------------- | ---------------- | -------- | ------------------------------------------------------ |
| `client_id`     | `str`            | yes      | OAuth2 client ID                                       |
| `client_secret` | `str`            | yes      | OAuth2 client secret                                   |
| `token_url`     | `str`            | yes      | Token endpoint URL                                     |
| `scope`         | `str \| None`    | no       | Space-separated OAuth2 scopes                          |
| `ttl_leeway`    | `int`            | no       | Seconds before expiry to force a refresh (default: 60) |
| `extra_params`  | `dict[str, str]` | no       | Extra form fields sent with the token request          |

```python
from plynt.http.auth import OAuth2ClientCredentialsConfig, auth_from_config

auth = auth_from_config(
    OAuth2ClientCredentialsConfig(
        client_id="my-client-id",
        client_secret="my-client-secret",
        token_url="https://auth.example.com/oauth/token",
        scope="read write",
        ttl_leeway=60,
    )
)
```

______________________________________________________________________

## OAuth2JWTBearerConfig

OAuth2 JWT Bearer Token flow (RFC 7523). You provide a factory that
generates a signed JWT assertion. Plynt exchanges it for an access token.

| Field                | Type                | Required | Description                                              |
| -------------------- | ------------------- | -------- | -------------------------------------------------------- |
| `token_url`          | `str`               | yes      | Token endpoint URL                                       |
| `assertion_factory`  | `Callable[[], str]` | yes      | Callable that produces a signed JWT assertion            |
| `cache_key_material` | `str`               | yes      | Unique string used to derive the cache key for the token |
| `ttl_leeway`         | `int`               | no       | Seconds before expiry to force a refresh (default: 60)   |

```python
from plynt.http.auth import OAuth2JWTBearerConfig, auth_from_config


def build_assertion() -> str:
    # Build and sign your JWT here
    return "<signed-jwt>"


auth = auth_from_config(
    OAuth2JWTBearerConfig(
        token_url="https://auth.example.com/oauth/token",
        assertion_factory=build_assertion,
        cache_key_material="my-issuer:my-subject",
    )
)
```

______________________________________________________________________

## OAuth2PasswordConfig

OAuth2 Resource Owner Password Credentials (ROPC) flow. Deprecated in
most modern APIs — prefer `OAuth2ClientCredentialsConfig` or
`OAuth2JWTBearerConfig`.

| Field           | Type          | Required | Description                                            |
| --------------- | ------------- | -------- | ------------------------------------------------------ |
| `client_id`     | `str`         | yes      | OAuth2 client ID                                       |
| `client_secret` | `str`         | yes      | OAuth2 client secret                                   |
| `token_url`     | `str`         | yes      | Token endpoint URL                                     |
| `username`      | `str`         | yes      | Resource owner username                                |
| `password`      | `str`         | yes      | Resource owner password                                |
| `scope`         | `str \| None` | no       | Space-separated OAuth2 scopes                          |
| `ttl_leeway`    | `int`         | no       | Seconds before expiry to force a refresh (default: 60) |

______________________________________________________________________

## Token caching

OAuth2 flows cache tokens in memory by default. Provide a
`CacheBackend` to share the token across processes:

```python
import redis
from plynt.cache import RedisCache
from plynt.http.auth import OAuth2ClientCredentialsConfig, auth_from_config

cache = RedisCache(redis.Redis(host="localhost"), prefix="tokens:")

auth = auth_from_config(
    OAuth2ClientCredentialsConfig(
        client_id="...",
        client_secret="...",
        token_url="...",
    ),
    cache=cache,
)
```

______________________________________________________________________

## Async

Use `async_auth_from_config()` with `HttpxAsyncTransport`:

```python
from plynt.http.auth import async_auth_from_config

auth = async_auth_from_config(OAuth2ClientCredentialsConfig(...))
```
