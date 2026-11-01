# How-to guides

How-to guides are **task-oriented**. Each guide helps you complete one specific
goal. They assume you are already familiar with the basics.

## Core Plynt

- [Add authentication](add-authentication.md) — Bearer tokens, Basic auth,
  OAuth2 client credentials, JWT Bearer, and ROPC flows
- [Use middleware](use-middleware.md) — caching, logging, retry, circuit
  breaking, rate limiting, and static headers
- [Write custom middleware](write-middleware.md) — implement the
  `SyncMiddleware` or `AsyncMiddleware` protocol
- [Use caching](use-cache.md) — choose and configure a cache backend
- [Configure logging](configure-logging.md) — structured JSON logging, log
  throttling, and exception filters
- [Handle errors](handle-errors.md) — catch and inspect typed HTTP exceptions
- [Use async](use-async.md) — switch to async/await for concurrent workloads

## Extension documentation

Framework-specific recipes live in the
[adapter documentation](../../adapters/README.md). Platform-specific recipes
live with each connector under [connector documentation](../../connectors/).
