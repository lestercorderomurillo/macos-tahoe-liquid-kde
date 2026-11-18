---
name: qt-qml-test-run
description: "Run selected existing Qt Quick tests and interpret their reports for Tahoe."
---

# qt-qml-test-run

Read [project integration](../../project-integration.md), then use the
[bundled upstream guidance](UPSTREAM_SKILL.md) for the requested operation.
Resolve relative upstream resource paths from this directory.

Use existing project test integration; --wire-up is optional, not an installation step. The bundled JUnit parser exits zero when parsing succeeds even if tests failed: inspect failed, skipped and total counts together with the actual test-runner exit code. Run tests requiring desktop services only in the disposable environment.

The upstream entry point is retained as reference. Resource adaptations, when
present, are recorded in provenance. This entry point was adapted for Tahoe and Golden Gate on 2026-11-17; consult the collection
[provenance](../upstream.json) for the immutable source and original hashes.
