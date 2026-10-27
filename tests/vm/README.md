# Real desktop VM qualification

`./vm list` lists the 12 distribution targets. These are graphical QEMU/KVM
guests with real Plasma sessions. Container builds do not qualify a desktop.
Debian uses testing (Forky); stock Debian 13 is below the Plasma 6.6 minimum.
Kubuntu pins 26.04.1 LTS for the Plasma 6.6 launcher regression reported in
[Golden Gate issue #2](https://github.com/lestercorderomurillo/macos-golden-gate-liquid-kde/issues/2).
This new test target is pending full live qualification; adding it is not a
compatibility badge.

## Start a guest

Install QEMU with KVM, `qemu-img`, `genisoimage`, `curl`, Python 3 and OVMF on
the host. The qualification controller additionally needs `sshpass` and Pillow.
Run from the repository root:

```sh
./vm debian
```

Arch, Fedora, openSUSE, KDE neon and Debian provision a desktop from their cloud
recipes. Wait for provisioning and Plasma login to finish. The guest account is
`tester`, password `tester`, with passwordless sudo. Debian's image download is
checked against the official SHA-512 manifest.

CachyOS, Manjaro, EndeavourOS, Garuda, Nobara, Artix and Kubuntu boot their own official
installation media, pinned by URL and checksum in `.vm/images.json`. Complete
the native installer onto the disposable 60 GB guest disk, select KDE Plasma,
and create `tester`. Artix uses its OpenRC Plasma edition. These guests are not
Arch or Fedora images with a changed distribution name.

After booting the installed OS, open its terminal and prepare it:

```sh
sudo mkdir -p /repo
sudo mount -t 9p -o trans=virtio,ro repo /repo
sudo cp /repo/tests/vm/prepare_guest.sh /tmp/prepare-guest.sh
sudo bash /tmp/prepare-guest.sh
sudo reboot
```

The helper checks that it is inside an installed QEMU guest, upgrades the OS,
installs QA tools, enables SSH and automatic Plasma login, and creates a writable
repository copy. It saves any existing GTK 4 profile as `~/vm-original-gtk-4.0`
so custom distro CSS cannot mask the theme during rendering checks. The theme
installer itself preserves custom CSS. Keep that backup when inspecting native
profile behavior.

Kubuntu preparation keeps the installed 26.04 LTS repositories and Plasma
stack, installs the launcher test tools, and enables Ubuntu's `ssh` service.
It does not add a PPA or upgrade to another Ubuntu release.

For remote control of the live installer, `tests/vm/live_access.sh` provides
optional loopback SSH setup inside the live QEMU guest. It refuses installed
systems. This is only a setup aid; qualification requires an installed desktop.

The host repository is read-only in every guest. Installer writes and compiled
components stay on the guest disk. SSH forwards bind to `127.0.0.1` only:

| Target | Port | Source | Start VM |
| --- | --- | --- | --- |
| <a id="arch"></a>Arch | 2221 | Arch cloud image | `./vm arch` |
| <a id="cachyos"></a>CachyOS | 2222 | Official desktop ISO | `./vm cachyos` |
| <a id="manjaro"></a>Manjaro | 2223 | Official KDE ISO | `./vm manjaro` |
| <a id="endeavouros"></a>EndeavourOS | 2224 | Official ISO, KDE selection | `./vm endeavouros` |
| <a id="garuda"></a>Garuda | 2225 | Official Dr460nized ISO | `./vm garuda` |
| <a id="fedora"></a>Fedora | 2226 | Fedora cloud image + KDE | `./vm fedora` |
| <a id="nobara"></a>Nobara | 2227 | Official KDE ISO | `./vm nobara` |
| <a id="opensuse"></a>openSUSE | 2228 | Tumbleweed cloud image + KDE | `./vm opensuse` |
| <a id="neon"></a>KDE neon | 2231 | Ubuntu cloud image + signed neon repositories | `./vm neon` |
| <a id="debian"></a>Debian | 2232 | Official Forky cloud image + KDE | `./vm debian` |
| <a id="artix"></a>Artix | 2233 | Official Plasma OpenRC ISO | `./vm artix` |
| <a id="kubuntu"></a>Kubuntu 26.04.1 LTS | 2234 | Official desktop ISO (SHA-256 pinned) | `./vm kubuntu` |

`VM_CACHE_DIR` and `VM_RUN_DIR` relocate images and disks. `VM_CPUS` and
`VM_MEM_MIB` control resources. Default graphics use accelerated VirtIO/virgl;
`VM_GPU=virtio-vga VM_GL=off ./vm <target>` selects software graphics when an
ISO installer needs it. `VM_UEFI_CODE` and `VM_UEFI_VARS` select OVMF firmware
when automatic discovery does not find the host's installation.

`./vm <target> --clean` deletes that target's disposable disk and prepares a
fresh one. Shut the target down before using it. `./vm all` opens all targets;
it does not automate the native ISO installers or assert that any test passed.

## Run the lifecycle test

On the host, after guest preparation:

```sh
python tests/vm/qualify.py debian --output build/vm-results/debian --poweroff
```

Replace `debian` with any listed target. `VM_PASSWORD` overrides the test
password. Use a separate output directory for each run. The controller checks
QEMU identity, distribution ID and the guest account before making changes.
It then:

1. Copies the mounted repository into the writable guest workspace.
2. Records the baseline Plasma desktop and SDK versions.
3. Creates a dedicated Firefox profile and local interaction fixture, sets
   3840×2160 output at 2× scale, and runs the full dark installation, including
   native compilation.
4. Checks actual panel widgets, Dock autohide, Qt/GTK appearance, loaded Acrylic
   Glass and its running build identity; captures the desktop.
5. Opens Firefox, Files (Nautilus), Dolphin and Konsole. Types into the local
   browser page, clicks its button and verifies the result and browser color
   preference. Checks the installed Firefox CSS and actual Files pixels.
6. Switches light and back to dark, checking that the applications, Plasma and
   KWin did not restart. Saves a 4K capture in each mode.
7. Reboots, requires a different boot ID, and repeats the desktop and app checks.
8. Runs the full uninstall and checks the success record, removed widgets and
   unloaded effect; captures the restored desktop.

Every command log, desktop JSON and PNG is saved with `result.json`. Failed
commands, appearance checks or blank captures fail the run. Inspect every
capture before claiming visual qualification. A successful QEMU cycle verifies
that guest configuration; it does not establish physical GPU compatibility.
Release publication screenshots use the separate `./release-screenshots` gate.

For Kubuntu, run `python tests/vm/qualify.py kubuntu --output build/vm-results/kubuntu`.
The identity guard requires Ubuntu 26.04 with the installed `kubuntu-desktop`
package. After installation and again after reboot, it also runs the native
launcher probe in isolated Xvfb sessions against the guest's Plasma SDK. All
eight combinations of edition, appearance and launcher preset must pass with
no skips. The probe exercises popup creation, search, preset changes, focus
transfers and outside-focus dismissal. Logs and JUnit results are retained.

---

# Plymouth render harness

A rendered-pixel integration check of the MacTahoe Plymouth theme without
rebooting.

```bash
sudo ./test --vm
```

Two pixel-validated PNG screenshots land in `tests/vm/output/`:

- `plymouth-boot-splash.png` — boot mode (logo + progress bar)
- `plymouth-shutdown-splash.png` — shutdown mode (logo only)

Open with `xdg-open tests/vm/output/plymouth-boot-splash.png`.

## Why `sudo`

`plymouthd` refuses to run unless `uid == 0`. The script checks
`$EUID` upfront and tells you to re-run with `sudo` instead of
prompting inline — same convention as `./uninstall`, and it avoids
the `pam_faillock` cascade that bricks installs on terminals where
the sudo prompt can’t read the password (VSCode integrated, tmux
with OSC133, sandboxed shells).

## How it works

1. Starts a private 1920×1080 Xvfb framebuffer, then copies
   `src/offline/plymouth/MacTahoeLiquidKde` into
   `/usr/share/plymouth/themes/`. An existing installed copy is moved aside
   transactionally and restored during cleanup.
2. Loops over `boot` and `shutdown`. For each:
   - Spawns `plymouthd --no-daemon --debug --mode=$MODE
     --kernel-command-line="splash plymouth.theme=MacTahoeLiquidKde"`.
     The `--kernel-command-line` flag pins the theme without touching
     `/etc/plymouth/plymouthd.conf` — so we don’t trigger
     `mkinitcpio -P` and don’t rewrite your real initramfs.
   - `plymouth show-splash` renders only inside the nested framebuffer; the
     host desktop never flashes or changes focus.
   - The temporary staged script forces 65% boot progress without modifying
     the source theme. This makes a missing progress bar a deterministic test
     failure instead of relying on Plymouth's timing.
   - `scrot --window <plymouth-window-id> …` captures Plymouth's own X11
     test-window pixmap. It does not depend on the host compositor,
     screenshot permission, active application, or monitor layout.
   - ImageMagick rejects the capture unless the frame is black, the logo
     is centred, boot has a visible fill, and shutdown
     has no bar. A desktop/app screenshot is a hard failure.
   - The daemon log is scanned for script errors before
     `plymouth --quit` brings your desktop back.
3. Cleanup trap on `EXIT/INT/TERM` removes the copied theme dir
   and `chown`s the output back to `$SUDO_USER` so you can read
   the logs without another sudo.

## File layout

```text
tests/vm/
├── README.md       # you are here
├── render.sh       # the whole harness
├── _ui.sh          # ui_section / ui_step / ui_ok / ui_fail / ui_info
└── output/         # gitignored — PNGs + plymouthd debug logs + .err files
```

## Prerequisites

Auto-installed on first run via `pacman`:

- `plymouth`
- `xorg-server-xvfb` (isolated 1920×1080 framebuffer)
- `xorg-xwininfo` (resolve Plymouth's exact test window)
- `scrot` (capture that exact X11 window)
- `imagemagick` (validate the captured pixels)

## Multi-monitor

The host's outputs are irrelevant: Plymouth renders on one private Xvfb screen.
The harness captures Plymouth's exact nested-X window ID, preventing the false
passing launcher/browser screenshots produced by the former host-focus path.

## Caveats

- The harness runs Plymouth's real script engine but uses Plymouth's X11
  renderer. The Fedora fix is installer policy that prevents the problematic
  simpledrm/native-DRM handoff; its actual initramfs and boot timing still
  require a Fedora VM or hardware reboot.

## Troubleshooting

The output dir is your forensics trail.

- `plymouthd-boot.log` / `plymouthd-shutdown.log` — plymouthd’s
  `--debug-file` output. Shows what theme it loaded, which renderer
  plugin (`x11.so`), and any script errors.
- `capture-boot.err` / `capture-shutdown.err` — X11 capture stderr.
- `xwin-tree-*.log` / `xwininfo-*.log` — exact nested window selection.
- `xvfb.log` — private framebuffer startup diagnostics.
