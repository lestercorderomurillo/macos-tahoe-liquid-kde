# Plymouth render harness

A quick visual check of the MacTahoe Plymouth theme without rebooting.

```bash
sudo ./test --vm
```

Two PNG screenshots land in `tests/vm/output/`:

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

1. Copies `src/offline/plymouth/MacTahoeLiquidKde` into
   `/usr/share/plymouth/themes/` (refuses if a real install is
   already there — run `./uninstall` first).
2. Loops over `boot` and `shutdown`. For each:
   - Spawns `plymouthd --no-daemon --debug --mode=$MODE
     --kernel-command-line="splash plymouth.theme=MacTahoeLiquidKde"`.
     The `--kernel-command-line` flag pins the theme without touching
     `/etc/plymouth/plymouthd.conf` — so we don’t trigger
     `mkinitcpio -P` and don’t rewrite your real initramfs.
   - `plymouth show-splash` — plymouth’s window flashes on screen.
   - `xdotool windowactivate $WID` forces focus to plymouth so
     `--activewindow` captures the right thing (without this,
     shutdown mode often loses focus and the screenshot grabs your
     code editor instead).
   - `spectacle --background --nonotify --activewindow --output …`
     captures via KDE’s `org.kde.KWin.ScreenShot2` DBus interface.
     X11 tools (`scrot`, `import`, `xwd`) can’t do this on Wayland —
     they only see XWayland’s internal framebuffer, which stays
     black even when plymouth is visibly on screen.
   - Spectacle runs as `$SUDO_USER`, not root: KWin refuses
     screenshot requests from non-session-owning UIDs. Session env
     (`XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`,
     `WAYLAND_DISPLAY`) is reconstructed because sudo strips it.
   - `plymouth --quit` brings your desktop back.
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
- `spectacle` (Wayland-native screenshot via KWin DBus)
- `xorg-xwininfo` (locate plymouth’s X window)
- `xdotool` (force-activate plymouth before the capture)

## Multi-monitor

We capture `--activewindow` (the focused plymouth window),
**not** `--fullscreen` — otherwise you’d get plymouth on one screen
and whatever your other monitor was showing on the other.

## Caveats

- Plymouth’s splash briefly takes over your screen (~5s per mode).
  This is normal — plymouth’s X11 plugin maps a fullscreen window
  so it can render as if it were on the boot console.
- Visual confirmation here is **not** the same as the real boot
  path. The actual `mkinitcpio` rebuild, kernel cmdline, and DRM
  renderer only fire on a real reboot. The render harness verifies
  the theme renders correctly under plymouth’s engine; reboot
  verifies the rest.

## Troubleshooting

The output dir is your forensics trail.

- `plymouthd-boot.log` / `plymouthd-shutdown.log` — plymouthd’s
  `--debug-file` output. Shows what theme it loaded, which renderer
  plugin (`x11.so`), and any script errors.
- `spectacle-boot.err` / `spectacle-shutdown.err` — spectacle’s
  stderr. If a screenshot failed, this is why.
