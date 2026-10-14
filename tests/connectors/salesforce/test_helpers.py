"""Tests for Salesforce query and search helper utilities."""

from __future__ import annotations

import pytest

from plynt.connectors.salesforce.helpers import (
    build_select_soql,
    escape_sosl,
    format_soql,
    is_salesforce_id,
    validate_salesforce_id,
)


class TestEscapeSosl:
    """Tests for escape_sosl."""

    def test_plain_text_unchanged(self) -> None:
        """Plain text without SOSL special characters passes through unchanged."""
        assert escape_sosl("Acme Corporation") == "Acme Corporation"

    def test_escapes_single_quote(self) -> None:
        """A single quote in input is escaped with a backslash."""
        assert escape_sosl("O'Brien") == r"O\'Brien"

    def test_escapes_double_quote(self) -> None:
        """A double quote in input is escaped with a backslash."""
        assert escape_sosl('say "hello"') == r"say \"hello\""

    def test_escapes_ampersand(self) -> None:
        """An ampersand in input is escaped with a backslash."""
        assert escape_sosl("Sales & Marketing") == r"Sales \& Marketing"

    def test_escapes_pipe(self) -> None:
        """A pipe character in input is escaped with a backslash."""
        assert escape_sosl("a|b") == r"a\|b"

    def test_escapes_exclamation(self) -> None:
        """An exclamation mark in input is escaped with a backslash."""
        assert escape_sosl("!urgent") == r"\!urgent"

    def test_escapes_braces(self) -> None:
        """Curly braces in input are each escaped with a backslash."""
        assert escape_sosl("{test}") == r"\{test\}"

    def test_escapes_parentheses(self) -> None:
        """Parentheses in input are each escaped with a backslash."""
        assert escape_sosl("(Ltd.)") == r"\(Ltd.\)"

    def test_escapes_brackets(self) -> None:
        """Square brackets in input are each escaped with a backslash."""
        assert escape_sosl("[alpha]") == r"\[alpha\]"

    def test_escapes_caret(self) -> None:
        """A caret character in input is escaped with a backslash."""
        assert escape_sosl("a^b") == r"a\^b"

    def test_escapes_tilde(self) -> None:
        """A tilde character in input is escaped with a backslash."""
        assert escape_sosl("a~b") == r"a\~b"

    def test_escapes_asterisk(self) -> None:
        """An asterisk in input is escaped with a backslash."""
        assert escape_sosl("wild*") == r"wild\*"

    def test_escapes_colon(self) -> None:
        """A colon in input is escaped with a backslash."""
        assert escape_sosl("key:value") == r"key\:value"

    def test_escapes_plus(self) -> None:
        """A plus sign in input is escaped with a backslash."""
        assert escape_sosl("a+b") == r"a\+b"

    def test_escapes_minus(self) -> None:
        """A minus sign in input is escaped with a backslash."""
        assert escape_sosl("a-b") == r"a\-b"

    def test_escapes_backslash(self) -> None:
        """A backslash in input is escaped with a second backslash."""
        assert escape_sosl("C:\\path") == r"C\:\\path"

    def test_escapes_question_mark(self) -> None:
        """A question mark in input is escaped with a backslash."""
        assert escape_sosl("what?") == r"what\?"

    def test_escapes_equals(self) -> None:
        """An equals sign in input is escaped with a backslash."""
        assert escape_sosl("a=b") == r"a\=b"

    def test_complex_user_input(self) -> None:
        """A realistic mixed-character user string is escaped correctly."""
        result = escape_sosl("O'Brien & Associates (Ltd.)")
        assert "'" not in result.replace("\\'", "")
        assert result.startswith("O\\'Brien")


class TestFormatSoql:
    """Tests for format_soql."""

    def test_string_param_is_quoted_and_escaped(self) -> None:
        """A string parameter is wrapped in single quotes in the output query."""
        result = format_soql("SELECT Id FROM Account WHERE Name = :name", name="Acme")
        assert result == "SELECT Id FROM Account WHERE Name = 'Acme'"

    def test_string_with_single_quote_is_escaped(self) -> None:
        """A string parameter containing a single quote is safely escaped."""
        result = format_soql(
            "SELECT Id FROM Account WHERE Name = :name", name="O'Brien"
        )
        assert result == "SELECT Id FROM Account WHERE Name = 'O\\'Brien'"

    def test_string_with_backslash_is_escaped(self) -> None:
        """A string parameter containing a backslash is double-escaped."""
        result = format_soql("SELECT Id FROM Account WHERE Name = :name", name="a\\b")
        assert result == "SELECT Id FROM Account WHERE Name = 'a\\\\b'"

    def test_none_param_renders_null(self) -> None:
        """A None parameter is rendered as the SOQL literal ``null``."""
        result = format_soql("SELECT Id FROM Account WHERE Phone = :phone", phone=None)
        assert result == "SELECT Id FROM Account WHERE Phone = null"

    def test_bool_true_renders_true(self) -> None:
        """A True boolean parameter is rendered as the SOQL literal ``true``."""
        result = format_soql(
            "SELECT Id FROM Account WHERE IsActive = :active", active=True
        )
        assert result == "SELECT Id FROM Account WHERE IsActive = true"

    def test_bool_false_renders_false(self) -> None:
        """A False boolean parameter is rendered as the SOQL literal ``false``."""
        result = format_soql(
            "SELECT Id FROM Account WHERE IsActive = :active", active=False
        )
        assert result == "SELECT Id FROM Account WHERE IsActive = false"

    def test_int_param_rendered_without_quotes(self) -> None:
        """An integer parameter is rendered as a bare numeric literal."""
        result = format_soql("SELECT Id FROM Account LIMIT :n", n=10)
        assert result == "SELECT Id FROM Account LIMIT 10"

    def test_float_param_rendered_without_quotes(self) -> None:
        """A float parameter is rendered as a bare decimal literal."""
        result = format_soql(
            "SELECT Id FROM Account WHERE Score__c > :score", score=4.5
        )
        assert result == "SELECT Id FROM Account WHERE Score__c > 4.5"

    def test_multiple_params(self) -> None:
        """Multiple named parameters are each substituted and escaped correctly."""
        result = format_soql(
            "SELECT Id FROM Contact WHERE FirstName = :first AND Active__c = :active",
            first="Ada",
            active=True,
        )
        exp = "SELECT Id FROM Contact WHERE FirstName = 'Ada' AND Active__c = true"
        assert result == exp

    def test_missing_param_raises_key_error(self) -> None:
        """A missing keyword argument raises KeyError naming the placeholder."""
        with pytest.raises(KeyError, match="name"):
            format_soql("SELECT Id FROM Account WHERE Name = :name")

    def test_query_without_placeholders_returned_unchanged(self) -> None:
        """A query string with no placeholders is returned as-is."""
        query = "SELECT Id FROM Account"
        assert format_soql(query) == query

    def test_placeholder_at_start(self) -> None:
        """A placeholder at the very start of the query string is replaced correctly."""
        result = format_soql(":val = 1", val="x")
        assert result == "'x' = 1"

    def test_underscore_in_placeholder_name(self) -> None:
        """A placeholder name containing underscores is matched and replaced."""
        result = format_soql("WHERE My_Field__c = :my_field", my_field="test")
        assert result == "WHERE My_Field__c = 'test'"


class TestBuildSelectSoql:
    """Tests for build_select_soql."""

    def test_builds_minimal_select(self) -> None:
        """A call with only the object name produces ``SELECT Id FROM <Object>``."""
        soql = build_select_soql("Account")
        assert soql == "SELECT Id FROM Account"

    def test_builds_select_with_fields_and_clauses(self) -> None:
        """All optional clauses are combined into a single valid SOQL string."""
        soql = build_select_soql(
            "Account",
            fields=["Id", "Name"],
            where="IsDeleted = false",
            order_by="CreatedDate DESC",
            limit=50,
            offset=10,
        )
        assert soql == (
            "SELECT Id, Name FROM Account WHERE IsDeleted = false "
            "ORDER BY CreatedDate DESC LIMIT 50 OFFSET 10"
        )

    def test_rejects_invalid_object_name(self) -> None:
        """An object name with invalid characters raises ValueError."""
        with pytest.raises(ValueError, match="Invalid SOQL object name"):
            build_select_soql("Account;DROP")

    def test_rejects_invalid_field_name(self) -> None:
        """A field name with invalid characters raises ValueError."""
        with pytest.raises(ValueError, match="Invalid SOQL field name"):
            build_select_soql("Account", fields=["Id", "Name;"])

    def test_rejects_empty_fields_list(self) -> None:
        """An empty fields list raises ValueError; at least one field is required."""
        with pytest.raises(ValueError, match="fields"):
            build_select_soql("Account", fields=[])

    def test_rejects_fields_as_single_string(self) -> None:
        """A single string for fields is rejected with a clear ValueError."""
        with pytest.raises(ValueError, match="single string"):
            build_select_soql("Account", fields="Id")

    def test_rejects_non_positive_limit(self) -> None:
        """A limit of zero or below raises ValueError."""
        with pytest.raises(ValueError, match="limit"):
            build_select_soql("Account", limit=0)

    def test_rejects_negative_offset(self) -> None:
        """A negative offset raises ValueError."""
        with pytest.raises(ValueError, match="offset"):
            build_select_soql("Account", offset=-1)


class TestIsSalesforceId:
    """Tests for is_salesforce_id."""

    def test_valid_15_char_id(self) -> None:
        """A 15-character alphanumeric string is recognised as a valid Salesforce ID."""
        assert is_salesforce_id("001000000000000") is True

    def test_valid_18_char_id_with_correct_checksum(self) -> None:
        # Build a valid 18-char ID from a known 15-char ID.
        """An 18-character ID with a matching checksum is recognised as valid."""
        from plynt.connectors.salesforce.helpers import _compute_id18_checksum

        id15 = "001000000000000"
        checksum = _compute_id18_checksum(id15)
        assert is_salesforce_id(id15 + checksum) is True

    def test_valid_18_char_id_with_uppercase_letters_in_base(self) -> None:
        # Exercises the isupper() == True branch inside _compute_id18_checksum.
        """The checksum algorithm handles uppercase letters in the base segment."""
        from plynt.connectors.salesforce.helpers import _compute_id18_checksum

        id15 = "001BcDeFgHiJkLm"
        checksum = _compute_id18_checksum(id15)
        assert is_salesforce_id(id15 + checksum) is True

    def test_invalid_18_char_id_wrong_checksum(self) -> None:
        """An 18-character ID whose checksum does not match is rejected."""
        assert is_salesforce_id("001000000000000XXX") is False

    def test_too_short(self) -> None:
        """A string shorter than 15 characters is rejected."""
        assert is_salesforce_id("001000000000") is False

    def test_too_long(self) -> None:
        """A string longer than 18 characters is rejected."""
        assert is_salesforce_id("001000000000000AAAA") is False

    def test_non_alphanumeric_chars(self) -> None:
        """A string containing non-alphanumeric characters is rejected."""
        assert is_salesforce_id("001-000000-0000!") is False

    def test_empty_string(self) -> None:
        """An empty string is rejected."""
        assert is_salesforce_id("") is False

    def test_16_char_id_invalid(self) -> None:
        """A 16-character string (neither 15 nor 18) is rejected."""
        assert is_salesforce_id("0010000000000001") is False

    @pytest.mark.parametrize(
        "id_val",
        [
            "001000000000000",
            "003000000000000",
            "00Q000000000000",
        ],
    )
    def test_various_valid_15_char_ids(self, id_val: str) -> None:
        """A range of valid 15-character Salesforce prefixes are all recognised."""
        assert is_salesforce_id(id_val) is True


class TestValidateSalesforceId:
    """Tests for validate_salesforce_id."""

    def test_valid_id_returned_unchanged(self) -> None:
        """A valid Salesforce ID is returned unchanged."""
        id15 = "001000000000000"
        assert validate_salesforce_id(id15) == id15

    def test_invalid_id_raises_value_error(self) -> None:
        """An invalid string raises ValueError with a descriptive message."""
        with pytest.raises(ValueError, match="Invalid Salesforce ID"):
            validate_salesforce_id("not-an-id")

    def test_error_message_includes_value(self) -> None:
        """The ValueError message includes the offending value for easy diagnosis."""
        with pytest.raises(ValueError, match="bad-value"):
            validate_salesforce_id("bad-value")

    def test_empty_string_raises_value_error(self) -> None:
        """An empty string raises ValueError."""
        with pytest.raises(ValueError):
            validate_salesforce_id("")
