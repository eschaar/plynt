"""Checkpoint storage primitives for Salesforce CDC replay cursors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from plynt.base.cache import CacheBackend

__all__ = [
    "CacheSalesforceCDCCheckpointStore",
    "InMemorySalesforceCDCCheckpointStore",
    "SalesforceCDCCheckpointStore",
]


@runtime_checkable
class SalesforceCDCCheckpointStore(Protocol):
    """Store and retrieve replay cursors for one CDC stream key."""

    def load(self, stream_key: str) -> int | None:
        """Return the last checkpointed replay cursor for ``stream_key``."""
        raise NotImplementedError

    def save(self, stream_key: str, replay_id: int) -> None:
        """Persist ``replay_id`` as the latest checkpoint for ``stream_key``."""
        raise NotImplementedError

    def delete(self, stream_key: str) -> None:
        """Remove a stored checkpoint for ``stream_key`` if present."""
        raise NotImplementedError


@dataclass(slots=True)
class InMemorySalesforceCDCCheckpointStore:
    """In-process checkpoint store for development and tests only."""

    _store: dict[str, int] = field(default_factory=dict)

    def load(self, stream_key: str) -> int | None:
        """Return the checkpointed replay cursor for ``stream_key``."""
        return self._store.get(stream_key)

    def save(self, stream_key: str, replay_id: int) -> None:
        """Persist ``replay_id`` for ``stream_key`` in local process memory."""
        self._store[stream_key] = replay_id

    def delete(self, stream_key: str) -> None:
        """Remove a local-process checkpoint if one exists."""
        self._store.pop(stream_key, None)


@dataclass(slots=True)
class CacheSalesforceCDCCheckpointStore:
    """Persist CDC checkpoints through the generic ``CacheBackend`` API."""

    backend: CacheBackend
    prefix: str = "salesforce:cdc:checkpoint:"

    # Pylint cannot infer the Protocol return type from CacheBackend.get.
    # The runtime contract here is still correct and validated by tests.
    # pylint: disable=assignment-from-no-return
    def load(self, stream_key: str) -> int | None:
        """Return a checkpointed replay cursor from the cache backend."""
        value = self.backend.get(self._key(stream_key))
        if isinstance(value, int):
            return value
        return None

    def save(self, stream_key: str, replay_id: int) -> None:
        """Persist a replay cursor in the cache backend without expiry."""
        self.backend.set(self._key(stream_key), replay_id)

    def delete(self, stream_key: str) -> None:
        """Delete a checkpoint entry from the cache backend."""
        self.backend.delete(self._key(stream_key))

    def _key(self, stream_key: str) -> str:
        """Build the cache key for one CDC stream."""
        return f"{self.prefix}{stream_key}"
