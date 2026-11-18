---
name: plasma-vm-qualification
description: Qualify an affected Plasma component in a disposable VM with explicit source, edition, backend and visible-behavior evidence, without touching the host desktop.
---

# Plasma VM qualification

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

That harness exercises install, switching, reboot and uninstall; use the full
transaction only when lifecycle coverage is affected. A narrow rendering fix
needs a focused guest scenario, not a full gallery or lifecycle run. Read the
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
