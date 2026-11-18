---
name: qt-qml-profiler
description: "Profile a demonstrated Tahoe Qt Quick 2D performance problem or inspect its existing trace."
---

# qt-qml-profiler

Read [project integration](../../project-integration.md), then use the
[bundled upstream guidance](UPSTREAM_SKILL.md) for the requested operation.
Resolve relative upstream resource paths from this directory.

Profile only the affected component in a disposable VM; retain matching before/after fixtures. The parser command is `python3 references/scripts/parse-qmlprofiler-trace.py <trace.qtd>` from this skill directory. It has no --help flag. It does not measure the full KWin compositor or Qt Quick 3D.

The upstream entry point is retained as reference. Resource adaptations, when
present, are recorded in provenance. This entry point was adapted for Tahoe and Golden Gate on 2026-11-17; consult the collection
[provenance](../upstream.json) for the immutable source and original hashes.
