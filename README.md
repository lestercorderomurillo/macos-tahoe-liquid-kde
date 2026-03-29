# MacOS Tahoe Liquid Glass for KDE Plasma

> [!CAUTION]
> **Status: In development** — Functional but under active development. Some features may not work as expected. Back up your KDE config before installing. Use at your own risk.

A full macOS Tahoe-style desktop experience for KDE Plasma — going beyond a simple theme.

Inspired by [Pear OS](https://pearos.xyz) in spirit — a complete environment, not just a coat of paint.

---

## Components

| Component | Description | Status |
|-----------|-------------|--------|
| **Wallpapers** | Tahoe, Heritage, Beach, Landscape — light/dark | ✅ Done |
| **Fonts** | SF Pro Display, Text, Rounded | ✅ Done |
| **Cursors** | Standard, Dark, Apple, Apple White | ✅ Done |
| **Icons** | Full macOS-style icon set (light & dark) | 🔧 In Progress |
| **Plasmoids** | Custom trash widget with configurable icons | ✅ Done |
| **Layout** | Transparent top bar + floating bottom dock | 🔧 In Progress |
| **Liquid Glass** | KWin blur + rounded corners effect | 🔧 In Progress |
| **Plasma theme** | Shell, panel, dock, look-and-feel | 🔲 Planned |
| **GTK theme** | GTK2/3/4 window chrome and controls | 🔲 Planned |
| **Kvantum theme** | Qt app theme | 🔲 Planned |
| **SDDM theme** | Login and lock screen | 🔲 Planned |
| **Aurorae decorations** | Window title bar and borders | 🔲 Planned |
| **Color schemes** | Tahoe Light & Dark palettes | 🔲 Planned |
| **Sounds** | Notification and event sounds | 🔲 Planned |

---

## Requirements

- KDE Plasma 6.6+
- sudo access
- [Panel Colorizer](https://store.kde.org/p/2130967) (auto-installed if missing)

## Usage

**Install**
```bash
bash install.sh
```

**Uninstall** (resets to Breeze defaults)
```bash
bash uninstall.sh
```

Both scripts ask for confirmation, request sudo upfront, and restart Plasma automatically.

---

## Repository Structure

```
macos-tahoe-liquid-kde/
├── install.sh              # main installer
├── uninstall.sh            # uninstaller (resets to Breeze)
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
    │   │   └── glass-kde-replica/
    │   └── layouts/        # panel layout scripts
    │       ├── mactahoe.js # transparent top bar + bottom dock
    │       └── default.js  # reset to stock KDE
    └── steps/              # per-component install scripts
```

---

## What the Installer Does

| Area | What changes |
|------|-------------|
| `~/.local/share/wallpapers/` | Wallpaper collection |
| `~/.local/share/fonts/` | SF Pro typefaces |
| `~/.local/share/icons/` | Cursor and icon themes |
| `~/.config/kdeglobals` | Fonts, icon theme |
| `~/.config/kcminputrc` | Cursor theme |
| `~/.config/kwinrc` | Liquid Glass effect config |
| `~/.local/share/plasma/plasmoids/` | Custom plasmoids |
| Panel layout | Top bar (transparent) + bottom dock (floating) |
| KWin effects | Liquid Glass blur + rounded corners |
| Plasma shell | Restarted to apply all changes |

The uninstaller reverses everything and resets to Breeze defaults.

---

## Credits

Based on [vinceliuice/MacTahoe-kde](https://github.com/vinceliuice/MacTahoe-kde) by [vinceliuice](https://github.com/vinceliuice).

---

## License

[LGPL-3.0](LICENSE)
