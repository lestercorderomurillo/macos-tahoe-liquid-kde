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
