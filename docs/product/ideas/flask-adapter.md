# Idea: Flask Adapter (`plynth[flask]`)

**Status:** Idea — not yet an ADR, no implementation started.
**Priority:** Low — plynth already works in Flask without an adapter;
this is a convenience layer only.

Convert to an ADR if there is a concrete use case that cannot be cleanly
handled by the user themselves.

______________________________________________________________________

## Goal

Allow Flask applications to use plynth transports and clients with idiomatic
Flask patterns — specifically the application factory pattern and
`app.extensions` for managing shared resources.

Flask applications typically:

- use the application factory pattern (`create_app()`)
- store shared resources in `app.extensions` via Flask extensions
- are primarily sync (Flask's async support exists but is limited — it wraps
  route coroutines in a thread, there is no real event loop)

______________________________________________________________________

## Why the priority is low

`HttpxSyncTransport.from_settings()` already works without any adapter:

```python
# This already works in Flask today — no adapter needed
from plynth.http.transport import HttpxSyncTransport
from myapp.settings import MyServiceSettings

transport = HttpxSyncTransport.from_settings(MyServiceSettings())
client = APIClient(base_url=settings.base_url, transport=transport)
```

A Flask adapter would only add the boilerplate of storing the transport in
`app.extensions` and retrieving it via a proxy — useful for consistency in
larger projects, but not architecturally necessary.

______________________________________________________________________

## Scope

### 1. Flask extension pattern

A `PlynthFlask` extension class manages one transport per Flask app and
follows the standard Flask extension pattern:

```python
from plynth.flask import PlynthFlask
from myapp.settings import MyServiceSettings

plynth = PlynthFlask()

def create_app():
    app = Flask(__name__)
    plynth.init_app(app, settings=MyServiceSettings())
    return app
```

The transport is stored in `app.extensions["plynth.<name>"]` and retrieved
via `current_app.extensions` or a convenience proxy.

### 2. App context proxy

Within a request or app context, the transport is accessible without importing
`app` directly:

```python
from plynth.flask import current_transport

@bp.route("/orders")
def list_orders():
    client = APIClient(base_url=settings.base_url, transport=current_transport)
    ...
```

### 3. Settings

Flask projects typically configure services via `app.config` (a dict loaded
from environment, TOML, or a config object). A thin `from_flask_config()`
factory reads a named prefix from `app.config` and returns a configured
`HTTPSettings`:

```python
# app.config["SALESFORCE_BASE_URL"] = "https://..."
sf_settings = SalesforceSettings.from_flask_config(app.config, prefix="SALESFORCE_")
```

______________________________________________________________________

## Install extra

```text
pip install plynth[flask]
```

Adds `flask` as a dependency. The `[httpx]` extra is a prerequisite.

______________________________________________________________________

## Constraints

- No Flask imports anywhere in `plynth.core` or `plynth.http`.
- Sync-only — Flask's async model is not a target.
- Must work with Flask 3.x.
- The adapter must remain a thin convenience layer; any logic beyond
  lifecycle management and config bridging belongs in the core.

______________________________________________________________________

## Open Questions

1. Is there a real demand for this, or does the existing zero-adapter approach
   cover all Flask use cases? Validate against at least one real Flask project
   before writing an ADR.
1. Should `plynth.flask` follow the Flask extension naming convention
   (class-based `init_app`) or be a simpler set of factory functions?
1. Multiple transports per app — store as a dict under a single
   `app.extensions["plynth"]` key, or separate keys per named transport?

______________________________________________________________________

## Next Step

Validate the need with a real Flask project. If there is clear friction that
the extension pattern would solve, write an ADR. Otherwise, document the
zero-adapter approach in the plynth usage guide and close this idea.
