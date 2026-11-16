# Original icon detail and contrast: v0.72.13

The glass renderer previously compressed source blacks into a silver range and
then tinted that range again. Finder's left eye and smile approached the blue
plate's luminance; Calendar lettering also lost separation. The repair preserves
the original tonal range, strengthens sparse original lettering without flattening
larger shaded forms, stabilizes the translucent plate over dark wallpaper and
adds a restrained relief shadow for pale shapes on bright tints. Regular icon
rendering and all source artwork remain unchanged.

Reference review used Apple's [actual Tahoe desktop photography](https://www.apple.com/newsroom/2025/06/macos-tahoe-26-makes-the-mac-more-capable-productive-and-intelligent-than-ever/),
[app icon guidance](https://developer.apple.com/design/human-interface-guidelines/app-icons),
and [contrast guidance](https://developer.apple.com/design/human-interface-guidelines/color).
These inform material separation and legibility, not a claim of pixel-identical
Apple rendering. No reference artwork was imported or redrawn.

`pytest tests/test_icon_toolset.py -k "glass or regular_dark"`: 10 passed.
The added executable case renders the actual bundled Finder and Calendar art
through the installer path at 64px, across all eight tints, both modes and light/
dark backdrops. Finder's eye and median Calendar letter contrast each exceed
3:1. This is a targeted icon-detail check, not certification of every glyph or
text accessibility across the complete icon library. Existing checks retain
regular-artwork behavior, aliases, source notices and glass alpha.

Focused VM qualification and refreshed Dock photographs are recorded with their
actual source hashes. The installer fixture limits generated artwork to displayed
Dock applications, Apps and both Trash states while retaining the real installer
archive staging, installation destinations and repeat-install behavior. Main
README color tables contain eight colors only; Trash states remain test evidence.
[Full remote CI passed](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/runs/43951362726), including all four primary shards, eleven distro legs and Nix.

Reviewed 22 focused Dock photographs: eight light tints per edition and blue
light/dark with empty/full Trash. Each edition uses its own wallpaper and
controls. [Capture provenance](../src/screenshots/previews/tahoe-icon-contrast-provenance.json)
records the archive, renderer override, original artwork hashes and image hashes.
The original artwork checks passed for all eight generated tints and both modes.
Golden Gate pin/archive validation and focused wrapper checks: 45 passed.
