# ADR-0036: Rebrand the Project and Python Package to Plynt

**Date:** 2026-10-14
**Status:** Accepted

## Context

The project began as Plynth while its source repository was private. During
development, an unrelated project registered the `plynth` distribution name
on PyPI. The existing project had been using the name before that registration,
but private development did not reserve the name on PyPI.

The project has no external users or active deployments that depend on its
current import path. This makes a consistent rename less disruptive now than
after public adoption. Keeping the old distribution name would prevent normal
PyPI publication under `plynth`, while publishing as `plynth-client` would
leave the project, distribution, and Python import with different names.

The replacement name `Plynt` preserves the short pronunciation and distinctive
sound of Plynth while avoiding the registered PyPI distribution name. A
read-only PyPI lookup found no project named `plynt` on the decision date.
PyPI names are not reserved by lookup, so availability must be verified again
immediately before the first publication.

## Decision

We will rename the project to **Plynt** consistently across its repository,
distribution package, Python import package, documentation, and release
metadata. The distribution name and import package will both be `plynt`, and
the source package will move from `src/plynth/` to `src/plynt/`. The GitHub
repository will be renamed from `eschaar/plynth` to `eschaar/plynt`.

Historical ADRs, release notes, and changelog entries will retain the name
used when they were written. Current documentation and code will use Plynt.
PyPI publication remains subject to the existing release-please, CI, and
trusted-publishing gates; this ADR does not authorize bypassing those gates
or making the repository public.

## Alternatives Considered

### Keep Plynth and use a different distribution name

Keep `import plynth` and publish the project as `plynth-client` or another
qualified distribution name.

**Pros:**

- Avoids changing the existing import path and package directory.
- Keeps the current project name.

**Cons:**

- Uses different project, distribution, and import names.
- Requires users to remember the distinction in installation instructions.

**Why rejected:** The project has no external users, so preserving this
compatibility offers little benefit compared with adopting one consistent name.

### Request the `plynth` name from its current owner

Ask the unrelated PyPI project owner to transfer or relinquish the name.

**Pros:**

- Could retain the original spelling across the project and package.

**Cons:**

- Depends on another party and has no predictable outcome or timeline.
- Delays publication without improving the product itself.

**Why rejected:** The project should not depend on obtaining a name that is
currently registered to another project.

### Defer the name change

Continue private development under Plynth and decide on naming later.

**Pros:**

- Avoids immediate rename work.

**Cons:**

- Leaves the PyPI distribution name unresolved.
- Makes a later change more disruptive as documentation and adoption grow.

**Why rejected:** The name conflict is known before public adoption, which is
the lowest-cost point to resolve it.

## Rationale

Plynt preserves the recognizable sound of Plynth while giving the project a
distinct PyPI distribution name. Using `plynt` for the project, package
distribution, and Python imports keeps installation and usage straightforward.

The rename changes a public import path, but there are no known consumers who
need a compatibility window. The change will happen before the first public
release, so an old `plynth` import alias would add complexity without serving
an existing user base.

The name check is only a point-in-time lookup. The initial PyPI publication
must perform the authoritative name-availability check and use the existing
trusted publisher configuration.

## Consequences

### Positive

- The project has one consistent name across repository, distribution, and
  Python imports.
- The PyPI name conflict no longer blocks publication under the project name.
- The rename happens before external adoption, avoiding a user migration.

### Negative / Tradeoffs

- Source directories, imports, tests, examples, metadata, and current
  documentation must change together.
- Existing local environments and unpublished build artifacts using `plynth`
  will need to be recreated.
- The GitHub repository URL changes, even though GitHub normally redirects
  requests from the old repository URL after a rename.

### Risks

- `plynt` may be registered on PyPI before the first upload. Recheck
  availability immediately before publication and stop if it is unavailable.
- Missed old import paths or metadata can cause installed-package failures.
  Validate clean wheel and source-distribution installs, imports, and the
  complete CI matrix before publishing.
- External links or local clones may continue to use the old repository URL.
  Preserve the GitHub redirect and update project links after the rename.

## Related ADRs

- ADR-0027: Public API Compatibility and Deprecation Policy — the import
  rename occurs before public adoption and does not require a deprecation
  window.
- ADR-0031: Experimental Release Installation Contract — existing optional
  installation profiles remain in force.
- ADR-0035: Pre-1.0 Versioning Policy — the rename is a breaking change during
  0.x development and follows the existing minor-release policy.
