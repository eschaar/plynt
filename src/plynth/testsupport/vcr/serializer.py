"""Custom serializers for VCR cassette readability."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from typing import Any, cast

import yaml

# Use libYAML when available for performance parity with vcrpy defaults.
try:
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import Dumper  # type: ignore[assignment]


READABLE_YAML_SERIALIZER_NAME = "yaml_readable"


class _ReadableDumper(Dumper):
    """YAML dumper that emits multiline strings using block style."""


def _represent_str(dumper: _ReadableDumper, value: str) -> yaml.Node:
    """Represent multiline strings with ``|`` for human-readable cassettes."""
    if "\n" in value:
        return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", value)


_ReadableDumper.add_representer(str, _represent_str)


class ReadableYamlSerializer:
    """Serializer compatible with vcrpy's serializer contract."""

    @staticmethod
    def _prettify_response_json(cassette_dict: Mapping[str, Any]) -> dict[str, Any]:
        """Return a copy with JSON response body strings pretty-printed.

        This improves cassette readability even when the body was captured as a
        compact single-line JSON string.
        """
        data = cast(dict[str, Any], copy.deepcopy(cassette_dict))
        interactions = data.get("interactions")
        if not isinstance(interactions, list):
            return data

        for interaction in interactions:
            if not isinstance(interaction, dict):
                continue
            response = interaction.get("response")
            if not isinstance(response, dict):
                continue
            body = response.get("body")
            if not isinstance(body, dict):
                continue
            body_string = body.get("string")
            if not isinstance(body_string, str):
                continue

            try:
                body["string"] = json.dumps(
                    json.loads(body_string),
                    indent=2,
                    ensure_ascii=False,
                )
            except ValueError:
                continue

        return data

    @staticmethod
    def deserialize(cassette_string: str) -> dict[str, Any]:
        """Deserialize a YAML cassette string into a Python mapping."""
        return cast(dict[str, Any], yaml.safe_load(cassette_string))

    @staticmethod
    def serialize(cassette_dict: Mapping[str, Any]) -> str:
        """Serialize cassette data with readable multiline block strings."""
        readable = ReadableYamlSerializer._prettify_response_json(cassette_dict)
        return yaml.dump(
            readable,
            Dumper=_ReadableDumper,
            sort_keys=False,
            allow_unicode=True,
            width=4096,
            default_flow_style=False,
        )


READABLE_YAML_SERIALIZER = ReadableYamlSerializer()
