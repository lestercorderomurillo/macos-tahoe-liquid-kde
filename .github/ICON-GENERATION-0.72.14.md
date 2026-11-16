# Deterministic icon generation: v0.72.14

Original SVG artwork is transformed offline with librsvg and Pillow. No image
model, downloaded artwork or replacement drawings are involved. The immutable
`GlassMaterial` recipe and `installer-build --material` JSON make the optics
explicit; RGB tint and worker count are separate arguments. Resolved parameters,
source hashes, generator hashes and renderer versions are recorded per theme.

Unique artworks run in four concurrent jobs by default. Aliases reuse the first
canonical artwork. Light and dark glass share identical PNG bytes. Decomposing
large minimum filters into 3x3 passes preserves every pixel while avoiding
large-window rank-selection cost. Ordered collection preserves deterministic
aliases and metadata. Failed workers cannot publish a partial CLI output.

The same representative original-artwork fixture took **3.84 s before and
0.97 s after (74.7% less time)**, including generation and PNG writes. It contains
13 unique artworks, 268 names and 536 PNG files across both glass modes. All PNG
bytes match v0.72.13 and a second run. This is a scoped measurement, not a claim
that every installation or complete-library run is 74.7% faster.

Validation: the focused icon/toolset and installer suite passed (47 cases), then
updated serial/four-worker recipe validation passed (5 selected cases), and the
worker-failure cleanup case passed. These checks cover original artwork,
parameter errors, alias preservation, exact minimum-filter equivalence,
reproducible outputs and transactional failure. No unchanged suites were repeated.
The actual icon installer and repeat-install path passed in the disposable neon
Plasma 6.8.1 / Qt 6.11.1 Wayland VM with the displayed-artwork generation fixture.
Base archives, real installation destinations and receipts remain in that test.
No full wizard, new X11 session or exhaustive icon-library qualification is claimed.
Existing reviewed photographs retain their source identity; defaults are
byte-identical, so no new desktop photography was needed.

Commands: `pytest tests/test_icon_toolset.py tests/test_icons_step.py -q`;
`pytest tests/test_icon_toolset.py -k 'recipe or small_kernel or installer' -q`;
`pytest tests/test_icon_toolset.py -k worker_failure -q`.
The benchmark invokes v0.72.13 and candidate `installer_themes` on the same
fixture and compares the SHA-256 of every PNG. Captured result and source identity:

```json
{
  "baseline": "v0.72.13",
  "scope": "13 original artworks, 268 names, 536 PNG outputs, glass blue, light/dark; not the complete library or full install time",
  "before_seconds": 3.8416384530028154,
  "after_seconds": 0.9731001179970917,
  "repeat_seconds": 0.9689287940018403,
  "reduction_percent": 74.66965905559206,
  "png_inventory_sha256": "5e9d1622e7a060674dc95fce91ddf2b31dda3a09d4972ca177533cdb45b6782b",
  "pixel_result": "All 536 PNG bytes identical to baseline and repeated generation",
  "environment": {
    "python": "3.14.7",
    "pillow": "12.3.0",
    "librsvg": "2.62.3"
  },
  "source_overrides": {
    "icon_materials.py": "fb244c23b3967e876a11bf1f1efdc812859eacc87209d41890761ce4558020a2",
    "icon_toolset.py": "60a6aa5efad6ad00889a0a6ef544e88360c3c5548a2f5679b3909acacc94339f"
  },
  "vm_source_base": "83534c8ea0bc964d23318ebc14f2635b68ea2f97",
  "vm_source_archive_sha256": "7d680f22b0be66b7e86ce38f307d53caf2939513f62adb1207701a9b2e45669f",
  "vm_install_log_sha256": "86cb897c07ae20368b2210e9b0cc021a20c38e1bacfd8bcec659750cb3cc8661"
}
```

[Full remote CI passed](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/runs/43953947694): four primary shards, eleven distro legs and Nix.
