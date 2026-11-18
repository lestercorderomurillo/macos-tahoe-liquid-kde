---
name: plasma-vm-qualification
description: Qualify an affected Plasma component in a disposable VM with explicit source, edition, backend and visible-behavior evidence, without touching the host desktop.
---

# Plasma VM qualification

Before starting a guest, identify the changed component, visible difference,
required scenarios/frames and exact SDK/backend coverage from `AGENTS.md`.
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
actual preview remains separate. Preserve compact evidence/recovery data, then
remove only task-created disposable resources after qualification is complete.
