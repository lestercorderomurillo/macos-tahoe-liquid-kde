# Dock icon reference review

This is an offline paint comparison, not a live Plasma capture or release
approval. Original SVG drawings remain unchanged. Review the candidate with
the user before publishing any appearance change.

## Registered references

`icon-reference-frames.json` records the exact capture hashes, source URLs,
native dimensions, ICC profile hashes, crop positions, selected modes and
video timestamps. It also pins the thirteen original Dock drawings.

- [512 Pixels](https://512pixels.net/projects/aqua-screenshot-library/macos-26-tahoe/):
  six original 2880×1800 PNG captures covering Default, Dark, Clear Light/Dark
  and green Tinted Light/Dark. Preserve their embedded profile and convert
  to sRGB before sampling.
- [MacMost](https://macmost.com/customizing-your-mac-with-icon-widget-styles.html):
  red and blue Tinted Light/Dark frames from the 2560×1440 video. These are
  compressed evidence, with less reliable small-detail and color measurements.
  Blue is the displayed Automatic selection, not a verified numeric RGB input.

Reference images are downloaded locally, never bundled as project artwork.
Keep the original filenames specified by the manifest. A changed hash must
be inspected and registered again; do not silently reuse the old mode label.
Inspect the selected control in the original capture, not its filename.

## Repeat the comparison

Use the untouched unpacked bundled icon archive as `--source`. Keep one output
directory per candidate. For example, with the original captures in
`build/reference` and the unmodified checkout in `$BASELINE_REPO`:

```sh
python3 .github/scripts/icon_reference_review.py \
  --repo "$BASELINE_REPO" --reference build/reference \
  --source "$ICON_SOURCE" --output build/review/before
python3 .github/scripts/icon_reference_review.py \
  --repo . --reference build/reference --source "$ICON_SOURCE" \
  --output build/review/candidate --baseline build/review/before
```

Open the native crops and `red-blue-before-after.png` first. `comparison.png`
uses integer 2× nearest-neighbor enlargement, without smoothing or synthesized
detail. `*-selected-mode.png` retains the controls; `*-sampling.png` exposes
the measured regions. Inspect them whenever a measurement seems surprising.

`measurements.json` records median paint colors, both Finder eye polarities,
local contrast, perceptual color distances and renderer/artwork hashes.
`comparison.md` compares the same reference, selected tint and artwork before
and after. Averages diagnose changes; they do not certify an icon as matching.
Inspect individual regions and regressions, including dark-mode results.

`dock-all-modes.png` covers Apps, the ten pinned application drawings and both
Trash states. `geometry.json` records the original hashes and coverage check.
Check aliases through the existing installer generator tests separately.

## Calibration and limits

The current paint transfer interpolates measured red, green and blue anchors
in OKLab hue space. The foreground and background have separate transfers.
Exposed ink and details enclosed by a foreground shape use different paint
roles. Source gradients use their own tonal range. Original rims and shadows
remain original layers, and unplated objects retain their material.

All three reference hues are calibration inputs; none is an independent
validation set. New hues need new reference captures before claiming fidelity.
The input tint is the displayed selector swatch sampled in sRGB, not an
assertion about Apple's internal color parameters.

The comparison estimates the hidden Dock backing from clear crop corners.
It does not recover live macOS blur/refraction. Static cached PNGs cannot
reproduce that wallpaper-dependent material exactly. Dark tinted paint keeps
enough opacity for the original eyes and lettering to remain visible on bright
wallpapers; this currently differs from the dark reference surfaces.

Original drawings also differ from Apple's drawings, especially Apps' internal
relief and Calendar's date. Compare semantic paint regions instead of hiding
those differences with geometric warping or reporting whole-image pixel error
as a meaningful score. No current measurement establishes a 1:1 match.
