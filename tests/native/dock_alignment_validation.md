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


## Final focused integration

Code candidate `80403fd7d3de2de2de1e9aceadade50222ba5c5f`:

- `python -m pytest -p no:cacheprovider tests/test_launcher_presets.py tests/test_taskmanager_qml.py -k 'not native_launcher_popup' -q`:
  48 passed, eight popup cases deselected (already rerun separately after the
  same panel-root change: eight passed).
- Golden Gate prepared content `bb62d6ffe74a3fcc58d2`, staged from that isolated
  candidate using the explicit source override and no-update flag:
  `python -m pytest -p no:cacheprovider tests/test_launcher_presets.py -k 'custom_dock or follow_panel_thickness or installed_launcher' -q`:
  12 passed. No unpublished Downloads or battery work is in this candidate.

Publication requires a complete newly reviewed capture bundle from this candidate
and exact-release-commit push CI on both branches. Rejected frames and incomplete sets are excluded from publication.
The first complete Tahoe edition capture passed review. When the Golden Gate
system menu did not open after its scripted click, that edition was retried in
a fresh pinned VM. Passing Tahoe frames retain their original source/profile,
hashes and capture provenance; the combined set must pass the unmodified
90-frame validator. No failed Golden Gate frame is filled with an older one.


## CI validation corrections

The initial exact-commit runs at `3c716001335841eb2765dcd1cea2355ff338af77`
reported a stale collected-case badge (2024 versus 2032) and a suppressed
QML debug-level success marker on Fedora. The latter reproduced locally with
`QT_LOGGING_RULES='*.debug=false'`. Probe success messages now use info level;
all geometry assertions and completion checks remain enabled.

`QT_LOGGING_RULES='*.debug=false' python -m pytest -p no:cacheprovider tests/test_launcher_presets.py tests/test_static.py -k 'follow_panel_thickness or custom_dock or readme_tests_count_badge' -q`:
nine passed. These edits affect test logging and the README count; runtime
Dock inputs and the reviewed capture source are unchanged. Publication still
requires successful push CI for the corrected exact release commit on both
branches; the failed initial runs are not release evidence.


## Trash artwork correction — v0.61.13

The review of v0.61.12 correctly identified a remaining optical mismatch:
matching applet cells and icon viewports does not compensate for the bundled
Trash SVG's internal padding. Its body spans y=6..59 in a 64-unit canvas;
application tiles span y=4..60. `DockIcon` now applies the 56/53 height ratio
and centres that body, only when the Trash applet opts in and uses the bundled
empty/full icon names. Custom icons, desktop widgets and the separate glyphs
at 24 logical pixels or below keep their existing geometry. The bin retains
its natural narrower shape. No task margins, panel allocation or native ABI
changed.

Stable runtime candidate: `c421178eeed95376506c157d0dbce9fd554aed2f`.
The new assertions compare the SVG body bounds with application-tile bounds
through the existing seven-scale, light/dark, resize/aspect/orientation probe.
They also exercise empty/full/custom icon changes and the desktop exemption.
A session fixture seeds the actual bundled SVGs and small glyphs, then selects
that theme explicitly in the native runner. A missing system icon theme cannot
turn painted-size assertions into a false pass. `tar`/`zstd` are already present
in every affected native CI image. The final probe rejects the discarded
viewport-enlargement implementation (case 3); log:
`/tmp/dock115-optical-rounding-regression.log`.
An initial centre-anchor implementation failed the fractional geometry checks.
The first installed frame then exposed Kirigami's discrete icon-size rounding:
enlarging its requested viewport jumped to a larger icon bucket. That capture
was rejected. The final component keeps the original viewport and painted size,
then scales the resulting artwork. The probe now checks the painted size as well
as body bounds, catching that bucket jump.

- CachyOS / Qt 6.11.2: `python3 -m pytest -q tests/test_launcher_presets.py
  tests/test_taskmanager_qml.py -k 'not native_launcher_popup'`: 48 passed.
- The private Xvfb/D-Bus native popup checks passed all eight edition/mode/preset
  cases. The first sandboxed invocation could not bind a private D-Bus socket;
  that environment error is not a rendering result. The isolated invocation
  ran with the required socket access. The subsequent small-glyph guard only
  affects an opted-in Trash icon; these popup inputs remain unchanged.
- Prepared Golden Gate content `e70d974347c0558d36f9` from this candidate:
  `python3 -m pytest -q tests/test_launcher_presets.py -k 'custom_dock or
  follow_panel_thickness or installed_launcher'`: 12 passed.

The prior 112-state installed-panel allocation evidence remains applicable:
this follow-up changes artwork sizing within the existing cells, not their
allocation. Fresh installed optical QA in the checksum-pinned KDE neon VM reviewed 20
frames: light/dark, empty/full, scale 1 and 2 at requested panel size 68, and
scale 1.5 at requested sizes 32, 68 and 96. Plasma clamps the 32 request to its
40-pixel minimum; `results.json` records both requested and actual geometry.
The successful run waits two 3-second polling intervals before each capture.
An earlier development run with a shorter wait had stale empty/full labels and
was rejected. Final reviewed artifacts: `/tmp/dock115-optical-live-c421`.
The actual body heights and baselines match adjacent application tiles while
preserving the bin's narrower shape and the papers above its full-state rim.
The official publication captures use runtime source `c421178` in fresh VMs;
no discarded or stale-labelled development frame is used for publication. Physical GPUs and mixed-DPI multi-monitor
configurations remain untested.
