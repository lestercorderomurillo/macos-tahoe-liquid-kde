# MacOS Tahoe Liquid Glass for KDE Plasma

A full macOS Tahoe-style desktop experience for KDE Plasma — going beyond a simple theme. MacTahoe Liquid KDE bundles a curated collection of widgets, GTK & KDE themes, SDDM login screen, window decorations, icons, cursors, fonts, sounds, wallpapers, and a custom Electron app menu, bringing a cohesive Tahoe look to every layer of your desktop.

Inspired by [Pear OS](https://pearos.xyz) in spirit — a complete environment, not just a coat of paint.

---

## Components

| Component | Description | Status |
|-----------|-------------|--------|
| **Wallpapers** | Tahoe, Heritage, Beach, Landscape — light/dark | ✅ Done |
| **Fonts** | SF Pro Display, Text, Rounded | ✅ Done |
| **Cursors** | Standard, Dark, Apple, Apple White | ✅ Done |
| **Plasma theme** | Shell, panel, dock, look-and-feel | 🔲 Planned |
| **GTK theme** | GTK2/3/4 window chrome and controls | 🔲 Planned |
| **Kvantum theme** | Qt app theme | 🔲 Planned |
| **Liquid Glass** | Apple's Tahoe signature material effect | 🔲 Planned |
| **SDDM theme** | Login and lock screen | 🔲 Planned |
| **Aurorae decorations** | Window title bar and borders | 🔲 Planned |
| **Color schemes** | Tahoe Light & Dark palettes | 🔲 Planned |
| **Icons** | Full macOS-style icon set | 🔲 Planned |
| **Sounds** | Notification and event sounds | 🔲 Planned |
| **Custom Electron apps** | "About This Mac" and System Settings | 🔲 Planned |
| **Firefox** | Liquid Glass skin | 🔲 Planned |
| **Widgets** | Plasma widgets styled after Tahoe UI | 🔲 Planned |

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
