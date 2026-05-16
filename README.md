<p align="center">
  <img src="src/screenshots/banner_v2.svg" alt="tahoe 26" width="360">
</p>

# macOS Tahoe Liquid Theme for KDE Plasma

[![release](https://img.shields.io/github/v/release/lestercorderomurillo/macos-tahoe-liquid-kde?label=release&cacheSeconds=0)](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/releases) [![tests](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/workflows/test.yml/badge.svg)](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/workflows/test.yml) [![tests count](https://img.shields.io/badge/tests-349_passing-brightgreen)](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/workflows/test.yml) [![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE) [![plasma](https://img.shields.io/badge/KDE_Plasma-6.6%2B-1d99f3?logo=kde)](https://kde.org/plasma-desktop/) [![last commit](https://img.shields.io/github/last-commit/lestercorderomurillo/macos-tahoe-liquid-kde)](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/commits/) [![report a bug](https://img.shields.io/badge/report-a%20bug-red?logo=github)](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new)

> [!NOTE]
> Things break sometimes as KDE, KWin and friends update. The installer checks for updates on launch to stay in sync with upstream packages, which helps avoid crashes and breakages — please [report any issue](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new) you run into.

A full macOS Tahoe-style desktop experience for KDE Plasma 6.6+.

<br>

# Features

### Tahoe Launcher

App grid with categories and search.

<p align="center">
  <img src="src/screenshots/launcher_v2.png" width="415">
  <img src="src/screenshots/launcher_dark_v2.png" width="415">
</p>

<p align="center">
  <sub>Example of Light and Dark variant.</sub>
</p>

### Tahoe Dock

Liquid-glass dock with macOS-style red notification bubbles and wallpaper refraction.

<p align="center">
  <img src="src/screenshots/dock_1_v2.png" width="840"><br>
  <sub>Bright dock glow with the red macOS-style notification bubble.</sub>
</p>

<p align="center">
  <img src="src/screenshots/dock_2_v2.png" width="840"><br>
  <sub>Refraction example with the wallpaper visibly bending through the glass surface.</sub>
</p>

<p align="center">
  <img src="src/screenshots/dock_3_v2.png" width="840"><br>
  <sub>Dark dock variant with the same liquid-glass depth.</sub>
</p>

### Tahoe Finder

Nautilus file manager with macOS-style sidebar.

<p align="center">
  <img src="src/screenshots/finder_v2.png" width="415">
  <img src="src/screenshots/finder_dark_v2.png" width="415">
</p>

<p align="center">
  <sub>Example of Light and Dark variant.</sub>
</p>

### Menu

System menu with native QMenu dropdown.

<p align="center">
  <img src="src/screenshots/menu_v2.png" width="415">
  <img src="src/screenshots/menu_dark_v2.png" width="415">
</p>

<p align="center">
  <sub>Example of Light and Dark variant.</sub>
</p>

### System Information

Glass system information window.

<p align="center">
  <img src="src/screenshots/about_v2.png" width="415">
  <img src="src/screenshots/about_dark_v2.png" width="415">
</p>

<p align="center">
  <sub>Example of Light and Dark variant.</sub>
</p>

### Plasma Theme

Desktop right-click with translucent glass blur.

<p align="center">
  <img src="src/screenshots/context_menu_v2.png" width="415">
  <img src="src/screenshots/context_menu_dark_v2.png" width="415">
</p>

<p align="center">
  <sub>Example of Light and Dark variant.</sub>
</p>

---

## Roadmap

| Component | Description | Status |
|-----------|-------------|--------|
| **Color Schemes** | Light and Dark color palettes | ✅ |
| **Wallpapers** | Tahoe Iridescence + Landscape (Morning/Evening/Night) | ✅ |
| **Fonts** | SF Pro Display, Text, Rounded, Mono | ✅ |
| **Cursors** | Tahoe style cursors | ✅ |
| **Plasma Theme** | Translucent panels + close/min/max buttons | ✅ |
| **Kvantum Theme** | Kvantum theme | ✅ |
| **GTK Theme** | GTK2/3/4 window chrome and controls | ✅ |
| **Acrylic Glass** | KWin blur, rounded corners, glass effect | ✅ |
| **Auto Theme Switcher** | Auto light/dark via Plasma native sunrise/sunset | ✅ |
| **Aurorae Decorations** | Window title bar and borders | ✅ |
| **Global Menu Plasmoid** | Unified menu bar: system menu, app name, window controls, app menus | ✅ |
| **Dock Task Manager** | Icons-only dock applet with macOS-style notification badges | ✅ |
| **Nautilus** | Install Nautilus and set as default file manager on KDE | ✅ |
| **Icons** | Full icon set (light & dark) | 🔧 |
| **Launcher Plasmoid** | App grid launcher | 🔧 |
| **Trashcan Plasmoid** | Trash widget with configurable icons | 🔧 |
| **Sounds** | Notification and event sounds | 🔲 |
| **Firefox Theme** | Firefox browser theme | 🔲 |
| **Konsole Theme** | Terminal profile | 🔲 |
| **Kate Theme** | Text editor theme | 🔲 |
| **SDDM Theme** | Login and lock screen | 🔲 |
| **Calendar Plasmoid** | Calendar dropdown | 🔲 |
| **Control Center Plasmoid** | Quick settings panel | 🔲 |
| **System Preferences Plasmoid** | Settings launcher | 🔲 |
| **OS Selector** | Boot manager / OS picker screen | 🔲 |
| **Boot Screen** | Plymouth splash for startup (1080p–4K) | ✅ |
| **Shutdown Screen** | Styled logout / shutdown sequence | 🔲 |

---

## Requirements

- KDE Plasma 6.6+
- Python 3.10+
- `sudo` for both `./install` and `./uninstall` — see below

---

## Usage

```bash
sudo ./install                                   # install everything
sudo ./install --help                            # show all options
sudo ./install --preflight                       # dry-run the safety checks, exit
sudo ./uninstall                                 # uninstall, reset to Breeze
```

### Staying up to date

```bash
sudo ./install --check-update                    # check without installing
sudo MAC_TAHOE_NO_UPDATE_CHECK=true ./install    # disable the check
```

### Feature Flags

Every component has a CLI flag. Use `--no-` to skip, or `--only` to run just the listed ones:

```bash
sudo ./install --no-gtk --no-sddm                # skip GTK and SDDM
sudo ./install --only --fonts --icons            # install only fonts and icons
sudo ./uninstall --only --cursors                # uninstall only cursors
```

Available flags:

| | | | |
|---|---|---|---|
| `--wallpapers` | `--fonts` | `--cursors` | `--plasma-theme` |
| `--window-decorations` | `--kvantum` | `--color-schemes` | `--icons` |
| `--plasmoids` | `--acrylic-glass` | `--global-theme` | `--layout` |
| `--sounds` | `--gtk` | `--sddm` | `--apps` |
| `--nautilus` | `--portals` | | |

Use `--no-download` to skip asset downloads and use cached files.

### Theme Mode

```bash
sudo ./install                                   # auto (default)
sudo ./install --dark                            # force dark
sudo ./install --light                           # force light
```

- **`--auto`** is the default. It switches between light mode at `06:00` and dark mode at `18:00` with a systemd timer, and `Persistent=true` catches missed transitions after suspend, shutdown, or late login.
- **`--light`** / **`--dark`** lock the theme to one mode and disable the timer.

After install, you can switch manually:

```bash
mac-tahoe-theme-switch light                     # force light (disables timer)
mac-tahoe-theme-switch dark                      # force dark (disables timer)
mac-tahoe-theme-switch auto                      # re-enable clock-based 6–18
```

### Persistence

```bash
sudo ./install --no-gtk --dark --save            # save settings to features.json
sudo ./install                                   # reuses saved features.json
sudo ./install --reset                           # reset features.json to defaults
```

Used flags are recorded at `~/.local/state/mac-tahoe-liquid-kde/last-run.json`.

---

## Repository Structure

```
macos-tahoe-liquid-kde/
├── install                 # entry point → src/scripts/cli.run_install
├── uninstall               # entry point → src/scripts/cli.run_uninstall
├── features.json           # toggle individual components on/off
├── build/
│   ├── steps/              # downloaded cache used by installer steps (ignored)
│   ├── plasmoids/          # native plasmoid build outputs (ignored)
│   └── kwin-effects/       # native KWin effect build outputs (ignored)
└── src/
    ├── scripts/
    │   ├── cli.py              # argparse, feature flags, install/uninstall flow
    │   ├── theme_switch.py     # light/dark switcher (installed as ~/.local/bin)
    │   ├── set-transparency    # CLI: tune background opacity (Kvantum/Plasma/GTK)
    │   ├── svgzc               # CLI: decode/encode .svgz for editing
    │   ├── paths.py            # REPO_ROOT / SRC_DIR / BUILD_DIR / OFFLINE_DIR / read_version()
    │   ├── log.py, state.py, step_runner.py, utils.py
    │   └── steps/              # one module per feature: install/uninstall/...
    │       ├── wallpapers.py, fonts.py, cursors.py, icons.py, ...
    │       └── (21 modules — apply, layout, plasmoids, theme_switch, ...)
    ├── mirrors/            # download source definitions (JSON)
    │   ├── wallpapers.json
    │   ├── fonts.json
    │   ├── icons.json
    │   └── cursors.json
    ├── screenshots/        # documentation screenshots
    └── offline/            # assets bundled in-repo (no download needed)
        ├── plasma-theme/   # Plasma desktop theme (transparent glass dock)
        ├── color-schemes/  # KDE color schemes
        ├── kvantum/        # Kvantum Qt theme (blur + translucency)
        ├── gtk/            # GTK 2/3/4 theme
        ├── aurorae/        # macOS-style window decorations
        ├── plasmoids/      # custom Plasma widgets
        ├── kwin-effects/   # Acrylic Glass KWin effect (built from source)
        ├── layouts/        # panel layout scripts
        ├── nautilus/       # optional Nautilus overrides
        ├── wallpapers/     # Tahoe Iridescence + Landscape (Morning/Evening/Night)
        └── *.service / *.timer  # systemd units for the theme switcher
```

---

## What the Installer Does

### Appearance

| Component | What it installs | Location |
|-----------|-----------------|----------|
| **Color Schemes** | Light and Dark palettes for all KDE apps | `~/.local/share/color-schemes/` |
| **Global Theme** | Look-and-feel packages (light + dark variants) | `~/.local/share/plasma/look-and-feel/` |
| **Plasma Theme** | Translucent glass panels and dock styling | `~/.local/share/plasma/desktoptheme/` |
| **Kvantum** | Qt widget theme with blur and translucency | `~/.config/Kvantum/` |
| **GTK** | GTK 2/3/4 theme for non-Qt apps (Nautilus, Firefox, etc.) | `~/.themes/` |
| **Icons** | macOS-style icon set with light and dark variants | `~/.local/share/icons/` |
| **Cursors** | macOS-style cursor theme | `~/.local/share/icons/` |
| **Wallpapers** | Tahoe Iridescence + Landscape (Morning/Evening/Night) | `~/.local/share/wallpapers/` |
| **Fonts** | SF Pro Display, Text, Rounded, and SF Mono | `~/.local/share/fonts/` |

### Desktop

| Component | What it installs | Location |
|-----------|-----------------|----------|
| **Layout** | Transparent top bar + floating glass dock | Panel config via JS scripting API |
| **Global Menu** | Unified menu bar: system menu, app name with window controls, app menus | `/usr/lib/qt6/plugins/plasma/applets/` + `/usr/lib/qt6/qml/...` |
| **Dock Task Manager** | Icons-only dock task manager with macOS-style notification badges (solid red, white bold text) | `/usr/lib/qt6/plugins/plasma/applets/` + `/usr/lib/qt6/qml/...` |
| **Launcher** | App grid with categories and search | `~/.local/share/plasma/plasmoids/` |
| **Trashcan** | Dock trash widget with configurable icons | `~/.local/share/plasma/plasmoids/` |
| **Window Decorations** | macOS-style title bars (Aurorae) | `~/.local/share/aurorae/themes/` |
| **Nautilus** | Installs Nautilus, sets as default file manager, applies macOS-like Finder defaults | System package + `~/.config/mimeapps.list` |

### Effects and Services

| Component | What it installs | Location |
|-----------|-----------------|----------|
| **Acrylic Glass** | KWin blur + rounded corners effect (built from source) | `/usr/lib/qt6/plugins/kwin/effects/` |
| **Theme Switcher** | Auto light/dark via Plasma native sunrise/sunset | `~/.local/bin/mac-tahoe-theme-switch` |
| **Watcher Service** | Keeps Kvantum and GTK in sync with Plasma theme | systemd user service |
| **Sounds** | Notification and event sounds | `~/.local/share/sounds/` |
| **SDDM** | macOS-style login screen | `/usr/share/sddm/themes/` |

### Config Files Modified

| File | What changes |
|------|-------------|
| `~/.config/kdeglobals` | Fonts, color scheme, icon theme, auto dark mode |
| `~/.config/kwinrc` | Window decorations, Acrylic Glass effect |
| `~/.config/plasmashellrc` | Panel opacity, floating dock style |
| `~/.config/plasmarc` | Active Plasma theme |

The uninstaller reverses all changes, clears explicit KDE color overrides, and resets to Breeze defaults.

---

## Reporting Bugs

Found something broken? Please open a GitHub issue:

**👉 [Report a bug](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new)**

You can also reach the issue tracker straight from the desktop:

- **Apple menu → About This Computer → Report a Bug…** opens the same form in your browser.
- After every `./install` or `./uninstall` run, the final line of the output prints the issues URL.

When filing, please include:

- Your Plasma version (`plasmashell --version`) and distro (`cat /etc/os-release | grep PRETTY_NAME`)
- The MacTahoe Liquid KDE version (`cat VERSION` in the repo, or the version shown in *About This Computer*)
- The exact `./install` flags you used (also recorded in `~/.local/state/mac-tahoe-liquid-kde/last-run.json`)
- A screenshot or recording if it's a visual regression

---

## Disclaimer

Build using AI tools.

This project is an independent reimplementation inspired by the macOS aesthetic. No assets, code, or intellectual property from Apple Inc. have been copied or redistributed. All themes, icons, plasmoids, and configurations are original work or derived from open-source projects under compatible licenses. "macOS" and "Apple" are trademarks of Apple Inc. This project is not affiliated with or endorsed by Apple.

If you like Apple, buy an Apple product.

---

## License

[MIT](LICENSE)
