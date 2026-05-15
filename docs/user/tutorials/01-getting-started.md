# Getting started with Plynth

This tutorial walks you through installing Plynth, making your first HTTP
request, and progressively building up to a service class that wraps a
JSON REST API. No external accounts or credentials are needed.

## Prerequisites

- Python 3.12 or later
- `pip` (or another package installer)

## Step 1 — Install

```bash
pip install "plynth[httpx]"
```

This installs the core library and the httpx transport. `httpx` is the
only supported transport backend.

## Step 2 — Make a plain HTTP GET

Start with the lowest level: send one request with a transport directly.

```python
from plynth.http.transport import HttpxSyncTransport
from plynth.base.request import Request

transport = HttpxSyncTransport()
request = Request(method="GET", url="https://httpbin.org/get")
response = transport.send(request)

print(response.status_code)   # 200
print(response.json())
```

`Transport.send()` returns a `Response` with `status_code`, `headers`,
`content` (bytes), and a `.json()` helper.

## Step 3 — Use HTTPClient for convenience

`HTTPClient` adds a base URL and HTTP verb shortcuts so you no longer
construct `Request` objects manually.

```python
from plynth.http.client import HTTPClient
from plynth.http.transport import HttpxSyncTransport

transport = HttpxSyncTransport()
client = HTTPClient(base_url="https://httpbin.org", transport=transport)

resp = client.get("/get")
print(resp.status_code)

resp = client.post("/post", content=b'{"hello": "world"}')
print(resp.json())
```

## Step 4 — Use APIClient for JSON REST APIs

`APIClient` extends `HTTPClient` with two additions:

- It sends `Content-Type: application/json` and `Accept: application/json`
  by default.
- It calls `raise_for_status()` on every response, raising an
  `HttpStatusError` on 4xx and 5xx.

```python
from plynth.http.client import APIClient
from plynth.http.transport import HttpxSyncTransport

transport = HttpxSyncTransport()
client = APIClient(base_url="https://jsonplaceholder.typicode.com", transport=transport)

resp = client.get("/todos/1")
todo = resp.json()
print(todo["title"])
```

## Step 5 — Wrap the client in a service

Services translate raw HTTP responses into domain objects. The service is
what your application code uses — it never sees the client or transport.

```python
from dataclasses import dataclass
from plynth.http.client import APIClient
from plynth.http.service import APIService
from plynth.http.transport import HttpxSyncTransport


@dataclass
class Todo:
    id: int
    title: str
    completed: bool


class TodoService(APIService):
    def get(self, todo_id: int) -> Todo:
        resp = self._client.get(f"/todos/{todo_id}")
        data = resp.json()
        return Todo(id=data["id"], title=data["title"], completed=data["completed"])

    def list(self) -> list[Todo]:
        resp = self._client.get("/todos")
        return [Todo(id=d["id"], title=d["title"], completed=d["completed"])
                for d in resp.json()]


# Wire it up
transport = HttpxSyncTransport()
client = APIClient(base_url="https://jsonplaceholder.typicode.com", transport=transport)
service = TodoService(client)

todo = service.get(1)
print(todo.title)
```

## What you built

- A transport that handles I/O.
- A client that handles base URL and HTTP verbs.
- A service that handles domain logic and response mapping.

These three layers stay separate — the service does not know about httpx,
and the transport does not know about `Todo`.

## Next steps

- [Build your own connector](02-build-a-connector.md) — add settings and
  authentication for a real API.
- [Add middleware](03-add-middleware.md) — add logging, retry, and circuit
  breaking to any transport.
- [Add response caching](04-add-caching.md) — cache GET responses in
  memory or in Redis.
