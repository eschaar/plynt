"""Salesforce query and search helper utilities.

Provides safe formatting and validation helpers for SOQL and SOSL:

- ``format_soql`` — safe SOQL query formatting with named placeholders.
- ``escape_sosl`` — escape special characters in SOSL search terms.
- ``is_salesforce_id`` — check whether a string is a valid Salesforce ID.
- ``validate_salesforce_id`` — validate and return a Salesforce ID or raise.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from plynt.connectors.salesforce.constants import SALESFORCE_ID_RE

__all__ = [
    "build_select_soql",
    "escape_sosl",
    "format_soql",
    "is_salesforce_id",
    "validate_salesforce_id",
]

# SOSL special characters that must be escaped with a backslash.
# Reference: Salesforce SOSL documentation — reserved characters.
_SOSL_SPECIAL_RE = re.compile(r'([?&|!{}()\[\]^~*:\\"\'+=\-\\])')

# Pattern for named SOQL placeholders: :identifier
_SOQL_PLACEHOLDER_RE = re.compile(r":([a-zA-Z_][a-zA-Z0-9_]*)")

# Conservative identifier matcher for object and field references.
# Supports common Salesforce names like Account, Custom__c, Owner.Name.
_SOQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")

# Lookup table used for computing the 18-character Salesforce ID checksum.
_ID18_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"


def escape_sosl(text: str) -> str:
    r"""Escape special characters in a SOSL search term.

    Salesforce reserves the following characters in SOSL expressions and
    requires them to be escaped with a backslash when they appear in
    user-supplied search terms::

        ? & | ! { } [ ] ( ) ^ ~ * : \\ \" ' + - =

    Example::

        from plynt.connectors.salesforce.helpers import escape_sosl

        user_input = "O'Brien & Associates (Ltd.)"
        sosl = f"FIND {{{escape_sosl(user_input)}}} IN NAME FIELDS"

    """
    return _SOSL_SPECIAL_RE.sub(r"\\\1", text)


def _soql_escape_value(value: Any) -> str:
    """Render a Python value as a safe SOQL literal string."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _validate_soql_identifier(value: str, *, kind: str) -> None:
    """Validate SOQL identifier-like tokens used by lightweight builders."""
    if not _SOQL_IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid SOQL {kind}: {value!r}")


def _normalized_select_fields(fields: Sequence[str] | None) -> list[str]:
    """Return validated SELECT fields for SOQL builders."""
    if isinstance(fields, str):
        raise ValueError(
            "fields must be a sequence of field names, not a single string"
        )
    selected_fields = list(fields) if fields is not None else ["Id"]
    if not selected_fields:
        raise ValueError("fields must contain at least one field name")
    for field_name in selected_fields:
        _validate_soql_identifier(field_name, kind="field name")
    return selected_fields


def _validate_limit_offset(limit: int | None, offset: int | None) -> None:
    """Validate LIMIT/OFFSET arguments for SOQL builders."""
    if limit is not None and limit <= 0:
        raise ValueError("limit must be a positive integer")
    if offset is not None and offset < 0:
        raise ValueError("offset must be a non-negative integer")


def _build_select_parts(
    object_name: str,
    selected_fields: list[str],
    *,
    where: str | None,
    order_by: str | None,
    limit: int | None,
    offset: int | None,
) -> list[str]:
    """Build SOQL SELECT statement parts from validated values."""
    parts = [
        f"SELECT {', '.join(selected_fields)}",
        f"FROM {object_name}",
    ]
    if where:
        parts.append(f"WHERE {where}")
    if order_by:
        parts.append(f"ORDER BY {order_by}")
    if limit is not None:
        parts.append(f"LIMIT {limit}")
    if offset is not None:
        parts.append(f"OFFSET {offset}")
    return parts


def build_select_soql(
    object_name: str,
    *,
    fields: Sequence[str] | None = None,
    where: str | None = None,
    order_by: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> str:
    """Build a lightweight SOQL SELECT statement from common parts.

    This helper targets the common case where callers want a concise and
    mostly-safe way to assemble SELECT queries without a full ORM-like DSL.
    It validates object and field identifiers and validates numeric bounds
    for ``limit`` and ``offset``. It does not parse or escape ``where`` or
    ``order_by`` clause bodies; those values are interpolated as-is and must
    come from trusted input or be built via safe parameterization patterns.

    Args:
        object_name: Salesforce object API name.
        fields: Optional list of field references. Defaults to ``["Id"]``.
        where: Optional WHERE clause body (without ``WHERE`` keyword).
            Interpolated as-is; do not pass untrusted user input directly.
        order_by: Optional ORDER BY clause body (without ``ORDER BY``).
            Interpolated as-is; do not pass untrusted user input directly.
        limit: Optional positive LIMIT value.
        offset: Optional non-negative OFFSET value.

    Raises:
        ValueError: If object/field identifiers are invalid or numeric values
            are out of range.

    Returns:
        A SOQL string ready to pass into query services.

    """
    _validate_soql_identifier(object_name, kind="object name")
    selected_fields = _normalized_select_fields(fields)
    _validate_limit_offset(limit, offset)
    parts = _build_select_parts(
        object_name,
        selected_fields,
        where=where,
        order_by=order_by,
        limit=limit,
        offset=offset,
    )
    return " ".join(parts)


def format_soql(query: str, **params: Any) -> str:
    r"""Format a SOQL query string with safely-escaped named parameters.

    Replaces ``:name`` placeholders in ``query`` with properly-escaped SOQL
    literals derived from the corresponding keyword arguments. String values
    are single-quoted and have single quotes and backslashes escaped.
    ``None`` maps to ``null``; booleans map to ``true`` / ``false``; numbers
    are rendered as-is.

    Args:
        query: A SOQL template string containing ``:name`` placeholders.
        **params: Named values to substitute into the template.

    Raises:
        KeyError: When a placeholder name has no corresponding keyword
            argument.

    Example::

        from plynt.connectors.salesforce.helpers import format_soql

        soql = format_soql(
            "SELECT Id, Name FROM User WHERE Name = :name AND IsActive = :active",
            name="O'Brien & Co",
            active=True,
        )
        # → "SELECT Id, Name FROM User WHERE Name = 'O\\'Brien & Co'"
        #    " AND IsActive = true"

    """

    def _replace(match: re.Match[str]) -> str:
        """Replace a single ``:{name}`` placeholder with its escaped parameter value."""
        name = match.group(1)
        if name not in params:
            raise KeyError(f"Missing SOQL parameter: {name!r}")
        return _soql_escape_value(params[name])

    return _SOQL_PLACEHOLDER_RE.sub(_replace, query)


def _compute_id18_checksum(id15: str) -> str:
    """Compute the 3-character checksum suffix for a 15-char Salesforce ID."""
    chunks = [id15[i : i + 5] for i in range(0, 15, 5)]
    result = []
    for chunk in chunks:
        value = 0
        for i, char in enumerate(chunk):
            if char.isupper():
                value += 1 << i
        result.append(_ID18_CHARS[value])
    return "".join(result)


def is_salesforce_id(value: str) -> bool:
    """Return ``True`` when ``value`` is a syntactically valid Salesforce ID.

    Accepts both the 15-character (case-sensitive) and 18-character
    (case-insensitive with checksum) formats. For 18-character IDs the
    checksum suffix is verified.

    Example::

        is_salesforce_id("001000000000000AAA")  # True (18-char)
        is_salesforce_id("001000000000000")      # True (15-char)
        is_salesforce_id("not-an-id")            # False

    """
    if not SALESFORCE_ID_RE.match(value):
        return False
    if len(value) == 18:
        expected = _compute_id18_checksum(value[:15])
        return value[15:] == expected
    return True


def validate_salesforce_id(value: str) -> str:
    """Validate ``value`` as a Salesforce record ID and return it.

    Raises:
        ValueError: When ``value`` is not a valid 15- or 18-character
            Salesforce record ID.

    Example::

        record_id = validate_salesforce_id(request.data["id"])

    """
    if not is_salesforce_id(value):
        raise ValueError(
            f"Invalid Salesforce ID: {value!r}. "
            "Expected a 15- or 18-character alphanumeric record ID."
        )
    return value
