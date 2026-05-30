# VM smoke tests

Real QEMU/KVM VM smoke tests. If a distro's script exits 0 here, the
installer is verified end-to-end on that distro at the level of:

1. Real distro repo provides every dep
2. `sudo ./install --preflight` passes against a real Plasma session
3. `sudo ./install` runs to completion against a real KWin + plasmashell
4. The resulting desktop produces a screenshot (visual eyeball check)
5. `journalctl --user -p err` after install is captured for review
6. `sudo ./uninstall` runs to completion

What this does NOT cover: visual correctness (GPU rendering), the
06:00/18:00 wall-clock theme switch, multi-monitor layouts.

## Run locally

```bash
bash tests/vm-smoke/run-fedora.sh
bash tests/vm-smoke/run-arch.sh
bash tests/vm-smoke/run-cachyos.sh
bash tests/vm-smoke/run-opensuse.sh
bash tests/vm-smoke/run-all.sh
```

`run-fedora.sh`, `run-arch.sh`, `run-cachyos.sh`, and
`run-opensuse.sh` are real cloud-image flows. First run downloads the
base `qcow2` image into `tests/vm-smoke/.work/images/`, then creates a
fresh overlay under `tests/vm-smoke/.work/<distro>/` for each run.
Cloud-init installs KDE inside the guest, reboots into an autologin
Plasma session, and runs the smoke script from there. The CachyOS path
starts from the official Arch cloud image, then switches the guest onto
the official CachyOS repos before the KDE smoke run.

Output per distro: `tests/vm-smoke/.work/<distro>/output/` with
`smoke.log`, `desktop.png`, `provision.log`, `cloud-init-output.log`,
and the guest `console.log`.

## Host requirements

- `qemu-system-x86_64` and `qemu-img` with KVM enabled
- `genisoimage` for the cloud-init drive
- `sshpass`, `curl`
- ~10 GB free disk for the base image + throwaway overlay

Auto-installed if missing on Fedora/Arch hosts (the workflow does
this); on local dev install them yourself first.

## Distro status

Real VM smoke implemented now:

- `run-fedora.sh` — Fedora 44 Cloud Base
- `run-arch.sh` — official Arch cloud image
- `run-cachyos.sh` — Arch cloud image switched to official CachyOS repos
- `run-opensuse.sh` — openSUSE Tumbleweed Minimal-VM Cloud image

Explicit `SKIP` wrappers exist for the rest of the support matrix so
`run-all.sh` makes the current gaps obvious instead of silently
ignoring them:

- `run-manjaro.sh`
- `run-endeavouros.sh`
- `run-garuda.sh`
- `run-gentoo.sh`
- `run-nobara.sh`
- `run-bazzite.sh`

Those scripts all exit `2` with a reason:

- Arch-family derivatives currently publish installer-first paths, not
  official unattended cloud images.
- Gentoo has an official cloud-init `qcow2`, but a first-boot Plasma
  install is still too heavy without a prebuilt Plasma/binpkg path.
- Nobara currently publishes installer ISOs rather than a cloud image.
- Bazzite is immutable, and the current installer still assumes a
  mutable `/usr/lib64/qt6`.

## CI

This harness is local-only for now; no VM smoke workflow is checked in
yet.
