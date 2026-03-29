# MacOS Tahoe Liquid Glass for KDE Plasma

> [!CAUTION]
> **Status: In development** — Functional but under active development. Some features may not work as expected. Back up your KDE config before installing. Use at your own risk.

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
| **Liquid Glass** | KWin glass effect with specular, iridescence, shadows | ✅ Done |
| **SDDM theme** | Login and lock screen | 🔲 Planned |
| **Aurorae decorations** | Window title bar and borders | 🔲 Planned |
| **Color schemes** | Tahoe Light & Dark palettes | 🔲 Planned |
| **Icons** | Full macOS-style icon set (light & dark) | ✅ Done |
| **Sounds** | Notification and event sounds | 🔲 Planned |
| **Custom Electron apps** | "About This Mac" and System Settings | 🔲 Planned |
| **Firefox** | Liquid Glass skin | 🔲 Planned |
| **Plasmoids** | Custom Plasma widgets (trash, more planned) | ✅ In Progress |
| **Layout** | Top menu bar + bottom floating dock | ✅ Done |
| **Widgets** | Plasma widgets styled after Tahoe UI | 🔲 Planned |

---

## Usage

Requires KDE Plasma 6.6+.

**Install**
```bash
bash install.sh
```

**Uninstall**
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
    │   ├── cursors.txt
    │   └── icons.txt
    ├── offline/            # assets bundled in-repo (no download needed)
    │   ├── plasmoids/      # custom Plasma widgets
    │   │   └── org.kde.mactahoe-liquid-kde.trash/
    │   ├── kwin-effects/   # KWin compositor effects (built from source)
    │   │   └── glass-kde-replica/  # Apple-style glass material
    │   └── layouts/        # panel layout scripts
    │       ├── mactahoe.js # top bar + bottom dock
    │       └── default.js  # reset to stock KDE
    └── steps/              # per-component install scripts
        ├── utils.sh
        ├── step-wallpapers.sh
        ├── step-fonts.sh
        ├── step-cursors.sh
        ├── step-icons.sh
        ├── wallpapers/     # online
        ├── fonts/          # online
        ├── cursors/        # online
        └── icons/          # online
```

---

## What the Installer Touches

| Area | What changes |
|------|-------------|
| `~/.local/share/wallpapers/` | Wallpaper collection |
| `~/.local/share/fonts/` | SF Pro typefaces |
| `~/.local/share/icons/` | Cursor themes and icon themes |
| `~/.config/kdeglobals` | System fonts, icon theme |
| `~/.config/kcminputrc` | Cursor theme applied |
| `~/.local/share/plasma/plasmoids/` | Custom plasmoids |
| `plasma-org.kde.plasma.desktop-appletsrc` | Panel layout (top bar + dock) |

---

## Credits

Based on [vinceliuice/MacTahoe-kde](https://github.com/vinceliuice/MacTahoe-kde) by [vinceliuice](https://github.com/vinceliuice) — consider [donating](https://www.paypal.me/vinceliuice) to support the original work.

---

## License

[LGPL-3.0](LICENSE)
