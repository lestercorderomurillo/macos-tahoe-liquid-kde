---
name: focused-validation
description: Select the smallest sufficient executable checks for an actual Tahoe or Golden Gate diff, including edition staging and native backend coverage gaps.
---

# Focused validation

Obtain [project-impact](../project-impact/SKILL.md)'s report, inspect the changed
behavior and direct callers, then consult the active `AGENTS.md` testing-scope
table. Briefly connect each affected claim to a check before execution.

For ordinary Python regressions, use the declared environment and run:

```bash
cd <affected-checkout>
python3 -m pytest <selected-test-files-or-node-ids>
```

Inspect selected fixtures and the CI environment before adding dependencies.
`./test` is not a harmless discovery command: Tahoe's wrapper can install
pytest using the system package manager. Never run an installer on the host.

Wrapper/source-selection changes need wrapper regressions. Shared changes
also need affected Tahoe regressions and prepared Golden Gate checks when
staging changes execution. Native changes need the applicable SDK and session
coverage from `AGENTS.md`; separate build, load and visible behavior evidence.
Use existing shader/pixel checks when coordinates or shader inputs change.

Prose-only changes need consistency/link review and `git diff --check`.
Executable skill helpers need their own focused behavior checks, not desktop
qualification. Preserve independent failure cases and existing CI coverage.
Reuse matching passing checks; expand only for a failure or concrete dependency.
The graph's suggestions never establish an automatic exclusion from CI.
