# Plynth user documentation

Plynth is a framework-agnostic Python HTTP client library. It provides a
layered architecture — transport, middleware, client, and service — that
makes it easy to integrate with external APIs and to add cross-cutting
concerns (caching, retries, circuit breaking, authentication, logging) in a
composable way.

## Architecture overview

```mermaid
graph TB
    subgraph App["Your application"]
        SL["Facade / Service layer\n(HTTPService · APIService · your own subclass)"]
        CL["Client layer\n(HTTPClient / APIClient)"]
        subgraph TC["Transport + middleware chain"]
            CM[CacheMiddleware]
            LM[LoggingMiddleware]
            AM[AuthMiddleware]
            RM[RetryMiddleware]
            CB[CircuitBreakerMiddleware]
            NET["(network)"]
            CM --> LM --> AM --> RM --> CB --> NET
        end
        SL --> CL --> TC
    end
```

See [Architecture explanation](explanation/architecture.md) for a full
description of each layer.

## Documentation structure

Documentation follows the [Diátaxis](https://diataxis.fr/) framework:

| Section                              | Purpose                      | Start here when...                                       |
| ------------------------------------ | ---------------------------- | -------------------------------------------------------- |
| [Tutorials](tutorials/README.md)     | Step-by-step learning guides | You are new to Plynth                                    |
| [How-to guides](how-to/README.md)    | Task-oriented recipes        | You need to accomplish a specific goal                   |
| [Reference](reference/README.md)     | Technical API descriptions   | You need to look up a class, setting, or error           |
| [Explanation](explanation/README.md) | Conceptual background        | You want to understand *why* things work the way they do |

## Quick start

```bash
pip install "plynth[httpx]"
```

```python
from plynth.http.transport import HttpxSyncTransport
from plynth.http.client import APIClient

transport = HttpxSyncTransport()
client = APIClient(base_url="https://api.example.com", transport=transport)
response = client.get("/items")
print(response.json())
```

See [Tutorial 1 — Getting started](tutorials/01-getting-started.md) for a
full walkthrough.

## Connectors

Plynth ships with Salesforce and generic LLM connectors. Connector-specific
documentation lives alongside each connector:

- [Generic LLM connector](../connectors/llm/README.md)
- [Salesforce connector](../connectors/salesforce/user/README.md)

## Runnable examples

Use runnable examples when you want to validate credentials, endpoint setup,
and basic service behavior end-to-end.

- [LLM examples](../../examples/llm/README.md)
- [Django examples](../../examples/django/README.md)
- [Salesforce examples](../../examples/salesforce/README.md)

## Installation extras

Install `plynth[httpx]` for built-in HTTP transports or
`plynth[salesforce]` for Salesforce REST, Bulk, and AI services.
Experimental Salesforce CDC composes `plynth[grpc,salesforce]`,
including the Avro decoder.

Framework adapters use the `django`, `drf`, and `fastapi` extras. OAuth2
helpers are included in the package; there is no separate `oauth` extra.
Development bootstrap deliberately includes all implemented runtime extras.

See the canonical [installation reference](reference/installation.md) for
the complete profiles, runtime compatibility, and development commands.
