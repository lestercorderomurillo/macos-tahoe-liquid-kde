# Development skills

These 25 task-specific skills supplement the existing communication skill.
Canonical collections live under `skills/`; `.agents/skills/` contains relative
symlinks for normal Codex discovery. Load only the skill relevant to the task.
Read [project integration](project-integration.md) when using external guidance.
No global skills, desktop settings, installer defaults or release pins are changed.

## Project helpers

| Skill | Operation |
| --- | --- |
| [project-impact](lester-skills/project-impact/SKILL.md) | Read-only diff, caller and suggested-test report using the existing offline graph. |
| [focused-validation](lester-skills/focused-validation/SKILL.md) | Connect affected claims to sufficient selected checks and explicit coverage gaps. |
| [evidence-reuse](lester-skills/evidence-reuse/SKILL.md) | Distinguish reusable evidence, invalidated checks and whole-record integrity. |
| [paired-release](lester-skills/paired-release/SKILL.md) | Check local versions, immutable pin, release tag and an optional supplied archive. |
| [plasma-vm-qualification](lester-skills/plasma-vm-qualification/SKILL.md) | Scope isolated guest qualification and route to existing capture/lifecycle tools. |
| [screenshot-provenance](lester-skills/screenshot-provenance/SKILL.md) | Audit edition, path containment, image hashes and content-addressed names. |

## External guidance and adaptations

Original entry points are retained as `UPSTREAM_SKILL.md`. Collection provenance
files record immutable upstream commits, original SHA-256 values and downstream
resource changes. Licenses are retained alongside the collection or skill.
The CI timing workflow is independently written and links its upstream reference;
the large upstream audit package is not bundled.

| Skill | Collection | Use |
| --- | --- | --- |
| [qt-cmake-project](qt-skills/qt-cmake-project/SKILL.md) | [qt-skills](qt-skills/upstream.json) | Edit existing Tahoe Qt 6 CMake targets, resources and plugin integration. |
| [qt-cpp-review](qt-skills/qt-cpp-review/SKILL.md) | [qt-skills](qt-skills/upstream.json) | Review affected Qt C++ code for ownership, threading and API errors in Tahoe. |
| [qt-qml](qt-skills/qt-qml/SKILL.md) | [qt-skills](qt-skills/upstream.json) | Write and debug QML bindings, delegates and state changes in Tahoe and Golden Gate. |
| [qt-qml-profiler](qt-skills/qt-qml-profiler/SKILL.md) | [qt-skills](qt-skills/upstream.json) | Profile a demonstrated Tahoe Qt Quick 2D performance problem or inspect its existing trace. |
| [qt-qml-test](qt-skills/qt-qml-test/SKILL.md) | [qt-skills](qt-skills/upstream.json) | Write missing Qt Quick behavior regressions for Tahoe QML components. |
| [qt-qml-test-run](qt-skills/qt-qml-test-run/SKILL.md) | [qt-skills](qt-skills/upstream.json) | Run selected existing Qt Quick tests and interpret their reports for Tahoe. |
| [bash-defensive-patterns](wshobson-skills/bash-defensive-patterns/SKILL.md) | [wshobson-skills](wshobson-skills/upstream.json) | Fix quoting, exit handling and temporary-file lifecycle in project shell entry points. |
| [changelog-automation](wshobson-skills/changelog-automation/SKILL.md) | [wshobson-skills](wshobson-skills/upstream.json) | Draft requested release notes from the actual delivered commits in both editions. |
| [github-actions-templates](wshobson-skills/github-actions-templates/SKILL.md) | [wshobson-skills](wshobson-skills/upstream.json) | Maintain affected GitHub Actions workflows while preserving the editions' coverage and release ordering. |
| [python-performance-optimization](wshobson-skills/python-performance-optimization/SKILL.md) | [wshobson-skills](wshobson-skills/upstream.json) | Measure and reduce a demonstrated Python installer or tooling bottleneck in these editions. |
| [python-testing-patterns](wshobson-skills/python-testing-patterns/SKILL.md) | [wshobson-skills](wshobson-skills/upstream.json) | Write or review focused Python behavior tests for the Tahoe installer and Golden Gate wrapper. |
| [shellcheck-configuration](wshobson-skills/shellcheck-configuration/SKILL.md) | [wshobson-skills](wshobson-skills/upstream.json) | Use ShellCheck on affected shell scripts and interpret portability findings in these repositories. |
| [gh-address-comments](openai-skills/gh-address-comments/SKILL.md) | [openai-skills](openai-skills/upstream.json) | Resolve review threads already included in an authorized project PR task. |
| [gh-fix-ci](openai-skills/gh-fix-ci/SKILL.md) | [openai-skills](openai-skills/upstream.json) | Investigate and repair relevant failed GitHub Actions checks in the paired repositories. |
| [security-best-practices](openai-skills/security-best-practices/SKILL.md) | [openai-skills](openai-skills/upstream.json) | Perform an explicitly requested security review of supported project Python code. |
| [security-threat-model](openai-skills/security-threat-model/SKILL.md) | [openai-skills](openai-skills/upstream.json) | Model explicitly requested downloader, archive, installer and release trust boundaries in these repositories. |
| [systematic-debugging](superpowers-skills/systematic-debugging/SKILL.md) | [superpowers-skills](superpowers-skills/upstream.json) | Find the cause of an observed project failure using reproduction, evidence and bounded hypotheses. |
| [verification-before-completion](superpowers-skills/verification-before-completion/SKILL.md) | [superpowers-skills](superpowers-skills/upstream.json) | Check that a project completion claim is supported by applicable recorded evidence. |
| [ci-speedup](starsling-skills/ci-speedup/SKILL.md) | [starsling-skills](starsling-skills/upstream.json) | Audit measured GitHub Actions runtime and runner-minute bottlenecks for Tahoe and Golden Gate. |

## Qualification limits

[Review evidence](review.md) records the batch checks. Format validation and
parser fixtures do not prove every upstream recommendation or a Qt desktop
runtime works in every SDK. Rendering/profiling still needs the relevant VM
and declared dependencies. The release preflight does not establish publication
or visual approval, and the screenshot audit does not inspect pixels or focus.
