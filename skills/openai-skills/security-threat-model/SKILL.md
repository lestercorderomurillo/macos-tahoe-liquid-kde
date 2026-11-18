---
name: security-threat-model
description: "Model explicitly requested downloader, archive, installer and release trust boundaries in these repositories."
---

# security-threat-model

Read [project integration](../../project-integration.md), then use the
[bundled upstream guidance](UPSTREAM_SKILL.md) for the requested operation.
Resolve relative upstream resource paths from this directory.

Separate build/release tooling from installed desktop behavior. Tie each threat to actual assets and entry points. Use existing context before asking questions, and retain material assumptions and coverage limits in the result.

The upstream entry point is retained as reference. Resource adaptations, when
present, are recorded in provenance. This entry point was adapted for Tahoe and Golden Gate on 2026-11-17; consult the collection
[provenance](../upstream.json) for the immutable source and original hashes.
