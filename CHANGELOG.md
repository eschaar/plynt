# Changelog

All notable changes to this project are documented in this file.

## [0.4.0](https://github.com/eschaar/plynth/compare/0.3.0...0.4.0) (2026-05-15)


### Features

* **salesforce:** implement models and agent APIs with typed contracts ([b75221c](https://github.com/eschaar/plynth/commit/b75221c06f37d9f599e2b4b61c64530d69a3677f))
* **vcr:** Add readable YAML serializer for VCR cassettes ([7d431f2](https://github.com/eschaar/plynth/commit/7d431f290725096786a176c5ac38488e4fe2fc67))


### Fixes

* **cache:** add ttl parameter to CacheMiddleware and AsyncCacheMiddleware ([b2c2671](https://github.com/eschaar/plynth/commit/b2c26715663053eb361f4a581badecad27604b95))
* **deps:** add pydantic to salesforce extra and expand pyproject keywords ([f327343](https://github.com/eschaar/plynth/commit/f3273430a4e6fe2dab70514808fcce836cce6591))
* **salesforce:** return SalesforceQueryResponse from query_all for consistent typing ([3124b6f](https://github.com/eschaar/plynth/commit/3124b6f24bd330202b76ccde78c3bf364bfcfe09))
* **vcr:** Resolve MyPy type checking errors in serializer ([8ce9d4d](https://github.com/eschaar/plynth/commit/8ce9d4d255abb7d07bd92bbf7368cbd3a276e362))


### Refactoring

* **docs:** reorganize Salesforce AI docs by proper concerns ([0bc86fd](https://github.com/eschaar/plynth/commit/0bc86fd6d413ddcdea653abe0c68adff6124db32))


### Documentation

* **adr:** propose generic llm contract boundary ([52caa58](https://github.com/eschaar/plynth/commit/52caa584d384a86eb6362b5d028fcd0cae0c0d26))
* **adr:** propose upstream rate governance policy ([06414d1](https://github.com/eschaar/plynth/commit/06414d1efed210b82e996f44051c4f35f20e031c))
* **examples:** Use custom UserName__c field in Salesforce examples ([b97d5e8](https://github.com/eschaar/plynth/commit/b97d5e87e33867f695de17fff0727280b0947b78))
* fix README.md and README-pypi.md scope and accuracy ([a813844](https://github.com/eschaar/plynth/commit/a813844678201e9465ec13fa8c94fd307f486630))
* **roadmap:** parallelize ai connector tracks ([9fde804](https://github.com/eschaar/plynth/commit/9fde80405c9ec40928cdbac5fe5be5e89a1d86e3))
* **salesforce:** align roadmap upstream governance note ([a798232](https://github.com/eschaar/plynth/commit/a798232ff6b120601db38031841fe919fec7d676))
* **salesforce:** Clarify roadmap scope and resilience guidance ([9446179](https://github.com/eschaar/plynth/commit/9446179c8b3bf265752ae84590890f723ac14ad8))
* **salesforce:** update roadmap and AI boundary artifacts ([8523d83](https://github.com/eschaar/plynth/commit/8523d83f872533cbf81cd588a8aaf4e2cce8661f))


### Maintenance

* **deps:** Add types-PyYAML for type checking YAML serializer ([a4221a0](https://github.com/eschaar/plynth/commit/a4221a0418931a2f1c49c252538d4c7c38463ac4))
* **mypy:** disable warn_unused_ignores for vcr serializer module ([cf791cf](https://github.com/eschaar/plynth/commit/cf791cf57c06a947920d927ad0407c410a2b8357))


### Tests

* **salesforce:** sanitize smoke vcr cassettes ([c486d17](https://github.com/eschaar/plynth/commit/c486d176401285e4b67e4aec61abd44b0565572c))
* **vcr:** Normalize Salesforce cassettes for security and consistency ([2af679e](https://github.com/eschaar/plynth/commit/2af679e7fc64f992bf8c0c7463313a4110a002ae))

## [0.3.0](https://github.com/eschaar/plynth/compare/0.2.1...0.3.0) (2026-05-14)


### Features

* adr-0017 streaming response ([#4](https://github.com/eschaar/plynth/issues/4)) ([22619d7](https://github.com/eschaar/plynth/commit/22619d71191fcd2c22116c64cd518a596f67990b))

## [0.2.1](https://github.com/eschaar/plynth/compare/0.2.0...0.2.1) (2026-05-14)


### Documentation

* **readme:** align project and PyPI readme for release baseline ([4376b06](https://github.com/eschaar/plynth/commit/4376b066982f96e6513cac3ae18e0f60ff020335))


### Maintenance

* **ci:** disable workflows and stabilize release baseline ([51dcaba](https://github.com/eschaar/plynth/commit/51dcaba39100183ce984786e6748fd94c27e57d5))

## [0.2.0] - 2026-05-14

### Added

- Salesforce connector package with typed client and service modules.
- Salesforce auth, query, bulk, metadata, identity, composite, and utility APIs.
- Connector-focused tests, smoke coverage, and usage examples.

## [0.1.0] - 2026-05-14

### Added

- Core HTTP foundation with request, response, transport, and middleware layers.
- Cache abstractions and default cache adapters.
- Shared error mapping, retry policies, logging utilities, and VCR test support.
- Project documentation, ADR set, and core test suite.

## [0.0.0] - 2026-05-14

### Added

- Technical anchor release used to initialize the rebuilt history.
