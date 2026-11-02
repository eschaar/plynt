# Changelog

All notable changes to this project are documented in this file.

## Unreleased — roadmap preparation

Release-please owns version selection and versioned entries.

- Add typed HTTP network and authentication errors, request-ID propagation,
  configurable adapter error envelopes, and optional error reporting/Sentry.
- Document shared Salesforce auth cleanup and the FastAPI lifespan recipe;
  ship typing metadata and reorganize framework guides.
- Breaking: built-in network failures now raise Plynt transport types; token
  failures no longer expose response bodies in their messages. See the
  [migration guide](docs/user/migrations/typed-transport-errors.md) and
  [release preparation](docs/releases/2026-11-01-roadmap-release-notes.md).
- Live CDC remains Experimental and deferred; performance is unmeasured.

## [0.12.1](https://github.com/eschaar/plynt/compare/0.12.0...0.12.1) (2026-11-02)


### Fixes

* **auth:** include scope in OAuth token cache keys ([1691bb4](https://github.com/eschaar/plynt/commit/1691bb4071fb426a7d13aa3f507ccda2c3abd15c))
* **cache:** isolate response entries by request identity ([ad0de56](https://github.com/eschaar/plynt/commit/ad0de5606bcdcc233779c7c84173bd1cdab13cc4))
* **cache:** preserve duplicate header value order ([397000e](https://github.com/eschaar/plynt/commit/397000e2fb0977a19d00da5902105c2a74baaadb))
* **ci:** audit all runtime extras ([ccb45d1](https://github.com/eschaar/plynt/commit/ccb45d1161d98e7a3d7a26e12b40d63438a60681))
* **ci:** isolate release metadata from shell ([e3d254e](https://github.com/eschaar/plynt/commit/e3d254e4db0b73b81da31091c1592f8613dd514a))
* **ci:** propagate tox failures through evidence pipelines ([2c327df](https://github.com/eschaar/plynt/commit/2c327df1da72cef6aa58d512adacaf5928442488))
* **errors:** restore authentication error from serialized details ([6c15f4d](https://github.com/eschaar/plynt/commit/6c15f4d98ce0b24ed0c19363723090737b27ce99))
* **middleware:** reject nonfinite rate limit values ([280c064](https://github.com/eschaar/plynt/commit/280c064b46ec8d741a95b80f0225df0f43941374))
* **middleware:** release ignored circuit breaker probes ([ab730c2](https://github.com/eschaar/plynt/commit/ab730c2ec887f58a6139ac1cf93953a9434c05f0))
* **middleware:** release only the admitted breaker probe ([d500706](https://github.com/eschaar/plynt/commit/d50070677baa1bbac9e347be300f5dae9a5a62dd))
* **middleware:** validate retry attempt and backoff budgets ([ad29cca](https://github.com/eschaar/plynt/commit/ad29ccaa236d8abb2b090c4efbdf6aff66343520))
* **reporting:** isolate OAuth token retry observations ([b2bb4e2](https://github.com/eschaar/plynt/commit/b2bb4e2e5efdedd562123c9e53dd9883adea36ac))
* **salesforce:** cap Bulk polling before exponentiation ([7f945c8](https://github.com/eschaar/plynt/commit/7f945c85ff66957441107f211a818c01f3766f33))
* **salesforce:** enforce the Bulk polling budget ([cc98ba7](https://github.com/eschaar/plynt/commit/cc98ba73ca5067afdfa164d517b3f921488cada8))
* **salesforce:** report Bulk cleanup failures safely ([e08ccb8](https://github.com/eschaar/plynt/commit/e08ccb85dc345781d8fcbe12f326fc46086938c7))


### Documentation

* **arch:** add secure cache identity ADR ([55091ca](https://github.com/eschaar/plynt/commit/55091ca1f4d34e0d9884194aed6c040dc244813a))
* **architecture:** define tested gRPC upgrade policy in ADR-0044 ([dd33d27](https://github.com/eschaar/plynt/commit/dd33d2784688b3e33c1c51f97ec736bb0b502f1c))
* **cache:** align architecture guidance with accepted contracts ([11c3661](https://github.com/eschaar/plynt/commit/11c3661ec15735f3db49924c69cdca5f77fa9225))
* **cache:** describe Redis TTL truncation accurately ([63510cb](https://github.com/eschaar/plynt/commit/63510cb366887b2403b46cb22a77dc46db30cd2b))
* **release:** record ADR-0044 refresh evidence ([3deddb9](https://github.com/eschaar/plynt/commit/3deddb9ab8c42a243a3b69b53efd46dae8576adf))


### Maintenance

* **ci:** update TruffleHog action to 3.99.7 ([e9e0bdc](https://github.com/eschaar/plynt/commit/e9e0bdc1f2edb9ee95f9cf4d15a33aec79dd6581))
* **grpc:** refresh generated toolchain to 1.85.0 ([51a20b5](https://github.com/eschaar/plynt/commit/51a20b57bbf9fbddfd56292e92e111080ad6992e))


### Tests

* **asyncio:** make fixture loop scope explicit ([d234bac](https://github.com/eschaar/plynt/commit/d234bac8c915ab20bdb25efb170488e28773518b))

## [0.12.0](https://github.com/eschaar/plynt/compare/0.11.1...0.12.0) (2026-11-01)


### ⚠ BREAKING CHANGES

* merge roadmap errors and reporting improvements
* **http:** Token failure messages no longer include response bodies. Inspect status_code and explicitly access response_body when needed.
* **http:** Built-in HTTP transports now raise TransportTimeoutError and TransportConnectionError instead of raw httpx2 network exceptions. Update exception handlers and custom retry classifiers accordingly.

### Features

* **base:** add configurable error envelope contract ([a400fbe](https://github.com/eschaar/plynt/commit/a400fbee55d56a48adaa4a38c9a4b82499d485c8))
* **base:** add request ID policy and scoped context ([f1c2c43](https://github.com/eschaar/plynt/commit/f1c2c431d2160685eba3b0b0d9550eaa122726e4))
* **base:** add safe authentication error ([83c4d3e](https://github.com/eschaar/plynt/commit/83c4d3e035a4dd402506f1b061a2272acafea803))
* **base:** add typed transport errors ([21a917d](https://github.com/eschaar/plynt/commit/21a917dad3c40c37749736cd5da2fd9d96ed98df))
* **base:** add vendor-neutral error reporter protocol ([1ad3698](https://github.com/eschaar/plynt/commit/1ad36985f027563d696a90f71b110bc84d6f164c))
* **django:** add sync and async request ID middleware ([5d3de25](https://github.com/eschaar/plynt/commit/5d3de257c0f9f0494e8c26613be0c1417823da54))
* **drf:** support configurable error envelopes ([27eb6f9](https://github.com/eschaar/plynt/commit/27eb6f94fb8cd2fcacadcc291305fc59818f87d2))
* **fastapi:** add pure ASGI request ID middleware ([29f78d0](https://github.com/eschaar/plynt/commit/29f78d065186de652c946d5d624e507c4086444d))
* **fastapi:** support configurable error envelopes ([aa77d31](https://github.com/eschaar/plynt/commit/aa77d3190b3822da5b876453e90cb4c9a296bcf6))
* **http:** add close and aclose to OAuth2 auth middleware ([a9cbc76](https://github.com/eschaar/plynt/commit/a9cbc7676a397a36192a89e42047eecb1d014e7f))
* **http:** normalize transport network errors ([ad592e7](https://github.com/eschaar/plynt/commit/ad592e7752fde3107296c59f6e0afba7fc8850c1))
* **http:** raise typed authentication errors for token failures ([2efb2a6](https://github.com/eschaar/plynt/commit/2efb2a6232c52bde7846d3dbcf8928d6b9a9868f))
* **log:** add scoped request ID filter ([152baa4](https://github.com/eschaar/plynt/commit/152baa4f08e9ddeb8ddd1efd01af9e1884333f29))
* merge roadmap errors and reporting improvements ([8dda9ba](https://github.com/eschaar/plynt/commit/8dda9baf8b337ff3d7db14a0dbe61e6161313820))
* **middleware:** propagate scoped request IDs in headers ([fd94cfc](https://github.com/eschaar/plynt/commit/fd94cfcbd059768de98518f3ccc91f99e4261348))
* **middleware:** report failures with scoped context and event IDs ([82198b2](https://github.com/eschaar/plynt/commit/82198b23fcd3912c786f949c0ecbc7c27a8ca271))
* **salesforce:** accept JWT bearer auth on Salesforce API clients ([0a5e258](https://github.com/eschaar/plynt/commit/0a5e2585e2be7aeb77d7e39345f0bbfc772ec9c5))
* **sentry:** add optional sanitized error reporting integration ([ef7a93b](https://github.com/eschaar/plynt/commit/ef7a93beddd97e8d57c2a12a718fc79a2aa80fde))
* ship py.typed marker in the wheel ([f181199](https://github.com/eschaar/plynt/commit/f181199cfcd6839e1b29377b29a04761ecb9aa88))


### Refactoring

* **base:** name request ID module explicitly ([d4f10a2](https://github.com/eschaar/plynt/commit/d4f10a2f00f832c241b04256a75fc79e43bbeaec))
* **http:** drop closable protocols from OAuth2 middleware ([dedc3b7](https://github.com/eschaar/plynt/commit/dedc3b7c39d276f8faa90b8bb1b2cb8b27244edb))


### Documentation

* **adr:** accept ADR-0039 to ADR-0041 ([dffc70d](https://github.com/eschaar/plynt/commit/dffc70d48aa34b184576eb562e5f355cfd1bef38))
* **adr:** accept error reporting context handoff ([d03a960](https://github.com/eschaar/plynt/commit/d03a96034a06db57714bd8194f3afb313bca3984))
* **adr:** define reporting state and exception-bound event IDs ([7f16270](https://github.com/eschaar/plynt/commit/7f1627054c9fbd88dcb0d79127a44373c7947756))
* **adr:** propose ADR-0039 to ADR-0041 ([e1a3328](https://github.com/eschaar/plynt/commit/e1a33289bac7931fd15e151e1e98c1144a98f68b))
* **release:** clear resolved authentication blocker ([ade65c6](https://github.com/eschaar/plynt/commit/ade65c6a410425825b89478d9bf5f4b612c34c2b))
* **release:** prepare roadmap migration and signed-off release notes ([3d87a93](https://github.com/eschaar/plynt/commit/3d87a933daa9166301977082c5b9c032d1516256))
* **release:** register authenticated push blocker and candidate ([5a2dc92](https://github.com/eschaar/plynt/commit/5a2dc9203bb70f1e2e9d954d7314f7d1faa4e73e))
* **release:** register PR and pending remote checks ([a62ba1b](https://github.com/eschaar/plynt/commit/a62ba1bd2e42c39d8065eaad0ce5c1a848b6f5e1))
* **roadmap:** add async auth lifecycle and typing gaps from Sales API ([ff891c4](https://github.com/eschaar/plynt/commit/ff891c476e24493cf2634a61ae19af7b60b20533))
* **roadmap:** add error-tracking item and generalize request-ID helpers ([98099c7](https://github.com/eschaar/plynt/commit/98099c793489fff184feecf60fa776cc72cc6a4a))
* **roadmap:** add FastAPI inbound request-ID and error envelope idea ([8cc487f](https://github.com/eschaar/plynt/commit/8cc487f4b09ff5dcf85289bd26e77ed7cdb41f27))
* **roadmap:** add transport error and SObject path doc gaps ([b891c4c](https://github.com/eschaar/plynt/commit/b891c4cca689fdc0a35251a722fc03feb5f49b28))
* **roadmap:** align delivered capabilities and completion statuses ([10699ef](https://github.com/eschaar/plynt/commit/10699efb837a4135e56718fbcdb4bebdb9d5e55e))
* **roadmap:** complete async auth lifecycle and typing track ([7a7b96b](https://github.com/eschaar/plynt/commit/7a7b96b33ebccec6ce63b7fca16c156851484843))
* **roadmap:** mark 2o quick wins done and link proposed ADRs ([2812da4](https://github.com/eschaar/plynt/commit/2812da4037b3437b8edf01931c43e3782019b854))
* **roadmap:** mark ADR-0039 typed errors implemented ([cc9c208](https://github.com/eschaar/plynt/commit/cc9c2084d4518f7f172c2f4dd3bc3e8c351b0a75))
* **roadmap:** record composable middleware extension ideas ([e29a6c2](https://github.com/eschaar/plynt/commit/e29a6c28522af8151268c9b2b110f2395b1ed055))
* **salesforce:** add tested shared-auth FastAPI lifespan recipe ([19344b4](https://github.com/eschaar/plynt/commit/19344b49600ce4119fc5a6150b139adb81b61fdf))
* **salesforce:** align SObject path docstrings with sent paths ([1f5293a](https://github.com/eschaar/plynt/commit/1f5293afe642b7fd83e0f4dc4ae89f046743a35b))
* separate core guides from optional extensions ([0270edd](https://github.com/eschaar/plynt/commit/0270edd577d95deca324efdf8e5a27707ba2ddf6))


### Maintenance

* bump local pyenv patch versions ([eb0055f](https://github.com/eschaar/plynt/commit/eb0055f9b1bb0171a4b73e22a171b913ab9e9b63))

## [0.11.1](https://github.com/eschaar/plynt/compare/0.11.0...0.11.1) (2026-10-26)


### Fixes

* harden retries and streaming with deterministic tests ([ee7a19a](https://github.com/eschaar/plynt/commit/ee7a19aafc501981b85fa0b8110dceb4452244a2))
* **http:** retry backend network failures (ADR-0038) ([178fc29](https://github.com/eschaar/plynt/commit/178fc298686bd5ce3abf1dd978bed601f14a501e))
* **streaming:** close discarded responses before retry (ADR-0038) ([9af513f](https://github.com/eschaar/plynt/commit/9af513fffa94978636a6a4f20ce1d6afe05561b0))


### Maintenance

* **ci:** bump trufflesecurity/trufflehog ([14b8a8f](https://github.com/eschaar/plynt/commit/14b8a8f0d7dfec85ab9690426a25ec43ee1d840b))
* **ci:** integrate TruffleHog update from PR [#69](https://github.com/eschaar/plynt/issues/69) ([2659283](https://github.com/eschaar/plynt/commit/265928365a9326d141f171676624f640d362ef70))
* **deps:** integrate PR [#55](https://github.com/eschaar/plynt/issues/55) and retain newer httpx2 (ADR-0023) ([8b24839](https://github.com/eschaar/plynt/commit/8b24839c9333f50896e2c8a801c87471c240f586))
* **deps:** integrate PR [#57](https://github.com/eschaar/plynt/issues/57) and retain newer pydantic (ADR-0003) ([e44e3d2](https://github.com/eschaar/plynt/commit/e44e3d2b429ac988cbc6f8021b0b3f4f478d8ef0))
* **deps:** integrate PR [#58](https://github.com/eschaar/plynt/issues/58) and retain newer cryptography ([b42e004](https://github.com/eschaar/plynt/commit/b42e00486acc2057557635311a4b6c8697db9b2d))


### Tests

* **salesforce:** verify AI streaming and feedback contracts ([9de24d5](https://github.com/eschaar/plynt/commit/9de24d597ec2cd005c6d3f7df91ae962e3b69a84))
* standardize deterministic clocks (ADR-0037) ([a014490](https://github.com/eschaar/plynt/commit/a014490e27501dbb5fc0576811322347079d7714))
* **throttle:** make HTTP-date delay checks deterministic ([6d11678](https://github.com/eschaar/plynt/commit/6d1167859a32d3aed7b9e99ffc6c3a20887e1d11))

## [0.11.0](https://github.com/eschaar/plynt/compare/0.10.0...0.11.0) (2026-10-14)


### ⚠ BREAKING CHANGES

* Rename distribution and import package to plynt.

### Features

* rebrand project and package as Plynt ([d28e9ac](https://github.com/eschaar/plynt/commit/d28e9ac7278a917455c7a3026e1dca54b814d726))


### Fixes

* **privacy:** sanitize recordings and omit author email ([d204686](https://github.com/eschaar/plynt/commit/d2046867e156bdf40d46d604accb67ec4a319ad1))
* **privacy:** sanitize recordings and omit author email ([59176e8](https://github.com/eschaar/plynt/commit/59176e84d9b33c7b8a282a12716bf82ad7a12304))


### Documentation

* **adr:** merge rebrand decisions ([62d0f18](https://github.com/eschaar/plynt/commit/62d0f18ecca3b063fe52790ce2c2548a7ea30e19))
* align historical docs with Plynt ([b68bff4](https://github.com/eschaar/plynt/commit/b68bff42c1fb7e0e99b6ea316d536767e4deca30))

## [0.10.0](https://github.com/eschaar/plynt/compare/0.9.5...0.10.0) (2026-10-14)


### ⚠ BREAKING CHANGES

* **deps:** Python 3.11 and Django versions below 6.1.2 are no longer supported. Upgrade to Python 3.12+ and migrate Django applications first.

### Features

* **grpc:** add experimental Salesforce CDC and harden release gates ([68f912c](https://github.com/eschaar/plynt/commit/68f912ce253ac2d23470b4075797f93fc7613421))
* **salesforce-cdc:** vendor Salesforce Pub/Sub proto stub ([e03561f](https://github.com/eschaar/plynt/commit/e03561f391944766aca2b9e826f9897d454dbf98))


### Fixes

* **ci:** use active Python for Salesforce proto drift check ([dd3fe93](https://github.com/eschaar/plynt/commit/dd3fe9336e10c47c6fa31cbd4c52e216a8056bca))
* **connectors:** harden Salesforce CDC flow control and bitmap decoding ([74bef3b](https://github.com/eschaar/plynt/commit/74bef3bdeeae281ce0549505338fcfb039c81aed))
* **salesforce-cdc:** base CDC errors on plynt's BaseError contract ([181623e](https://github.com/eschaar/plynt/commit/181623e278e61cfc7ff71e59a6958d365b43e8ac))
* **salesforce-cdc:** reconnect and classify real grpc errors correctly ([42d6f2f](https://github.com/eschaar/plynt/commit/42d6f2fa37cce8d8b141b43b1ee62312c360ad6e))
* **salesforce-cdc:** serialize real requests in vendored pubsub adapter ([cce7205](https://github.com/eschaar/plynt/commit/cce72058fddd8c55e908952391848ffc86fa2190))


### Refactoring

* **salesforce-cdc:** move error types to a dedicated errors module ([5acb4c1](https://github.com/eschaar/plynt/commit/5acb4c1fae50c10f0edc500ff92b45e5a181f447))


### Documentation

* align architecture and roadmap with experimental hardening ([14596d9](https://github.com/eschaar/plynt/commit/14596d97980dfbcbe06b6459405fe7336cf61737))
* **salesforce-cdc:** add example to vendored pubsub factory docstring ([4510fcd](https://github.com/eschaar/plynt/commit/4510fcd119849d46560e84804fa07a788a1882d7))
* **salesforce-cdc:** add k8s deploy guide and rename checkpoint store ([3d63d81](https://github.com/eschaar/plynt/commit/3d63d81c54ca0bab4407cbacd6a9d03945fd2542))
* **salesforce:** align CDC guides and hardening evidence ([de00000](https://github.com/eschaar/plynt/commit/de00000c0f5bcc5d857c62da173f32edf85297f9))


### Maintenance

* **deps:** consolidate Dependabot patch updates ([8d281a1](https://github.com/eschaar/plynt/commit/8d281a17ff3959798af1c452ea74f62a796eab5d))
* **deps:** refresh compatible runtimes and verification tooling ([5cbc2d6](https://github.com/eschaar/plynt/commit/5cbc2d69c86eeedeead583b940fc541a1c7a092a))
* **deps:** require Python 3.12 and upgrade Django to 6.1 ([b008423](https://github.com/eschaar/plynt/commit/b0084236a1466f42091c1523080bd360b20f605c))
* **deps:** upgrade cryptography to 50.0.1 ([5559708](https://github.com/eschaar/plynt/commit/5559708f1db9d24246505bc3741f1abf5176c24d))
* **deps:** upgrade httpx2 to 2.12.0 ([90858ca](https://github.com/eschaar/plynt/commit/90858ca22a1faa33d97b769c00574702cb99ac60))
* **deps:** upgrade pydantic to 2.13.5 ([6fcea9b](https://github.com/eschaar/plynt/commit/6fcea9b4cdd0806f982d74ee2bcde876f7d09516))
* **grpc:** refresh pinned codegen and align runtime minimum ([82cffbd](https://github.com/eschaar/plynt/commit/82cffbdf5610674ade0eb0c5f939d1db01db766d))
* harden release installations and enforce full coverage ([f78247e](https://github.com/eschaar/plynt/commit/f78247e2918ded6d37f2be0fe42a78e3411985f8))
* merge main and resolve dependency conflicts ([97f121c](https://github.com/eschaar/plynt/commit/97f121cfe910a3c2b749830df7e4343f85b94ee5))
* **python:** default to Python 3.14 and standardize local environments ([3153d62](https://github.com/eschaar/plynt/commit/3153d62951897dd2af40f7e8de0fd7ed7b284ac9))
* **python:** support Python 3.15 and document local pyenv bootstrap ([8c3b2e1](https://github.com/eschaar/plynt/commit/8c3b2e13bf8bf393cd3cc7458394ba21716d70e4))
* **release:** use minor bumps for pre-1.0 breaking changes ([943a66f](https://github.com/eschaar/plynt/commit/943a66f215c39c135c2a83a7e3cbd5ab571cfa19))

## [0.9.5](https://github.com/eschaar/plynt/compare/0.9.4...0.9.5) (2026-08-23)


### Maintenance

* **deps:** update httpx2 requirement from &gt;=2.9.1 to &gt;=2.10.0 ([63fec29](https://github.com/eschaar/plynt/commit/63fec29e9d059deabe719418785835862c94ef45))

## [0.9.4](https://github.com/eschaar/plynt/compare/0.9.3...0.9.4) (2026-08-17)


### Maintenance

* **ci:** bump trufflesecurity/trufflehog in the gha-patch-minor group ([81831ba](https://github.com/eschaar/plynt/commit/81831ba0305ecc69b6f9000c5f1f37a08c3143ad))

## [0.9.3](https://github.com/eschaar/plynt/compare/0.9.2...0.9.3) (2026-08-16)


### Maintenance

* **deps:** update django requirement from &lt;6,&gt;=5.2.16 to &gt;=5.2.17,&lt;6 ([3ee4a9d](https://github.com/eschaar/plynt/commit/3ee4a9d0987af458548e0ead1b2bfac109fdf375))
* **deps:** update djangorestframework requirement ([4aa17ab](https://github.com/eschaar/plynt/commit/4aa17ab9f01cf03f96db320d2b15f7447312e8b3))
* **deps:** update pydantic-settings requirement ([075dcea](https://github.com/eschaar/plynt/commit/075dcea1f6fd210e1f73c9ceb3772148c5be2fbb))
* **deps:** update setuptools requirement from &gt;=83.0.0 to &gt;=84.0.0 ([22bd8c5](https://github.com/eschaar/plynt/commit/22bd8c55583451624d53ee0f0d5cbf422e7837c2))

## [0.9.2](https://github.com/eschaar/plynt/compare/0.9.1...0.9.2) (2026-08-08)


### Maintenance

* **deps:** update cryptography requirement from &gt;=49.0.0 to &gt;=50.0.0 ([25ce6a9](https://github.com/eschaar/plynt/commit/25ce6a9cb00cfbb3f3b5e0f553526fceca05b9fc))
* **deps:** update fastapi requirement ([cc5c63c](https://github.com/eschaar/plynt/commit/cc5c63cc83859772686b42f95d327a29b2e47960))

## [0.9.1](https://github.com/eschaar/plynt/compare/0.9.0...0.9.1) (2026-07-31)


### Maintenance

* **ci:** bump trufflesecurity/trufflehog in the gha-patch-minor group ([f5a6e5d](https://github.com/eschaar/plynt/commit/f5a6e5dcdb2ea8a17a5e81ed45411c9f2510c619))
* **deps:** update fastapi requirement from &lt;1,&gt;=0.110 to &gt;=0.140.13,&lt;1 ([f0d4a6a](https://github.com/eschaar/plynt/commit/f0d4a6a5046ab7082d08a13e2a460fd769dfaaaa))
* **deps:** update httpx2 requirement from &gt;=2.7.0 to &gt;=2.9.1 ([9a0ca8c](https://github.com/eschaar/plynt/commit/9a0ca8c217548bb167547fd20268b5c42f87f7bd))

## [0.9.0](https://github.com/eschaar/plynt/compare/0.8.1...0.9.0) (2026-07-25)


### Features

* **fastapi:** ship adapter lifecycle, DI, docs, and tests ([11bf7be](https://github.com/eschaar/plynt/commit/11bf7be98f97ba1a85ac165e0c9452a0244d29e9))


### Fixes

* **fastapi:** keep service cache on request state ([e8f6035](https://github.com/eschaar/plynt/commit/e8f6035ddc529790ad4ab63692d9f144403327b3))


### Documentation

* **vcr:** wrap README example calls ([dea145d](https://github.com/eschaar/plynt/commit/dea145d864f635091bb65a588cbeee6df7699db2))


### Maintenance

* **ci:** bump actions/setup-python from 6 to 7 ([7c6fe3c](https://github.com/eschaar/plynt/commit/7c6fe3c3a50fa5f39985d6a1568cedc0ee9aad18))


### Tests

* **fastapi:** guard optional imports during collection ([33fed24](https://github.com/eschaar/plynt/commit/33fed24f651df89ad3b9a50db177b792984f917d))

## [0.8.1](https://github.com/eschaar/plynt/compare/0.8.0...0.8.1) (2026-07-15)


### Maintenance

* **deps:** update django requirement from &lt;6,&gt;=4.2 to &gt;=5.2.16,&lt;6 ([b3b7463](https://github.com/eschaar/plynt/commit/b3b74630787edf69ab54edbb04492f70602479c0))
* **deps:** update djangorestframework requirement ([533492f](https://github.com/eschaar/plynt/commit/533492feac9cfe350435f23dc2d9c02f55ef3164))
* **deps:** update httpx2 requirement from &gt;=2.5.0 to &gt;=2.7.0 ([5a7245e](https://github.com/eschaar/plynt/commit/5a7245e47a68840ec85e41e18a01797920dd241a))

## [0.8.0](https://github.com/eschaar/plynt/compare/0.7.1...0.8.0) (2026-07-14)


### Features

* **django-drf:** add DRF helpers and usage guides ([c110994](https://github.com/eschaar/plynt/commit/c110994b1814413bd76fd94177abd6a8d6bbcd3e))
* **django-drf:** complete middleware and error integration ([b5308fc](https://github.com/eschaar/plynt/commit/b5308fcd23abd9fe55523d94dcde3b5ed0d00300))
* **django:** add adapter skeleton and settings bridge ([60fac3e](https://github.com/eschaar/plynt/commit/60fac3e9b6048498f8e2b8e9c92602c05a9d122c))
* **django:** add async django and drf adapter support ([072e884](https://github.com/eschaar/plynt/commit/072e884f91a7687c8aeb74277e9fca8b7d8f3306))
* **django:** implement cache backend with usage docs ([f0936ec](https://github.com/eschaar/plynt/commit/f0936ec7d9bb99b87408b6d073be29841dc5606a))
* **django:** implement settings-based transport helper ([0c01bce](https://github.com/eschaar/plynt/commit/0c01bce51854046a461d99cd5230a9c9d69ddd64))


### Fixes

* **django-drf:** close transport resources in tests ([93c1894](https://github.com/eschaar/plynt/commit/93c1894f6efde402d787a5d62376888d4b0d84cd))


### Documentation

* **django-drf:** add interoperability contract and ViewSet guidance ([df647ad](https://github.com/eschaar/plynt/commit/df647ad0b89daa0b35d3d9a1049dd3a65e10fbb1))
* **django:** align roadmap, ADR, and change plan ([05911eb](https://github.com/eschaar/plynt/commit/05911ebf261f1ee326375ecfcb19f830d755f9c0))
* **examples:** migrate django examples to markdown snippets ([63f19d0](https://github.com/eschaar/plynt/commit/63f19d00c58faf268a7155fee386febd4365b234))
* **examples:** migrate llm and salesforce examples to markdown snippets ([585b6a5](https://github.com/eschaar/plynt/commit/585b6a585ee7059078373eb39d52e555712767ac))


### Tests

* **django-drf:** add framework-aware adapter smoke tests ([933553f](https://github.com/eschaar/plynt/commit/933553f703488ee6763fc964bb6b7bf1a609def8))

## [0.7.1](https://github.com/eschaar/plynt/compare/0.7.0...0.7.1) (2026-07-10)


### Maintenance

* **ci:** bump trufflesecurity/trufflehog in the gha-patch-minor group ([cc49976](https://github.com/eschaar/plynt/commit/cc49976b399db1ff6b5333e372d90256cda8c99e))

## [0.7.0](https://github.com/eschaar/plynt/compare/0.6.2...0.7.0) (2026-07-08)


### Features

* **llm:** add Anthropic adapter and stream normalization ([f74299c](https://github.com/eschaar/plynt/commit/f74299ce6f7e2c53a6040ce3fc7f81f926e5635e))
* **llm:** harden OpenAI responses adapters and stream parsing ([658ca4c](https://github.com/eschaar/plynt/commit/658ca4c5733c77cac37e0ea5c4eee4a32f336156))


### Refactoring

* **llm:** harden adapter flow and align docs roadmap ([9843b18](https://github.com/eschaar/plynt/commit/9843b18df5dcf2f08fad77a785cd4a2707c1a891))


### Documentation

* **llm:** align ADRs, roadmap, and runnable examples ([7503f73](https://github.com/eschaar/plynt/commit/7503f73bc4d540f7ac6b874eb2674216131ccba6))

## [0.6.2](https://github.com/eschaar/plynt/compare/0.6.1...0.6.2) (2026-07-06)


### Maintenance

* **ci:** bump actions/checkout from 6 to 7 ([06f2ffc](https://github.com/eschaar/plynt/commit/06f2ffc6c0ee8f21ed0a44c2e82f6375e5f6483e))
* **ci:** bump trufflesecurity/trufflehog in the gha-patch-minor group ([743ba7e](https://github.com/eschaar/plynt/commit/743ba7eca7210150c40cb792a0d4721e99538877))

## [0.6.1](https://github.com/eschaar/plynt/compare/0.6.0...0.6.1) (2026-07-05)


### Maintenance

* **ci:** bump trufflesecurity/trufflehog in the gha-patch-minor group ([bb75695](https://github.com/eschaar/plynt/commit/bb756957bee72781de664812a335728ebcf8936f))

## [0.6.0](https://github.com/eschaar/plynt/compare/0.5.1...0.6.0) (2026-07-04)


### Features

* **connectors:** implement generic llm connector and docs ([595291b](https://github.com/eschaar/plynt/commit/595291bfb1c18753c3f1919cab2131b2a2941d8a))
* **http:** add httpx2 http2 and client tuning settings ([2298add](https://github.com/eschaar/plynt/commit/2298add9e594ae2cdaa0a7ef4fbf6fa4602c40c4))
* **http:** switch transport backend dependency to httpx2 ([57a4b0a](https://github.com/eschaar/plynt/commit/57a4b0ade753571a8797b2f46c7219704fcc3f95))


### Refactoring

* **http:** complete httpx2 migration cleanup and pylint fixes ([f1ec72b](https://github.com/eschaar/plynt/commit/f1ec72b57c20ab2427a90ee9cc9096bb7785bb6e))
* **http:** remove lint warnings and DRY client builders ([0923547](https://github.com/eschaar/plynt/commit/0923547a51583675ecb20f7fc42dc468f5201bf1))


### Documentation

* **adr:** accept ADR-0021 and define SF-0012 acceptance triggers ([db1951d](https://github.com/eschaar/plynt/commit/db1951d0f4ef3227b0294e17d1eabf3200499369))
* **adr:** clarify transport-middleware boundary and add SSE roadmap option ([7674aa5](https://github.com/eschaar/plynt/commit/7674aa5f36e18b8bdee24850c0394b841041362d))
* **adr:** propose httpx2 transport backend migration ([f269630](https://github.com/eschaar/plynt/commit/f2696309c510ef74b5cdd7320ee31f9100d7c328))
* **architecture:** define connector and adapter boundaries ([bf8cf7e](https://github.com/eschaar/plynt/commit/bf8cf7e3187325e02bf14a0ae35793e5161b3a7f))
* **architecture:** relocate ai risk note and refresh ADR statuses ([9e8e574](https://github.com/eschaar/plynt/commit/9e8e574ea600c56e3e9e8db5ba743ac475ae1cd3))
* **cache:** complete backend how-to guidance and close roadmap item ([b2018f1](https://github.com/eschaar/plynt/commit/b2018f120deaf0c6dc1652a3fa13c80dfe1c7897))
* **middleware:** clarify generic vs HTTP middleware layers ([05bce16](https://github.com/eschaar/plynt/commit/05bce164c87305c7d3ea72745f021750d1d112d3))
* **roadmap:** align transport and middleware roadmap narrative ([0b00e32](https://github.com/eschaar/plynt/commit/0b00e3276bf6805997ba20b0479541cb8b509131))


### Tests

* **connectors:** harden llm stream parsing coverage ([6409d92](https://github.com/eschaar/plynt/commit/6409d92e5f279b5c56afca6057eb9f0b83cf12e4))
* **coverage:** close remaining gaps and stabilize httpx2 transport tests ([7f13f70](https://github.com/eschaar/plynt/commit/7f13f708f58f8ba66d3f28e6c3ef24476c059a94))

## [0.5.1](https://github.com/eschaar/plynt/compare/0.5.0...0.5.1) (2026-05-28)


### Maintenance

* **deps:** update pydantic requirement from &gt;=2.7.0 to &gt;=2.13.4 ([37b5ecd](https://github.com/eschaar/plynt/commit/37b5ecd1d3761ab329b85ccbb0627660bd2b9809))
* **deps:** update pyjwt requirement from &gt;=2.12.1 to &gt;=2.13.0 ([af6a881](https://github.com/eschaar/plynt/commit/af6a8812bd998909abb0f8cb4bf63003b3420c33))

## [0.5.0](https://github.com/eschaar/plynt/compare/0.4.0...0.5.0) (2026-05-16)


### Features

* **http:** add raw response mode and document layer boundary ([3657240](https://github.com/eschaar/plynt/commit/365724030adcd8b0129672ff79756cac984f90ce))
* **middleware:** add throttle governance and align retry handling ([e6731f1](https://github.com/eschaar/plynt/commit/e6731f1448e31fd1df21eb34460e822a02f36cb9))


### Fixes

* **base:** use StrEnum for ThrottleGovernanceAction ([dbd8cb6](https://github.com/eschaar/plynt/commit/dbd8cb687b9e2bf3aa4f8ba10522602fc90194b1))
* **http:** fix stream timeout, remove unnecessary ellipsis, and increase coverage ([4300f1c](https://github.com/eschaar/plynt/commit/4300f1c3033ba7354aa4ce01182a4c4c041fb16d))
* **http:** move lazy imports to module level; fix pylint disable placement ([38ef321](https://github.com/eschaar/plynt/commit/38ef321b62ef5aac9d20321657325d1b2bf98a15))
* **middleware:** case-insensitive header lookup in throttle governance ([0e32c81](https://github.com/eschaar/plynt/commit/0e32c812db62d27d5c41e28a6e5105a3b5ccb7e2))
* **middleware:** extract reset_at_seconds for 429 and 503 signals ([3f1aff4](https://github.com/eschaar/plynt/commit/3f1aff47bebd2d28055ceb60261bd2e4cfa450f8))
* **middleware:** harden throttle governance and align parity ([46b2e46](https://github.com/eschaar/plynt/commit/46b2e46f145ae0ac7d0561210ecccf6d865e6b89))
* **middleware:** honour reset_at_seconds in throttle governance ([bbcf7d6](https://github.com/eschaar/plynt/commit/bbcf7d614d3dea418c9a692fa1fb434a563780fb))
* **middleware:** implement SyncMiddleware/AsyncMiddleware protocol in throttle middleware ([677cb55](https://github.com/eschaar/plynt/commit/677cb552ec1733a0551f72bf9d13ee39010385c9))
* **middleware:** never retry on ThrottleGovernedError ([828fe0f](https://github.com/eschaar/plynt/commit/828fe0f489b7ebec49fb415aaad9e601ea0782ce))
* **middleware:** parse HTTP-date Retry-After header format ([a19c3a0](https://github.com/eschaar/plynt/commit/a19c3a02585a1dac795e50bd23cac70acdc31aa8))
* **middleware:** reject non-finite Retry-After values ([bfdd0ca](https://github.com/eschaar/plynt/commit/bfdd0cacb70ad6480f3d6d4a41f2771d8a0a1776))
* **salesforce:** early return for raw mode; add raw=True test coverage ([7543bbc](https://github.com/eschaar/plynt/commit/7543bbc95230d34460d55d9e14d58107a736ffab))
* **tests:** freeze time in HTTP-date Retry-After parser test ([e8a213a](https://github.com/eschaar/plynt/commit/e8a213ab5548ad775fcc6278c7789ec1dd088069))
* **tests:** patch sleep in remaining retry backoff tests ([a98dfab](https://github.com/eschaar/plynt/commit/a98dfab84708b148aa3b9189d6f7f2ae12e596b5))
* **tests:** patch sleep in retry governance integration tests ([5c67dbe](https://github.com/eschaar/plynt/commit/5c67dbe8f17a56316c57d48a4664bd5e12806a23))


### Refactoring

* **middleware:** rename public policy attribute to _policy for consistency ([e814eb5](https://github.com/eschaar/plynt/commit/e814eb5f5bb120a3b8acf61e6296f00ec17da638))


### Documentation

* **adr:** clarify dependency and settings decisions ([9ca80b6](https://github.com/eschaar/plynt/commit/9ca80b6e20ee6c0aa54751ac499c5d7f8224c514))
* **adr:** mark all acceptance criteria implemented in ADR-0022 ([9ce48d1](https://github.com/eschaar/plynt/commit/9ce48d1f4100dcd77fc9d0512872b67d80b35b3e))
* fix middleware ordering in reference; mark ADR-0022 criteria implemented ([0fbf521](https://github.com/eschaar/plynt/commit/0fbf5215415549587b6166e1eefee27c5b9ed315))
* **http:** correct raw mode use cases in error handling guide ([bad0b67](https://github.com/eschaar/plynt/commit/bad0b67034cb5d193f51b4a73e9dd3cbaf8c00ac))
* **middleware:** document X-RateLimit-Reset as fallback delay source ([fd21526](https://github.com/eschaar/plynt/commit/fd21526a3189210c96bd76b910912df458362f14))
* **middleware:** remove misleading Attributes section from async throttle middleware ([96fb028](https://github.com/eschaar/plynt/commit/96fb028c5dd2404efb7eb92f87affcb97c3f5809))
* **middleware:** show policy as optional in ThrottleGovernanceMiddleware signature ([6c07924](https://github.com/eschaar/plynt/commit/6c07924e34f7aacb9206efef78b2e080f0747d81))
* **salesforce:** document raw=True behaviour on both request() overloads ([80bc5ff](https://github.com/eschaar/plynt/commit/80bc5ff49413d3d28db010cabb95295dca02bfce))


### Tests

* **middleware:** increase throttle middleware coverage ([12e3758](https://github.com/eschaar/plynt/commit/12e375816da048af642ec598482286d2f62ba2e7))

## [0.4.0](https://github.com/eschaar/plynt/compare/0.3.0...0.4.0) (2026-05-15)


### Features

* **salesforce:** implement models and agent APIs with typed contracts ([b75221c](https://github.com/eschaar/plynt/commit/b75221c06f37d9f599e2b4b61c64530d69a3677f))
* **vcr:** Add readable YAML serializer for VCR cassettes ([7d431f2](https://github.com/eschaar/plynt/commit/7d431f290725096786a176c5ac38488e4fe2fc67))


### Fixes

* **cache:** add ttl parameter to CacheMiddleware and AsyncCacheMiddleware ([b2c2671](https://github.com/eschaar/plynt/commit/b2c26715663053eb361f4a581badecad27604b95))
* **deps:** add pydantic to salesforce extra and expand pyproject keywords ([f327343](https://github.com/eschaar/plynt/commit/f3273430a4e6fe2dab70514808fcce836cce6591))
* **salesforce:** return SalesforceQueryResponse from query_all for consistent typing ([3124b6f](https://github.com/eschaar/plynt/commit/3124b6f24bd330202b76ccde78c3bf364bfcfe09))
* **vcr:** Resolve MyPy type checking errors in serializer ([8ce9d4d](https://github.com/eschaar/plynt/commit/8ce9d4d255abb7d07bd92bbf7368cbd3a276e362))


### Refactoring

* **docs:** reorganize Salesforce AI docs by proper concerns ([0bc86fd](https://github.com/eschaar/plynt/commit/0bc86fd6d413ddcdea653abe0c68adff6124db32))


### Documentation

* **adr:** propose generic llm contract boundary ([52caa58](https://github.com/eschaar/plynt/commit/52caa584d384a86eb6362b5d028fcd0cae0c0d26))
* **adr:** propose upstream rate governance policy ([06414d1](https://github.com/eschaar/plynt/commit/06414d1efed210b82e996f44051c4f35f20e031c))
* **examples:** Use custom UserName__c field in Salesforce examples ([b97d5e8](https://github.com/eschaar/plynt/commit/b97d5e87e33867f695de17fff0727280b0947b78))
* fix README.md and README-pypi.md scope and accuracy ([a813844](https://github.com/eschaar/plynt/commit/a813844678201e9465ec13fa8c94fd307f486630))
* **roadmap:** parallelize ai connector tracks ([9fde804](https://github.com/eschaar/plynt/commit/9fde80405c9ec40928cdbac5fe5be5e89a1d86e3))
* **salesforce:** align roadmap upstream governance note ([a798232](https://github.com/eschaar/plynt/commit/a798232ff6b120601db38031841fe919fec7d676))
* **salesforce:** Clarify roadmap scope and resilience guidance ([9446179](https://github.com/eschaar/plynt/commit/9446179c8b3bf265752ae84590890f723ac14ad8))
* **salesforce:** update roadmap and AI boundary artifacts ([8523d83](https://github.com/eschaar/plynt/commit/8523d83f872533cbf81cd588a8aaf4e2cce8661f))


### Maintenance

* **deps:** Add types-PyYAML for type checking YAML serializer ([a4221a0](https://github.com/eschaar/plynt/commit/a4221a0418931a2f1c49c252538d4c7c38463ac4))
* **mypy:** disable warn_unused_ignores for vcr serializer module ([cf791cf](https://github.com/eschaar/plynt/commit/cf791cf57c06a947920d927ad0407c410a2b8357))


### Tests

* **salesforce:** sanitize smoke vcr cassettes ([c486d17](https://github.com/eschaar/plynt/commit/c486d176401285e4b67e4aec61abd44b0565572c))
* **vcr:** Normalize Salesforce cassettes for security and consistency ([2af679e](https://github.com/eschaar/plynt/commit/2af679e7fc64f992bf8c0c7463313a4110a002ae))

## [0.3.0](https://github.com/eschaar/plynt/compare/0.2.1...0.3.0) (2026-05-14)


### Features

* adr-0017 streaming response ([#4](https://github.com/eschaar/plynt/issues/4)) ([22619d7](https://github.com/eschaar/plynt/commit/22619d71191fcd2c22116c64cd518a596f67990b))

## [0.2.1](https://github.com/eschaar/plynt/compare/0.2.0...0.2.1) (2026-05-14)


### Documentation

* **readme:** align project and PyPI readme for release baseline ([4376b06](https://github.com/eschaar/plynt/commit/4376b066982f96e6513cac3ae18e0f60ff020335))


### Maintenance

* **ci:** disable workflows and stabilize release baseline ([51dcaba](https://github.com/eschaar/plynt/commit/51dcaba39100183ce984786e6748fd94c27e57d5))

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
