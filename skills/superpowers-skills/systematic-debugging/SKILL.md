---
name: systematic-debugging
description: "Find the cause of an observed project failure using reproduction, evidence and bounded hypotheses."
---

# systematic-debugging

Read [project integration](../../project-integration.md), then use the
[bundled upstream guidance](UPSTREAM_SKILL.md) for the requested operation.
Resolve relative upstream resource paths from this directory.

Do not run the bundled npm-specific find-polluter.sh against this pytest project. Scale the investigation to the diff and failure. Reuse matching reproductions, logs and passing evidence. Do not mandate new tests, broad scans or workflow changes for every small fix.

The upstream entry point is retained as reference. Resource adaptations, when
present, are recorded in provenance. This entry point was adapted for Tahoe and Golden Gate on 2026-11-17; consult the collection
[provenance](../upstream.json) for the immutable source and original hashes.
