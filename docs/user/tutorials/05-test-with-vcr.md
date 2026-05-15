# Test your connector with VCR

This tutorial shows how to use Plynth's VCR support to record real HTTP
interactions and replay them in tests. By the end you will have a test suite
that runs without network access.

## What is VCR testing?

VCR (Video Cassette Recorder) testing records HTTP requests and responses
to YAML files called *cassettes*. On subsequent test runs, Plynth replays
the cassette instead of making real network calls. This gives you:

- Fast, deterministic tests.
- No dependency on external APIs in CI.
- A permanent record of what the API actually returned.

## Prerequisites

```bash
pip install "plynth[httpx]" vcrpy pytest
```

## How it works in Plynth

Plynth's VCR support is a transport middleware (`VCRMiddleware`). It
intercepts requests and either records the response to a cassette file or
replays a previously recorded response — depending on the configured
`VCRMode`.

```text
Request → VCRMiddleware → (real network on record, cassette on replay)
```

## Step 1 — Create a test for your connector

Using the connector from [Tutorial 2](02-build-a-connector.md):

```python
# tests/test_issue_service.py
import pytest
from plynth.http.transport import HttpxSyncTransport
from plynth.http.client import APIClient
from connector.service import IssueService


@pytest.fixture
def service():
    transport = HttpxSyncTransport()
    client = APIClient(base_url="https://api.example.com", transport=transport)
    return IssueService(client)


def test_list_issues_returns_open_issues(service):
    issues = service.list(status="open")
    assert len(issues) > 0
    assert all(i.status == "open" for i in issues)
```

This test hits the real network. Next, we make it use a cassette.

## Step 2 — Add VCRMiddleware to the transport

```python
# tests/test_issue_service.py
import pytest
from pathlib import Path
from plynth.http.transport import HttpxSyncTransport
from plynth.http.client import APIClient
from plynth.testsupport.vcr.middleware import VCRMiddleware
from plynth.testsupport.vcr.config import VCRSettings, VCRMode
from connector.service import IssueService

CASSETTE_DIR = Path(__file__).parent / "_cassettes"


@pytest.fixture
def service(request):
    vcr = VCRMiddleware(
        cassette_root=CASSETTE_DIR,
        node_id=request.node.nodeid,
        settings=VCRSettings(mode=VCRMode.ONCE),
    )
    transport = HttpxSyncTransport(middlewares=[vcr])
    client = APIClient(base_url="https://api.example.com", transport=transport)
    return IssueService(client)


def test_list_issues_returns_open_issues(service):
    issues = service.list(status="open")
    assert len(issues) > 0
    assert all(i.status == "open" for i in issues)
```

## Step 3 — Record the cassette

Run the test once with network access:

```bash
pytest tests/test_issue_service.py -v
```

Plynth records the response to a YAML file under `tests/_cassettes/`.
The cassette path is derived deterministically from the pytest node ID.

## Step 4 — Verify replay

Run the tests again without network access to confirm they use the cassette:

```bash
pytest tests/test_issue_service.py -v
```

The test passes without any network calls.

## VCR modes

| Mode           | Behaviour                                          |
| -------------- | -------------------------------------------------- |
| `ONCE`         | Record on first run; replay on all subsequent runs |
| `NEW_EPISODES` | Replay known interactions; record new ones         |
| `ALL`          | Always record (overwrites existing cassette)       |
| `PASSTHROUGH`  | Always pass through to the real network            |
| `NONE`         | Middleware disabled (default)                      |

Use `ONCE` for most tests. Use `NEW_EPISODES` when an API adds new
endpoints and you want to extend an existing cassette.

## Step 5 — Filter sensitive headers

Strip secrets from cassettes before committing them:

```python
settings = VCRSettings(
    mode=VCRMode.ONCE,
    filter_headers=(
        ("Authorization", None),   # remove the header entirely
        ("X-Api-Key", "REDACTED"),  # replace with a placeholder
    ),
)
```

## Step 6 — Use `vcr_session` context manager for fine-grained control

For complex scenarios you can manage the VCR session directly:

```python
from plynth.testsupport.vcr.session import vcr_session
from plynth.testsupport.vcr.config import VCRSettings, VCRMode

with vcr_session(
    cassette_path=str(CASSETTE_DIR / "my_cassette.yaml"),
    settings=VCRSettings(mode=VCRMode.ONCE),
):
    result = service.list()
```

## Cassette file format

Cassettes are human-readable YAML files. Each interaction records the
request (method, URI, headers, body) and the response (status code,
headers, body). JSON response bodies are pretty-printed:

```yaml
interactions:
- request:
    body: null
    headers:
      Accept: ['application/json']
    method: GET
    uri: https://api.example.com/issues?status=open
  response:
    body:
      string: |
        [
          {
            "id": 1,
            "title": "First issue",
            "status": "open"
          }
        ]
    headers:
      Content-Type: ['application/json']
    status:
      code: 200
      message: ''
version: 1
```

## Next steps

- [Reference: middleware](../reference/middleware.md) — all middleware
  classes including the full `VCRSettings` fields.
- [How to handle errors](../how-to/handle-errors.md) — test error paths by
  creating cassettes that return 4xx/5xx responses.
