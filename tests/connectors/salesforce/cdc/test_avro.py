"""Focused tests for Salesforce CDC Avro decode primitives."""

from __future__ import annotations

import json
from io import BytesIO
from types import SimpleNamespace
from typing import Any

import fastavro
import pytest

from plynth.connectors.salesforce.cdc import avro


class _FakeFastAvroRuntime:
    """Small fastavro-like runtime stand-in for deterministic tests."""

    def __init__(self) -> None:
        """Track parse calls to verify schema-cache behavior."""
        self.parse_calls = 0

    def parse_schema(self, schema: Any) -> dict[str, Any]:
        """Return a wrapped schema and count parse invocations."""
        self.parse_calls += 1
        return {"parsed": schema}

    @staticmethod
    def schemaless_reader(stream: Any, parsed_schema: dict[str, Any]) -> dict[str, Any]:
        """Return a deterministic dictionary from bytes and schema input."""
        return {
            "payload": stream.read().decode("utf-8"),
            "schema": parsed_schema,
        }


class TestAvroPayloadDecoder:
    """Verify runtime guard, decode flow, and schema caching behavior."""

    def test_raises_clear_error_when_runtime_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fail clearly when fastavro is not installed."""
        monkeypatch.setattr(
            avro,
            "_FASTAVRO_IMPORT_ERROR",
            ModuleNotFoundError("No module named 'fastavro'"),
        )

        with pytest.raises(RuntimeError, match="fastavro runtime is not installed"):
            avro.ensure_fastavro_runtime()

    def test_decodes_real_avro_record_and_reuses_schema(self) -> None:
        """Round-trip real binary Avro rather than a decoder-shaped test double"""
        schema = {
            "type": "record",
            "name": "Account",
            "fields": [
                {"name": "Name", "type": "string"},
                {"name": "Description", "type": ["null", "string"]},
                {
                    "name": "Address",
                    "type": {
                        "type": "record",
                        "name": "Address",
                        "fields": [{"name": "City", "type": "string"}],
                    },
                },
            ],
        }
        record = {
            "Name": "Example",
            "Description": None,
            "Address": {"City": "Utrecht"},
        }
        output = BytesIO()
        fastavro.schemaless_writer(output, schema, record)
        decoder = avro.AvroPayloadDecoder()
        schema_json = json.dumps(schema)

        assert decoder.decode(schema_json, output.getvalue()) == record
        assert decoder.decode(schema_json, output.getvalue()) == record

    def test_real_avro_rejects_truncated_payload(self) -> None:
        schema = (
            '{"type":"record","name":"Account",'
            '"fields":[{"name":"Name","type":"string"}]}'
        )
        with pytest.raises(EOFError):
            avro.AvroPayloadDecoder().decode(schema, b"")

    def test_decodes_payload_with_runtime_shim(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Decode one payload record using parse and schemaless reader hooks."""
        runtime = _FakeFastAvroRuntime()
        monkeypatch.setattr(avro, "_FASTAVRO_IMPORT_ERROR", None)
        monkeypatch.setattr(avro, "_load_fastavro_runtime", lambda: runtime)

        decoder = avro.AvroPayloadDecoder()
        record = decoder('{"type": "record", "name": "Account"}', b"abc")

        assert record["payload"] == "abc"
        assert record["schema"]["parsed"]["name"] == "Account"
        assert runtime.parse_calls == 1

    def test_caches_parsed_schema_for_repeat_decode(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Parse one schema only once across repeated payload decodes."""
        runtime = _FakeFastAvroRuntime()
        monkeypatch.setattr(avro, "_FASTAVRO_IMPORT_ERROR", None)
        monkeypatch.setattr(avro, "_load_fastavro_runtime", lambda: runtime)

        decoder = avro.AvroPayloadDecoder()
        schema_json = '{"type": "record", "name": "Account"}'

        decoder.decode(schema_json, b"one")
        decoder.decode(schema_json, b"two")

        assert runtime.parse_calls == 1

    def test_raises_for_invalid_schema_json(self) -> None:
        """Raise a clear error when schema JSON cannot be parsed."""
        decoder = avro.AvroPayloadDecoder()

        with pytest.raises(RuntimeError, match="Schema JSON is not valid Avro JSON"):
            decoder.decode("{invalid-json}", b"x")

    def test_raises_when_reader_returns_non_dict(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Raise a clear error for non-dictionary Avro decode output."""

        class _BadRuntime(_FakeFastAvroRuntime):
            @staticmethod
            def schemaless_reader(stream: Any, parsed_schema: dict[str, Any]) -> Any:
                return [stream.read(), parsed_schema]

        runtime = _BadRuntime()
        monkeypatch.setattr(avro, "_FASTAVRO_IMPORT_ERROR", None)
        monkeypatch.setattr(avro, "_load_fastavro_runtime", lambda: runtime)

        decoder = avro.AvroPayloadDecoder()
        with pytest.raises(
            RuntimeError,
            match="Decoded Avro payload is not a dictionary record",
        ):
            decoder.decode('{"type": "record", "name": "Account"}', b"x")

    @pytest.mark.parametrize("missing_hook", ["parse_schema", "schemaless_reader"])
    def test_rejects_runtime_without_required_callable(
        self, monkeypatch: pytest.MonkeyPatch, missing_hook: str
    ) -> None:
        runtime = SimpleNamespace(
            parse_schema=lambda schema: schema,
            schemaless_reader=lambda stream, schema: {},
        )
        setattr(runtime, missing_hook, None)
        monkeypatch.setattr(avro, "_load_fastavro_runtime", lambda: runtime)

        with pytest.raises(RuntimeError, match=f"does not expose {missing_hook}"):
            avro.AvroPayloadDecoder().decode(
                '{"type":"record","name":"Account","fields":[]}', b""
            )
