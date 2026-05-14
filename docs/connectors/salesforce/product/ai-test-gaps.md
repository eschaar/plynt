# Salesforce AI Test Gaps

## Coverage Gaps

- behavior:
  Streaming chat completion with chunk ordering and terminal completion marker.
- current coverage weakness:
  No Salesforce AI streaming tests exist yet for chunk order and end-of-stream
  semantics.
- production risk:
  Consumers may render incomplete or out-of-order model output.
- suggested test type: integration

- behavior:
  Stream interruption mid-response.
- current coverage weakness:
  No connector-level tests for abrupt disconnect and typed error mapping.
- production risk:
  Silent partial output and hard-to-debug failures in user-facing flows.
- suggested test type: unit

- behavior:
  Sync and async parity across Models and Agent methods.
- current coverage weakness:
  No parity suite exists for planned AI endpoints.
- production risk:
  Inconsistent behavior by runtime mode and regressions in one path.
- suggested test type: contract

- behavior:
  Feedback endpoint validation and ack handling.
- current coverage weakness:
  No tests for invalid ratings, missing IDs, or idempotency expectations.
- production risk:
  Feedback data quality issues and unstable client retries.
- suggested test type: unit

## False Confidence Risks

- location:
  Planned AI services (future `models` and `agent` modules).
- why confidence is false:
  High coverage percentages can still miss stream-failure behavior and parity.
- correction:
  Require explicit streaming failure tests and parity matrix checks as release
  gates.

- location:
  Generic HTTP transport tests only.
- why confidence is false:
  Transport coverage does not prove Salesforce payload mapping correctness.
- correction:
  Add connector contract tests with representative Salesforce AI responses.

## Priority Test Backlog

- test title:
  Models streaming chunks preserve order and finalize correctly
- owner role:
  tester
- acceptance check:
  Stream tests assert deterministic chunk sequence and final completion marker.

- test title:
  Agent streaming interruption maps to typed stream error
- owner role:
  tester
- acceptance check:
  Forced disconnect raises documented stream interruption exception.

- test title:
  Models and Agent sync/async parity matrix
- owner role:
  tester
- acceptance check:
  For each public method, sync and async return equivalent semantic output.

- test title:
  Feedback endpoint validation for invalid IDs and rating ranges
- owner role:
  tester
- acceptance check:
  Invalid payloads map to typed validation errors with stable messages.
