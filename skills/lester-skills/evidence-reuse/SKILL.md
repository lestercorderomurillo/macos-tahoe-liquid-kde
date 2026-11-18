---
name: evidence-reuse
description: Determine whether recorded Tahoe and Golden Gate validation evidence still applies, and identify only the checks invalidated by changed inputs or environment.
---

# Evidence reuse

Read the current diff and `release-evidence.json`. For each claim compare the
tested implementation/content, inputs, environment, backend/SDK and command
with the affected change. A matching commit alone is insufficient; a changed
documentation commit alone does not invalidate unchanged runtime behavior.
Do not invent missing environment details or infer a pass from absent results.

Tahoe already has a read-only verifier. Run it when release-record integrity is
the question, with no ref fetching:

```bash
python3 <tahoe-checkout>/.github/scripts/release_evidence.py --repo <checkout>
```

It verifies the existing whole-source fingerprint, recorded checks and capture
hashes. It does not prove the original commands ran, establish user approval,
or model per-check inputs/environments. Its fingerprint includes tracked
executable tooling, so agent-tool edits can stale the record even when desktop
evidence remains applicable. Report those facts separately; never rewrite a
recorded pass or its source merely to satisfy the verifier.

Summarize evidence as reusable, invalidated, or missing, with the reason and
affected claim. Keep original capture provenance. Rerun only invalidated checks
required for the task; do not rerun merely for version, commit or publication
bookkeeping. Keep pending CI and publication states distinct from local checks.
