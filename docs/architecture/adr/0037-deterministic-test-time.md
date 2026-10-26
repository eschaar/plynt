# ADR-0037: Deterministic Test Time

**Date:** 2026-10-26
**Status:** Accepted

## Context

Time-sensitive tests currently mix real waits, patched calendar clocks,
duplicated monotonic clocks, and sequences of mocked clock reads. A fixed
Retry-After date eventually became historical and broke a test. Real waits
also make expiry tests slower and sensitive to scheduling.

Calendar time and elapsed time have different responsibilities. HTTP dates
and JWT claims use calendar time. Cache TTLs, rate-limit windows, recovery
intervals, and polling deadlines use monotonic time. Async event loops also
use monotonic time and must not be frozen accidentally.

## Decision

1. Add `time-machine` only to the existing test and development extras.
   Do not add it to core or runtime integration extras.
1. Use explicitly scoped `time_machine.travel(..., tick=False)` contexts for
   calendar-time tests. Prefer timezone-aware UTC datetimes.
1. Use one function-scoped `monotonic_clock` pytest fixture for elapsed-time
   tests. Advance it explicitly instead of waiting or scripting clock reads.
1. Bind the monotonic fixture to each module under test through a module-local
   replacement of its `time` reference. Never mutate the shared
   `time.monotonic` function or the event loop's clock.
1. Patch polling and retry waits only where necessary. Advance the test clock
   from a mocked polling wait when exercising deadlines.
1. Test before, at, and after time boundaries where behavior changes.
1. Leave production clocks, public APIs, and transport contracts unchanged.
   Do not freeze time automatically across the suite.

The initial migration covers throttle dates and reset timestamps, JWT expiry,
cache TTLs, rate-limit windows, circuit-breaker recovery, OAuth token expiry,
and Salesforce polling deadlines. Sleep mocks that only suppress retry waits
do not need replacement.

## Alternatives Considered

### Keep individual patches and real waits

This adds no dependency, but duplicates clocks and couples timeout tests to
the number of clock reads. Real waits remain slow and timing-sensitive.

### Use freezegun for all time

One library can control calendar and monotonic clocks, but freezing monotonic
time can interfere with asyncio scheduling. Special handling would be needed
to keep event-loop time live. This is not the selected approach.

### Use time-machine for all time

Its scoped calendar API avoids patching each import location, but version 3
does not mock `time.monotonic()`. It cannot replace elapsed-time test clocks.

### Inject clocks into production objects

Explicit clock injection is useful when production design requires it.
Changing constructors or core abstractions solely for this migration is
unnecessary and outside this decision.

## Rationale

Use time-machine for consistent calendar reads and a small pytest helper for
explicit elapsed time. This preserves the distinction between the two clocks
without changing runtime behavior or introducing a production abstraction.

## Consequences

### Positive

- Expiry and timeout tests no longer require elapsed wall time.
- Shared fixtures remove duplicate monotonic clock implementations.
- Exact boundaries can be tested without relying on machine speed.
- Consumers do not install an additional runtime dependency.

### Tradeoffs and Risks

- time-machine adds a CPython-specific test dependency. Validate it against
  the supported Python 3.12-3.15 Linux matrix.
- Calendar travel affects the whole process, including concurrent tasks.
  Keep contexts short and restore time on exit.
- Every module participating in a monotonic scenario must be bound explicitly,
  including cache and authentication modules when both use the same clock.
- Database-side clocks and external processes are not controlled.
- Keep concurrency synchronization separate from simulated expiry.

## Validation

Run focused time-sensitive tests, the full local quality gate, and the
supported interpreter matrix. Verify clock isolation, fixture teardown, exact
expiry boundaries, and sync/async parity without network access.

## Related ADRs

- [ADR-0003](0003-dependency-policy.md): Dependency Policy
- [ADR-0028](0028-supported-environments-and-extras-policy.md):
  Supported Environments and Extras Policy
- [ADR-0033](0033-python-315-support-and-local-pyenv.md):
  Python Support and Local pyenv Bootstrap
- [ADR-0034](0034-django-6-support.md): Django 6.x Support

## References

- [time-machine usage](https://time-machine.readthedocs.io/en/latest/usage.html)
- [time-machine installation and support](https://time-machine.readthedocs.io/en/latest/installation.html)
