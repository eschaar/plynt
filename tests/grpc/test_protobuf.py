"""Contract tests for generic protobuf helpers in the gRPC layer."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest

from plynt.grpc import protobuf


class _FakeMessage:
    """Minimal protobuf-like object for deterministic contract tests."""

    def __init__(self, payload: bytes = b"") -> None:
        """Initialize fake protobuf message state."""
        self.payload = payload

    def SerializeToString(self) -> bytes:  # noqa: N802  # pylint: disable=invalid-name
        """Return payload bytes for serialization contracts."""
        return self.payload

    def ParseFromString(self, data: bytes) -> int:  # noqa: N802  # pylint: disable=invalid-name
        """Capture parsed payload and return parsed byte length."""
        self.payload = data
        return len(data)


class TestProtobufContract:
    """Verify generic protobuf helper behavior and error handling."""

    def test_protocol_stub_methods_raise_not_implemented(self) -> None:
        """Validate protocol method stubs are not callable by default."""
        with pytest.raises(NotImplementedError):
            protobuf.ProtobufSerializable.SerializeToString(
                cast(protobuf.ProtobufSerializable, object())
            )

        with pytest.raises(NotImplementedError):
            protobuf.ProtobufParseTarget.ParseFromString(
                cast(protobuf.ProtobufParseTarget, object()),
                b"payload",
            )

    def test_serialize_message_returns_wire_bytes(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Validate serializer contract for protobuf-like objects."""
        monkeypatch.setattr(protobuf, "_PROTOBUF_IMPORT_ERROR", None)

        payload = protobuf.serialize_message(_FakeMessage(b"wire"))

        assert payload == b"wire"

    def test_deserialize_message_populates_instance(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Validate deserializer contract with a callable message factory."""
        monkeypatch.setattr(protobuf, "_PROTOBUF_IMPORT_ERROR", None)

        message = protobuf.deserialize_message(b"events", _FakeMessage)

        assert isinstance(message, _FakeMessage)
        assert message.payload == b"events"

    @pytest.mark.parametrize(
        "helper,args",
        [
            (protobuf.ensure_protobuf_runtime, ()),
            (protobuf.serialize_message, (_FakeMessage(b"x"),)),
            (protobuf.deserialize_message, (b"x", _FakeMessage)),
        ],
    )
    def test_helpers_raise_clear_error_when_runtime_missing(
        self,
        helper: Callable[..., object],
        args: tuple[object, ...],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Validate clear runtime error path without protobuf installation."""
        monkeypatch.setattr(
            protobuf,
            "_PROTOBUF_IMPORT_ERROR",
            ModuleNotFoundError("No module named 'google.protobuf'"),
        )

        with pytest.raises(RuntimeError, match="protobuf runtime is not installed"):
            helper(*args)
