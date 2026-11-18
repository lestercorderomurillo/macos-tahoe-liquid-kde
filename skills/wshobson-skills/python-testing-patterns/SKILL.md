---
name: python-testing-patterns
description: "Write or review focused Python behavior tests for the Tahoe installer and Golden Gate wrapper."
---

# python-testing-patterns

Read [project integration](../../project-integration.md), then use the
[bundled upstream guidance](UPSTREAM_SKILL.md) for the requested operation.
Resolve relative upstream resource paths from this directory.

Use existing fixtures and declared dependencies. Prefer executable scenarios covering multiple related claims; preserve independent failure cases. Run `python3 -m pytest <selected-tests>` in the target repository with its declared environment; do not run ./test merely to discover commands because it can install packages.

The upstream entry point is retained as reference. Resource adaptations, when
present, are recorded in provenance. This entry point was adapted for Tahoe and Golden Gate on 2026-11-17; consult the collection
[provenance](../upstream.json) for the immutable source and original hashes.
