# Salesforce Connector — User Documentation

This section covers everything you need to use the Plynth Salesforce connector.

## Structure

| Section                              | Purpose                                                |
| ------------------------------------ | ------------------------------------------------------ |
| [Tutorials](tutorials/README.md)     | Step-by-step guides for getting started                |
| [How-to guides](how-to/README.md)    | Task-focused recipes for common operations             |
| [Reference](reference/README.md)     | Full API surface: services, settings, errors, models   |
| [Explanation](explanation/README.md) | Background on auth flows, limits, and design decisions |

## Quick links

- [Connect to Salesforce for the first time](tutorials/01-connect-and-query.md)
- [Authenticate with Client Credentials](how-to/authenticate.md)
- [Query records with SOQL](how-to/query-records.md)
- [Handle Salesforce errors](how-to/handle-errors.md)
- [Add resilience (circuit breaker, quota observability)](how-to/resilience.md)
- [Service reference](reference/services.md)
- [Error reference](reference/errors.md)
- [Settings reference](reference/settings.md)

## What the connector covers

The Salesforce connector implements the Salesforce Platform REST API:

- SObject CRUD and metadata
- SOQL queries with pagination
- SOSL search
- Bulk API v2
- Composite, batch, and tree operations
- Metadata REST deployment
- Identity access primitives
- Apex REST passthrough
- Generative AI — Models API (chat, text, embeddings)
- Generative AI — Agent API (session lifecycle, streaming)
- OAuth2 Client Credentials and Username/Password auth flows

See the [roadmap](../../product/roadmap.md) for the full capability matrix
and future direction.
