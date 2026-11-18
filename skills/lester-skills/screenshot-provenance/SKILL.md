---
name: screenshot-provenance
description: Audit Tahoe or Golden Gate screenshot hashes, content-addressed filenames and edition provenance without recapturing or relabeling historical images.
---

# Screenshot provenance

Run the read-only audit:

```bash
python3 <skill-directory>/scripts/audit.py --repo <checkout> --edition <tahoe-or-golden-gate>
```

It verifies edition identity, manifest paths, content hashes and the 12-character
hash in each filename. It reports recorded source versions as historical
provenance, without changing them or comparing them to HEAD.

This audit does not prove application identity, focus, visual correctness,
licensing, truthful original capture metadata or user approval. Inspect the
actual affected frames and approval context separately. Check README/TESTING
links when publishing; preserve unaffected photographs with their original
records. Use Tahoe's existing staging/verification commands after the applicable
review gate; this skill never captures, stages or marks images approved.
