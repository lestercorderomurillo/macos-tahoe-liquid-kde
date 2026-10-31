# Dock alignment and resizing — issue #115

Local development evidence recorded 2026-10-30, against baseline
`a7ad8e7be6028fc62e61cacd35dbe983f2861562` and the Dock alignment changes.

Launcher and Trash share the native launcher module's `DockIcon` QML type.
The component uses the task frame's directional indicator margins and the task
icon's rectangular bounds, allowing Kirigami to fit and round the artwork.
Desktop widgets retain their inset exemption. Task badges, dragging, launch
animation and magnification retain their existing implementation. Both editions
and launcher presets use the shared component; no backend ABI changed.

## Focused checks

- Native geometry probe: seven scale factors (1, 1.25, 1.5, 1.75, 2, 2.5, 3),
  light/dark themes, four edges, three cell aspect ratios and 19 successive
  grow/shrink sizes from 16 to 128 logical pixels, including fractional sizes.
  Each process verifies the actual QQuickView device-pixel ratio. Each theme
  executes 228 panel cases plus desktop geometry. Rectangular cells fail the
  former square-icon implementation; all seven scale cases pass the fix.
- Host: CachyOS, Qt 6.11.2. Command:
  `python -m pytest -p no:cacheprovider tests/test_launcher_presets.py tests/test_taskmanager_qml.py tests/test_downloads.py -k 'not native_launcher_popup' -q`:
  50 passed, eight deselected in the existing development checkout (including
  unpublished Downloads work). An earlier invocation reported host config drift
  at safety-net teardown; the read-only sandbox prevented file restoration.
  The subsequent invocation passed without changing that guard.
- Private Xvfb/D-Bus popup probe:
  `python -m pytest -p no:cacheprovider tests/test_launcher_presets.py -k native_launcher_popup -q`:
  eight passed, covering both editions, modes and launcher presets.
- Golden Gate:
  `GOLDEN_GATE_TAHOE_SOURCE=<Tahoe checkout> MAC_TAHOE_NO_UPDATE_CHECK=true ./install --prepare`
  followed by its prepared source's `tests/test_launcher_presets.py -k custom_dock`:
  seven passed. Wrapper `tests/test_bootstrap.py`: 38 passed.
- Disposable KDE neon overlay, Qt 6.11.1 / Plasma 6.8.1, pinned image SHA-256
  `2a09de13ad568da01a8e16dd93e6aec120e63375bfc0ec24b4e804b43ecb4f8c`:
  same seven-scale geometry cases passed. Final light/dark icon sheets rendered
  at 1.5× using bundled Launcher, Files, Settings, Terminal and Trash SVGs,
  at 24/32/48/64/96 logical pixels; both were visually reviewed. Initial
  incomplete reference frames were rejected. Final local artifacts:
  `/tmp/dock115-vm2/dock-Light.png`, `/tmp/dock115-vm2/dock-Dark.png`,
  `geometry.log` and `render.log`. Guest stopped after checks.
- `git diff --check` passed in both source checkouts.

The installed-Dock publication probe exposed an additional allocation issue:
Plasma allocated 52-pixel applets beside a 68-pixel task manager. The final
applets request `CanFillArea` and a square cell matching panel thickness.
An executable QtQuick GridLayout regression checks resizing and orientation
changes using their production layout expressions (one test, both applets).
The installed Golden Gate Dock then passed 112 live combinations: seven scale
factors, four panel edges and 32/48/68/96 logical pixel panel sizes. Six final
light/dark frames at 1×/1.5×/2× were reviewed; artifacts and recorded geometry
are in `/tmp/dock115-live-final`. Earlier undersized publication frames were
rejected and are not used as release screenshots. The popup regressions were
rerun after the root-layout change: eight passed.

These checks do not establish all monitor, GPU, resolution or distro
combinations or pointer-driven drag sequences. Exact-commit CI and
publication captures are separate release gates. Unrelated Downloads and
battery changes are excluded from the isolated release candidate.
