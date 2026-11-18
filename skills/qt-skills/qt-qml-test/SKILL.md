---
name: qt-qml-test
description: "Write missing Qt Quick behavior regressions for Tahoe QML components."
---

# qt-qml-test

Read [project integration](../../project-integration.md), then use the
[bundled upstream guidance](UPSTREAM_SKILL.md) for the requested operation.
Resolve relative upstream resource paths from this directory.

Extend existing executable scenarios before generating a test per source file. Test observable state and signals; avoid source-text assertions and redundant coverage. QML tests do not replace native/session rendering qualification.

The upstream entry point is retained as reference. Resource adaptations, when
present, are recorded in provenance. This entry point was adapted for Tahoe and Golden Gate on 2026-11-17; consult the collection
[provenance](../upstream.json) for the immutable source and original hashes.
