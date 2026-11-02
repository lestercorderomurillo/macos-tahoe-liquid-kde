# Nautilus path-bar state validation

The path bar retains its capsule fill and contour when the window loses focus.
Its scrolling viewport stays transparent, and the current-folder button does
not introduce a second background when checked. Background contrast increases
in both appearance modes; enabled inactive-window controls retain full opacity
and ancestor labels use 85% opacity. Geometry, GTK3, saved choices and edition
defaults are unchanged. All eight primary/adaptive/fallback GTK4 sheets carry
the same per-mode path-bar declarations. Both editions share these assets.

## Focused evidence

Based on Tahoe `365c03cee67d2c79bce31f5b80cc3fce9f830844` with the GTK4
path-bar patch and probes in this change. Host: CachyOS, Python 3.14.

```sh
python -m pytest tests/test_nautilus_styles.py tests/test_gtk_upgrade.py tests/test_gtk_window_geometry.py tests/test_nautilus_step.py -q -p no:cacheprovider
```

The original affected component selection passed 42 checks. After adding the
adaptive-sheet parity regression, its 30 cases passed. Golden Gate's explicit
local-source `./install --prepare` staged these same assets with MacGoldenGate
and launcher preset 2; the final affected selection passed 48 checks there.
Its wrapper suite passed 95 checks. The source checkout and host desktop were
not installed or changed by these checks. Other pre-existing Acrylic Glass
and installer changes in the sibling worktree are excluded from this candidate.

## Native rendering

Disposable KDE neon VM, sealed `neon-base-v2.qcow2`, SHA-256
`2a09de13ad568da01a8e16dd93e6aec120e63375bfc0ec24b4e804b43ecb4f8c`.
Only the temporary overlay is writable. GTK 4.14, native GTK snapshot renderer.

```sh
python3 tests/nautilus_toolbar_probe.py --theme-variant Light --output /tmp/toolbar-final-home
```

The final probe passed 150 cases: 120 legacy/class-based comparisons across
light/dark/light, LTR/RTL and ten states, plus 30 current-folder state checks.
The latter require visible capsule fill, low corner coverage, unchanged pixels
and dimensions during checked/normal/active/normal, and unchanged central fill
when inactive. The fixture includes Home's icon and label. All adaptive sheets
are independently checked for parity on GTK 4.14, 4.16 and 4.22 paths.

Negative controls load the parent's adaptive CSS and run the new state checks
without repeating the pre-existing selector comparisons. The parent fails the
contrast check (central alpha 3/255) and, with only the contrast assertions
removed for that control, fails the checked-state pixel equality assertion.
The candidate passes both checks. Development PNG/JSON evidence lives under
`/tmp/nautilus-state-qa/`; these are not publication gallery images.

## Limits and release gate

The native widget fixture verifies the shared GTK styling, not every Nautilus
version, compositor or GPU. It does not establish that the user's exact
cropped frame was reproduced. No host installer, theme switch or desktop input
was used. Publication additionally requires reviewed release captures and
successful exact-commit push CI on main and dev in both repositories, followed
by the guarded release workflows. Local focused results do not replace those
gates.
