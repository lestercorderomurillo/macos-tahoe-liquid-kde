# Acrylic Glass conflict handling and window backing

Validated on 2026-11-02 in CachyOS with KWin 6.7.4. Source is the working
changes over `365c03cee67d2c79bce31f5b80cc3fce9f830844`; the compiled effect
reports build identity
`e60d5ed3ab458a5f1db95ba4faae8a59092d5b7c9f506e8b7fd4c53ccfd9218a`.

## Behavior checked

- Compilation does not change any live effect or saved enable state.
- Installation disables exact known blur IDs, checks writes and live unload,
  and keeps the original enable settings across reinstalls. Failed handoff,
  shader initialization failure and uninstall can restore the saved settings.
  Recovery refuses to re-enable competitors while Acrylic Glass remains loaded.
- Nautilus's client blur works with decoration blur disabled. Both Wayland
  application identity and Xwayland resource-name matching were exercised.
- Classic keeps the original material. Tinted adds a 45% white/dark backing
  beneath application content, using the window palette. Optics, masks,
  premultiplied alpha, panels and menus retain their existing behavior.
- The KCM saves/reopens the independent backing selection across edition
  preset changes. The wizard skips the page in both navigation directions
  unless Nautilus and Acrylic Glass are selected; choices survive navigation.
  The summary fits the tested larger system font. Translation and published
  screenshot provenance checks passed.

## Evidence

Configured with `cmake -S src/offline/kwin-effects/acrylic-glass
-B /tmp/tahoe-116-effect-build -DCMAKE_BUILD_TYPE=Release`, then built with
`cmake --build /tmp/tahoe-116-effect-build -j4`. Both effect backends and the
KCM compiled. Existing unused-parameter/helper and range-loop warnings remain.

Effect binary SHA-256:

- Wayland: `f69f74d7154d3297cdbae48c4896c4d51deb98ae396a01de2b72b8d6df34e7d5`
- X11: `40a9bb1a4ab6ed986af1ee869225615bf9b9473f2b33a248d8d983743d25c6b3`

The focused regression run passed **454 tests**, with no skips, using
`MTTKDE_X11_PLUGIN=/tmp/tahoe-116-effect-build/src/liquidglass_x11.so`.
It covered Acrylic Glass configuration, conflicts, install/uninstall, filters,
materials/KCM/shader pixels, wizard/UI, theme switching, apply safety, shared
surfaces, localization and screenshot provenance. The exact final run is in
`/tmp/tahoe-116-final-tests.log`. After the KCM help wording changed, its
material and multilanguage suites were rerun: **53 passed**, recorded in
`/tmp/tahoe-116-kcm-locales-final.log`.

Three private compositor captures used:

```sh
python tests/acrylic_glass_capture.py --plugin /tmp/tahoe-116-effect-build/src/liquidglass.so --output /tmp/tahoe-116-proof-classic --identity org.gnome.Nautilus --expect changed --no-decoration-blur
python tests/acrylic_glass_capture.py --plugin /tmp/tahoe-116-effect-build/src/liquidglass.so --output /tmp/tahoe-116-proof-light --identity org.gnome.Nautilus --expect changed --no-decoration-blur --backing-tint --appearance light
python tests/acrylic_glass_capture.py --plugin /tmp/tahoe-116-effect-build/src/liquidglass.so --output /tmp/tahoe-116-proof-dark --identity org.gnome.Nautilus --expect changed --no-decoration-blur --backing-tint --appearance dark --backend xcb
```

All three verified the compositor D-Bus owner, mapped plugin inode, load,
shader readiness and visible rendering: 546240 of 614400 pixels changed with
the effect enabled. Reviewed the local comparison at
`/tmp/tahoe-116-proof-contact.png`. The same background sample averaged RGB
`[128.6,132.7,112.5]` in Classic, `[185.5,187.8,176.7]` in light Tinted, and
`[70.7,73.0,62.0]` in dark Tinted. Individual captures, logs and binary hashes
remain in those temporary directories. The X11 smoke test additionally loaded
the exact `liquidglass_x11.so` inside private KWin/Xvfb.

## Limits

These are synthetic clients and software-rendered isolated compositors on one
installed SDK, not real Nautilus application or full desktop lifecycle
qualification. No disposable libvirt VM was available. Plasma 6.6/6.8 SDKs,
other distributions, hardware GPU rendering and the reporter's machine were
not exercised. No host theme installation, release publication or new gallery
screenshots were performed. This evidence does not establish the reporter's
original cause or replace the required release CI and VM gates.
