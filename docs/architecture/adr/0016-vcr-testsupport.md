# ADR-0016: VCR Testsupport Layer

## Status

Accepted

## Context

Teams need deterministic HTTP tests without always calling real backends.
The test harness must support:

1. Replay mode for stable CI runs.
1. Record mode for creating or updating fixtures.
1. Passthrough mode for explicit live smoke tests.

The solution should be reusable across integrations and should not force
integration-specific behavior into a generic core.

Another required scenario is state transitions for the same URL:

1. Read object (response A is cached in cassette).
1. Update object.
1. Read object again from the same URL.

If matching uses only method and URL, step 3 may incorrectly replay
response A. This causes stale replay after mutation.

## Decision

Adopt `vcrpy` as the persistence and matching engine for testsupport.

Expose a thin Plynth adapter in `plynth.testsupport.vcr` with three
interfaces:

1. Context manager: `use_vcr(...)`
1. Decorator: `@with_vcr(...)`
1. Transport middleware:
   - `VCRMiddleware`
   - `AsyncVCRMiddleware`

All interfaces use one VCR cassette backend with deterministic pathing.

### Core Components

1. `vcrpy` cassette engine
   - native YAML/JSON serializers
   - record/replay modes and matcher support
1. `VCRSettings`
   - typed wrapper for mode, matchers, filters, and state tracking
1. deterministic cassette path helper
   - test-node-derived path shape and hash suffix
1. optional state-tracking extension
   - revision header injected into VCR matching requests

### Configuration Model

Configuration is layered and overridable.

1. Global defaults
   - defined once for the full test run
   - intended for CI-safe baseline behavior
1. Suite-level overrides
   - defined in local test configuration for a subtree
   - used for integration-specific match and scrub rules
1. Test-level overrides
   - provided via context manager or decorator arguments
   - used for exceptional test cases only

Precedence order is strict:

- test-level overrides
- suite-level overrides
- global defaults

This allows central policy while preserving local control.

### Typed Middleware Configuration

Middleware is configured with typed settings objects.

1. `VCRSettings`
   - mode (`none | once | new_episodes | all | passthrough`)
   - matchers (`match_on`)
   - `filter_headers`
   - `decode_compressed_response`
   - `custom_matchers`
   - state tracking config
1. `StateTrackingSettings`
   - strategy (`off | resource | global`)
   - synthetic revision header name
   - mutating methods set
   - success status range for revision increments

### Optional Anti-Stale Mechanism

Add an optional state-aware discriminator to request matching.

Configuration:

- `state_tracking = off | resource | global`
- default is `off` for backward compatibility
- enabled through typed state tracking settings

Behavior when enabled:

1. Determine a state key:
   - `resource`: derived from normalized URL path
   - `global`: one shared key for the whole cassette session
1. Maintain a per-key revision counter in memory.
1. Include the current revision in a synthetic request header used by
   VCR matchers.
1. For successful mutating requests (`POST`, `PUT`, `PATCH`, `DELETE`),
   increment revision for the selected key.

Result:

- Read-before-update and read-after-update no longer collide,
  even if method and URL are identical.

### Extensibility

Integration-specific behavior stays outside the generic layer:

- custom cassette path conventions
- custom matcher registration
- custom `match_on` sets per suite
- custom state-key extraction extension points

## Consequences

Positive:

- Deterministic tests in replay mode.
- Reusable tooling across integrations with lower maintenance burden.
- Uses battle-tested VCR behavior and cassette format.
- Supports sync and async via a shared adapter.
- Solves stale replay after mutation when state tracking is enabled.

Trade-offs:

- Adds dependency on `vcrpy` for testsupport usage.
- State-aware matching adds runtime bookkeeping.
- Incorrect resource-key extraction can reduce replay quality.

Mitigations:

- Keep defaults simple and conservative.
- Provide a tested default resource extractor.
- Allow explicit override per test suite.
- Keep CI defaults replay-safe; allow local opt-in recording.

## Implementation Notes

Recommended rollout:

1. Introduce `plynth.testsupport.vcr` adapter layer.
1. Migrate existing testsupport usage to `plynth.testsupport.vcr`.
1. Keep state tracking optional until broadly validated.

No integration-specific logic is part of this ADR.

Implementation and usage guide:

- [VCR Testsupport Guide](../../src/plynth/testsupport/vcr/README.md)
