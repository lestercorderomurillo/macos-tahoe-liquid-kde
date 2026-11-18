---
name: paired-release
description: Check Tahoe and Golden Gate version, immutable pin and archive consistency, then carry out an authorized paired delivery through the existing release workflows.
---

# Paired release

Read the current delivery rules in both `AGENTS.md` files and inspect the diff.
Documentation/agent-tooling delivery does not itself require a desktop version
bump or release. For an implementation release, run this read-only preflight:

```bash
python3 <skill-directory>/scripts/check_pair.py --tahoe <tahoe-checkout> --golden <golden-checkout> --archive <published-tahoe-archive>
```

It verifies local version/pin/tag consistency and the supplied archive digest.
Without `--archive` it explicitly reports the checksum gap. It does not query
GitHub, establish publication, inspect rendered behavior or grant approval.
Do not fetch/update checkouts as a side effect of checking a pair.

Before publication, reuse applicable selected qualification and inspect relevant
known CI failures. A visual candidate requires the user's approval of its actual
preview. Record the approval context; never infer it from capture metadata.
After that gate, follow the existing workflows in order: Tahoe publication,
its observed published immutable source and archive checksum, then Golden Gate.
Never use `gh release create` directly. Workflow submission is not publication.

Coordinate shared-checkout ownership before moving refs. Preserve unrelated
work, use fail-fast dependent commands, deliver the authorized commits to both
dev/main and leave both installation checkouts synchronized. Do not poll
unrelated CI or rerun qualification for release bookkeeping.
