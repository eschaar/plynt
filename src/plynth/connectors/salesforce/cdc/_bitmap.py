"""Translate Salesforce CDC header bitmaps into usable field names

Pub/Sub encodes ``changedFields``, ``nulledFields``, and ``diffFields`` as
hexadecimal bitmaps. Field positions refer to the event's Avro schema, not
to payload dictionary order or a Salesforce object's describe response.
"""

from __future__ import annotations

import json
import re
from typing import Any


class _FieldBitmapDecoder:
    """Resolve CDC field bitmaps using the schema for each event

    Bit zero selects the first field in the Avro record, including header
    fields. A root entry such as ``0x06`` selects positions one and two.
    A compound entry such as ``3-0x02`` selects child position one within
    the record at root position three and produces a dotted field name,
    for example ``BillingAddress.Street``. Further position prefixes can
    traverse deeper records.

    Optional records and named type references are resolved through Avro
    unions and namespaces. Parsed schemas and named records are cached per
    decoder instance, keyed by schema JSON, so schema changes do not reuse
    old field positions. Already-decoded names from custom adapters pass
    through unchanged; decoding never mutates the input list.
    """

    _HEX_BITMAP = re.compile(r"0[xX][0-9a-fA-F]+")

    def __init__(self) -> None:
        self._schemas: dict[str, tuple[dict[str, Any], dict[str, dict[str, Any]]]] = {}

    def decode(self, schema_json: str, value: Any) -> list[str]:
        """Expand CDC header bitmap entries into field names

        Args:
            schema_json: Avro schema returned by GetSchema for this event.
                Parsed only when an entry contains a bitmap.
            value: One header field's list of root or compound bitmap entries,
                or field names already decoded by a custom adapter.

        Returns:
            Names in entry order, with fields within each bitmap in schema
            order. Return an empty list for an absent header field.

        Raises:
            RuntimeError: If the input, schema, bitmap, or field position
                cannot be resolved safely.

        """
        if value is None:
            return []
        if not isinstance(value, list) or any(
            not isinstance(entry, str) for entry in value
        ):
            raise RuntimeError("CDC field bitmap must be a list of strings")
        names: list[str] = []
        for entry in value:
            if entry.lower().startswith("0x") or "-0x" in entry.lower():
                names.extend(self._decode_entry(schema_json, entry))
            else:
                names.append(entry)
        return names

    def _get_schema(
        self, schema_json: str
    ) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        """Parse and index each bitmap schema once per subscriber"""
        if schema_json not in self._schemas:
            try:
                schema = json.loads(schema_json)
            except json.JSONDecodeError as exc:
                raise RuntimeError("CDC field bitmap schema is not valid JSON") from exc
            self._record_fields(schema)
            records: dict[str, dict[str, Any]] = {}
            self._collect_records(schema, records)
            self._schemas[schema_json] = schema, records
        return self._schemas[schema_json]

    def _decode_entry(self, schema_json: str, entry: str) -> list[str]:
        """Resolve field positions from the least-significant bitmap bit"""
        positions = entry.split("-")
        bitmap = positions.pop()
        if self._HEX_BITMAP.fullmatch(bitmap) is None:
            raise RuntimeError("CDC field bitmap contains invalid hexadecimal data")
        record, records = self._get_schema(schema_json)
        namespace = self._record_namespace(record, "")
        prefix = ""
        for position in positions:
            if not position.isascii() or not position.isdecimal():
                raise RuntimeError("CDC compound bitmap has an invalid field position")
            fields = self._record_fields(record)
            index = int(position)
            if index >= len(fields):
                raise RuntimeError("CDC compound bitmap position exceeds schema fields")
            field = fields[index]
            prefix += f"{field['name']}."
            record = self._resolve_record(field.get("type"), records, namespace)
            namespace = self._record_namespace(record, namespace)
        fields = self._record_fields(record)
        bits = int(bitmap, 16)
        if bits.bit_length() > len(fields):
            raise RuntimeError("CDC field bitmap exceeds schema fields")
        return [
            f"{prefix}{field['name']}"
            for index, field in enumerate(fields)
            if bits & (1 << index)
        ]

    @staticmethod
    def _record_fields(record: Any) -> list[dict[str, Any]]:
        """Validate and return Avro fields without changing declaration order"""
        if not isinstance(record, dict) or record.get("type") != "record":
            raise RuntimeError("CDC field bitmap requires an Avro record schema")
        fields = record.get("fields")
        if not isinstance(fields, list) or any(
            not isinstance(field, dict) or not isinstance(field.get("name"), str)
            for field in fields
        ):
            raise RuntimeError("CDC field bitmap schema has invalid record fields")
        return fields

    @classmethod
    def _collect_records(
        cls, schema: Any, records: dict[str, dict[str, Any]], namespace: str = ""
    ) -> None:
        """Index nested Avro records by fully qualified name for type resolution"""
        if isinstance(schema, list):
            for branch in schema:
                cls._collect_records(branch, records, namespace)
        elif isinstance(schema, dict):
            if schema.get("type") == "record":
                name = schema.get("name")
                if not isinstance(name, str) or not name:
                    raise RuntimeError("CDC field bitmap schema has an unnamed record")
                namespace = schema.get("namespace", namespace)
                full_name = (
                    name if "." in name or not namespace else f"{namespace}.{name}"
                )
                namespace = full_name.rpartition(".")[0]
                # Retain the defining namespace when a later field uses a name.
                records[full_name] = {**schema, "namespace": namespace}
                for field in cls._record_fields(schema):
                    cls._collect_records(field.get("type"), records, namespace)
            else:
                cls._collect_records(schema.get("items"), records, namespace)
                cls._collect_records(schema.get("values"), records, namespace)
                if isinstance(schema.get("type"), (dict, list)):
                    cls._collect_records(schema["type"], records, namespace)

    @staticmethod
    def _record_namespace(record: dict[str, Any], parent_namespace: str) -> str:
        """Resolve a record's explicit namespace or inherit its parent's"""
        name = record.get("name", "")
        if "." in name:
            return str(name.rpartition(".")[0])
        return str(record.get("namespace", parent_namespace))

    @classmethod
    def _resolve_record(
        cls, schema: Any, records: dict[str, dict[str, Any]], namespace: str
    ) -> dict[str, Any]:
        """Find the compound record behind a union, wrapper, or named reference"""
        if isinstance(schema, list):
            candidates = [
                branch
                for branch in schema
                if (isinstance(branch, dict) and branch.get("type") == "record")
                or (
                    isinstance(branch, str)
                    and (branch in records or f"{namespace}.{branch}" in records)
                )
            ]
            if len(candidates) != 1:
                raise RuntimeError(
                    "CDC compound bitmap requires one record union branch"
                )
            return cls._resolve_record(candidates[0], records, namespace)
        if isinstance(schema, str):
            schema = records.get(f"{namespace}.{schema}", records.get(schema))
        elif isinstance(schema, dict) and schema.get("type") != "record":
            return cls._resolve_record(schema.get("type"), records, namespace)
        if not isinstance(schema, dict):
            raise RuntimeError("CDC compound bitmap does not reference a record")
        cls._record_fields(schema)
        return schema
