# Build your own connector

This tutorial builds a complete connector for a fictional Issue Tracker API
from scratch: settings, auth middleware, service class, and a facade.
By the end you will have a reusable package that follows Plynth's connector
conventions.

## What we're building

A connector for `https://api.example.com`. The API:

- Uses OAuth2 Client Credentials for authentication.
- Returns JSON.
- Has a `/issues` resource with `GET /issues` and `GET /issues/{id}`.

## Step 1 — Define settings

Settings centralise all configuration and load credentials from the
environment.

```python
# connector/settings.py
from plynth.http.settings import ApiSettings
from plynth.http.auth import OAuth2ClientCredentialsConfig
from pydantic_settings import SettingsConfigDict


class IssueTrackerSettings(ApiSettings):
    """Settings for the Issue Tracker API connector.

    Required environment variables (with ISSUE_ prefix):

    - ISSUE_BASE_URL — e.g. https://api.example.com
    - ISSUE_CLIENT_ID — OAuth2 client ID
    - ISSUE_CLIENT_SECRET — OAuth2 client secret
    - ISSUE_TOKEN_URL — OAuth2 token endpoint
    """

    model_config = SettingsConfigDict(
        env_prefix="ISSUE_",
        env_file=".env",
    )

    client_id: str = ""
    client_secret: str = ""
    token_url: str = ""

    @property
    def auth(self) -> OAuth2ClientCredentialsConfig | None:
        if not self.client_id:
            return None
        return OAuth2ClientCredentialsConfig(
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_url=self.token_url,
        )
```

`ApiSettings` (from `plynth.http.settings`) provides `base_url`, timeout,
and proxy fields out of the box. Override `auth` to enable authentication.

## Step 2 — Define domain models

```python
# connector/models.py
from dataclasses import dataclass


@dataclass(frozen=True)
class Issue:
    id: int
    title: str
    status: str
    body: str
```

Keep models as plain dataclasses or Pydantic models — no HTTP logic here.

## Step 3 — Write the service

```python
# connector/service.py
from plynth.http.service import APIService
from connector.models import Issue


class IssueService(APIService):
    """Service for the /issues resource."""

    def list(self, *, status: str | None = None) -> list[Issue]:
        params = {"status": status} if status else None
        resp = self._client.get("/issues", params=params)
        return [_parse_issue(r) for r in resp.json()]

    def get(self, issue_id: int) -> Issue:
        resp = self._client.get(f"/issues/{issue_id}")
        return _parse_issue(resp.json())

    def create(self, title: str, body: str) -> Issue:
        resp = self._client.post(
            "/issues",
            content=self._renderer.render({"title": title, "body": body}),
        )
        return _parse_issue(resp.json())


def _parse_issue(data: dict) -> Issue:
    return Issue(
        id=data["id"],
        title=data["title"],
        status=data["status"],
        body=data.get("body", ""),
    )
```

`APIService` provides `self._client` (an `APIClient`) and
`self._renderer` (a `JSONRenderer` by default).

## Step 4 — Write a facade (optional)

A facade constructs services on demand from a single client, which is
convenient when a connector has many services.

```python
# connector/facade.py
from plynth.http.client import APIClient
from connector.service import IssueService


class IssueTrackerFacade:
    """Convenience entry point for the Issue Tracker connector."""

    def __init__(self, client: APIClient) -> None:
        self._client = client

    def issues(self) -> IssueService:
        return IssueService(self._client)
```

## Step 5 — Wire it all together

```python
# main.py
from plynth.http.transport import HttpxSyncTransport
from plynth.http.client import APIClient
from connector.settings import IssueTrackerSettings
from connector.facade import IssueTrackerFacade

settings = IssueTrackerSettings()
transport = HttpxSyncTransport.from_settings(settings)
client = APIClient(base_url=settings.base_url, transport=transport)
tracker = IssueTrackerFacade(client)

issues = tracker.issues().list(status="open")
for issue in issues:
    print(issue.id, issue.title)
```

`from_settings()` reads `base_url`, timeouts, and auth config from the
settings object and constructs a fully wired transport.

## What you built

```text
connector/
├── settings.py   ← IssueTrackerSettings (env vars + auth config)
├── models.py     ← Issue (domain model)
├── service.py    ← IssueService (HTTP operations → domain models)
└── facade.py     ← IssueTrackerFacade (entry point)
```

Each layer has a single responsibility:

- **Settings** — configuration and secrets.
- **Models** — data shape, no I/O.
- **Service** — HTTP calls and response mapping.
- **Facade** — constructs services from a shared client.

## Next steps

- [Add middleware](03-add-middleware.md) — add logging, retry, and circuit
  breaking to the transport.
- [Add response caching](04-add-caching.md) — cache GET responses.
- [Test with VCR](05-test-with-vcr.md) — record and replay HTTP interactions
  in tests.
