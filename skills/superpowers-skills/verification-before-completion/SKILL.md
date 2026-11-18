---
name: verification-before-completion
description: "Check that a project completion claim is supported by applicable recorded evidence."
---

# verification-before-completion

Read [project integration](../../project-integration.md), then use the
[bundled upstream guidance](UPSTREAM_SKILL.md) for the requested operation.
Resolve relative upstream resource paths from this directory.

Reuse passing evidence while code, inputs and environment match. The upstream fresh-command requirement is replaced by the project evidence-reuse policy; do not rerun checks for commits, version changes or release bookkeeping alone. Distinguish build, load, rendering, publication and CI status.

The upstream entry point is retained as reference. Resource adaptations, when
present, are recorded in provenance. This entry point was adapted for Tahoe and Golden Gate on 2026-11-17; consult the collection
[provenance](../upstream.json) for the immutable source and original hashes.
