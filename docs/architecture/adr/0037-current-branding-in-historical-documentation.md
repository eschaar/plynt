# ADR-0037: Use Current Branding in Historical Documentation

**Date:** 2026-10-14
**Status:** Accepted

## Context

ADR-0036 established Plynt as the project, distribution, and import name. It
also directed contributors to preserve the previous name in historical ADRs,
change documents, release evidence, and changelog entries.

That policy left obsolete branding and package paths throughout the Markdown
archive. These references can confuse readers about the current project name,
installation commands, imports, and repository location. The user has decided
to align historical Markdown with current naming while retaining the original
name-conflict facts that ADR-0036 exists to record.

## Decision

We will update historical Markdown to use Plynt branding, `plynt` package and
import paths, and the renamed repository URL where applicable. Preserve
historical dates, decisions, release outcomes, commit IDs, and evidence.

ADR-0036 may retain the former name where needed to accurately document the
name conflict and the decision to rebrand. This decision refines its
historical-documentation policy without changing the rebrand itself.

## Alternatives Considered

### Preserve all historical wording

**Description:** Keep every historical document exactly as written.

**Pros:**

- Preserves the original wording of each historical record.
- Requires no documentation maintenance.

**Cons:**

- Leaves obsolete package names, imports, and repository links in Markdown
  readers may use as current guidance.

**Why rejected:** Consistent current naming is more useful than preserving
outdated identifiers in historical prose and examples.

### Rewrite historical records as if they were originally about Plynt

**Description:** Replace the former name everywhere, including the rebrand
decision record, without distinguishing historical context.

**Pros:**

- Removes the previous name from nearly all project documentation.

**Cons:**

- Obscures the reason for the rebrand and makes the decision record
  historically inaccurate.

**Why rejected:** Historical facts must remain understandable and accurate.

### Update old identifiers while preserving historical facts

**Description:** Use current branding, package paths, and repository links in
historical Markdown while preserving decisions, dates, and evidence.

**Pros:**

- Keeps examples and references consistent with the current project.
- Retains the historical sequence and meaning of prior decisions.

**Cons:**

- Historical documents no longer reproduce their original wording exactly.

**Why chosen:** Readers need current identifiers, while historical outcomes
and decision context remain unchanged.

## Rationale

Markdown documents serve both as historical records and as reference material.
Old package imports and repository links are misleading when copied into
current workflows. Updating identifiers improves consistency without changing
what was decided, when it was decided, or what evidence supported it.

The rebrand decision itself remains an exception where the former name is
needed to explain the conflict. This preserves the reason for the rename
without treating obsolete identifiers as current usage instructions.

## Consequences

### Positive

- Markdown examples and repository references use current Plynt identifiers.
- Historical decisions, dates, and release evidence remain available.
- The exception for the rebrand decision is explicit.

### Negative / Tradeoffs

- Historical documents no longer preserve every original identifier verbatim.

### Risks

- A replacement could alter text that is not a project identifier. Review the
  diff and search all Markdown for remaining old-name references.
- Historical paths may point to renamed source locations. Verify Markdown
  links and examples after updating them.

## Related ADRs

- ADR-0036: Rebrand the Project and Python Package to Plynt — this ADR refines
  only its historical-documentation policy.
