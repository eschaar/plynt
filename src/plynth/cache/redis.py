"""Redis cache backend and its typed configuration.

``RedisCache`` wraps any Redis client and adapts it to the ``CacheBackend``
protocol.  Values are serialised with ``pickle``.

Requires ``pip install redis``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from plynth.base.cache import CacheBackend, CacheConfigBase, SupportsStats, SupportsTTL


class RedisCache(CacheBackend, SupportsTTL, SupportsStats):
    """Adapts a Redis client to the ``CacheBackend`` protocol.

    Values are serialised with ``pickle`` before storing and deserialised
    on retrieval.

    .. warning::

        Deserialising pickle data from an untrusted or compromised Redis
        instance can lead to remote code execution.  Ensure your Redis
        instance is properly secured (authentication, network isolation)
        and never expose it to untrusted parties.

    Per-key TTL is supported via Redis ``EXPIRE`` (seconds, rounded to
    the nearest integer).  Pass ``ttl=`` to ``set()`` to activate it.

    Keys are prefixed with *prefix* to avoid collisions with other
    applications sharing the same Redis instance.

    Satisfies ``CacheBackend``, ``SupportsTTL``, and ``SupportsStats``.

    Requires ``pip install redis``.

    Example::

        import redis
        from plynth.cache import RedisCache

        client = redis.Redis(host="localhost", port=6379, db=0)
        backend = RedisCache(client, prefix="plynth:")

    Args:
        client: A Redis client instance (``redis.Redis`` or compatible).
        prefix: Key prefix to namespace all entries.  Defaults to
            ``"plynth:"``.

    """

    def __init__(self, client: Any, prefix: str = "plynth:") -> None:
        """Initialize RedisCache."""
        self._client = client
        self._prefix = prefix

    def _key(self, key: str) -> str:
        """Handle key."""
        return f"{self._prefix}{key}"

    def get(self, key: str, default: Any = None) -> Any:
        """Return the cached value for *key*, or *default* if absent."""
        import pickle

        data = self._client.get(self._key(key))
        if data is None:
            return default
        return pickle.loads(data)  # noqa: S301

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store *value* under *key*, optionally expiring after *ttl* seconds.

        Args:
            key: Cache key.
            value: Value to store (serialised with pickle).
            ttl: Time-to-live in seconds.  Rounded to the nearest integer
                for Redis ``EXPIRE``.  ``None`` means no expiry.

        """
        import pickle

        data = pickle.dumps(value)
        rkey = self._key(key)
        if ttl is not None:
            self._client.setex(rkey, max(1, int(ttl)), data)
        else:
            self._client.set(rkey, data)

    def delete(self, key: str) -> None:
        """Remove *key* from Redis."""
        self._client.delete(self._key(key))

    def clear(self) -> None:
        """Remove all keys matching this adapter's prefix.

        Uses ``SCAN`` to avoid blocking the Redis server with a single
        large ``KEYS`` or ``FLUSHDB`` call.

        """
        cursor = 0
        pattern = f"{self._prefix}*"
        while True:
            cursor, keys = self._client.scan(cursor, match=pattern, count=100)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break

    # ------------------------------------------------------------------
    # SupportsTTL
    # ------------------------------------------------------------------

    def ttl(self, key: str) -> float | None:
        """Return remaining TTL in seconds for *key*.

        Returns:
            Remaining seconds, ``0.0`` if the key is absent or expired,
            or ``None`` if the key has no expiry.

        """
        remaining = self._client.ttl(self._key(key))
        if remaining == -1:
            return None  # key exists, no expiry
        if remaining < 0:
            return 0.0  # key absent (Redis returns -2) or expired
        return float(remaining)

    # ------------------------------------------------------------------
    # SupportsStats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Return selected Redis ``INFO`` metrics."""
        info: dict[str, Any] = self._client.info()
        return {
            "connected_clients": info.get("connected_clients"),
            "used_memory_human": info.get("used_memory_human"),
            "keyspace_hits": info.get("keyspace_hits"),
            "keyspace_misses": info.get("keyspace_misses"),
        }


@dataclass
class RedisCacheConfig(CacheConfigBase):
    """Configuration for the ``RedisCache`` backend.

    Wraps a Redis client with full connection options.  The ``location``
    must be a ``redis://`` or ``rediss://`` URL — it is validated in
    ``__post_init__`` so misconfigurations are caught at construction time.

    Requires ``pip install redis``.

    Args:
        location: Redis connection URL, e.g.
            ``"redis://localhost:6379/0"`` or
            ``"rediss://myhost:6380/1"`` for TLS.
        key_prefix: Prefix prepended to every cache key to avoid
            collisions with other applications sharing the same Redis
            instance.  Defaults to ``"plynth:"``.
        socket_timeout: Timeout in seconds for socket operations.
            Passed to the underlying Redis client.  ``None`` uses the
            Redis client default (no timeout).
        retry_on_timeout: When ``True``, the Redis client retries
            timed-out socket operations once.  Defaults to ``False``.
        max_connections: Maximum number of connections in the connection
            pool.  ``None`` uses the Redis client default (unlimited).
        ssl_certfile: Path to a PEM-encoded client certificate file for
            mutual TLS.  Only meaningful with ``rediss://`` URLs.
        ssl_keyfile: Path to the private key file for the client cert.
            Only meaningful with ``rediss://`` URLs.
        ssl_ca_certs: Path to a CA bundle file used to verify the
            server certificate.  Only meaningful with ``rediss://`` URLs.

    Example::

        from plynth.cache import RedisCacheConfig

        class SalesforceSettings(HTTPSettings):
            redis_url: str = ""  # SF_REDIS_URL=redis://...

            @property
            def caches(self) -> dict[str, CacheConfig] | None:
                if not self.redis_url:
                    return None
                return {
                    "responses": RedisCacheConfig(
                        location=self.redis_url,
                        key_prefix="sf:http:",
                    ),
                    "tokens": RedisCacheConfig(
                        location=self.redis_url,
                        key_prefix="sf:tokens:",
                        socket_timeout=2.0,
                    ),
                }

    """

    location: str
    key_prefix: str = "plynth:"
    socket_timeout: float | None = None
    retry_on_timeout: bool = False
    max_connections: int | None = None
    ssl_certfile: str | None = None
    ssl_keyfile: str | None = None
    ssl_ca_certs: str | None = None

    def __post_init__(self) -> None:
        """Validate the Redis location URL."""
        if not self.location:
            raise ValueError(
                "RedisCacheConfig requires a non-empty location. "
                "Expected a redis:// or rediss:// URL."
            )
        if not self.location.startswith(("redis://", "rediss://")):
            raise ValueError(
                "RedisCacheConfig.location must start with redis:// or "
                f"rediss://, got: {self.location!r}"
            )
