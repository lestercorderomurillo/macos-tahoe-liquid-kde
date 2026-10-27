# Window controls

The native installer offers **Flat** and **Glassy** close, minimize and maximize
buttons. Tahoe starts with Flat; Golden Gate starts with Glassy. An explicit
choice overrides the edition for this installation. A new wizard launch starts
with its source edition's defaults again.

`src/scripts/window_controls.py` constructs the glassy controls offline from
circles, paths and gradients. It does not import the fork's SVG drawings.
The flat controls retain the bundled Tahoe artwork and its notices. Both styles
share the existing frame geometry and configurable window shadows.

The visual treatment uses solid red, yellow and green for Flat. Glassy follows
the maintainer's supplied close-up reference: saturated red, yellow and green
faces, a narrow illuminated rim and a gentle increase in brightness toward the
bottom. The broad white upper reflection and separate lower arc were removed;
they made the earlier candidate look too much like classic Aqua. Hover uses a
heavier close cross and minimize bar, with the paired maximize triangles.
Inactive controls become neutral; pressing adds a darker response and disabled
states are fainter. These are independently drawn static SVG approximations,
not extracted Apple assets or dynamic optical refraction. KDE's additional
window buttons retain their existing artwork.

Both Aurorae families are installed. The choice selects the matching family
in the installer, global-theme defaults, configuration verifier and standalone
theme switcher. The switcher embeds the transaction's choice so scheduled,
login and manual light/dark transitions retain it without the source checkout.
GTK 3/4 uses matching SVGs for Glassy and the original assets for Flat; each
reinstallation starts from fresh bundled GTK sources. GTK below 4.20 requires
explicit light/dark selection for literal SVG URLs in its adaptive stylesheet.
Nix staging retains the edition default without running the graphical installer.

Standalone GTK SVGs use a 128×128 intrinsic canvas with a 16×16 view box;
the stylesheet keeps the buttons at their existing 16 logical pixels. This
prevents GTK from enlarging a low-resolution raster on high-DPI displays.
Aurorae state-sheet dimensions and frame geometry remain unchanged.

The installer previews are lossless crops of a focused Nautilus window in a
disposable VM at 3840×2160 with 4× display scale. Each crop includes the rounded
corner, all three controls, surrounding title bar and the start of the sidebar.
The separate Window shadows page compares None, Soft, Medium and Hard with
eight additional Nautilus crops: four levels in each appearance mode. Those
crops show the lower window corner against an identical neutral background,
with room for the shadow to fade. Medium remains the default.
`src/installer/assets/sources.json` records the original capture hash, crop,
VM image identity and content-addressed output filename. These are separate
from the complete fixed-profile release screenshot bundle.

Component checks cover both styles in both editions, Aurorae install/reinstall
and removal, GTK asset selection, standalone switching and wizard navigation.
Native previews establish the rendered title-bar appearance; release captures
separately verify the complete desktop and each installer page.

## Fork capture investigation

Inspected jadetheda's fork at commit
[`771b4b4`](https://github.com/jadetheda/macos-golden-gate-liquid-kde/tree/771b4b4b7ff1f0c50c3f93cdf12262d12cfb19da).
Its [runner script](https://github.com/jadetheda/macos-golden-gate-liquid-kde/blob/771b4b4b7ff1f0c50c3f93cdf12262d12cfb19da/tools/capture_runner.sh)
combines Swift/AppKit window screenshots, `assetutil` catalog inspection and
an attempted `cartool` extraction. These are different outputs: a screenshot
of a button is not an extracted transparent control asset.

In completed [run 40429416668](https://github.com/jadetheda/macos-golden-gate-liquid-kde/actions/runs/40429416668),
the `macos-latest` artifact reports macOS 26.6.2 and contains 20 live-capture PNGs
and 26 catalog JSON files, with no images extracted from those catalogs.
The nine cluster PNGs within each appearance mode have identical decoded RGBA
pixels and show gray controls, including the files labeled hover and pressed.
The decoded-pixel SHA-256 prefixes are `c78c54824c0c` for light and `05fe9a98a775`
for dark. Thus that successful workflow does not establish a usable set of
active/hover/pressed button assets. Its shell script tolerates extraction
failures, so the green job status alone is insufficient evidence.

Native capture can be reproduced on a macOS runner, but this inspected output
is not suitable for the theme. No fork artwork, Apple system assets or fork
scripts were imported. We retain the independently constructed SVGs and the
maintainer-requested softer treatment, refined against the close-up they supplied.
