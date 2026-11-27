# Liquid Glass desktop widgets

`liquidglass-kde-widgets.tar.zst` holds the desktop widgets of
[liquidglass-kde-widgets](https://github.com/jaxparrow07/liquidglass-kde-widgets)
by jaxparrow07 (GPL-3.0, see `LICENSE`), packaged with their own
`package.sh -a`: calendar, clocks, cities, music, timer and weather.

Two parts are by RoxasYTB and are not in the upstream repository yet:

- the **Photos** widget (jaxparrow07/liquidglass-kde-widgets#41);
- the **automatic Solid/Glass style**: Solid while the desktop is clear, Glass
  as soon as a window is open on the screen (jaxparrow07/liquidglass-kde-widgets#40).

Sources:

| Part | Repository | Commit |
|---|---|---|
| Widget set | jaxparrow07/liquidglass-kde-widgets `master` | `0d1b9fe34ca3d21fc6f31b599990490d637ce8f8` |
| Automatic style | RoxasYTB/liquidglass-kde-widgets `feat/auto-style` | `9040b9b075b511264579d965f25c43b30f9daef3` |
| Photos widget | RoxasYTB/liquidglass-kde-widgets `feat/photos-widget` | `0cf99d0da0c099f4aae21cefd0234bf76f51bbd5` |

The widgets ship the same SF Pro faces as the theme's own fonts, plus the iOS
faces they use for the clock styles.

To rebuild: merge the two branches onto upstream `master`, run
`./package.sh -a`, unzip each `.plasmoid` into a directory named after its
`KPlugin.Id`, apply `patch -p0 < calendar-providers.patch` from the unpacked widget directory,
apply `patch -p1 < widget-blur-transition.patch` inside each desktop widget package that contains `contents/ui/components/LiquidGlass.qml`,
apply `patch -p1 < widget-selection.patch` in those same packages,
then `tar -cf - . | zstd -19 --long=27`.
