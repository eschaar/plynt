# Changelog

All notable changes to this project are documented in this file.

## [0.5.0](https://github.com/eschaar/plynth/compare/0.4.0...0.5.0) (2026-05-15)


### Features

* adr-0017 streaming response ([#4](https://github.com/eschaar/plynth/issues/4)) ([22619d7](https://github.com/eschaar/plynth/commit/22619d71191fcd2c22116c64cd518a596f67990b))
* **core:** release clean foundation ([a1deca8](https://github.com/eschaar/plynth/commit/a1deca8c3b20f42863ac370214261d88a2baff81))
* **salesforce:** add connector package ([c4f2423](https://github.com/eschaar/plynth/commit/c4f2423ea65cc817e6b3e3d4f61f7f53c55f3cca))
* **salesforce:** implement models and agent APIs with typed contracts ([b75221c](https://github.com/eschaar/plynth/commit/b75221c06f37d9f599e2b4b61c64530d69a3677f))
* **vcr:** Add readable YAML serializer for VCR cassettes ([84f6756](https://github.com/eschaar/plynth/commit/84f675685c7ab8d19d321946427b98672e8e43a4))


### Fixes

* **cache:** add ttl parameter to CacheMiddleware and AsyncCacheMiddleware ([c4d6c6c](https://github.com/eschaar/plynth/commit/c4d6c6c269b8425ffd46a96576e8949587086e8d))
* **deps:** add pydantic to salesforce extra and expand pyproject keywords ([c9dc515](https://github.com/eschaar/plynth/commit/c9dc5159daa9aa999aa8f313a952a2ed0fef394b))
* **salesforce:** return SalesforceQueryResponse from query_all for consistent typing ([a799aaa](https://github.com/eschaar/plynth/commit/a799aaad587fc03841c527facb32f213de479c6f))
* **vcr:** Resolve MyPy type checking errors in serializer ([2bb2328](https://github.com/eschaar/plynth/commit/2bb23283a2bafc3464647a95495c629da671f9d2))


### Refactoring

* **docs:** reorganize Salesforce AI docs by proper concerns ([aa0c1d6](https://github.com/eschaar/plynth/commit/aa0c1d6577a42b7005a3c7078ed9097addd9d308))


### Documentation

* **adr:** propose generic llm contract boundary ([52caa58](https://github.com/eschaar/plynth/commit/52caa584d384a86eb6362b5d028fcd0cae0c0d26))
* **adr:** propose upstream rate governance policy ([06414d1](https://github.com/eschaar/plynth/commit/06414d1efed210b82e996f44051c4f35f20e031c))
* **changelog:** 0.2.1 ([850f9bf](https://github.com/eschaar/plynth/commit/850f9bfcb27991b62010d716f00903ba3a5f8a7c))
* **changelog:** 0.3.0 ([d66768a](https://github.com/eschaar/plynth/commit/d66768a4306165fa38c708c218af055cca592b9a))
* **changelog:** 0.4.0 ([e53f43f](https://github.com/eschaar/plynth/commit/e53f43fc6dfa5ebe3c0089e1c17cb31d955e6088))
* **examples:** Use custom UserName__c field in Salesforce examples ([adad500](https://github.com/eschaar/plynth/commit/adad500ec65c7690e2eeeae5f8328987c555fa6f))
* fix README.md and README-pypi.md scope and accuracy ([350f6e9](https://github.com/eschaar/plynth/commit/350f6e9326d63340c1f753cfefabdc8896c4debe))
* **readme:** align project and PyPI readme for release baseline ([4376b06](https://github.com/eschaar/plynth/commit/4376b066982f96e6513cac3ae18e0f60ff020335))
* **roadmap:** parallelize ai connector tracks ([9fde804](https://github.com/eschaar/plynth/commit/9fde80405c9ec40928cdbac5fe5be5e89a1d86e3))
* **salesforce:** align roadmap upstream governance note ([a798232](https://github.com/eschaar/plynth/commit/a798232ff6b120601db38031841fe919fec7d676))
* **salesforce:** Clarify roadmap scope and resilience guidance ([d7e768f](https://github.com/eschaar/plynth/commit/d7e768f83bfc027d61f03cc96df72d94edc479a6))
* **salesforce:** update roadmap and AI boundary artifacts ([8523d83](https://github.com/eschaar/plynth/commit/8523d83f872533cbf81cd588a8aaf4e2cce8661f))


### Maintenance

* **ci:** disable workflows and stabilize release baseline ([51dcaba](https://github.com/eschaar/plynth/commit/51dcaba39100183ce984786e6748fd94c27e57d5))
* **deps:** Add types-PyYAML for type checking YAML serializer ([41a5eae](https://github.com/eschaar/plynth/commit/41a5eaeaa903064ab211fde1ed64a993f9744b03))
* **mypy:** disable warn_unused_ignores for vcr serializer module ([20c70e3](https://github.com/eschaar/plynth/commit/20c70e3e7b458c25117a10d3126d444e8a5dd46c))
* **repo:** initialize clean plynth foundation ([33bdcff](https://github.com/eschaar/plynth/commit/33bdcff6f274efb4428dab680d6f3f51fa44098d))


### Tests

* **salesforce:** sanitize smoke vcr cassettes ([c486d17](https://github.com/eschaar/plynth/commit/c486d176401285e4b67e4aec61abd44b0565572c))
* **vcr:** Normalize Salesforce cassettes for security and consistency ([d534a4b](https://github.com/eschaar/plynth/commit/d534a4b79e3b2e99790b41ce98f1671f83ec06a8))
* **vcr:** replace internal Salesforce hostname with myorg placeholder ([c3bcdbd](https://github.com/eschaar/plynth/commit/c3bcdbd958b6f6673c6cd7c2d9ac7dc552069963))

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
