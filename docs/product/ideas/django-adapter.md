# Idea: Django Adapter (`plynth[django]`)

**Status:** Idea — not yet an ADR, no implementation started.

Convert to an ADR when the approach is agreed and implementation is about to
begin.

______________________________________________________________________

## Goal

Allow Django projects to use plynth transports and clients without friction,
by bridging plynth's settings and caching model into Django's own conventions.

Django projects typically:

- store third-party API configuration in `settings.py` (as a dict or
  individual constants, not raw env vars)
- share a central cache framework (`django.core.cache`) already backed by
  Redis, Memcached, or another store
- use Django's built-in logging which already integrates with stdlib `logging`

The adapter should leverage all three, so a Django team gets plynth working
with zero new infrastructure.

______________________________________________________________________

## Scope

### 1. Settings bridge

Django projects configure plynth-based clients via `settings.py`:

```python
# myproject/settings.py
SALESFORCE = {
    "BASE_URL": "https://myorg.my.salesforce.com",
    "CLIENT_ID": env("SF_CLIENT_ID"),
    "CLIENT_SECRET": env("SF_CLIENT_SECRET"),
    "TOKEN_URL": "https://myorg.my.salesforce.com/services/oauth2/token",
    "MAX_ATTEMPTS": 3,
}
```

A `from_django_settings()` classmethod (or a thin factory function) reads a
named key from Django's `settings` object and returns a configured
`HTTPSettings` (or subclass) instance:

```python
from plynth.django import from_django_settings
from myapp.settings_classes import SalesforceSettings

sf_settings = from_django_settings("SALESFORCE", SalesforceSettings)
transport = HttpxSyncTransport.from_settings(sf_settings)
```

Open question: should `from_django_settings()` live on the settings class
(classmethod) or as a standalone factory in `plynth.django`?

### 2. Cache adapter

Wraps Django's cache framework in the `Cache` Protocol so plynth transports
can use an existing Django cache backend (Redis, Memcached, local-memory)
without an additional dependency:

```python
from plynth.django.cache import DjangoCacheBackend
from plynth.http.transport import HttpxSyncTransport

transport = HttpxSyncTransport(
    client=_build_httpx_client(settings),
    cache=DjangoCacheBackend(alias="plynth"),  # uses CACHES["plynth"] in settings.py
)
```

`DjangoCacheBackend` serialises `Response` objects to/from Django's cache.
TTL is passed through to Django's `cache.set(key, value, timeout=ttl)`.

### 3. Logging

No adapter is needed — plynth's log filters are stdlib-compatible and will
work inside Django's logging configuration out of the box. What is needed is:

- documentation showing how to add plynth's log filters to `LOGGING` in
  `settings.py`
- a note on sensitive-header scrubbing (once `core/log/` is more complete)

______________________________________________________________________

## Install extra

```text
pip install plynth[django]
```

Adds `django` as a dependency. The `[httpx]` extra is a prerequisite
(transport still requires httpx2).

______________________________________________________________________

## Constraints

- No Django imports anywhere in `plynth.core` or `plynth.http` — the boundary
  must be enforced by import structure, not just convention.
- The adapter must work with Django 4.2 LTS and 5.x.
- Sync-only for now — Django's async ORM and views are evolving, but plynth's
  primary Django use case is sync service calls from views or management commands.
  Async support can be a follow-up.

______________________________________________________________________

## Open Questions

1. Settings classmethod vs standalone factory — which fits Django's idioms better?
1. How to handle `Response` serialisation in the cache (pickle, JSON, custom)?
   Pickle is simplest but fragile across deploys; JSON requires `Response` to
   be serialisable.
1. Should `DjangoCacheBackend` support per-key TTL or only a global TTL
   configured at construction time?
1. Does the adapter ship as part of this repository or as a separate
   `plynth-django` package from the start?

______________________________________________________________________

## Next Step

Write a new ADR covering the settings bridge and cache adapter design before
any code is written.
