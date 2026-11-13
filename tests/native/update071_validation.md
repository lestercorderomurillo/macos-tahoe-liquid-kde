# v0.71.0 focused release qualification

The candidate adds a glass application About window, moves window controls into
View, simplifies installer progress, fixes the installer appearance independently
of the desktop style, and adds Prism plus a macOS wallpaper selection.

## Passing checks

- Host: Plasma SDK 6.7.4, Qt 6.11.2. The focused About, native Global Menu,
  installer UI/wizard, wallpapers, catalogs and component-cache selection passed
  **146 tests**. An additional **21 wallpaper ownership/switching tests** passed.
- Two disposable KDE neon Plasma/KWin 6.8.1, Qt 6.11.1 Wayland overlays: Tahoe
  and the actual Golden Gate wrapper-prepared source each passed installation
  and reinstallation of Global Menu and wallpapers. The backend also installed
  the edition's theme switcher. All Prism/Monterey light/dark installed image
  bytes matched their source bundles.
- Each guest passed **47 focused tests**, including building/loading the plugin,
  the private Xvfb/D-Bus importer and popup regressions, QML applet composition,
  application About and the native installer navigation/palette/font checks.
- Each guest's explicit Wayland `liveWindowControls` test passed with **zero
  skips**: About metadata, Zoom/Restore, enter/exit fullscreen, minimize,
  reactivate and close through the new View menu.
- Each edition's real Wayland QML About passed five metadata cases in both
  modes, plain-text/long-path rendering, clipboard, Escape, Ctrl+W and reopening.
- Four composited desktop captures were reviewed, using each edition's wallpaper
  and controls. The exact shared QML was opened standalone with a Files metadata
  fixture; this is distinct from the actual applet composition test. Real pointer
  dragging moved each window by approximately 120 × 80 logical pixels. These are
  focused development captures, not replacements for the README gallery.

The exact scoped installer command, with that edition's default choices encoded
in `MTTKDE_WIZARD_OPTIONS`, was:

```sh
sudo env MAC_TAHOE_NO_UPDATE_CHECK=true MTTKDE_NO_CONFIRM=1 \
  MTTKDE_WIZARD_OPTIONS='<edition defaults with appearance=light>' \
  <source>/src/scripts/installer_backend.py install \
  --only --globalmenu --wallpapers --no-apply-theme
```

Full commands and results are recorded under `build/release-071/`. The QEMU base
was verified as SHA-256
`412e7933f10add20b921b92c02709e7eea56acd14dc14cf654f58fba4ea3cc9d`.
Final VM input archive SHA-256 values:

- Tahoe: `018c395313be70a6f0c8a10090861bd22760efa3ace94f55d9a89eeaf5459a36`.
- Golden Gate: `ad77499fc68ddaccbaf1491f8c8e8348143c7d4882022f1487140d47f5ba5e25`.

The first live minimize assertion raced Qt's visibility notification after KWin
had already reported the minimized task. It now waits for both observations;
the rerun passed. Installer/runtime bytes were unchanged, so successful lifecycle
evidence was reused. QEMU's EGL backend cannot provide `screendump`; composited
captures used Spectacle instead. Golden Gate's light capture includes old Baloo
crash notifications: guest journal entries identify October 25 coredumps already
present before the sealed reference image, not a new installer failure.

Local qualification does not replace the complete remote distro matrix. Remote
CI outcomes are tracked separately and must succeed before reporting delivery.
