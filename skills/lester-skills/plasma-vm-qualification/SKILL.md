---
name: plasma-vm-qualification
description: Qualify an affected Plasma component in a disposable VM with explicit source, edition, backend and visible-behavior evidence, without touching the host desktop.
---

# Plasma VM qualification

Use one prepared KDE neon desktop with the SDK and build cache for quick
captures and README previews of both editions. Install the current local
candidate in a disposable overlay and use the edition's defaults. Select
additional environments only for specific release qualification claims.
Keep provisioning separate from timed qualification and report measured
timings and incomplete work. If an attempt or retry is
expected to take 20 minutes or more, reassess scope and tell the user the
estimate and reason before starting it.
If the estimate is exceeded or attempts total 20 minutes, stop that approach
unless the user explicitly authorizes a longer run. Save usable evidence
and report actual time and storage. Check the total allocated disk budget
before provisioning multiple bases.

First apply [focused validation](../focused-validation/SKILL.md) and the
environment selection rules in `AGENTS.md`. Use this workflow for claims that
need a desktop VM or for required desktop captures. Check the inventory for a
prepared base for the relevant distro and backend before provisioning.

Before starting a guest, identify the changed component, visible difference,
required scenarios/frames and exact SDK/backend coverage from `AGENTS.md`.
Check the scratch filesystem with `df -h` before booting. For Tahoe's `./vm`,
set `VM_RUN_DIR` to a task-owned directory on the secondary project disk and
point `VM_CACHE_DIR` at the reusable image cache there. Verify the mount with
`findmnt -T` before creating files. On this workstation `/var/tmp` shares
the root device. Budget for guest writes across all concurrent guests, and
run them sequentially when space is tight.

Inspect the existing VM inventory and harness options in Tahoe:

```bash
cd <tahoe-checkout>
python3 tests/vm/qualify.py --help
```

Choose release qualification checks from the affected behavior and existing
coverage, including installer lifecycle, applications and distro-specific
probes where applicable. For a narrow rendering fix, run a focused capture
from the prepared guest. Read the
affected guest helper and `tests/vm/README.md` for connection details; verify the
target is an isolated QEMU guest before input, settings or installation.

Record staged/installed source fingerprints, edition, system/SDK versions and
session type. Check build, module load and visible behavior separately. For
appearance transitions keep affected Qt/Kvantum/GTK apps open and verify actual
transitions, continuity and latest-selection behavior required by the diff.

Documentation file-manager previews use Tahoe's exact entry point:

```bash
./release-screenshots file-previews --ref <source-ref> --vm-image <pinned-base.qcow2> --output <temporary-output>
```

Use it only when those four installer frames are requested/affected. System
menu capture offers `capture --only-system-menu`; it is not a generic
single-component flag. If no focused option exists, inspect the helper and keep
the preview separate instead of guessing flags or rebuilding the gallery.

For a targeted recapture, inspect the exact approved frame and its provenance
first. Reuse its capture method, installed configuration, fonts, material,
wallpaper, scale and crop. Change only what the user requested. Compare the
actual frames at the same scale before staging them. If the original setup
cannot be reproduced, keep the existing approved image and report the gap.

Review frame identity/focus and retain source hashes. User approval of the
actual preview remains separate. On success, failure or interruption, account for each task-created disk.
Save the requested frames, logs, source fingerprints and unique recovery data
outside the disposable run directory. After the last required scenario for
each guest, shut down that task's guest, confirm its disk is closed and check
that no retained overlay depends on it. Remove its disposable disk before
starting the next independent run. Preserve active work, shared bases and
disks needed for a specific pending reproduction. Record the path and reason
for any retained disk so the next agent can finish cleanup. Verify allocated
usage with `du -sh` and available space with `df -h` after cleanup.
