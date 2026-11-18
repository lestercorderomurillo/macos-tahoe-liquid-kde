---
name: bash-defensive-patterns
description: "Fix quoting, exit handling and temporary-file lifecycle in project shell entry points."
---

# bash-defensive-patterns

Read [project integration](../../project-integration.md), then use the
[bundled upstream guidance](UPSTREAM_SKILL.md) for the requested operation.
Resolve relative upstream resource paths from this directory.

Check the actual shebang and callers. Do not add Bash syntax to POSIX sh scripts or enable set -e/-u globally without checking their error and optional-variable contracts. Syntax-check with the declared shell; run ShellCheck only if available. Never run the live installer to test a wrapper.

The upstream entry point is retained as reference. Resource adaptations, when
present, are recorded in provenance. This entry point was adapted for Tahoe and Golden Gate on 2026-11-17; consult the collection
[provenance](../upstream.json) for the immutable source and original hashes.
