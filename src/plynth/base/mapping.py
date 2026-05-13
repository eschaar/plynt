from abc import ABC, abstractmethod
from typing import Any, ClassVar, Generic, TypeVar

SourceError = TypeVar("SourceError")
MappedError = TypeVar("MappedError")


class ErrorMapper(ABC, Generic[SourceError, MappedError]):
    """Abstract base class for mapping errors from one type to another.
    Example use case: mapping core errors to API errors.
    Subclasses should define ERROR_MAPPING and implement to_mapped_error.
    """

    # Maps source error types to their mapped counterparts. Values may be
    # concrete types or any callable that produces a MappedError instance.
    ERROR_MAPPING: ClassVar[dict[type, Any]] = {}

    @classmethod
    @abstractmethod
    def to_mapped_error(cls, exc: SourceError) -> MappedError:
        """Convert a source error to a mapped error."""
        raise NotImplementedError("Subclasses must implement to_mapped_error")
