# Changelog

All notable changes to this project are documented in this file.

## [0.6.2](https://github.com/eschaar/plynth/compare/0.6.1...0.6.2) (2026-07-06)


### Maintenance

* **ci:** bump actions/checkout from 6 to 7 ([06f2ffc](https://github.com/eschaar/plynth/commit/06f2ffc6c0ee8f21ed0a44c2e82f6375e5f6483e))
* **ci:** bump trufflesecurity/trufflehog in the gha-patch-minor group ([743ba7e](https://github.com/eschaar/plynth/commit/743ba7eca7210150c40cb792a0d4721e99538877))

## [0.6.1](https://github.com/eschaar/plynth/compare/0.6.0...0.6.1) (2026-07-05)


### Maintenance

* **ci:** bump trufflesecurity/trufflehog in the gha-patch-minor group ([bb75695](https://github.com/eschaar/plynth/commit/bb756957bee72781de664812a335728ebcf8936f))

## [0.6.0](https://github.com/eschaar/plynth/compare/0.5.1...0.6.0) (2026-07-04)


### Features

* **connectors:** implement generic llm connector and docs ([595291b](https://github.com/eschaar/plynth/commit/595291bfb1c18753c3f1919cab2131b2a2941d8a))
* **http:** add httpx2 http2 and client tuning settings ([2298add](https://github.com/eschaar/plynth/commit/2298add9e594ae2cdaa0a7ef4fbf6fa4602c40c4))
* **http:** switch transport backend dependency to httpx2 ([57a4b0a](https://github.com/eschaar/plynth/commit/57a4b0ade753571a8797b2f46c7219704fcc3f95))


### Refactoring

* **http:** complete httpx2 migration cleanup and pylint fixes ([f1ec72b](https://github.com/eschaar/plynth/commit/f1ec72b57c20ab2427a90ee9cc9096bb7785bb6e))
* **http:** remove lint warnings and DRY client builders ([0923547](https://github.com/eschaar/plynth/commit/0923547a51583675ecb20f7fc42dc468f5201bf1))


### Documentation

* **adr:** accept ADR-0021 and define SF-0012 acceptance triggers ([db1951d](https://github.com/eschaar/plynth/commit/db1951d0f4ef3227b0294e17d1eabf3200499369))
* **adr:** clarify transport-middleware boundary and add SSE roadmap option ([7674aa5](https://github.com/eschaar/plynth/commit/7674aa5f36e18b8bdee24850c0394b841041362d))
* **adr:** propose httpx2 transport backend migration ([f269630](https://github.com/eschaar/plynth/commit/f2696309c510ef74b5cdd7320ee31f9100d7c328))
* **architecture:** define connector and adapter boundaries ([bf8cf7e](https://github.com/eschaar/plynth/commit/bf8cf7e3187325e02bf14a0ae35793e5161b3a7f))
* **architecture:** relocate ai risk note and refresh ADR statuses ([9e8e574](https://github.com/eschaar/plynth/commit/9e8e574ea600c56e3e9e8db5ba743ac475ae1cd3))
* **cache:** complete backend how-to guidance and close roadmap item ([b2018f1](https://github.com/eschaar/plynth/commit/b2018f120deaf0c6dc1652a3fa13c80dfe1c7897))
* **middleware:** clarify generic vs HTTP middleware layers ([05bce16](https://github.com/eschaar/plynth/commit/05bce164c87305c7d3ea72745f021750d1d112d3))
* **roadmap:** align transport and middleware roadmap narrative ([0b00e32](https://github.com/eschaar/plynth/commit/0b00e3276bf6805997ba20b0479541cb8b509131))


### Tests

* **connectors:** harden llm stream parsing coverage ([6409d92](https://github.com/eschaar/plynth/commit/6409d92e5f279b5c56afca6057eb9f0b83cf12e4))
* **coverage:** close remaining gaps and stabilize httpx2 transport tests ([7f13f70](https://github.com/eschaar/plynth/commit/7f13f708f58f8ba66d3f28e6c3ef24476c059a94))

## [0.5.1](https://github.com/eschaar/plynth/compare/0.5.0...0.5.1) (2026-05-28)


### Maintenance

* **deps:** update pydantic requirement from &gt;=2.7.0 to &gt;=2.13.4 ([37b5ecd](https://github.com/eschaar/plynth/commit/37b5ecd1d3761ab329b85ccbb0627660bd2b9809))
* **deps:** update pyjwt requirement from &gt;=2.12.1 to &gt;=2.13.0 ([af6a881](https://github.com/eschaar/plynth/commit/af6a8812bd998909abb0f8cb4bf63003b3420c33))

## [0.5.0](https://github.com/eschaar/plynth/compare/0.4.0...0.5.0) (2026-05-16)


### Features

* **http:** add raw response mode and document layer boundary ([3657240](https://github.com/eschaar/plynth/commit/365724030adcd8b0129672ff79756cac984f90ce))
* **middleware:** add throttle governance and align retry handling ([e6731f1](https://github.com/eschaar/plynth/commit/e6731f1448e31fd1df21eb34460e822a02f36cb9))


### Fixes

* **base:** use StrEnum for ThrottleGovernanceAction ([dbd8cb6](https://github.com/eschaar/plynth/commit/dbd8cb687b9e2bf3aa4f8ba10522602fc90194b1))
* **http:** fix stream timeout, remove unnecessary ellipsis, and increase coverage ([4300f1c](https://github.com/eschaar/plynth/commit/4300f1c3033ba7354aa4ce01182a4c4c041fb16d))
* **http:** move lazy imports to module level; fix pylint disable placement ([38ef321](https://github.com/eschaar/plynth/commit/38ef321b62ef5aac9d20321657325d1b2bf98a15))
* **middleware:** case-insensitive header lookup in throttle governance ([0e32c81](https://github.com/eschaar/plynth/commit/0e32c812db62d27d5c41e28a6e5105a3b5ccb7e2))
* **middleware:** extract reset_at_seconds for 429 and 503 signals ([3f1aff4](https://github.com/eschaar/plynth/commit/3f1aff47bebd2d28055ceb60261bd2e4cfa450f8))
* **middleware:** harden throttle governance and align parity ([46b2e46](https://github.com/eschaar/plynth/commit/46b2e46f145ae0ac7d0561210ecccf6d865e6b89))
* **middleware:** honour reset_at_seconds in throttle governance ([bbcf7d6](https://github.com/eschaar/plynth/commit/bbcf7d614d3dea418c9a692fa1fb434a563780fb))
* **middleware:** implement SyncMiddleware/AsyncMiddleware protocol in throttle middleware ([677cb55](https://github.com/eschaar/plynth/commit/677cb552ec1733a0551f72bf9d13ee39010385c9))
* **middleware:** never retry on ThrottleGovernedError ([828fe0f](https://github.com/eschaar/plynth/commit/828fe0f489b7ebec49fb415aaad9e601ea0782ce))
* **middleware:** parse HTTP-date Retry-After header format ([a19c3a0](https://github.com/eschaar/plynth/commit/a19c3a02585a1dac795e50bd23cac70acdc31aa8))
* **middleware:** reject non-finite Retry-After values ([bfdd0ca](https://github.com/eschaar/plynth/commit/bfdd0cacb70ad6480f3d6d4a41f2771d8a0a1776))
* **salesforce:** early return for raw mode; add raw=True test coverage ([7543bbc](https://github.com/eschaar/plynth/commit/7543bbc95230d34460d55d9e14d58107a736ffab))
* **tests:** freeze time in HTTP-date Retry-After parser test ([e8a213a](https://github.com/eschaar/plynth/commit/e8a213ab5548ad775fcc6278c7789ec1dd088069))
* **tests:** patch sleep in remaining retry backoff tests ([a98dfab](https://github.com/eschaar/plynth/commit/a98dfab84708b148aa3b9189d6f7f2ae12e596b5))
* **tests:** patch sleep in retry governance integration tests ([5c67dbe](https://github.com/eschaar/plynth/commit/5c67dbe8f17a56316c57d48a4664bd5e12806a23))


### Refactoring

* **middleware:** rename public policy attribute to _policy for consistency ([e814eb5](https://github.com/eschaar/plynth/commit/e814eb5f5bb120a3b8acf61e6296f00ec17da638))


### Documentation

* **adr:** clarify dependency and settings decisions ([9ca80b6](https://github.com/eschaar/plynth/commit/9ca80b6e20ee6c0aa54751ac499c5d7f8224c514))
* **adr:** mark all acceptance criteria implemented in ADR-0022 ([9ce48d1](https://github.com/eschaar/plynth/commit/9ce48d1f4100dcd77fc9d0512872b67d80b35b3e))
* fix middleware ordering in reference; mark ADR-0022 criteria implemented ([0fbf521](https://github.com/eschaar/plynth/commit/0fbf5215415549587b6166e1eefee27c5b9ed315))
* **http:** correct raw mode use cases in error handling guide ([bad0b67](https://github.com/eschaar/plynth/commit/bad0b67034cb5d193f51b4a73e9dd3cbaf8c00ac))
* **middleware:** document X-RateLimit-Reset as fallback delay source ([fd21526](https://github.com/eschaar/plynth/commit/fd21526a3189210c96bd76b910912df458362f14))
* **middleware:** remove misleading Attributes section from async throttle middleware ([96fb028](https://github.com/eschaar/plynth/commit/96fb028c5dd2404efb7eb92f87affcb97c3f5809))
* **middleware:** show policy as optional in ThrottleGovernanceMiddleware signature ([6c07924](https://github.com/eschaar/plynth/commit/6c07924e34f7aacb9206efef78b2e080f0747d81))
* **salesforce:** document raw=True behaviour on both request() overloads ([80bc5ff](https://github.com/eschaar/plynth/commit/80bc5ff49413d3d28db010cabb95295dca02bfce))


### Tests

* **middleware:** increase throttle middleware coverage ([12e3758](https://github.com/eschaar/plynth/commit/12e375816da048af642ec598482286d2f62ba2e7))

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
