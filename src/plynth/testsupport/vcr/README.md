# VCR Testsupport Guide

This guide explains how to use the VCR-backed testsupport layer in Plynth.

## What You Get

The VCR layer gives deterministic HTTP tests for sync and async clients,
without duplicating transport logic.

Supported record/replay modes:

1. `none`: replay only, fail on misses.
1. `once`: replay existing, record if cassette is new.
1. `new_episodes`: replay existing and append new interactions.
1. `all`: always record from live requests.
1. `passthrough`: bypass VCR and call real transport.

Main API:

- `VCRSettings`
- `StateTrackingSettings`
- `VCRMode`
- `StateTrackingMode`
- `VCRSession`
- `VCRMiddleware`
- `AsyncVCRMiddleware`
- `use_vcr`
- `with_vcr`
- `build_cassette_path`
- `DeterministicCassettePathResolver`
- `NormalizedJSONBodyMatcher`
- `ProxyAwarePathMatcher`
- `VCRMatcherLibrary`
- `VCRMissError`

## Install

Local development in this repository (editable install)

```bash
pip install -e ".[test]"
```

Installed from a published package version (non-editable)

```bash
pip install "plynth[test]"
```

For CI and release pipelines, prefer non-editable installs with pinned
versions.

## Quick Decision Guide

Use `VCRMiddleware` or `AsyncVCRMiddleware` when:

- your code path already runs through transport middleware
- you want record/replay to be transparent for service/client calls

Use `use_vcr(...)` context manager when:

- you want to scope one session across multiple calls in a block
- you want explicit local control in a single test

Use `@with_vcr(...)` decorator when:

- you want concise wrapper behavior on test functions
- you want repeatable policy on many test methods

## Deterministic Cassette Paths

Use `build_cassette_path(node_id, root, extension)` with pytest node ids.

Path shape:

- `<suite>/<module>/<class?>/<test>__<hash>.yaml`

Example:

```python
from pathlib import Path

from plynth.testsupport.vcr import build_cassette_path

node_id = "tests/http/test_client.py::TestClient::test_get"
path = build_cassette_path(node_id, Path("tests/cassettes"), extension=".yaml")
print(path)
# tests/cassettes/http/client/client/get__a1b2c3d4.yaml (example)
```

### Class-based resolver (recommended)

```python
from pathlib import Path

from plynth.testsupport.vcr import DeterministicCassettePathResolver

resolver = DeterministicCassettePathResolver(
    cassette_root=Path("tests/cassettes"),
    extension=".yaml",
)

path = resolver.resolve(
    cassette_path=None,
    node_id="tests/http/test_client.py::TestClient::test_get",
)
```

### Optional `cassette_path`

`cassette_path` is optional for `VCRSession`, `use_vcr`, `with_vcr`,
`VCRMiddleware`, and `AsyncVCRMiddleware`.

Resolution order:

1. Use explicit `cassette_path` if provided.
1. Else use explicit `node_id` if provided.
1. Else use `PYTEST_CURRENT_TEST` (inside pytest).
1. Else raise a `ValueError` (outside pytest without explicit path).

This gives deterministic, repeatable paths and avoids collisions by using a
hash suffix derived from node id.

## Context Manager Usage

### Minimal sync example

```python
from plynth.base.request import Request
from plynth.base.response import Response
from plynth.testsupport.vcr import VCRMode, VCRSettings, use_vcr


def fake_next(request: Request) -> Response:
    return Response(status_code=200, content=b"ok")


settings = VCRSettings(mode=VCRMode.NEW_EPISODES)

with use_vcr(
    cassette_path="tests/cassettes/example.yaml", settings=settings
) as session:
    req = Request(method="GET", url="https://api.example.test/items/1")
    res = session.handle_sync(req, fake_next)
    assert res.content == b"ok"
```

### Minimal async example

```python
from plynth.base.request import Request
from plynth.base.response import Response
from plynth.testsupport.vcr import VCRMode, VCRSettings, use_vcr


async def fake_next(request: Request) -> Response:
    return Response(status_code=200, content=b"ok")


settings = VCRSettings(mode=VCRMode.NEW_EPISODES)

with use_vcr(
    cassette_path="tests/cassettes/example-async.yaml", settings=settings
) as session:
    req = Request(method="GET", url="https://api.example.test/items/1")
    res = await session.handle_async(req, fake_next)
    assert res.content == b"ok"
```

## Decorator / Wrapper Usage

### Direct decorator on pytest test function

```python
from plynth.testsupport.vcr import VCRMode, VCRSettings, with_vcr


@with_vcr(
    cassette_path="tests/cassettes/test_orders.yaml",
    settings=VCRSettings(mode=VCRMode.NONE),
)
def test_orders_are_replayed_only() -> None:
    # Execute code that uses VCRMiddleware/AsyncVCRMiddleware in transport.
    # If request is missing in cassette, VCRMissError is raised.
    pass
```

### Wrapper helper for reusable policy

```python
from pathlib import Path

from plynth.testsupport.vcr import VCRMode, VCRSettings, build_cassette_path, with_vcr


def vcr_wrapped(node_id: str):
    cassette = build_cassette_path(node_id, Path("tests/cassettes"), extension=".yaml")
    return with_vcr(
        cassette_path=str(cassette),
        settings=VCRSettings(mode=VCRMode.NEW_EPISODES),
    )


@vcr_wrapped("tests/http/test_orders.py::test_list_orders")
def test_list_orders() -> None:
    pass
```

## Middleware Usage

### Sync middleware in a transport chain

```python
from plynth.http.client import APIClient
from plynth.http.transport import HttpxSyncTransport
from plynth.testsupport.vcr import VCRMiddleware, VCRMode, VCRSettings

vcr_mw = VCRMiddleware(
    cassette_path="tests/cassettes/sync-orders.yaml",
    settings=VCRSettings(mode=VCRMode.NEW_EPISODES),
)

transport = HttpxSyncTransport(middlewares=[vcr_mw])
client = APIClient(base_url="https://api.example.test", transport=transport)

response = client.get("/orders")
assert response.status_code == 200
```

### Async middleware in a transport chain

```python
from plynth.http.client import AsyncAPIClient
from plynth.http.transport import HttpxAsyncTransport
from plynth.testsupport.vcr import AsyncVCRMiddleware, VCRMode, VCRSettings

vcr_mw = AsyncVCRMiddleware(
    cassette_path="tests/cassettes/async-orders.yaml",
    settings=VCRSettings(mode=VCRMode.NEW_EPISODES),
)

transport = HttpxAsyncTransport(middlewares=[vcr_mw])
client = AsyncAPIClient(base_url="https://api.example.test", transport=transport)

response = await client.get("/orders")
assert response.status_code == 200
```

## pytest Integration Patterns

### Global fixture pattern

```python
# tests/conftest.py
from pathlib import Path

import pytest

from plynth.testsupport.vcr import (
    StateTrackingMode,
    StateTrackingSettings,
    VCRMode,
    VCRSettings,
    build_cassette_path,
)


@pytest.fixture
def vcr_cassette_path(request: pytest.FixtureRequest) -> Path:
    root = Path(__file__).resolve().parent / "cassettes"
    return build_cassette_path(request.node.nodeid, root, extension=".yaml")


@pytest.fixture
def vcr_settings() -> VCRSettings:
    return VCRSettings(
        mode=VCRMode.NONE,
        state_tracking=StateTrackingSettings(mode=StateTrackingMode.RESOURCE),
    )
```

### Per-suite override pattern

```python
# tests/connectors/salesforce/conftest.py
import pytest

from plynth.testsupport.vcr import VCRMode, VCRSettings


@pytest.fixture
def vcr_settings() -> VCRSettings:
    # Replay only in CI-safe integration tests.
    return VCRSettings(mode=VCRMode.NONE)
```

### Record-on-demand marker pattern

```python
import pytest

from plynth.testsupport.vcr import VCRMode, VCRSettings


@pytest.fixture
def vcr_settings(request: pytest.FixtureRequest) -> VCRSettings:
    if request.node.get_closest_marker("record_http"):
        return VCRSettings(mode=VCRMode.NEW_EPISODES)
    return VCRSettings(mode=VCRMode.NONE)


@pytest.mark.record_http
def test_refresh_cassette_when_needed() -> None:
    pass
```

## unittest Integration Patterns

### `unittest.TestCase` with context manager

```python
import unittest

from plynth.testsupport.vcr import VCRMode, VCRSettings, use_vcr


class TestLegacySync(unittest.TestCase):
    def test_sync_flow(self) -> None:
        settings = VCRSettings(mode=VCRMode.NONE)
        with use_vcr(
            settings=settings,
            cassette_path="tests/cassettes/unittest-sync.yaml",
        ):
            # call code that goes through VCR middleware
            self.assertTrue(True)
```

### `unittest.TestCase` with decorator

```python
import unittest

from plynth.testsupport.vcr import VCRMode, VCRSettings, with_vcr


class TestLegacyDecorated(unittest.TestCase):
    @with_vcr(
        cassette_path="tests/cassettes/unittest-decorated.yaml",
        settings=VCRSettings(mode=VCRMode.NONE),
    )
    def test_flow(self) -> None:
        self.assertTrue(True)
```

### `unittest.IsolatedAsyncioTestCase` with async decorator

```python
import unittest

from plynth.testsupport.vcr import VCRMode, VCRSettings, with_vcr


class TestLegacyAsync(unittest.IsolatedAsyncioTestCase):
    @with_vcr(
        cassette_path="tests/cassettes/unittest-async.yaml",
        settings=VCRSettings(mode=VCRMode.NONE),
    )
    async def test_async_flow(self) -> None:
        self.assertTrue(True)
```

## State Tracking

State tracking avoids stale replay when a test mutates state and then reads
the same URL again.

Modes:

1. `off`: no state discriminator.
1. `resource`: revision per normalized URL path.
1. `global`: one revision for entire session.

Example:

```python
from plynth.testsupport.vcr import (
    StateTrackingMode,
    StateTrackingSettings,
    VCRMode,
    VCRSettings,
)

settings = VCRSettings(
    mode=VCRMode.NEW_EPISODES,
    state_tracking=StateTrackingSettings(mode=StateTrackingMode.RESOURCE),
)
```

When enabled, matching includes an internal revision discriminator so this
sequence does not collide:

1. GET `/object/1` -> response A
1. PATCH `/object/1`
1. GET `/object/1` -> response B

## Custom Matchers and Header Filtering

### Class-based built-in matcher library

```python
from plynth.testsupport.vcr import VCRMatcherLibrary

custom_matchers = VCRMatcherLibrary.as_dict()
```

### Redact headers before persistence

```python
from plynth.testsupport.vcr import VCRMode, VCRSettings

settings = VCRSettings(
    mode=VCRMode.NEW_EPISODES,
    filter_headers=(
        ("Authorization", "<redacted>"),
        ("X-Api-Key", "<redacted>"),
    ),
)
```

### Register custom matcher

```python
from plynth.testsupport.vcr import VCRMode, VCRSettings


def match_json_api_version(r1: object, r2: object) -> None:
    # Raise AssertionError when requests should not match.
    h1 = getattr(r1, "headers", {})
    h2 = getattr(r2, "headers", {})
    if h1.get("X-Api-Version") != h2.get("X-Api-Version"):
        raise AssertionError("X-Api-Version mismatch")


settings = VCRSettings(
    mode=VCRMode.NEW_EPISODES,
    custom_matchers={"api_version": match_json_api_version},
    match_on=("method", "host", "path", "query", "api_version"),
)
```

### Use class-based JSON and proxy-aware matchers

```python
from plynth.testsupport.vcr import (
    NormalizedJSONBodyMatcher,
    ProxyAwarePathMatcher,
    VCRMode,
    VCRSettings,
)

settings = VCRSettings(
    mode=VCRMode.NEW_EPISODES,
    custom_matchers={
        "json_body": NormalizedJSONBodyMatcher.match,
        "proxy_aware_path": ProxyAwarePathMatcher.match,
    },
    match_on=("method", "scheme", "host", "proxy_aware_path", "json_body"),
)
```

## Error Handling

When replay-only modes cannot find a matching interaction, a `VCRMissError`
is raised.

```python
import pytest

from plynth.testsupport.vcr import VCRMissError


def test_replay_miss_raises() -> None:
    with pytest.raises(VCRMissError):
        # call code that requests an interaction missing from cassette
        pass
```

## Recommended Team Defaults

For stable CI and predictable local behavior:

1. Default to `VCRMode.NONE` in shared fixtures.
1. Use explicit opt-in markers for recording.
1. Keep deterministic cassette path generation in one fixture.
1. Redact secrets via `filter_headers` by default.
1. Use `StateTrackingMode.RESOURCE` where write-then-read flows exist.

## Related Docs

- [ADR-0016 VCR Testsupport Layer](../../../../docs/architecture/adr/0016-vcr-testsupport.md)
- [Plynth testsupport package](../)
