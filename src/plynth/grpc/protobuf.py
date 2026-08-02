"""Generic protobuf helper contracts for the gRPC layer."""

from __future__ import annotations

from collections.abc import Callable
from importlib.util import find_spec
from typing import Protocol, TypeVar, runtime_checkable

__all__ = [
    "ProtobufParseTarget",
    "ProtobufSerializable",
    "deserialize_message",
    "ensure_protobuf_runtime",
    "serialize_message",
]

try:  # pragma: no cover
    HAS_PROTOBUF = find_spec("google.protobuf.message") is not None
except ModuleNotFoundError:  # pragma: no cover
    HAS_PROTOBUF = False

if not HAS_PROTOBUF:  # pragma: no cover
    _PROTOBUF_IMPORT_ERROR: Exception | None = ModuleNotFoundError(
        "No module named 'google.protobuf'"
    )
else:  # pragma: no cover
    _PROTOBUF_IMPORT_ERROR = None


@runtime_checkable
class ProtobufSerializable(Protocol):
    """Duck-typed protocol for protobuf-like outbound messages."""

    def SerializeToString(self) -> bytes:  # noqa: N802  # pylint: disable=invalid-name
        """Return the wire-encoded protobuf payload."""
        raise NotImplementedError


@runtime_checkable
class ProtobufParseTarget(Protocol):
    """Duck-typed protocol for protobuf-like parse targets."""

    def ParseFromString(self, data: bytes) -> int:  # noqa: N802  # pylint: disable=invalid-name
        """Parse a protobuf payload into the receiving instance."""
        raise NotImplementedError


ParseTargetT = TypeVar("ParseTargetT", bound=ProtobufParseTarget)


def ensure_protobuf_runtime() -> None:
    """Raise a clear runtime error when protobuf is unavailable."""
    if _PROTOBUF_IMPORT_ERROR is not None:
        raise RuntimeError(
            "protobuf runtime is not installed; install plynth[grpc] or add protobuf"
        ) from _PROTOBUF_IMPORT_ERROR


def serialize_message(message: ProtobufSerializable) -> bytes:
    """Serialize a protobuf-like message into wire bytes."""
    ensure_protobuf_runtime()
    return message.SerializeToString()


def deserialize_message(
    payload: bytes,
    factory: Callable[[], ParseTargetT],
) -> ParseTargetT:
    """Create and populate a protobuf-like message from wire bytes."""
    ensure_protobuf_runtime()
    message = factory()
    message.ParseFromString(payload)
    return message
