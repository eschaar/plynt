"""Tests for custom VCR cassette serializers."""

from __future__ import annotations

from plynth.testsupport.vcr.serializer import READABLE_YAML_SERIALIZER


class TestReadableYamlSerializer:
    """Validate readable YAML serializer behavior."""

    def test_multiline_strings_use_block_style(self) -> None:
        """Serialize multiline string values as YAML block strings."""
        cassette = {
            "interactions": [
                {
                    "response": {
                        "body": {
                            "string": '{\n  "ok": true\n}',
                        }
                    }
                }
            ]
        }

        rendered = READABLE_YAML_SERIALIZER.serialize(cassette)

        assert "string: |-" in rendered
        assert '\\"ok\\"' not in rendered

    def test_round_trip_preserves_multiline_content(self) -> None:
        """Round-trip through serializer keeps the exact body string value."""
        original = {
            "interactions": [
                {
                    "response": {
                        "body": {
                            "string": '{\n  "ok": true\n}',
                        }
                    }
                }
            ]
        }

        rendered = READABLE_YAML_SERIALIZER.serialize(original)
        parsed = READABLE_YAML_SERIALIZER.deserialize(rendered)

        body = parsed["interactions"][0]["response"]["body"]["string"]
        assert body == original["interactions"][0]["response"]["body"]["string"]

    def test_compact_json_response_is_pretty_printed(self) -> None:
        """Serialize compact JSON response bodies as readable multiline JSON."""
        cassette = {
            "interactions": [
                {
                    "response": {
                        "body": {
                            "string": '{"ok":true,"items":[1,2]}',
                        }
                    }
                }
            ]
        }

        rendered = READABLE_YAML_SERIALIZER.serialize(cassette)
        parsed = READABLE_YAML_SERIALIZER.deserialize(rendered)

        body = parsed["interactions"][0]["response"]["body"]["string"]
        assert body == '{\n  "ok": true,\n  "items": [\n    1,\n    2\n  ]\n}'

    def test_request_body_is_not_pretty_printed(self) -> None:
        """Keep request body strings unchanged to avoid matcher drift."""
        cassette = {
            "interactions": [
                {
                    "request": {
                        "body": '{"k":"v"}',
                    },
                    "response": {
                        "body": {
                            "string": '{"ok":true}',
                        }
                    },
                }
            ]
        }

        rendered = READABLE_YAML_SERIALIZER.serialize(cassette)
        parsed = READABLE_YAML_SERIALIZER.deserialize(rendered)

        request_body = parsed["interactions"][0]["request"]["body"]
        assert request_body == '{"k":"v"}'
