# Adaptive Contrast qualification

Candidate `a8dc6781b78aa87ba7a2dccfb7b9889b0fe92d9a`. The component photographs come from the installed desktops. The Qt renderer results below come from the approved contrast candidate. Repeated shaping on the integrated implementation returned identical geometry after glyph outline caching. Both final desktop installations include the v0.85.32 Launchpad and its options menu.

| Scope | Tahoe | Golden Gate |
| --- | --- | --- |
| Continuous foreground · installed two-tone boundary | [Open screenshot](tahoe/scopes/continuous-letter-gradient.png) | [Open screenshot](golden-gate/scopes/continuous-letter-gradient.png) |
| Letter · Glass Text Clock at 100% text tint | [Open screenshot](tahoe/scopes/glass-clock-letter.png) | [Open screenshot](golden-gate/scopes/glass-clock-letter.png) |
| Line · wrapped launcher grid label | [Open screenshot](tahoe/scopes/wrapped-launcher-line.png) | [Open screenshot](golden-gate/scopes/wrapped-launcher-line.png) |
| Bubble · neighboring Control Center tiles | [Open screenshot](tahoe/scopes/control-center-bubbles.png) | [Open screenshot](golden-gate/scopes/control-center-bubbles.png) |
| Component · visible launcher category strip | [Open screenshot](tahoe/scopes/launcher-category-component.png) | [Open screenshot](golden-gate/scopes/launcher-category-component.png) |
| Line · styled notification with link | [Open screenshot](tahoe/scopes/rich-notification-lines.png) | [Open screenshot](golden-gate/scopes/rich-notification-lines.png) |
| Letter · selected native menu item | [Open screenshot](tahoe/scopes/selected-native-letter.png) | [Open screenshot](golden-gate/scopes/selected-native-letter.png) |

## Exact pixels in the installed compositor

A diagnostic panel applet uses the installed panel sampler and glyph renderer. The panel is transparent over the desktop. The measurement places a single physical-pixel white stripe under the second of two shaped letters. Captures with the text hidden record the visible material. The original raw correction decisions are recorded separately from the smoothed final ink. The compositor reply for the two positions is recorded independently of the screenshot.

| Edition | Physical centers | Visible RGB | Raw decisions | Capture |
| --- | --- | --- | --- | --- |
| tahoe | [[3559, 14], [3564, 14]] | [[0, 0, 0], [251, 251, 251]] | #ffffff, #000000 | [background](tahoe/scopes/transparent-under-glyphs.png) · [ink](tahoe/scopes/transparent-glyphs.png) · [measurements](tahoe/pixel-verification.json) |
| golden-gate | [[3559, 14], [3564, 14]] | [[0, 0, 0], [251, 251, 251]] | #ffffff, #000000 | [background](golden-gate/scopes/transparent-under-glyphs.png) · [ink](golden-gate/scopes/transparent-glyphs.png) · [measurements](golden-gate/pixel-verification.json) |

### Installed launcher popup

Both installed launchers supplied distinct sparse color values within one coarse grid cell.

- tahoe returned #202124 and #ffffff in cell [26, 22]. [Sparse sample record](tahoe/launcher-sparse.json)
- golden-gate returned #202124 and #ffffff in cell [26, 22]. [Sparse sample record](golden-gate/launcher-sparse.json)

## Smoothness and antialiasing

The Qt Quick test paints a black-to-white ramp through the candidate shader, reverses the target, and reads back the rendered framebuffer. Transparent mask pixels preserved the magenta backing, including pixels inside the layer bounds. The same shader draws the enabled letter overlays in the installed QML components. Native menus use the same gradient interpolation with the original Qt style mask.

~~~text
ramp endpoints 1 255 max adjacent delta 3 at DPR 1
moving endpoint 0 -> 76 -> 254
ramp endpoints 0 254 max adjacent delta 5 at DPR 1.25
moving endpoint 0 -> 107 -> 255
ramp endpoints 0 254 max adjacent delta 4 at DPR 1.45
moving endpoint 0 -> 105 -> 255
~~~

## Material, shaping, clipping and motion

~~~text
Animated Qt Quick item: 30 observed positions; stable on gray 77/78, returned to black on gray 100.
Captured glass shader output: backing gray 160, material samples 104 and 157
SVG, gradient and transparent pixels matched the rendered window at 1x; glyph centers at physical x=6 and 9 resolved black and white inside one grid cell.
CONTROL_GLASS_REGIONS_OK
Animated Qt Quick item: 30 observed positions; stable on gray 77/78, returned to black on gray 100.
Captured glass shader output: backing gray 160, material samples 103 and 157
SVG, gradient and transparent pixels matched the rendered window at 1.25x; glyph centers at physical x=8 and 11 resolved black and white inside one grid cell.
CONTROL_GLASS_REGIONS_OK
Animated Qt Quick item: 30 observed positions; stable on gray 77/78, returned to black on gray 100.
Captured glass shader output: backing gray 160, material samples 103 and 157
SVG, gradient and transparent pixels matched the rendered window at 1.45x; glyph centers at physical x=9 and 13 resolved black and white inside one grid cell.
CONTROL_GLASS_REGIONS_OK
~~~

A combining accent stayed with its base character. Wrapped runs recovered the source string. The category sampler excluded clipped regions. The grouped probe produced matching ink for two labels in the same bubble.

The installed single-pixel test exercises the panel path. The opaque split-SVG test exercises the popup resolver. Both installed launcher popups also returned distinct near-black and white values for neighboring positions within one coarse cell. A separate custom transparent top-level window did not return a sparse reply. Device-pixel precision for that window type remains unverified. The gallery stress frames retain the configured material and its blur.

## Correction and presets

Already-legible ink stayed unchanged. A target within the old cap reached 78. A translucent target needed 105 against the old 102 cap. The bounded fallback stopped at +112. A running QML consumer applied a valid sample count of 21, kept it after invalid input, returned base ink when disabled, and restored 15 when reset. The native settings dialog rejected an invalid import, saved and reopened the valid preset, and restored defaults.

<!-- issue-summary -->

The installed boundary demonstration compares neighboring glyph centers over a one-device-pixel stripe at 125%. Both installed launchers separately returned distinct foreground sample values within the same coarse grid cell. The Qt probes also cover opaque SVG, translucent gradient, transparent pixels, shader-rendered glass, grouping, clipping, shaping and 30 motion positions. The foreground renderer preserved transparent mask pixels and produced intermediate colors during a live target reversal. Visual approval is pending.

The combined source passed the launcher interaction and clipboard cases in light and dark configurations for both editions. KWin X11 6.6.5 and Wayland 6.7.4 compiled the integrated material classification. The installed PNGs exercise Plasma 6.8.1 Wayland.
