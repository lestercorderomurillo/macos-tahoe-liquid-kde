# Dock spacing and resizing — v0.61.18

The Dock now uses square task cells with inter-cell spacing matching Plasma's
panel spacing, instead of hiding extra horizontal space inside each task cell.
Launcher, tasks and Trash share the same pitch. The shared `DockCell` and
`DockMetrics` QML types coordinate available space within each panel window,
including constrained panels. Standalone cell bounds accommodate the panel's
integer allocation without introducing fractional boundary gaps. The icon box,
Trash artwork correction, indicators and magnification retain their rendering.

Bundled layouts omit the two obsolete margin separators. Upgrade migration
sorts widgets by their current panel index before removing only the shipped
Launcher/task and task/Trash or task/Downloads separators. It preserves pins,
settings, unrelated separators and other panels; running it again is safe.
Nix's existing separator-free layout uses the same shared runtime.

## Focused evidence

Runtime source: `90d2ef6ae90bc5e274286700559902a57203c5ce`, based on the published
v0.61.17 source. Host: CachyOS, Qt 6.11.2. Later report and test-settling edits do
not change the runtime inputs.

- `python3 -m pytest -q tests/test_launcher_presets.py tests/test_taskmanager_qml.py tests/test_plasmoids_step.py -k 'not native_launcher_popup'`:
  **64 passed**, eight popup cases deselected. This includes seven-scale task
  boundary checks, successive grow/shrink states, both orientations, constrained
  and oversized panels, changing task counts, hiding/showing a neighboring cell,
  real bundled Trash artwork, desktop exemptions and installer package removal.
- `python3 -m pytest -q tests/test_launcher_presets.py -k native_launcher_popup`:
  **8 passed** in private Xvfb/D-Bus sessions: both editions, both modes and both
  launcher presets. The host desktop was not changed.
- The new boundary regression fails against v0.61.17, detecting its larger task
  cells. A separate executable migration regression covers creation order
  differing from current visual order, pin preservation and repeat execution.
- Golden Gate prepared source, selected with
  `GOLDEN_GATE_TAHOE_SOURCE=<candidate> MAC_TAHOE_NO_UPDATE_CHECK=true ./install --prepare`:
  **23 passed** with
  `tests/test_launcher_presets.py -k 'custom_dock or follow_panel_thickness or installed_launcher or dock_boundary_spacing or separator_upgrade or share_compression'`.
  Wrapper suite: **89 passed**.

## Installed rendering

A disposable KDE neon guest used Plasma 6.8.1 / Qt 6.11.1 on Wayland, KVM,
virtio graphics, four CPUs and 8 GiB RAM. Its original sealed base image SHA-256
is `2a09de13ad568da01a8e16dd93e6aec120e63375bfc0ec24b4e804b43ecb4f8c`.
The task-manager applet and shared QML module were rebuilt from the runtime
source above and loaded before final measurement.

**224 installed combinations passed**: scales 1, 1.25, 1.5, 1.75, 2, 2.5 and 3;
bottom, top, left and right edges; 40, 48, 68 and 96 logical pixel thicknesses;
with and without the development Downloads widget. Measurements verify equal
cell allocation, including compressed panels, and the panel gaps at every
widget/task boundary. Real Plasma migration also passed after inserting the old
separators in a different creation order, with all ten pins retained.

**12 new frames were reviewed**: both appearances at 1, 1.5 and 2 times scaling,
with and without Downloads. Downloads remains an unpublished development
widget; its sizing is prepared and tested without enabling it in either edition.
The release galleries continue to show each edition's installed defaults.

Development artifacts: `/tmp/dock-gap-live-final`, including geometry records,
review sheets, image hashes and captured frames. Earlier incomplete runs were
rejected. An old compiled applet was replaced with the rebuilt candidate;
a temporary-storage failure was recovered by moving the disposable VM to a
larger volume. These runs are not counted as passes or used as publication
frames. No host installer, theme change, window movement or input injection was
used.

## Publication and limits

Documentation captures use `./release-screenshots` with fresh overlays of the
pinned image and the checked-in capture profile. Committed image hashes, source
identity, environment and review provenance are in
[`release-capture.json`](../../src/screenshots/release-capture.json).
Publication requires successful `test.yml` push runs on both `main` and `dev`
for each exact release commit, plus the release workflows' provenance gates.

These checks qualify the default icons-only Dock and its shared icon renderer;
they do not establish every GPU, monitor combination, custom spacing preference
or pointer-driven drag sequence. Distribution/SDK coverage comes from required
CI on the final implementation commit, not from the single guest's results.
