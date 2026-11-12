# Dock apps dialog — v0.69.1

Clicking **Dock apps…** on the layout page aborted the entire installer in
`CheckOption.paintEvent`: its containing `QDialog` had no `accent` attribute.
The dialog now receives the wizard's accent and outline colors before its first
paint. Refresh also removes saved selections for apps that became installed or
unavailable, including controls that were already unchecked when constructed.

The control run against the original code reproduced SIGABRT and
`AttributeError: 'QDialog' object has no attribute 'accent'` on the first painted
checkbox. Existing navigation tests visited the layout page without opening its
modal editor. The new subprocess regression clicks the actual button and runs
the real modal event loop; paint-callback failures fail that subprocess.

## Qualification

- Host focused suite: `QT_QPA_PLATFORM=offscreen python3 -m pytest -q
  tests/test_installer_wizard.py tests/test_dock_apps.py
  tests/test_dock_appearance.py tests/test_installer_ui.py`: **134 passed**.
- Golden Gate wrapper: `python3 -m pytest -q tests`: **97 passed**.
  Its prepared source also passed all **4** new edition/appearance cases.
- Disposable KDE neon guest: Plasma/KWin **6.8.1**, Qt **6.11.1**, Wayland.
  Both Tahoe and the source prepared by Golden Gate's actual wrapper passed
  `sudo env MAC_TAHOE_NO_UPDATE_CHECK=true MTTKDE_NO_CONFIRM=1
  <source>/src/scripts/installer_backend.py install --only --layout
  --apply-theme --light` twice: installation and reinstallation. Both runs
  activated the layout and restarted only the guest Plasma session.
- `python3 tests/installer_dock_apps_probe.py <light|dark>` passed all **8**
  edition/appearance/platform combinations: native Wayland and isolated X11 via
  `dbus-run-session -- xvfb-run -a -s '-screen 0 1920x1080x24'` with
  `QT_QPA_PLATFORM=xcb`. Each case opens **12 dialogs**, totaling **96**.
  The installed desktop appearance was switched before each appearance case.
  Four Wayland dialog images were inspected; all text, checkmarks, source
  controls and Continue/Cancel actions render in their matching appearance.

Every probe exercises all missing, partly installed and fully installed app
lists; unavailable native proposals; native/Flatpak source changes; the Flathub
checkbox; mouse and keyboard selection; Continue, Cancel and Escape; repeated
reopening and saved selections; isolation until Continue; and disabling the
editor when the Dock is disabled. App discovery/recommendations are deterministic
fixtures. These checks exercise the UI and selected install lifecycle, not real
optional app downloads or provisioning. Existing backend package tests cover
those independent paths. The installer never runs on the host desktop.

The initial dark capture used a forced dark palette with the installed light
Kvantum style and was rejected. Final images use matching installed desktop
styles. An isolated X11 portal inherited the SSH output pipe after the GUI
exited; redirecting subprocess output to a guest file corrected the harness.
Neither issue was counted as a successful appearance check.

## Exact inputs

- VM base SHA-256: `412e7933f10add20b921b92c02709e7eea56acd14dc14cf654f58fba4ea3cc9d`.
- Working-source archive SHA-256: `539a2ad9072a7253a2aa7ba15b2551f204ce2bebfaa8bb2cc0753a62c172ae88`.
- Runtime/test file SHA-256 values:
  - `src/installer/wizard_window.py`: `12d86171aeb9240d6c46efcb20a5f7ce3d0b67d6488aa768b708489e7f36853a`.
  - `tests/installer_dock_apps_probe.py`: `92c1904ca9b066028e2fb0a22d86512bedd7d4718f239c7da11dfad7134d0c23`.
  - `tests/test_installer_wizard.py`: `3703a642f3fdee11f328026bb3c2815086ebd2e2b356f4833770c4d94d318eb8`.

Reviewed local frame SHA-256 values:
- `tahoe-light-wayland-desktop-mode.png`: `973e768c4c903d314220bb7f1fc6a329cc1b0ee745df6782990843475767c8df`.
- `tahoe-dark-wayland-desktop-mode.png`: `9a46217759aafc36d215230c62e6300d6a7c3e8e7fb90e2b17a1d1278ddf3603`.
- `golden-gate-light-wayland-desktop-mode.png`: `973e768c4c903d314220bb7f1fc6a329cc1b0ee745df6782990843475767c8df`.
- `golden-gate-dark-wayland-desktop-mode.png`: `9a46217759aafc36d215230c62e6300d6a7c3e8e7fb90e2b17a1d1278ddf3603`.

Local commands, captures and the disposable overlay are in
`/tmp/dock-dialog-0691/`. They are development evidence, not replacement
README/installer photographs. Existing galleries retain their original records.
The complete remote CI matrix runs on `dev`; this focused VM does not claim
live coverage of every distribution or graphics driver.
