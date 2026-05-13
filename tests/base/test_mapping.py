from typing import ClassVar, cast

import pytest

from plynth.base.errors import BaseError
from plynth.base.mapping import ErrorMapper


class DummySourceError(BaseError):
    """Represent DummySourceError."""

    pass


class DummyMappedError(BaseError):
    """Represent DummyMappedError."""

    pass


class DummyMapper(ErrorMapper[DummySourceError, DummyMappedError]):
    """Represent DummyMapper."""

    ERROR_MAPPING: ClassVar[dict[type, type]] = {DummySourceError: DummyMappedError}

    @classmethod
    def to_mapped_error(cls, exc: DummySourceError) -> DummyMappedError:
        """Return to mapped error."""
        mapped_cls = cast(
            type[DummyMappedError], cls.ERROR_MAPPING.get(type(exc), DummyMappedError)
        )
        return mapped_cls(message=exc.message)


class TestErrorMapper:
    """Test suite for ErrorMapper."""

    def test_error_mapper_mapping(self) -> None:
        """Test that DummyMapper correctly maps DummySourceError to DummyMappedError."""
        err = DummySourceError(message="foo")
        mapped = DummyMapper.to_mapped_error(err)
        assert isinstance(mapped, DummyMappedError)
        assert mapped.message == "foo"

    def test_error_mapper_default(self) -> None:
        """Test that DummyMapper maps unknown DummySourceError subtypes
        to DummyMappedError."""

        class UnknownDummySourceError(DummySourceError):
            """Represent UnknownDummySourceError."""

            pass

        err = UnknownDummySourceError(message="unknown")
        mapped = DummyMapper.to_mapped_error(err)
        assert isinstance(mapped, DummyMappedError)
        assert mapped.message == "unknown"

    def test_error_mapper_abstract(self) -> None:
        """Test that direct instantiation or calling of the abstract base
        class raises TypeError."""
        with pytest.raises(TypeError):
            ErrorMapper()  # type: ignore

        # Also, directly calling the abstract method should raise TypeError
        class Dummy(ErrorMapper[DummySourceError, DummyMappedError]):
            """Represent Dummy."""

            ERROR_MAPPING: ClassVar[dict[type, type]] = {}

        with pytest.raises(NotImplementedError):
            Dummy.to_mapped_error(DummySourceError(message="x"))
