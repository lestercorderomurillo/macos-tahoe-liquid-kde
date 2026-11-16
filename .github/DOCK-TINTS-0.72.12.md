# Dock tint qualification: v0.72.12

Glass icon generation now includes the original bundled empty/full Trash artwork.
The Dock resolves Settings and Discover application aliases to their generated
application artwork, while reserved menu symbols remain unchanged. No new icon
symbols or replacement artwork were introduced.

Focused checks:

- Icon generation, tint changes, Apps/empty/full Trash, alias preservation and
  repeat generation: 3 passed.
- Installer staging/failure preservation and native reserved-menu resolution:
  4 passed.
- Executable Dock icon-source transition/custom-pixmap/application-alias case:
  passed locally and in Fedora, openSUSE and neon SDK containers (Qt 6.11.2,
  6.12.0 and 6.11.1 respectively). This change adds no KWin API or plugin ABI.
- Disposable neon Plasma 6.8.1 VM: rebuilt the changed Dock backend, installed
  and reinstalled its package with the normal privilege setup, restarted Plasma,
  and captured actual glass icon rendering. Native build, installed load and
  rendered behavior are separate observations.

The reviewed gallery covers both editions with their own wallpaper and controls,
Nautilus red/blue in light/dark, and all eight Dock tints in light/dark. Empty/full
Trash is checked separately. Capture provenance records the exact sources and
reviewed photographs; historical gallery provenance remains unchanged.
The preview harness uses the release-screenshots Guest/capture engine because
the full-gallery CLI requires regular icons. It retains the pinned profile and
VM base, checks glass icon identity explicitly and publishes separate previews.
Only the displayed Dock artwork is generated in the focused VM fixture; this
is not a complete icon-library or complete installer-wizard qualification.
The gallery contains 44 individually reviewed real VM photographs. All generated
source hashes were verified against the bundled icon archive; Settings shares
exactly the same original SVG hash as its menu alias. Pink frames from one
interrupted generation were rejected and only those four photographs were retaken.

[Tahoe capture provenance](../src/screenshots/previews/tahoe-tint-gallery-provenance.json)
and Golden Gate's matching provenance retain original source identities. Full remote
CI passed: [all 16 Tahoe jobs](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/runs/43945881151) and [Golden Gate wrapper CI](https://github.com/lestercorderomurillo/macos-golden-gate-liquid-kde/actions/runs/43946059702).
