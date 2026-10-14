from collections.abc import Callable
from typing import ClassVar

from plynt.base.errors import (
    BaseError,
    DependencyUnavailableError,
    FeatureDisabledError,
    InvalidInputError,
)
from plynt.base.mapping import ErrorMapper
from plynt.http.errors import (
    BadRequestError,
    HttpStatusError,
    InternalServerError,
    ServiceUnavailableError,
)

__all__ = ["APIErrorMapper"]


class APIErrorMapper(ErrorMapper[BaseError, HttpStatusError]):
    """Maps ``BaseError`` to ``HttpStatusError`` for consistent API responses."""

    ERROR_MAPPING: ClassVar[dict[type, Callable[..., HttpStatusError]]] = {
        InvalidInputError: BadRequestError,
        FeatureDisabledError: ServiceUnavailableError,
        DependencyUnavailableError: ServiceUnavailableError,
    }

    @classmethod
    def to_mapped_error(cls, error: BaseError) -> HttpStatusError:
        """Convert a core BaseError to a corresponding HttpStatusError.

        Uses ``ERROR_MAPPING`` to select the correct ``HttpStatusError``
        subclass. Falls back to ``InternalServerError`` (HTTP 500) when no
        mapping exists. All fields (message, details, code) are forwarded to
        the error constructor.

        """
        factory: Callable[..., HttpStatusError] = cls.ERROR_MAPPING.get(
            type(error), InternalServerError
        )
        return factory(
            error.message,
            details=error.details,
            code=error.code,
        )
