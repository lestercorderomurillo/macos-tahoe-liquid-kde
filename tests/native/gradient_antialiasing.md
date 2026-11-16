# Gradient edge and exclusion qualification, v0.72.2

Dock and Control Center omit the material gradient. Control Center's separate
QML gradient was also removed; its edition-specific solid translucent fill and
thin rim remain. Menus keep their configured gradient.

The native renderer now recovers disconnected rounded blur islands separately
and draws their complete bounds through the shader's fractional coverage mask.
Unknown cutouts retain their explicit regions. The before/after X11 fixture
restored 16 fractional edge pixels in the sampled corner (v0.72.1: zero), with
zero changed pixels in the gap between islands.

Reproduce the executable regression in an isolated compositor:

```bash
python3 tests/acrylic_glass_capture.py \
  --plugin build/kwin-effects/acrylic-glass/src/liquidglass_x11.so \
  --output /tmp/glass-islands-new --compositor x11 --identity GradientProbe \
  --material golden-gate --expect changed --popup-islands
```

The same edge assertion fails on v0.72.1. The probe owns its Xvfb, D-Bus,
configuration and plugin directory; it never installs on the host.

Focused geometry/shader/parser checks: 39 passed, 3 unrelated GTK/Kvantum
checks skipped in the Arch container. After observing Wayland's
`org.kde.plasmashell` identity, the final native shader/classification test
passed again. Capture safety: 6 passed. Native effects built on the supported
6.6 and 6.8 SDK branches and the host 6.7 SDK, without host installation.

Disposable pinned KDE neon VM: Plasma 6.8.1 / Qt 6.11.1, each edition's own
wallpaper and controls, install/reinstall and light/dark component frames.
The production QML tile pixel test additionally exercises both edition markers
through light/dark/light, asserting equal upper/lower fill pixels and preserved
fill opacity. Golden Gate's compositor-gradient toggle changes menu pixels but
leaves Dock and Control Center unchanged. See release-evidence.json for source
identities, captures, logs, retained evidence and exact coverage limits.

The first X11 fixture used xprop, which truncated the published region;
those captures were rejected. The retained probe writes the complete property
through Xlib. Capture setup frames with incorrect icon appearance or missing
popups were also rejected. The scoped installer setup was replaced with the
normal edition defaults before reviewing photographs.
