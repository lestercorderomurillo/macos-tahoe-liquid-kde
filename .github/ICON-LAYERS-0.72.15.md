# Original icon layers: v0.72.15

Icon variants now repaint the original background and foreground layers. They
retain the source contour, cutouts, existing rims and shadows. Unplated icons,
including empty/full Trash, never receive a generated tile. Regular dark uses
the same original artwork as light, rather than an alternate illustration.
Tinted light and dark are rendered separately instead of sharing PNG bytes.
Installer samples use the same renderer; unchanged samples retain their files.

## References and appearance mapping

- [Apple Icon Composer](https://developer.apple.com/icon-composer/) describes a
  single layered design with background and foreground groups.
- [Apple's Tahoe feature guide](https://www.apple.com/os/pdf/All_New_Features_macOS_Tahoe_Sept_2025.pdf)
  distinguishes default, dark, clear light/dark, and tinted light/dark. Light
  tint colors the background; dark tint colors the foreground.
- [MacMost's real Tahoe demonstration](https://macmost.com/customizing-your-mac-with-icon-widget-styles.html)
  provides the visual comparisons: default/dark around 2:10/2:35, clear light/dark
  around 4:10/4:23, blue light/dark at 8:13/8:19 and red light/dark at 8:44/9:03.
  These are compressed video references, not pixel-exact color measurements.

The existing installer `glass` selection produces the tinted appearance for
its chosen hue. The offline icon-toolset also exposes clear light/dark, default
light/dark and monochrome variants. This repair does not add installer choices.
Colorization remains static; it does not implement macOS live lighting/refraction.

## Focused qualification

Changed paths: icon material rendering, theme generation and installer samples.
Direct consumers: installer icon generation/previews and offline icon-toolset.
Both editions use the same renderer; no native ABI, shaders, dependencies or
appearance scheduling code changed.

- `pytest tests/test_icon_toolset.py -q`: 46 passing cases; the one obsolete
  identical-light/dark recipe expectation was corrected and passed separately.
- After the final affected edits: focused regular-dark, alias, contrast,
  arbitrary RGB, geometry and recipe checks passed. Final commands:
  `pytest tests/test_icon_toolset.py -k 'every_alias or regular_dark or finder_eyes or geometry or recipe_is' -q`
  (eight passed; two metadata failures repaired), then
  `pytest tests/test_icon_toolset.py -k 'every_alias or recipe_is' -q` (two passed),
  and `pytest tests/test_icon_toolset.py -k 'recipe_is or geometry' -q` (three passed).
  Synthetic geometry includes an unplated silhouette with an interior cutout.
  The real-artwork contrast scenario covers all eight selectable tints.
- Disposable neon Plasma 6.8.1 / Qt 6.11.1 Wayland VM: 13 original displayed
  artworks, including Apps, every pinned application and empty/full Trash.
  All six appearance variants preserve source coverage; clear may reduce opacity.
  Aliases were checked separately. Final generation reproduced all 536 captured
  PNGs per tint (red and blue), allowing the reviewed captures to be reused after
  regular-mode and metadata corrections.
- Twelve reviewed Dock captures cover red/blue, light/dark, both editions with
  their own wallpapers/controls, and blue empty/full Trash. Their manifests record
  source hashes, capture harness, profile, crop and output hashes.

[Tahoe capture evidence](../src/screenshots/previews/tahoe-icon-layers-provenance.json).
Golden Gate carries its own matching evidence and photographs.

No full installer lifecycle, new X11 session or automatic schedule boundary was
run: those paths were not changed. Default/clear received focused renderer checks;
the live desktop captures cover tinted red/blue. Other application artwork follows
the same renderer but was not exhaustively visually reviewed. Previous photographs
remain at their original provenance; outdated color examples are labeled.
The previous dev CI passed (run 43953947694); full new CI runs asynchronously.
