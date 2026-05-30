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
- `run-manjaro.sh` — Arch cloud image switched to Manjaro stable repos
- `run-endeavouros.sh` — Arch cloud image + EndeavourOS repo overlay
- `run-garuda.sh` — Arch cloud image + Chaotic-AUR + Garuda repo overlay
- `run-nobara.sh` — Fedora cloud image + Nobara repo overlay (Fyra Labs)

Still a SKIP wrapper:

- `run-gentoo.sh` — official Gentoo systemd-cloudinit qcow2 +
  `--getbinpkg` against the canonical binhost is feasible but mixes a
  binhost-built USE-flag set with the cloud profile's flags, so some
  packages fall back to source-compile and the smoke can take hours
  rather than minutes. Tracked separately.

Immutable rpm-ostree distros (Bazzite, Silverblue, Kinoite) are out of
scope: the installer writes into `/usr/lib*` and `/usr/share`, which
are read-only on those systems and need either an rpm-ostree layering
path or a Flatpak-extension wrapper that this project does not
maintain.

## CI

This harness is local-only for now; no VM smoke workflow is checked in
yet.
