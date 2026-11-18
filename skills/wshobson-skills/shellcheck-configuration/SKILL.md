---
name: shellcheck-configuration
description: "Use ShellCheck on affected shell scripts and interpret portability findings in these repositories."
---

# shellcheck-configuration

Read [project integration](../../project-integration.md), then use the
[bundled upstream guidance](UPSTREAM_SKILL.md) for the requested operation.
Resolve relative upstream resource paths from this directory.

Determine the declared shell first. Run `shellcheck <changed-script>` only when installed; a missing executable is a dependency gap, not a pass. Keep suppressions local and justified. Use the matching shell syntax check without executing installer entry points.

The upstream entry point is retained as reference. Resource adaptations, when
present, are recorded in provenance. This entry point was adapted for Tahoe and Golden Gate on 2026-11-17; consult the collection
[provenance](../upstream.json) for the immutable source and original hashes.
