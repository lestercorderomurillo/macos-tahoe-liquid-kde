# Nautilus toolbar validation — v0.61.14

Issue [#105](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/105)
is caused by Nautilus changing its path bar, breadcrumb and query editor from
widget IDs to CSS classes. The
[upstream migration](https://github.com/GNOME/nautilus/commit/15fb6784920fcc24169ce3e7d24ec206b1bea454)
leaves the old theme selectors unmatched. Both bundled GTK4 modes now apply
the same declarations to both naming schemes. The modern path bar includes
`.linked` in its selectors so generic linked-button rounding cannot win.
GTK3, geometry, colors, edition defaults and saved settings are unchanged.

## Focused checks

Source: `c421178` plus this release's two GTK4 stylesheets. Final SHA-256:

| Stylesheet | SHA-256 |
| --- | --- |
| Light | `9b349972b444a67ced617fb493f8fbef27bde7d2b226152eaa925982cf1a92f0` |
| Dark | `72491f4ed7c952307510c658763c4919bf0c1f9e792b44aef4bbb07dd8140c14` |

Host checks used Python 3 and pytest, without installing the theme:

```sh
python -m pytest tests/test_nautilus_styles.py tests/test_static.py tests/test_gtk_upgrade.py tests/test_gtk_window_geometry.py tests/test_nautilus_step.py -q
python -m pytest tests/test_theme_switch.py -q
```

Results: 52 asset/lifecycle/static checks and 120 theme-switch checks passed.
One theme-switch Unix-socket test needed an unrestricted rerun after the
sandbox denied socket creation; that rerun passed. Collection reports 2,036
cases, including conditional tests, rather than 2,036 executed passes.

Golden Gate's explicit-source `./install --prepare` produced an isolated copy
with `MacGoldenGate` and launcher preset 2. The toolbar, GTK upgrade, GTK
geometry and Nautilus integration subset passed there: 22 checks. Golden
Gate's wrapper suite passed all 80 checks. Staging does not modify GTK4 CSS,
so the native toolbar result applies to both editions.

## Native rendering

The checksum-pinned disposable KDE neon capture guest used Plasma 6.8.1,
Qt 6.11.1, GTK 4.14.5, libadwaita 1.5 and Nautilus 46.4. The base image's
SHA-256 is `2a09de13ad568da01a8e16dd93e6aec120e63375bfc0ec24b4e804b43ecb4f8c`;
only its temporary overlay was writable. Command inside the guest session:

```sh
python3 tests/nautilus_toolbar_probe.py --output /tmp/nautilus-toolbar-final
```

All 72 legacy/class-based pixel comparisons passed: path and search controls,
light → dark → light, LTR/RTL, and normal, hover, active, checked, backdrop and
disabled states. The real GTK widget hierarchy models the upstream naming
change. The unmodified-release control failed on its first modern path-bar
render, detecting different dimensions and square button styling. Reviewed
fixed renders show round menu feedback and correct mirrored RTL placement.
The native probe's PNGs and JSON remain in `/tmp/issue105-vm/` on the capture
host; they are development evidence, not documentation gallery images.

The probe does not qualify the complete Nautilus 50 application, every distro,
GTK runtime or GPU. It directly verifies the changed selectors on GTK4's real
renderer and the older-GTK stylesheet translation. Python regressions also
cover the unmodified GTK 4.16+ stylesheet path. Release gallery captures use
the repository's pinned VM/profile and retain their exact source, environment,
image hashes and review decisions in screenshot provenance.

## Integration and publication

Required `test.yml` push runs on both `main` and `dev` gate the exact release
commit; earlier runs and local focused results cannot replace that gate.
The full suite and distro matrix run in CI, without a duplicate local matrix.
Both editions' committed screenshot provenance must verify before their
release workflows can publish matching `v0.61.14` releases.
