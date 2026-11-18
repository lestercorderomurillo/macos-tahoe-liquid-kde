---
name: ci-speedup
description: "Audit measured GitHub Actions runtime and runner-minute bottlenecks for Tahoe and Golden Gate."
---

# ci-speedup

Read [project integration](../../project-integration.md).

Use existing completed runs and stated cache conditions. Preserve coverage and safe compiler caches; qualify proposed savings against measured before/after evidence. Audit scripts are read-only unless their inspected CLI proves otherwise. Do not launch duplicate matrices or change branch protection.

Collect an existing run with `gh run view <run-id> --repo <owner/repo> --json jobs,headSha,status,conclusion,url`. Save the JSON outside tracked sources and run `python3 scripts/summarize_run.py <run.json>` from this skill directory. The report ranks completed jobs by elapsed time, keeps incomplete jobs separate and never estimates savings or asserts coverage equivalence. Inspect the measured bottleneck and its workflow before proposing changes. Compare runs with matching fixtures and explicit cache conditions.

This project workflow was written on 2026-11-17. The [upstream reference](https://github.com/starslingdev/skills/tree/8f17f5bcf43d5ec82433186658962a17c90f7c6a/skills/ci-speedup) is optional; its package and scripts are not bundled. See [provenance](../upstream.json).
