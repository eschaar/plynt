# SF-0009: Salesforce Identity Access Primitives

- Status: Accepted
- Date: 2026-05-11

## Context

The Salesforce connector already provides generic SObject, query, bulk,
composite, search, and utility services. Consumers repeatedly needed a small
set of identity-related operations that are low-level and reusable across
projects, but these operations were implemented ad hoc in each consuming
application.

At the same time, identity workflows are sensitive to business policy and org
conventions. The connector must avoid role-policy mapping, provisioning
workflows, and password-management behavior that is not universally applicable.

The team needed a decision on whether to add a narrow identity surface in core
or keep all identity operations outside the connector.

## Decision

Add a policy-neutral identity service pair:

- SalesforceIdentityAccessService
- AsyncSalesforceIdentityAccessService

Expose them through facade entrypoints:

- facade.identity_access()
- async_facade.identity_access()

Ship only generic primitives:

- get_user(...), list_users(...)
- permission set assignment create/delete
- permission set group assignment create/delete
- user active-flag update

Keep expansion deferred and pattern-driven using documented activation
criteria in the Salesforce roadmap.

## Alternatives Considered

### Option A: Keep identity fully out of connector

Pros:

- Zero new connector surface area.
- No risk of policy coupling.

Cons:

- Duplicated low-level code across consumers.
- Inconsistent error handling and request construction.

Rejected because repeated generic usage justified a small shared primitive
layer.

### Option B: Add full user administration feature set

Pros:

- Broad out-of-the-box capabilities.

Cons:

- High risk of org-specific policy coupling.
- Hard to keep behavior generic across tenants.

Rejected because it violates connector boundary rules.

### Option C: Add narrow identity access primitives (chosen)

Pros:

- Removes duplicated low-level integration code.
- Keeps scope generic and framework-agnostic.
- Preserves clear boundary between connector and business policy.

Cons:

- Adds one more service surface to maintain.
- Requires explicit governance for future expansion.

Chosen because it balances reuse and architectural discipline.

## Consequences

Positive:

- Consumers get a stable, typed identity access surface for common operations.
- Sync/async parity is preserved under the same facade model.

Negative / Tradeoffs:

- Identity-related requests remain low-level; richer workflows stay external.

Risks:

- Risk of scope creep into policy behavior.
- Mitigation: keep deferred-expansion criteria explicit in roadmap and enforce
  ADR review for broader identity features.

## Related ADRs

- SF-0002: Salesforce facade ergonomics — identity service is exposed through
  the same facade pattern.
- SF-0003: Salesforce Query Service Design — identity listing uses the same
  generic query-building approach.
- SF-0001: Salesforce Error Mapping — identity calls use existing typed error
  behavior.
