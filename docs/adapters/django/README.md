# Django adapter

Install `plynt[django]`. The adapter adds settings-driven transport factories
and cache support without introducing Django behavior into the core.

- [Use Django cache](use-django-cache-backend.md)
- [Build a transport from settings](use-django-transport-helper.md)
- [Middleware interoperability](django-middleware-interoperability.md)
- [Scope and echo request IDs](use-request-id-middleware.md)
- [Django REST Framework](drf/README.md)
- [Runnable examples](../../../examples/django/README.md)

## Runtime migration

The extra requires Django 6.1.2 or newer within the 6.x series and Python 3.12
or newer. Applications upgrading from Django 5.2 must follow the
[Django 6.0 release notes](https://docs.djangoproject.com/en/6.0/releases/6.0/)
and
[Django 6.1 release notes](https://docs.djangoproject.com/en/6.1/releases/6.1/).
See [ADR-0034](../../architecture/adr/0034-django-6-support.md) for the
decision.
