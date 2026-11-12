# Generic application About — v0.70.0

The application-name menu now begins with **About <application>**. One reusable
window follows the centered icon/name/description composition of macOS Finder's
About window. It shows the selected app's real icon, name, description, executable
location and application ID; Copy Details includes its desktop file and process
ID when available. Long paths wrap and the content scrolls. Escape and the
platform Close shortcut dismiss the window. Reopening it for another app replaces
its snapshot; focusing the About window never changes that snapshot.

This is generic metadata presentation, independent of application-menu export.
There are no Firefox-specific commands or new fallback menus. Existing exported
File/Edit/View/Search actions retain their behavior. Existing window actions
remain available below About. Their task index is now persistent, so deleting a
window while its menu is open cannot redirect an old action to another row.

Metadata comes from task roles, the registered desktop file and `/proc/<pid>/exe`.
The code never executes the selected app or its desktop Exec entry. Command-line
arguments are not collected. Desktop Entry `Version` describes the desktop-file
format, so it is never presented as an application's software version. Sandboxed
or inaccessible executables can show the registered desktop-file location instead.
Unavailable metadata is omitted, with Not Available for an unknown location.

## Reference and visual review

- [Real About Finder comparison, right-hand macOS Tahoe panel](https://512pixels.net/2025/06/wwdc25-macos-tahoe-breaks-decades-of-finder-history/).
  Original image: https://512pixels.net/wp-content/uploads/2025/06/About-Finder.jpg
- The reference provides the composition, not app identity or Apple copyright.
  Every app retains its own name and artwork. Paths, the application ID and the
  Copy Details button replace information unavailable generically on Linux.
- The shared window uses system fonts, a large centered icon, a bold name and
  concise secondary information. Its native title bar and controls follow the
  installed decoration. This is a layout adaptation, not a pixel-identical clone.
- Four Wayland content captures, both edition sources in light/dark mode, were
  reviewed. The actual installed Files → About Files path was also clicked and
  its focused native window/frame inspected. These are focused development
  captures, not replacements for the historical README galleries.

## Qualification

- `QT_QPA_PLATFORM=offscreen python3 -m pytest -q tests/test_application_about.py
  tests/test_globalmenu_step.py tests/test_multilanguage.py`: **39 passed**.
- After final window geometry, `QT_QPA_PLATFORM=offscreen python3 -m pytest -q
  tests/test_application_about.py tests/test_component_cache.py`: **16 passed**.
  These command counts overlap; they are not additive.
- `MTTKDE_REQUIRE_NATIVE_GLOBALMENU=1 python3 -m pytest -q
  tests/test_globalmenu_model.py` passed on the host and for both sources in the
  disposable KDE neon VM. This builds the actual plugin and runs importer,
  popup and QML composition executables on a private Xvfb display and D-Bus bus.
  It covers all 16 capability combinations, Zoom/Restore and Enter/Exit Full
  Screen labels, actual task-proxy dispatch, deleted-task invalidation, metadata
  extraction, escaped ampersands, and mouse activation of the real applet's
  About action to show the QML window. Existing export/search/navigation checks
  remain enabled. The opt-in live test is run separately, not counted as covered
  by its skip in the isolated suite.
- Disposable KDE neon **Plasma/KWin 6.8.1, Qt 6.11.1**, Wayland: both Tahoe and
  Golden Gate's actual prepared source passed focused installation and
  reinstallation with `sudo env MAC_TAHOE_NO_UPDATE_CHECK=true
  MTTKDE_NO_CONFIRM=1 <source>/src/scripts/installer_backend.py install --only
  --globalmenu --no-apply-theme`. Four successful lifecycle operations.
- `QT_QPA_PLATFORM=wayland MTTKDE_LIVE_GLOBALMENU=1
  /tmp/about-live/globalmenu-popup-test liveWindowControls` passed with **zero
  skips** against actual KWin-managed windows. Mouse clicks exercised About,
  maximize, restore, enter/exit full screen, minimize/reactivate, and close.
  Compositor task roles and actual window visibility/state were checked.
- `python3 tests/application_about_probe.py --mode <light|dark>` passed all
  **8** edition/mode/backend combinations. Wayland used the actual session;
  X11 used `dbus-run-session -- xvfb-run -a -s '-screen 0 1920x1080x24'`.
  Each case covers Files, Firefox, a long Unicode/markup-like app name/path,
  a sandboxed desktop-file-only entry and missing metadata: **40** dialog
  openings, copy/clipboard checks, Escape, Close shortcut and reuse.
  Probe metadata is deterministic; the separate actual-menu check proves live
  Files metadata and the real panel path. The installer never runs on the host.

The first native test depended on a development-machine icon theme and failed
in the guest. It now provides its own desktop-entry icon fixture. A Golden Gate
appearance check initially imported Tahoe's verifier; invoking the prepared
source's own helper fixed the harness and the final edition checks passed.
Neither rejected check is presented as a product success.

This focused guest does not establish new live compatibility claims for every
distribution, graphics driver or a full X11 Plasma session. Existing remote CI
retains the full distro/SDK matrix; isolated X11 native behavior and real Wayland
compositor behavior are recorded separately.

## Exact inputs

VM base SHA-256: `412e7933f10add20b921b92c02709e7eea56acd14dc14cf654f58fba4ea3cc9d`.

Final source archive SHA-256: `d727a2c337cfd679b19fc355c175d8a0c8596daf6bcf9486f14e01bb9c8d43d7`.

Initial install archive SHA-256: `ba2c9b284419c017ad487d439fa02b2bc9e8f73f5a8274f60b4a5158b2846bca`.
Runtime implementation bytes were unchanged by the later test-fixture adjustment;
the passing focused install/reinstall evidence was reused.

Runtime/test file SHA-256:
- `src/offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu/appmenuapplet.cpp`: `f8e62e7a4dd49443ccbb205ed1b3aeeec683d5145eded5bd54147802926d10bc`.
- `src/offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu/appmenuapplet.h`: `69e6b1096f07eb366b7aa0cd65d1b8c4de4caadc76ba7cd40473e7b8f090e4ae`.
- `src/offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu/CMakeLists.txt`: `63d64cf25c0ec496e59277cfec7fc7d3ea612a994e66c989b7332557a554867b`.
- `src/offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu/qml/main.qml`: `1937b8207b37d5febb5b04c2a1834863d0ac7a5aaa83f62ca8663b343c8596c3`.
- `src/offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu/qml/ApplicationAboutWindow.qml`: `0ef8a76566b12975c7a424470ae1288eb3d7406c4073a8f5f4cb4a5ce4158964`.
- `tests/native/globalmenu/popup_test.cpp`: `433cd49782378351ddd56deba8ad8e830e801ec055846c84c07cbd41b212ceff`.
- `tests/native/globalmenu/composition_test.cpp`: `b3a1abf33ff0c4e238dd5254acdc56d326e7ca37d8bcc8191c3bec0546aa14ca`.
- `tests/application_about_probe.py`: `60d9e39273975564f07916cab79cb6b36ac1f4ecfa5545e53ae6d3ca2c192bcd`.

Reviewed local capture SHA-256:
- `tahoe-light-wayland.png`: `0a8df2708b911d8d5922d8d356342057f6db3643a8930cf36c2dbcfd0309f358`.
- `tahoe-dark-wayland.png`: `14214ec168432056409d7aefec3e062dd5cdf6a397b7a705d257acf8fdd3faad`.
- `golden-gate-light-wayland.png`: `e13f850a5b06c99f3e3b447a54a43a1a472b077feb90f5ae0172114cac878ffd`.
- `golden-gate-dark-wayland.png`: `b81df82404ae78d5e93b9a3994f842907863c316ab3a7f79242510e2f728f074`.
- `actual-about-crop.png`: `fa716d54fd443bdb48843dcdb4057a2baf99293d71f8c9eba47ccd99d03e5b71`.

Commands, logs and captures: `/tmp/app-about-070/`.
