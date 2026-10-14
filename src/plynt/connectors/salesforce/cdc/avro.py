"""Avro payload decoding primitives for Salesforce CDC."""

from __future__ import annotations

import json
from importlib import import_module
from importlib.util import find_spec
from io import BytesIO
from typing import Any

__all__ = [
    "AvroPayloadDecoder",
    "ensure_fastavro_runtime",
]

try:  # pragma: no cover
    HAS_FASTAVRO = find_spec("fastavro") is not None
except ModuleNotFoundError:  # pragma: no cover
    HAS_FASTAVRO = False

if not HAS_FASTAVRO:  # pragma: no cover
    _FASTAVRO_IMPORT_ERROR: Exception | None = ModuleNotFoundError(
        "No module named 'fastavro'"
    )
else:  # pragma: no cover
    _FASTAVRO_IMPORT_ERROR = None


def ensure_fastavro_runtime() -> None:
    """Raise a clear error when fastavro is unavailable."""
    if _FASTAVRO_IMPORT_ERROR is not None:
        raise RuntimeError(
            "fastavro runtime is not installed; "
            "install plynt[salesforce] or add fastavro"
        ) from _FASTAVRO_IMPORT_ERROR


def _load_fastavro_runtime() -> Any:
    """Load the fastavro module on demand."""
    ensure_fastavro_runtime()
    return import_module("fastavro")


class AvroPayloadDecoder:
    """Decode Salesforce CDC Avro payload bytes into Python dictionaries."""

    def __init__(self) -> None:
        """Initialize parsed-schema cache for repeated schema JSON input."""
        self._parsed_schema_cache: dict[str, Any] = {}

    def __call__(self, schema_json: str, payload: bytes) -> dict[str, Any]:
        """Decode one Avro payload using schema JSON."""
        return self.decode(schema_json, payload)

    def decode(self, schema_json: str, payload: bytes) -> dict[str, Any]:
        """Decode one payload and return a dictionary record."""
        parsed_schema = self._get_parsed_schema(schema_json)

        fastavro = _load_fastavro_runtime()
        schemaless_reader = getattr(fastavro, "schemaless_reader", None)
        if not callable(schemaless_reader):
            raise RuntimeError("fastavro runtime does not expose schemaless_reader")

        record = schemaless_reader(BytesIO(payload), parsed_schema)
        if not isinstance(record, dict):
            raise RuntimeError("Decoded Avro payload is not a dictionary record")
        return record

    def _get_parsed_schema(self, schema_json: str) -> Any:
        """Parse and cache one Avro schema JSON document."""
        cached = self._parsed_schema_cache.get(schema_json)
        if cached is not None:
            return cached

        try:
            schema = json.loads(schema_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Schema JSON is not valid Avro JSON") from exc

        fastavro = _load_fastavro_runtime()
        parse_schema = getattr(fastavro, "parse_schema", None)
        if not callable(parse_schema):
            raise RuntimeError("fastavro runtime does not expose parse_schema")

        parsed_schema = parse_schema(schema)
        self._parsed_schema_cache[schema_json] = parsed_schema
        return parsed_schema
