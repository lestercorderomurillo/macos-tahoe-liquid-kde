# Nautilus path-bar state validation

The path bar retains its capsule fill and contour when the window loses focus.
Its scrolling viewport stays transparent, and the current-folder button does
not introduce a second background when checked. Background contrast increases
in both appearance modes; enabled inactive-window controls retain full opacity
and ancestor labels use 85% opacity with both legacy `dim-label` and modern
`dimmed` classes. Geometry, GTK3, saved choices and edition
defaults are unchanged. All eight primary/adaptive/fallback GTK4 sheets carry
the same per-mode path-bar declarations. Both editions share these assets.

## Focused evidence

Visual source: Tahoe `785ff59ef5c77263be66620944dc08ff0d96dfcf`, based on
`365c03cee67d2c79bce31f5b80cc3fce9f830844`. Host: CachyOS, Python 3.14.7.

```sh
python -m pytest tests/test_nautilus_styles.py tests/test_gtk_upgrade.py tests/test_gtk_window_geometry.py tests/test_nautilus_step.py -q -p no:cacheprovider
```

Golden Gate's explicit local-source `./install --prepare` staged these assets
with MacGoldenGate and launcher preset 2. The affected selection passed **48**
checks, including 30 compatibility/installed-sheet parity cases. Its wrapper
suite passed **95** checks. The host desktop was not installed or changed by
these checks. Other pre-existing Acrylic Glass and installer changes in the
sibling worktree are excluded from this candidate.

## Native rendering

Disposable KDE neon VM, sealed `neon-base-v2.qcow2`, SHA-256
`2a09de13ad568da01a8e16dd93e6aec120e63375bfc0ec24b4e804b43ecb4f8c`.
Only the temporary overlay is writable. GTK 4.14, native GTK snapshot renderer.

```sh
python3 tests/nautilus_toolbar_probe.py --theme-variant Light --output /tmp/toolbar-final-relative-labels
```

The final probe passed 162 cases: 120 legacy/class-based comparisons across
light/dark/light, LTR/RTL and ten states, plus 30 current-folder state checks and 12 ancestor-label contrast checks.
The latter require visible capsule fill, low corner coverage, unchanged pixels
and dimensions during checked/normal/active/normal, and unchanged central fill
when inactive. The fixture includes Home's icon and label; the label-only check requires
rendered text alpha of at least 80% of an otherwise identical undimmed label
for both dimming classes, accounting for font antialiasing. All adaptive sheets
are independently checked for parity on GTK 4.14, 4.16 and 4.22 paths.

Negative controls load the parent's adaptive CSS and run the new state checks
without repeating the pre-existing selector comparisons. The parent fails the
contrast check (central alpha 3/255) and, with only the contrast assertions
removed for that control, fails the checked-state pixel equality assertion.
The candidate passes both checks. A separate control removes only the legacy
`dim-label` selectors and fails the new ancestor-label contrast assertion;
restoring those selectors passes it. Development PNG/JSON evidence lives under
`/tmp/nautilus-state-qa/`; these are not publication gallery images.

## Publication photographs

The official `./release-screenshots` recipe captured 90 reviewed frames from
visual source `785ff59ef5c77263be66620944dc08ff0d96dfcf` and the pinned VM/profile.
Both editions show Files and About separately and focused in each mode.
The real Nautilus 46.4 toolbar shows the stronger ancestor-label contrast and
continuous capsule ends. Wizard labels, edition defaults, controls, menus and
Dock were reviewed before staging with content-hashed filenames.

The initial controller terminated with SIGTERM after Tahoe finished. Its 46
reviewed frames and original per-frame records were retained byte-for-byte.
Golden Gate's 44 frames were captured in a fresh guest through the unchanged
entry point/recipe; resumption checked identical source, profile, VM image,
effect identity and host environment, then ran the unchanged complete-set
validator against all 90 frames. This did not repeat Tahoe or replace a failed
frame with an older capture. The complete bundle and review sheets are at
`/tmp/nautilus-pathbar-release-complete/`; the interrupted run is not staged.

```sh
./release-screenshots review --ref 785ff59ef5c77263be66620944dc08ff0d96dfcf --bundle /tmp/nautilus-pathbar-release-complete --approve <90 reviewed frame names>
./release-screenshots stage --ref 785ff59ef5c77263be66620944dc08ff0d96dfcf --bundle /tmp/nautilus-pathbar-release-complete --edition tahoe --destination /tmp/tahoe-pathbar-release
./release-screenshots stage --ref 785ff59ef5c77263be66620944dc08ff0d96dfcf --bundle /tmp/nautilus-pathbar-release-complete --edition golden-gate --destination /tmp/golden-gate-pathbar-release
```

## Limits and release gate

The native widget fixture verifies the shared GTK styling, not every Nautilus
version, compositor or GPU. It does not establish that the user's exact
cropped frame was reproduced. No host installer, theme switch or desktop input
was used. Publication additionally requires successful exact-commit push CI on main and dev in both repositories, followed
by the guarded release workflows. Local focused results do not replace those
gates.
