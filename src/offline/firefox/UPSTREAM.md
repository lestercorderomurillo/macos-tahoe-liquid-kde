# Firefox theme provenance

The CSS and SVG assets in `MacTahoeLiquidKde/` are a maintained, data-only
fork of the [`other/firefox`](https://github.com/vinceliuice/MacTahoe-gtk-theme/tree/main/other/firefox)
assets from `vinceliuice/MacTahoe-gtk-theme`, pinned from commit
`aaac1c5451fc2f14e02ec1d9b606baa41589cd41` (archive SHA-256
`5fabb43620793e171e6356076958deaafff704e3dc553697b2ede5f5d685bd14`).

Upstream's `install.sh` is intentionally neither bundled nor executed. This
project's Python installer handles profile discovery, per-install backups,
managed CSS imports, and reversible uninstall behavior. The asset fork keeps
the upstream MIT license in `LICENSE.MacTahoe`.
