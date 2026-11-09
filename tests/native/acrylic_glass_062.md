# Acrylic Glass 0.62.0 compatibility audit

Tested on November 5, 2026 (America/Costa_Rica), against the working tree
over `d59afae127628c71e3675f2832157af75e5e9d51`. This is development evidence,
not a published-release or full desktop-lifecycle qualification.

## Actual rendering

Every passing row ran the real compositor, loaded the specified compiled
plugin, checked its mapped inode and shader readiness, and compared captured
effect-off/on pixels. Builds alone were not counted.

| Runtime | Environment | Renderer | Pixels and live built-in blur handoff |
| --- | --- | --- | --- |
| KWin 6.6.4 Wayland | Fedora 44 SDK container | RX 9070 XT, Mesa 26.0.3, OpenGL 4.6 | Pass |
| KWin 6.7.4 Wayland | Private CachyOS session | Ryzen integrated GPU, Mesa 26.2.1, OpenGL 4.6 | Pass |
| KWin 6.8.0 Wayland | Arch SDK container, before opacity retirement | RX 9070 XT, Mesa 26.2.5, GLES 3.2 | Pass |
| KWin 6.8.2 Wayland | Arch, kwin 6.8.2-2 / plasma-workspace 6.8.2-1 | RX 9070 XT, Mesa 26.2.6, GLES 3.2 | Pass, final shader |
| KWin 6.6.5 X11 | Arch archive dated 2026-05-20, private Xvfb | Mesa software OpenGL | Pass |
| KWin 6.7.4 X11 | Private CachyOS/Xvfb session | Mesa software OpenGL | Pass |
| KWin 6.8 X11 | No maintained upstream release | — | Not applicable; not substituted with Xwayland |

The [KWin X11 retirement notice](https://invent.kde.org/plasma/kwin-x11/-/commit/8919c58c7)
identifies Plasma/6.7 as its last maintained branch. A Plasma 6.8 distribution
can still carry an older KWin X11 package; test that package's actual version.

The baseline synthetic surface changed 546,240 of 614,400 pixels on each
tested runtime. The tests also rejected blank captures and checked that the
opaque client rectangle and checkerboard background were present. No shader
compile/link, invalid-GL, or framebuffer-allocation errors were found in the
passing compositor logs.

Real Nautilus, with bundled GTK assets staged into the private configuration,
was additionally captured and visually inspected on KWin 6.7.4: light Tahoe
and dark Golden Gate/Tinted on Wayland, and light Tahoe on native X11.
Changed-pixel counts were 86,352, 87,620 and 86,264 respectively. These are real
application windows, not the synthetic client renamed to Nautilus.
GPU fractional-scale captures at 150% also passed for Tahoe/Tinted on 6.6 and
Golden Gate/dark Tinted on 6.8. Dark Golden Gate/Tinted passed on X11 6.6.

## Reproduced Nautilus failure

On Arch/KWin 6.8.2, a control build omitting only the Nautilus client fallback
produced **zero changed pixels** with real Nautilus, bundled dark GTK assets
and decoration blur disabled. The corrected build produced **88,158 changed
pixels**, with visible blurred sidebar detail. The final build after retiring
material opacity produced the same count, including with an old
`MaterialOpacity=0` setting. This reproduces one concrete cause of missing
Nautilus blur; it does not establish the reporter’s saved settings or competing
effect state. The original [issue #116](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/116)
only documents excessive transparency.

The full-client fallback depending on the decoration option already existed
in the initial bundled effect (`ec2c5e91`, March 28, 2026); it was not introduced
by Plasma 6.8.2. GTK transparency does not itself request compositor blur.

## Fixes and upstream review

- Reproduced the previous Nautilus fallback's ambiguous `Region(QRect)`
  constructor failure on KWin 6.6.4. An empty, present content request now
  selects the whole client and avoids applying a decoration offset twice.
  Native region regressions cover decorated/undecorated windows, case-insensitive
  Nautilus identity, unrelated applications and preserved explicit requests.
- Integrated the scene damage bounds required by KWin's
  [background-effect repaint change](https://invent.kde.org/plasma/kwin/-/commit/85666673a2ab7ca85fad81a917bd4059c66d0fb2).
  The installed SDK header selects this API, including its 6.6 backport;
  older SDKs and X11 retain their existing path. Reconfiguration refreshes
  bounds and sampling expansion through the existing region-update loop.
- Removed the Glass opacity control, KConfig entry, preset values and shader
  multiplier. Old saved values are ignored. Blur strength, window animation
  opacity, Dock coverage and edition gradients retain their distinct roles.
- Added the actual `better_blur_dx`, `better_blur_dx_woapi`, `glass_x11` and
  `forceblur_x11` competitor IDs,
  verified from upstream metadata/build targets. Existing default Blur,
  Glass, Force Blur and legacy IDs remain covered; Rounded Corners is excluded.
- A failed live-effect query now stops activation. Recovery retains its
  snapshot and does not re-enable competitors until Acrylic Glass is confirmed
  unloaded. Exact original settings, absent keys and later user edits survive.

Reviewed KWin branch tips: 6.6 `b83db456e72c031dbe650316d6f5e6a7bb7ff57b`,
6.7 `c1f623739f4e819d291b1ddda50d5a57674a54f5`,
6.8 `232eff12a64c581e0bb10ef764e7afaed4d1f3a9`.
Reviewed relevant Glass history through
[`884593287ec64503ed4158037ba0ed4d79c5d003`](https://github.com/4v3ngR/kwin-effects-glass/commit/884593287ec64503ed4158037ba0ed4d79c5d003).
The 6.8 boolean draw ABI, explicit modern shader selection, disabled blending
during intermediate blur passes, translucent prepaint handling and SSD-only
client-region offset were already represented locally. The upstream
GTK/Electron opacity fallback addresses opaque-region subtraction, which this
renderer does not perform; importing it wholesale would not fix this path.
Upstream material/specular feature additions are not compatibility fixes and
were not used to replace the project's material presets.

## Conflict behavior tested

Each runtime's passing built-in Blur control loaded before the installer
handoff. The actual installer functions disabled/unloaded it, preserved the
same original snapshot on reinstall, refused recovery while Acrylic Glass
was loaded, then restored and reloaded Blur after Acrylic Glass unloaded.
The subsequent Acrylic Glass capture proved shader rendering after handoff.
KConfig regressions also exercise failed writes, a still-loaded competitor,
corrupt snapshots, unknown live state and preservation of later user edits.
The earlier focused run passed **114 tests**, without skips, including native
shader/KCM pixels, region logic, installer lifecycle and private X11 loading.
The final full integration run passed 2,192 tests, skipped three conditional
checks and exposed two stale preset-test expectations after opacity retirement.
After correcting those expectations to retain and ignore the old key, all
**22 material/preset tests passed**, including native KCM and shader pixels.
No production code changed after that full run. The prepared Golden Gate
source passed **69 affected tests** covering presets, conflicts and the wizard.

The host's installed Better Blur DX was built for KWin 6.6.3 and was rejected
by KWin 6.7.4. That failed control is **not** counted as a passing live
Better Blur DX test. Its exact ID and saved-state handling are covered, but
this audit does not claim live rendering/handoff of every third-party binary.

## Reproduction and retained evidence

The extended `tests/acrylic_glass_capture.py` supports native X11,
GPU rendering, direct Wayland screenshot capture, actual Nautilus, material
presets and live conflict tests. See CONTRIBUTING.md for prerequisites.
Typical invocations, after building against the matching SDK:

```sh
python tests/acrylic_glass_capture.py --plugin /path/to/liquidglass.so --output /tmp/new-wayland-proof --identity org.gnome.Nautilus --expect changed --no-decoration-blur --renderer hardware --conflicts
python tests/acrylic_glass_capture.py --plugin /path/to/liquidglass_x11.so --output /tmp/new-x11-proof --identity org.gnome.Nautilus --expect changed --no-decoration-blur --compositor x11 --conflicts
python tests/acrylic_glass_capture.py --plugin /path/to/liquidglass.so --output /tmp/new-nautilus-proof --identity org.gnome.Nautilus --expect changed --no-decoration-blur --renderer hardware --application nautilus --material tahoe
```

Local evidence is retained in `build/acrylic-062-evidence/`: PNG comparisons,
JSON measurements, GPU/compositor support information, logs, the pinned X11
image recipe, initial failing 6.6 build log, upstream repaint diff, source-file
hashes and an evidence SHA-256 manifest. Original build trees and additional
attempt logs remain under `/tmp/tahoe-062-audit/`. These paths are not published
desktop screenshots and are not substitutes for release CI.

## Installed desktop captures

The pinned disposable KDE neon VM installed source commit
`5fbf5c9f10d586b6ec043eacec19abeeaa48f50c` separately for Tahoe and Golden Gate.
All 94 original 3840×2160 frames were visually inspected: launcher, Dock,
system/context menus, Nautilus, About, all sixteen installer pages in light
and dark modes, and the shared boot/shutdown frames. The first capture attempt
was discarded because the light Dock was hidden; the recipe now reveals it
and rejects hidden panels before capture. These captures establish installation
and light/dark rendering in that VM, not a full lifecycle qualification.
The reviewed bundle is `build/release-capture/v0.62.0-retry/`.

## Limits

These are real compositor processes and GPU/software rendering, with disposable
container/private-session state. They do not qualify a complete installed
Plasma desktop, reboot/uninstall lifecycle, NVIDIA/Intel hardware, HDR,
multi-monitor layouts or every third-party effect. No host installer was run.
The Arch userspace matches the reported 6.8.2 versions; containers share the
host CachyOS kernel 7.2.0, not the reporter’s Arch kernel 7.2.11.

The added partial-damage probe also passed with the pre-fix plugin. Its result
is inconclusive as a regression reproducer; it does not prove the repaint
defect was reproduced and eliminated. The scene integration follows the
reviewed upstream API contract and was built/rendered on all available targets.
Release publication and exact-commit CI remain separate gates.
