# Third-party notices and license scope

This index records known license locations; it is not a claim that every
bundled asset has a fully established chain of title. Preserve file-level
notices and original copyright holders. [NOTICE](NOTICE) covers original
project contributions only, and [LICENSE](LICENSE) covers the GPLv3 work as
a whole without replacing independent component grants.

| Material | License or notice to retain |
| --- | --- |
| Acrylic Glass | [Bundled GPLv3 text](src/offline/kwin-effects/acrylic-glass/LICENSE) and existing source copyright/SPDX headers, including GPL-2.0-or-later and GPL-3.0-or-later files. |
| Launcher | [Original GPLv2 text](src/offline/plasmoids/org.kde.mac-tahoe-liquid-kde.launcher/LICENSE-TahoeLauncher), file notices, and package metadata. The license text alone does not resolve version options for every file. |
| Panel Colorizer | [Bundled license](src/offline/plasmoids/luisbocanegra.panel.colorizer/LICENSE) and source notices. |
| QuickBar integration | [MIT notice](LICENSES/MIT-QuickBar.txt), original KDE/QuickBar file notices, and [integration provenance](docs/topbar-integration.md). Selected menu search and popup lifecycle code is adapted from commit `213a583adfd257ed420c77ef2cf1443a709a3425`; file-level GPL alternatives remain intact. |
| KDE-derived plasmoids and integration code | Existing copyright/SPDX headers, including GPL-2.0-or-later, LGPL-2.0-or-later, LGPL-2.1-or-later, and KDE alternative grants. The alternatives remain available as stated in each file. |
| Firefox theme | [MIT notice](src/offline/firefox/LICENSE.MacTahoe), including the WhiteSur Developers copyright. |
| GTK theme | [MIT upstream notice](LICENSES/MIT-MacTahoe.txt) from MacTahoe-gtk-theme; project modifications and any separately licensed material retain their own notices. |
| Lucide copy icons | [Lucide license and copyright notices](LICENSES/Lucide.txt); the bundled light/dark variants identify Lucide and ISC in their SVG comments. The complete upstream notice also records Feather-derived icon terms. |
| Kvantum source archive | Preserve `Kvantum-1.1.8/Kvantum/COPYING` and file notices inside `src/offline/kvantum-engine/Kvantum-1.1.8.tar.xz`. |
| Optional Rounded Corners | The license and file notices of the checksum-pinned source selected in [rounded_corners.py](src/scripts/steps/rounded_corners.py); the source is downloaded separately. |
| Distribution logos in the README | [Per-logo sources, licenses, changes, and hashes](src/screenshots/distros/sources.json). [Simple Icons' CC0 dedication](LICENSES/CC0-Simple-Icons.txt) does not erase rights in the underlying brands or override per-logo license information. |
| Apple wallpapers, SF Pro/SF Mono fonts, system sounds, and macOS emblems | Outside the project's GPL grant. See wallpaper metadata and the [sound provenance notice](src/offline/sounds/MacTahoeLiquidKde/NOTICE). Public availability and inclusion here do not grant redistribution permission. |
| Screenshots and contributor portraits | Preserve applicable source and authorship information. Embedded third-party artwork and personal likenesses are not made project-owned by inclusion in an image. |

Supplemental [GPLv2](LICENSES/GPL-2.0.txt),
[LGPLv2](LICENSES/LGPL-2.0.txt), and [LGPLv2.1](LICENSES/LGPL-2.1.txt)
texts accompany existing file-level grants. Their presence does not apply a
new license to unrelated files. [License text sources](LICENSES/sources.json)
record immutable references and hashes, not a claim that every bundled asset
was produced from those exact upstream revisions.

## Provenance gaps to keep visible

The bundled icon and cursor archives currently contain no standalone license
text (an icon named `license.svg` is artwork, not a license). The repository
identifies MacTahoe-icon-theme as a source; its upstream GPLv3 notice is a
reference, not proof of every nested asset's origin. Before refreshing or
separately repackaging these bundles, establish the exact source and applicable
notices for each included family and carry those notices with the payload.
Do not invent a copyright owner or blanket-license unverified assets.

The upstream [MacTahoe icon license](https://github.com/vinceliuice/MacTahoe-icon-theme/blob/839848b9a8a38a92a6936e30c4abe35cc6f2546d/COPYING)
and [GTK license](https://github.com/vinceliuice/MacTahoe-gtk-theme/blob/1e45e19f510edb8cde18fa84d6cd5319f60b086b/COPYING)
are reference points; existing embedded notices and the actual source history
must be checked for the version being redistributed. The GPLv3 notice at the
repository root does not resolve missing third-party permissions.

This index preserves attribution separately from the manually maintained
README Credits section. Corrections should include the affected path,
original source, license evidence, and the proposed notice.

The Global Menu also bundles KDE plasma-wayland-protocols `fake-input.xml`
(commit `1db07441870d54157e937674b99380a7dcc0fb32`), copyright 2015 Martin
Gräßlin, LGPL-2.1-or-later. The original notice is retained in the XML;
see `LICENSES/LGPL-2.1.txt` and `docs/topbar-integration.md`.
