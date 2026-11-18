---
name: qt-cmake-project
description: "Edit existing Tahoe Qt 6 CMake targets, resources and plugin integration."
---

# qt-cmake-project

Read [project integration](../../project-integration.md), then use the
[bundled upstream guidance](UPSTREAM_SKILL.md) for the requested operation.
Resolve relative upstream resource paths from this directory.

Preserve KDE/ECM conventions and supported SDK minimums. Do not introduce qt_standard_project_setup or new targets solely to match an upstream template. Build only the affected targets/SDK branches required by the actual diff.

The upstream entry point is retained as reference. Resource adaptations, when
present, are recorded in provenance. This entry point was adapted for Tahoe and Golden Gate on 2026-11-17; consult the collection
[provenance](../upstream.json) for the immutable source and original hashes.
