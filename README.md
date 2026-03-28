# MacOS Tahoe Liquid Glass for KDE Plasma

A full macOS Tahoe-style desktop experience for KDE Plasma — going beyond a simple theme. MacTahoe Liquid KDE bundles a curated collection of widgets, GTK & KDE themes, SDDM login screen, window decorations, icons, cursors, fonts, sounds, wallpapers, and a custom Electron app menu, bringing a cohesive Tahoe look to every layer of your desktop.

Inspired by [Pear OS](https://pearos.xyz) in spirit — a complete environment, not just a coat of paint.

---

## Components

| Component | Description | Status |
|-----------|-------------|--------|
| **Wallpapers** | Official macOS Tahoe & Heritage wallpapers — light/dark pairs, Beach series, Landscape series | ✅ Implemented |
| **Fonts** | SF Pro Display, SF Pro Text, SF Pro Rounded — downloaded from mirrors at install time | ✅ Implemented |
| **Cursors** | macOS-style cursor themes (standard, dark, Apple, Apple White) | ✅ Implemented |
| **Plasma theme** | macOS Tahoe-style shell, panel, dock, and look-and-feel for KDE Plasma | 🔲 Planned |
| **GTK theme** | Tahoe-style window chrome and controls for GTK2/3/4 apps | 🔲 Planned |
| **Kvantum theme** | Tahoe Kvantum theme for Qt apps | 🔲 Planned |
| **Liquid Glass** | Fork of the Liquid Glass effect — Apple's macOS Tahoe signature material | 🔲 Planned |
| **SDDM theme** | macOS-style login and lock screen | 🔲 Planned |
| **Aurorae decorations** | Apple-inspired window title bar and borders | 🔲 Planned |
| **Color schemes** | Tahoe Light & Dark KDE color palettes | 🔲 Planned |
| **Icons** | macOS-style full icon set | 🔲 Planned |
| **Sounds** | macOS-style notification and event sounds | 🔲 Planned |
| **Custom Electron apps** | "About This Mac" and System Settings — built from scratch, Apple-style | 🔲 Planned |
| **Firefox** | Refined Liquid Glass skin for Firefox as the Safari replacement | 🔲 Planned |
| **Widgets** | Plasma widgets styled after macOS Tahoe UI components | 🔲 Planned |

---

## Installation

Requires KDE Plasma 6.6+, `curl`, and `unzip`.

```bash
bash install.sh
```

---

## Uninstallation

```bash
bash uninstall.sh
```

---

## Repository Structure

```
macos-tahoe-liquid-kde/
├── install.sh              # main installer
├── uninstall.sh            # uninstaller
├── features.json           # toggle individual components on/off
└── src/
    ├── mirrors/            # mirror lists and asset source metadata
    │   ├── wallpapers.txt
    │   ├── fonts.txt
    │   └── cursors.txt
    └── steps/              # per-component install scripts
        ├── utils.sh
        ├── step-wallpapers.sh
        ├── step-fonts.sh
        ├── step-cursors.sh
        ├── wallpapers/     # online
        ├── fonts/          # online
        └── cursors/        # online
```

---

## What the Installer Touches

| Area | What changes |
|------|-------------|
| `~/.local/share/wallpapers/` | Wallpaper collection |
| `~/.local/share/fonts/` | SF Pro typefaces |
| `~/.local/share/icons/` | Cursor themes |
| `~/.config/kdeglobals` | System fonts set to SF Pro |
| `~/.config/kcminputrc` | Cursor theme applied |

---

## Credits

Based on [vinceliuice/MacTahoe-kde](https://github.com/vinceliuice/MacTahoe-kde) by [vinceliuice](https://github.com/vinceliuice) — consider [donating](https://www.paypal.me/vinceliuice) to support the original work.

---

## License

[LGPL-3.0](LICENSE)
