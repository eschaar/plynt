"""Test schema-based decoding of Salesforce CDC field bitmaps"""

from __future__ import annotations

import json
from typing import Any

import pytest

from plynth.connectors.salesforce.cdc._bitmap import _FieldBitmapDecoder


@pytest.fixture
def bitmap_schema() -> str:
    """Provide ordered fields, optional compound records, and named references"""
    return json.dumps(
        {
            "type": "record",
            "name": "Account",
            "namespace": "events",
            "fields": [
                {"name": "ChangeEventHeader", "type": "string"},
                {"name": "Name", "type": "string"},
                {"name": "Description", "type": ["null", "string"]},
                {
                    "name": "BillingAddress",
                    "type": [
                        "null",
                        {
                            "type": "record",
                            "name": "Address",
                            "fields": [
                                {"name": "City", "type": "string"},
                                {"name": "Street", "type": "string"},
                                {
                                    "name": "Location",
                                    "type": {
                                        "type": "record",
                                        "name": "Coordinates",
                                        "fields": [
                                            {"name": "Latitude", "type": "double"},
                                            {"name": "Longitude", "type": "double"},
                                        ],
                                    },
                                },
                            ],
                        },
                    ],
                },
                {
                    "name": "ShippingAddress",
                    "type": ["null", "string", "events.Address"],
                },
            ],
        }
    )


class TestFieldBitmapDecoder:
    """Verify bitmap positions, compound fields, compatibility, and failures"""

    @pytest.mark.parametrize(
        ("entries", "expected"),
        [
            ([], []),
            (["0x00"], []),
            (["0X02"], ["Name"]),
            (["0x0006"], ["Name", "Description"]),
            (
                ["0x06", "3-0x03"],
                ["Name", "Description", "BillingAddress.City", "BillingAddress.Street"],
            ),
            (["3-0x02"], ["BillingAddress.Street"]),
            (["4-0x01"], ["ShippingAddress.City"]),
            (["3-2-0x02"], ["BillingAddress.Location.Longitude"]),
            (["Name", "Description"], ["Name", "Description"]),
        ],
    )
    def test_maps_bitmaps_in_schema_order(
        self, bitmap_schema: str, entries: list[str], expected: list[str]
    ) -> None:
        decoder = _FieldBitmapDecoder()
        original = entries.copy()

        assert decoder.decode(bitmap_schema, entries) == expected
        assert entries == original

    def test_decodes_official_example_without_truncating_high_bits(self) -> None:
        schema = json.dumps(
            {
                "type": "record",
                "name": "Example",
                "fields": [
                    {"name": f"Field{index}", "type": "string"} for index in range(32)
                ],
            }
        )

        assert _FieldBitmapDecoder().decode(schema, ["0x650004E0"]) == [
            "Field5",
            "Field6",
            "Field7",
            "Field10",
            "Field24",
            "Field26",
            "Field29",
            "Field30",
        ]

    def test_keeps_schemas_separate_when_positions_change(self) -> None:
        decoder = _FieldBitmapDecoder()
        old_schema = (
            '{"type":"record","name":"Old","fields":[{"name":"A","type":"string"}]}'
        )
        new_schema = (
            '{"type":"record","name":"New","fields":[{"name":"B","type":"string"}]}'
        )

        assert decoder.decode(old_schema, ["0x01"]) == ["A"]
        assert decoder.decode(new_schema, ["0x01"]) == ["B"]
        assert decoder.decode(old_schema, ["0x01"]) == ["A"]

    def test_preserves_decoded_names_without_parsing_custom_schema(self) -> None:
        assert _FieldBitmapDecoder().decode("custom schema", ["Name"]) == ["Name"]
        assert _FieldBitmapDecoder().decode("custom schema", None) == []

    @pytest.mark.parametrize(
        ("entries", "message"),
        [
            (["0x"], "hexadecimal"),
            (["0xGG"], "hexadecimal"),
            (["0x-1"], "hexadecimal"),
            (["0x20"], "exceeds schema"),
            (["5-0x01"], "position exceeds"),
            (["bad-0x01"], "invalid field position"),
            (["-1-0x01"], "invalid field position"),
            (["1-0x01"], "does not reference a record"),
            (["3-0x08"], "exceeds schema"),
        ],
    )
    def test_rejects_invalid_bitmap_entries(
        self, bitmap_schema: str, entries: list[str], message: str
    ) -> None:
        with pytest.raises(RuntimeError, match=message):
            _FieldBitmapDecoder().decode(bitmap_schema, entries)

    @pytest.mark.parametrize("value", ["0x02", [None], [1], {}])
    def test_rejects_invalid_bitmap_container(
        self, bitmap_schema: str, value: Any
    ) -> None:
        with pytest.raises(RuntimeError, match="list of strings"):
            _FieldBitmapDecoder().decode(bitmap_schema, value)

    @pytest.mark.parametrize(
        ("schema", "message"),
        [
            ("not JSON", "not valid JSON"),
            ('{"type":"string"}', "record schema"),
            ('{"type":"record","name":"A"}', "invalid record fields"),
            ('{"type":"record","name":"A","fields":[{}]}', "invalid record fields"),
            ('{"type":"record","fields":[]}', "unnamed record"),
        ],
    )
    def test_rejects_invalid_schema(self, schema: str, message: str) -> None:
        with pytest.raises(RuntimeError, match=message):
            _FieldBitmapDecoder().decode(schema, ["0x01"])

    @pytest.mark.parametrize("container", ["array", "map"])
    def test_resolves_named_record_defined_in_collection(self, container: str) -> None:
        record = {
            "type": "record",
            "name": "events.Address",
            "fields": [{"name": "City", "type": "string"}],
        }
        schema = json.dumps(
            {
                "type": "record",
                "name": "events.Account",
                "fields": [
                    {
                        "name": "Addresses",
                        "type": {
                            "type": container,
                            "items" if container == "array" else "values": record,
                        },
                    },
                    {"name": "BillingAddress", "type": {"type": "events.Address"}},
                ],
            }
        )

        assert _FieldBitmapDecoder().decode(schema, ["1-0x01"]) == [
            "BillingAddress.City"
        ]

    def test_resolves_record_behind_type_wrapper(self) -> None:
        schema = json.dumps(
            {
                "type": "record",
                "name": "Account",
                "fields": [
                    {
                        "name": "Address",
                        "type": {
                            "type": {
                                "type": "record",
                                "name": "Address",
                                "fields": [{"name": "City", "type": "string"}],
                            }
                        },
                    }
                ],
            }
        )

        assert _FieldBitmapDecoder().decode(schema, ["0-0x01"]) == ["Address.City"]

    @pytest.mark.parametrize(
        "branches",
        [
            ["null", "string"],
            [
                {"type": "record", "name": "A", "fields": []},
                {"type": "record", "name": "B", "fields": []},
            ],
        ],
    )
    def test_rejects_union_without_exactly_one_compound_record(
        self, branches: list[Any]
    ) -> None:
        schema = json.dumps(
            {
                "type": "record",
                "name": "Account",
                "fields": [{"name": "Address", "type": branches}],
            }
        )

        with pytest.raises(RuntimeError, match="requires one record union branch"):
            _FieldBitmapDecoder().decode(schema, ["0-0x01"])
