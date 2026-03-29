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
| **Trash plasmoid** | Trash widget with configurable icons | ✅ Done |
| **Icons** | Full macOS-style icon set (light & dark) | 🔧 In Progress |
| **Layout** | Transparent top bar + floating bottom dock | 🔧 In Progress |
| **Liquid Glass** | KWin blur + rounded corners effect | 🔧 In Progress |
| **Plasma theme** | Shell, panel, dock, look-and-feel | 🔲 Planned |
| **GTK theme** | GTK2/3/4 window chrome and controls (light & dark) | ✅ Done |
| **Kvantum theme** | Qt app theme (light & dark) | ✅ Done |
| **SDDM theme** | Login and lock screen | 🔲 Planned |
| **Aurorae decorations** | Window title bar and borders | 🔲 Planned |
| **Color schemes** | Tahoe Light & Dark palettes | ✅ Done |
| **TimeOfDay Switcher** | Auto light/dark themes based on time of day | ✅ Done |
| **Sounds** | Notification and event sounds | 🔲 Planned |
| **Global Menu plasmoid** | macOS-style top bar app menu | 🔲 Planned |
| **System Preferences plasmoid** | macOS-style settings launcher | 🔲 Planned |

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

**TimeOfDay Theme Switcher** — Automatically switches between light and dark themes based on time of day. Light from 7 AM to 7 PM, dark at night.

```bash
mactahoe-theme-switch light    # force light
mactahoe-theme-switch dark     # force dark
mactahoe-theme-switch auto     # detect from system or time
```

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
    │   ├── kvantum/        # Kvantum Qt theme (light & dark)
    │   │   └── MacTahoeLiquidKde/
    │   ├── gtk/            # GTK theme (light & dark)
    │   │   ├── MacTahoeLiquidKde-Light/
    │   │   └── MacTahoeLiquidKde-Dark/
    │   ├── color-schemes/  # KDE color schemes (light & dark)
    │   ├── kwin-effects/   # KWin compositor effects (built from source)
    │   │   └── glass-kde-replica/
    │   ├── layouts/        # panel layout scripts
    │   │   ├── mactahoe.js # transparent top bar + bottom dock
    │   │   └── default.js  # reset to stock KDE
    │   ├── theme-switch.sh # auto light/dark switcher
    │   └── mactahoe-liquid-kde-theme.service
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
| `~/.config/Kvantum/MacTahoeLiquidKde/` | Kvantum theme (light & dark) |
| `~/.local/share/color-schemes/` | MacTahoe color schemes (light & dark) |
| `~/.themes/MacTahoeLiquidKde-*/` | GTK theme (light & dark) |
| `~/.local/share/plasma/plasmoids/` | Custom plasmoids |
| `~/.local/bin/mactahoe-theme-switch` | Auto light/dark theme switcher |
| Panel layout | Top bar (always visible) + bottom dock (auto-hide) |
| KWin effects | Liquid Glass blur + rounded corners |
| Plasma shell | Restarted to apply all changes |

The uninstaller reverses everything and resets to Breeze defaults.

---

## Credits

Based on [vinceliuice/MacTahoe-kde](https://github.com/vinceliuice/MacTahoe-kde) by [vinceliuice](https://github.com/vinceliuice).

---

## License

[LGPL-3.0](LICENSE)
