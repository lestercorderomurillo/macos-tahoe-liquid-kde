---
name: qt-cpp-review
description: "Review affected Qt C++ code for ownership, threading and API errors in Tahoe."
---

# qt-cpp-review

Read [project integration](../../project-integration.md), then use the
[bundled upstream guidance](UPSTREAM_SKILL.md) for the requested operation.
Resolve relative upstream resource paths from this directory.

Start with changed functions and callers. Use the bundled linter on explicit files; it has no --help option. Run `python3 references/lint-scripts/qt_review_lint.py --summary <file.cpp>` from this skill directory. Expand findings against source; a linter result does not prove rendering. Use inline review unless agent delegation is authorized.

The upstream entry point is retained as reference. Resource adaptations, when
present, are recorded in provenance. This entry point was adapted for Tahoe and Golden Gate on 2026-11-17; consult the collection
[provenance](../upstream.json) for the immutable source and original hashes.
