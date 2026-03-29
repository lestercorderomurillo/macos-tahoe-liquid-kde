# MacOS Tahoe Liquid Glass for KDE Plasma

> [!CAUTION]
> **Status: In development** — Functional but under active development. Some features may not work as expected. Back up your KDE config before installing. Use at your own risk.

A full macOS Tahoe-style desktop experience for KDE Plasma — going beyond a simple theme.

Inspired by [Pear OS](https://pearos.xyz) in spirit — a complete environment, not just a coat of paint.

---

## Components

| Component | Description | Status |
|-----------|-------------|--------|
| **Wallpapers** | Tahoe, Heritage, Beach, Landscape — auto light/dark | ✅ Done |
| **Fonts** | SF Pro Display, Text, Rounded, Mono | ✅ Done |
| **Cursors** | Standard, Dark, Apple, Apple White | ✅ Done |
| **Plasma theme** | Transparent glass dock, translucent panels | ✅ Done |
| **Color schemes** | Tahoe Light & Dark palettes | ✅ Done |
| **Kvantum theme** | Qt app styling with blur and translucency | ✅ Done |
| **GTK theme** | GTK2/3/4 window chrome and controls | ✅ Done |
| **Liquid Glass** | KWin blur, rounded corners, glass effect | 🔧 In Progress |
| **Icons** | Full macOS-style icon set (light & dark) | 🔧 In Progress |
| **Layout** | Transparent top bar + floating glass dock | 🔧 In Progress |
| **Trash plasmoid** | Dock trash widget with configurable icons | ✅ Done |
| **TimeOfDay Switcher** | Auto light/dark themes based on time of day | ✅ Done |
| **SDDM theme** | Login and lock screen | 🔲 Planned |
| **Aurorae decorations** | Window title bar and borders | 🔲 Planned |
| **Sounds** | Notification and event sounds | 🔲 Planned |
| **Calendar plasmoid** | macOS-style calendar dropdown | 🔲 Planned |
| **Control Center plasmoid** | macOS-style quick settings panel | 🔲 Planned |
| **Global Menu plasmoid** | macOS-style top bar app menu | 🔲 Planned |
| **System Preferences plasmoid** | macOS-style settings launcher | 🔲 Planned |
| **OS Selector** | Boot manager / OS picker screen | 🔲 Planned |
| **Boot Screen** | Plymouth splash for startup | 🔲 Planned |
| **Shutdown Screen** | Styled logout / shutdown sequence | 🔲 Planned |

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

### Feature Flags

Every component in `features.json` has a corresponding CLI flag. Flags override the file:

```bash
bash install.sh --no-gtk --no-sddm       # skip GTK and SDDM
bash install.sh --gtk --no-kvantum        # enable GTK, skip Kvantum
bash uninstall.sh --icons --cursors       # only uninstall icons and cursors
```

Available flags: `--wallpapers`, `--fonts`, `--cursors`, `--plasma-theme`, `--window-decorations`, `--kvantum`, `--color-schemes`, `--icons`, `--plasmoids`, `--liquid-glass`, `--layout`, `--sounds`, `--gtk`, `--sddm`, `--apps`, `--no-download`

Prefix any flag with `--no-` to disable it (e.g. `--no-fonts`).

### Theme Mode

Control light/dark behavior with `--light`, `--dark`, or `--auto`:

```bash
bash install.sh --dark                    # force dark theme
bash install.sh --light                   # force light theme
bash install.sh --auto                    # time-of-day switching (default)
```

In `--auto` mode, the watcher service runs at login and switches themes automatically (light 7 AM–7 PM, dark at night). In `--light` or `--dark` mode, the watcher is disabled.

### Save & Reset

```bash
bash install.sh --no-gtk --dark --save    # remember these settings for next run
bash install.sh                           # uses saved features.json
bash install.sh --reset                   # restore features.json to all-true defaults
```

### Manual Theme Switching

```bash
mac-tahoe-theme-switch light    # force light
mac-tahoe-theme-switch dark     # force dark
mac-tahoe-theme-switch auto     # detect from time of day
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
    ├── offline/            # assets bundled in-repo (no download needed)
    │   ├── plasma-theme/   # Plasma desktop theme (transparent glass dock)
    │   │   ├── MacTahoeLiquidKde-Light/
    │   │   └── MacTahoeLiquidKde-Dark/
    │   ├── color-schemes/  # KDE color schemes
    │   ├── kvantum/        # Kvantum Qt theme (blur + translucency)
    │   │   └── mac-tahoe-liquid-kde/
    │   ├── gtk/            # GTK 2/3/4 theme
    │   │   ├── MacTahoeLiquidKde-Light/
    │   │   └── MacTahoeLiquidKde-Dark/
    │   ├── plasmoids/      # custom Plasma widgets
    │   ├── kwin-effects/   # Liquid Glass KWin effect (built from source)
    │   ├── layouts/        # panel layout scripts
    │   ├── theme-switch.sh # TimeOfDay theme switcher
    │   └── mac-tahoe-liquid-kde-theme.service
    └── steps/              # per-component download scripts
```

---

## What the Installer Does

| Area | What changes |
|------|-------------|
| `~/.local/share/wallpapers/` | Wallpaper collection |
| `~/.local/share/fonts/` | SF Pro typefaces |
| `~/.local/share/icons/` | Cursor and icon themes |
| `~/.local/share/plasma/desktoptheme/` | Transparent glass dock + panels |
| `~/.local/share/color-schemes/` | Tahoe Light & Dark palettes |
| `~/.config/Kvantum/mac-tahoe-liquid-kde/` | Kvantum theme (blur + translucency) |
| `~/.themes/MacTahoeLiquidKde-*/` | GTK theme |
| `~/.local/share/plasma/plasmoids/` | Custom plasmoids |
| `~/.local/bin/mac-tahoe-theme-switch` | TimeOfDay theme switcher |
| `~/.config/kwinrc` | Liquid Glass effect config |
| Panel layout | Transparent top bar + floating glass dock |
| KWin effects | Liquid Glass blur + rounded corners |

The uninstaller reverses everything and resets to Breeze defaults.

---

## Credits

Based on [vinceliuice/MacTahoe-kde](https://github.com/vinceliuice/MacTahoe-kde) by [vinceliuice](https://github.com/vinceliuice).

---

## License

[LGPL-3.0](LICENSE)
