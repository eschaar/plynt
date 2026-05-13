"""Generic and REST API HTTP service base classes.

``HTTPService`` and ``AsyncHTTPService`` are base classes that define the
structural contract for services backed by a raw HTTP client. Domain-specific
services extend these classes and add their own endpoint methods.

``APIService`` and ``AsyncAPIService`` extend ``HTTPService`` and
``AsyncHTTPService`` respectively with conventions specific to JSON REST APIs.
They mirror the ``APIClient`` / ``HTTPClient`` hierarchy at the service layer:

- ``HTTPService`` / ``AsyncHTTPService`` — raw HTTP, optional renderer.
- ``APIService`` / ``AsyncAPIService`` — JSON REST; defaults the renderer to
  ``JSONRenderer`` so services do not need to hard-code JSON encoding.

Because ``APIClient`` is itself a subclass of ``HTTPClient``, an ``APIClient``
instance satisfies the ``HTTPClient`` type accepted by ``HTTPService``. The
service hierarchy mirrors the client hierarchy exactly.

Reference: ADR-0009
"""

from __future__ import annotations

from plynth.http.client import APIClient, AsyncAPIClient, AsyncHTTPClient, HTTPClient
from plynth.http.renderer import JSONRenderer, Renderer

__all__ = ["APIService", "AsyncAPIService", "AsyncHTTPService", "HTTPService"]


class HTTPService:
    """Base for services backed by a synchronous HTTP client.

    Subclasses implement domain endpoint methods that call ``self._client``
    and convert raw ``Response`` objects into domain models before returning.
    ``Response`` objects must never leak out of the service boundary.

    Args:
        renderer: Optional body serialiser. When provided, endpoint methods
            can call ``self._renderer.render(data)`` to produce request body
            bytes without hard-coding a content format.

    Example::

        class BillingService(HTTPService):
            def get_invoice(self, invoice_id: str) -> Invoice:
                resp = self._client.get(f"/invoices/{invoice_id}")
                return Invoice.model_validate_json(resp.content)

            def create_invoice(self, data: dict) -> Invoice:
                body = self._renderer.render(data)  # type: ignore[union-attr]
                resp = self._client.post("/invoices", content=body)
                return Invoice.model_validate_json(resp.content)

    """

    def __init__(
        self,
        client: HTTPClient,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize HTTPService."""
        self._client = client
        self._renderer = renderer


class AsyncHTTPService:
    """Base for services backed by an asynchronous HTTP client.

    The async mirror of ``HTTPService``. Endpoint methods are coroutines that
    call ``self._client`` and must convert raw ``Response`` objects into domain
    models before returning.

    Args:
        renderer: Optional body serialiser. When provided, endpoint methods
            can call ``self._renderer.render(data)`` to produce request body
            bytes without hard-coding a content format.

    Example::

        class AsyncBillingService(AsyncHTTPService):
            async def get_invoice(self, invoice_id: str) -> Invoice:
                resp = await self._client.get(f"/invoices/{invoice_id}")
                return Invoice.model_validate_json(resp.content)

    """

    def __init__(
        self,
        client: AsyncHTTPClient,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize AsyncHTTPService."""
        self._client = client
        self._renderer = renderer


class APIService(HTTPService):
    """Base for services backed by a synchronous JSON REST API client.

    Extends ``HTTPService`` with a default ``JSONRenderer`` so that endpoint
    methods can call ``self._renderer.render(data)`` without explicitly
    injecting a renderer. Mirrors the ``APIClient`` / ``HTTPClient``
    relationship at the service layer.

    ``_renderer`` is always non-``None`` for ``APIService`` subclasses;
    the type is narrowed via the class-level annotation so that subclasses
    can call ``self._renderer.render()`` without type-error suppression.

    ``HttpStatusError`` subclasses raised by ``APIClient`` may be caught and
    re-raised as domain-level exceptions, or allowed to propagate when the
    caller is expected to handle them directly.

    Args:
        renderer: Body serialiser. Defaults to ``JSONRenderer``. Inject a
            custom renderer (e.g. ``SalesforceRenderer``) to override
            serialisation behaviour for a specific integration.

    Example::

        class ProductService(APIService):
            def get_product(self, product_id: str) -> Product:
                resp = self._client.get(f"/products/{product_id}")
                return Product.model_validate_json(resp.content)

            def create_product(self, data: dict) -> Product:
                resp = self._client.post(
                    "/products",
                    content=self._renderer.render(data),
                )
                return Product.model_validate_json(resp.content)

    """

    _renderer: Renderer  # always set; defaults to JSONRenderer()

    def __init__(
        self,
        client: APIClient,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize APIService."""
        super().__init__(client, renderer=renderer or JSONRenderer())


class AsyncAPIService(AsyncHTTPService):
    """Base for services backed by an asynchronous JSON REST API client.

    The async mirror of ``APIService``. Endpoint methods are coroutines that
    call ``self._client`` and must convert ``Response`` objects into domain
    models before returning.

    ``_renderer`` is always non-``None`` for ``AsyncAPIService`` subclasses;
    the type is narrowed via the class-level annotation so that subclasses
    can call ``self._renderer.render()`` without type-error suppression.

    Args:
        renderer: Body serialiser. Defaults to ``JSONRenderer``.

    Example::

        class AsyncProductService(AsyncAPIService):
            async def get_product(self, product_id: str) -> Product:
                resp = await self._client.get(f"/products/{product_id}")
                return Product.model_validate_json(resp.content)

    """

    _renderer: Renderer  # always set; defaults to JSONRenderer()

    def __init__(
        self,
        client: AsyncAPIClient,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize AsyncAPIService."""
        super().__init__(client, renderer=renderer or JSONRenderer())
