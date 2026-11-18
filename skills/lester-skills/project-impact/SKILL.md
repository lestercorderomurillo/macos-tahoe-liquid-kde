---
name: project-impact
description: Map a Tahoe or Golden Gate change to callers, suggested tests and unresolved dependency coverage before reading broadly or choosing checks.
---

# Project impact

Run this skill's read-only helper from any directory:

```bash
python3 <skill-directory>/scripts/inspect_impact.py --repo <checkout>
```

Pass repository-relative paths after the options to inspect a proposed change.
Without paths it includes the diff against HEAD and untracked files. Use
`--graph <golden-checkout>/tools/repo_graph.py` when the checkouts are not siblings.
The helper delegates to the existing offline graph; it does not maintain a
second index or change CI selection.

Read the affected functions and caller edges first. Treat `unindexed` paths
and no suggested tests as coverage questions. Manually trace dynamic imports,
edition staging, generated assets and C++/SDK/QML runtime connections. The
graph is navigation evidence, not proof that omitted behavior is unaffected.

Then use [focused-validation](../focused-validation/SKILL.md) to select checks.
