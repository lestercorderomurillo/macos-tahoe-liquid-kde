---
name: github-actions-templates
description: "Maintain affected GitHub Actions workflows while preserving the editions' coverage and release ordering."
---

# github-actions-templates

Read [project integration](../../project-integration.md), then use the
[bundled upstream guidance](UPSTREAM_SKILL.md) for the requested operation.
Resolve relative upstream resource paths from this directory.

Use existing workflows as the starting point. Preserve distro legs, disjoint shards and compiler-content checking. Do not copy example action versions or introduce deployment approvals without inspecting the current project policy.

The upstream entry point is retained as reference. Resource adaptations, when
present, are recorded in provenance. This entry point was adapted for Tahoe and Golden Gate on 2026-11-17; consult the collection
[provenance](../upstream.json) for the immutable source and original hashes.
