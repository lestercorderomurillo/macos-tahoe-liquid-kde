# MacTahoe KDE

A full macOS Tahoe-style desktop experience for KDE Plasma — going beyond a simple theme. MacTahoe KDE bundles a curated collection of widgets, GTK & KDE themes, SDDM login screen, window decorations, icons, cursors, fonts, sounds, wallpapers, and a custom Electron app menu, bringing a cohesive Tahoe look to every layer of your desktop.

Inspired by [Pear OS](https://pearos.xyz) in spirit — a complete environment, not just a coat of paint.

---

## What's Included

| Component | Description |
|-----------|-------------|
| **Plasma theme** | macOS Tahoe-style shell, panel, dock, and look-and-feel for KDE Plasma |
| **GTK theme** | Tahoe-style window chrome and controls for GTK2/3/4 apps |
| **Kvantum theme** | Tahoe Kvantum theme for Qt apps |
| **Liquid Glass** | Fork of the Liquid Glass effect — Apple's macOS Tahoe signature material |
| **SDDM theme** | macOS-style login and lock screen |
| **Aurorae decorations** | Apple-inspired window title bar and borders |
| **Color schemes** | Tahoe Light & Dark KDE color palettes |
| **Icons** | macOS-style full icon set |
| **Cursors** | Matching macOS-style cursor theme |
| **Fonts** | Apple-inspired bundled typefaces |
| **Sounds** | macOS-style notification and event sounds |
| **Wallpapers** | Official and curated macOS Tahoe wallpapers |
| **Nautilus** | GNOME file manager styled and resourced to match the Tahoe aesthetic on KDE |
| **GNOME apps** | Calculator and other utilities themed for a native macOS look on KDE |
| **Custom Electron apps** | "About This Mac" and System Settings — built from scratch, Apple-style |
| **Firefox** | Refined Liquid Glass skin for Firefox as the Safari replacement |
| **Widgets** | Plasma widgets styled after macOS Tahoe UI components |

---

## Shell Support

| Shell | Supported |
|-------|-----------|
| `bash` | ✅ |
| `fish` | ✅ |
| `zsh` | ✅ |

---

## Installation

### Bash

```bash
bash install.sh
```

### Fish

```fish
bash install.sh
```

> A dedicated Fish-native wrapper is also provided:

```fish
source install.fish
```

---

## Uninstallation

### Bash

```bash
bash uninstall.sh
```

### Fish

```fish
source uninstall.fish
```

---

## Requirements

- KDE Plasma 6.6+
- `bash` ≥ 4.0 **or** `fish` ≥ 3.0

---


## Preview

| Light | Dark |
|-------|------|
| ![Light](src/plasma/look-and-feel/com.github.vinceliuice.MacTahoe-Light/contents/previews/fullscreenpreview.jpg) | ![Dark](src/plasma/look-and-feel/com.github.vinceliuice.MacTahoe-Dark/contents/previews/fullscreenpreview.jpg) |

---

## Repository Structure

```
macos-tahoe-liquid-kde/
├── install.sh
├── install.fish
├── uninstall.sh
├── uninstall.fish
└── src/
    ├── kvantum/
    ├── colors/
    ├── sddm/
    ├── plasma/
    ├── aurorae/
    ├── wallpapers/
    ├── sounds/
    ├── icons/
    └── fonts/
```

---

## What the Installer Touches

Running `install.sh` or `install.fish` will make changes to the following parts of your system:

| Area | What changes |
|------|-------------|
| `~/.local/share/plasma/` | Plasma shell, color schemes, look-and-feel |
| `~/.local/share/aurorae/` | Window decorations |
| `~/.local/share/icons/` | Icon and cursor themes |
| `~/.local/share/fonts/` | Bundled typefaces |
| `~/.local/share/sounds/` | Notification and event sounds |
| `~/.local/share/wallpapers/` | Wallpaper collection |
| `~/.config/Kvantum/` | Kvantum Qt theme |
| `~/.themes/` | GTK2/3/4 theme |
| `~/.config/gtk-3.0/` `~/.config/gtk-4.0/` | GTK config set to MacTahoe |
| `/usr/share/sddm/themes/` | SDDM login screen (requires sudo) |
| `~/.local/share/applications/` | Custom Electron apps registered |
| Firefox profile | Liquid Glass skin applied |
| KDE settings | Plasma theme, icons, cursors, fonts, colors applied via `lookandfeeltool` / `plasma-apply-*` |

> No system files outside of the above are modified. Everything installed to `~/.local/` can be removed without sudo.

---

## Credits

Based on [vinceliuice/MacTahoe-kde](https://github.com/vinceliuice/MacTahoe-kde) by [vinceliuice](https://github.com/vinceliuice) — consider [donating](https://www.paypal.me/vinceliuice) to support the original work.

---

## License

[LGPL-3.0](LICENSE)