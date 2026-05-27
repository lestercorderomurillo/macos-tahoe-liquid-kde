<p align="center">
  <img src="src/screenshots/banner_v2.svg" alt="tahoe 26" width="360">
</p>

# macOS Tahoe Liquid Theme for KDE Plasma

[![release](https://img.shields.io/badge/release-v0.15.3-blue)](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/releases) [![tests](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/workflows/test.yml/badge.svg)](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/workflows/test.yml) [![tests count](https://img.shields.io/badge/tests-647_passing-brightgreen)](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/workflows/test.yml) [![license](https://img.shields.io/badge/license-GPL--2.0-blue)](LICENSE) [![plasma](https://img.shields.io/badge/KDE_Plasma-6.6%2B-1d99f3?logo=kde)](https://kde.org/plasma-desktop/) [![last commit](https://img.shields.io/github/last-commit/lestercorderomurillo/macos-tahoe-liquid-kde)](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/commits/) [![report a bug](https://img.shields.io/badge/report-a%20bug-red?logo=github)](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new)

> [!WARNING]
> **Alpha / active development.** This project is under heavy development — things break as KDE, KWin and friends update. The installer pulls upstream changes on launch and may behave differently between runs. Expect rough edges, hold off on it for production desktops, and please [report any issue](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new) you run into.

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

### Boot Splash

Plymouth boot screen with centered Apple-style logo on every monitor, scaled dynamically from 1080p to 4K. Boot mode shows a progress bar; shutdown / reboot share the same layout without the bar.

<p align="center">
  <img src="src/screenshots/boot_v2.png" width="415">
  <img src="src/screenshots/boot_shutdown_v2.png" width="415">
</p>

<p align="center">
  <sub>Boot mode (with progress bar) and Shutdown mode (logo only).</sub>
</p>

---

## Tested distros

|     | Distro | Supported yet? |
|:---:|--------|:--------------:|
| <img src="https://cdn.simpleicons.org/cachyos" width="22"> | CachyOS | ✅ YES |
| <img src="https://cdn.simpleicons.org/archlinux" width="22"> | Arch Linux | ✅ YES |
| <img src="https://cdn.simpleicons.org/manjaro" width="22"> | Manjaro | ✅ YES |
| <img src="https://cdn.simpleicons.org/endeavouros" width="22"> | EndeavourOS | ✅ YES |
| <img src="https://cdn.simpleicons.org/linux" width="22"> | Garuda Linux | ✅ YES |
| <img src="https://cdn.simpleicons.org/gentoo" width="22"> | Gentoo | ✅ YES |
| <img src="https://cdn.simpleicons.org/fedora" width="22"> | Fedora / RHEL | ✅ YES |
| <img src="https://cdn.simpleicons.org/nobaralinux" width="22"> | Nobara | ✅ YES |
| <img src="https://cdn.simpleicons.org/linux" width="22"> | Bazzite | ✅ YES |
| <img src="https://cdn.simpleicons.org/opensuse" width="22"> | openSUSE Tumbleweed | ✅ YES |

Each ✅ distro is verified in CI on every push: `tests/containers/` runs the path-discovery layer, package-manager mapping, preflight destination checks, and the full pytest suite against the real distro environment. Report any issues you find on confirmed OSes.

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
| **Auto Theme Switcher** | One-shot service + 06:00 / 18:00 timer, single entry point | ✅ |
| **Multi-Distro Support** | Confirmed on CachyOS, Arch, Gentoo, Fedora, openSUSE — see the *Tested distros* table | ✅ |
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

## Requirements & Dependencies

### Hard requirements

The installer refuses to start without these. They are present on every default Plasma 6 install on the [supported distros](#tested-distros) above, so usually you have them already.

- **KDE Plasma 6.6+** (`plasmashell`, `kwriteconfig6`, `kreadconfig6`, `plasma-apply-lookandfeel`, `plasma-apply-cursortheme`, `plasma-apply-wallpaperimage`, `kpackagetool6`, `kbuildsycoca6`, `qdbus6` *or* `qdbus`)
- **Python 3.10+**
- **`sudo`** (for both `./install` and `./uninstall` — root needed to write the compiled plasmoids + KWin effect under the system Qt6 libdir)
- **Qt6 path discovery** — one of: `qmake6`, `qtpaths6`, or `pkg-config` + `Qt6Core.pc`. The installer asks Qt where its plugin / QML directories live; it refuses to guess. If none of those tools are installed, the installer falls back to the known libdir convention for your distro **only when that directory actually exists on disk**.
- **`dbus-send`** + **`systemctl`** — both ship with systemd, present on every supported distro.

### Build toolchain

Needed for the compiled pieces (Global Menu plasmoid, Dock Task Manager plasmoid, Acrylic Glass KWin effect). Skipped automatically if you `./install --no-plasmoids --no-acrylic-glass`.

- **`cmake`**
- **`g++`** (GCC C++ compiler)
- **`pkg-config`**

### KDE / Qt6 development SDK

Required by `find_package()` in the compiled units' `CMakeLists.txt`. Your distro's KDE Plasma 6 dev meta-package usually pulls all of these in one shot:

- **Extra CMake Modules** (`ECM`)
- **KF6**: `KCoreAddons`, `KConfig`, `KI18n`, `KWindowSystem`, `KDBusAddons`, `KCMUtils`, `KIconThemes`
- **KDecoration3**, **KWin** headers (`KWinDBusInterface`, `KWinX11DBusInterface`)
- **libplasma**, **libtaskmanager**, **libnotificationmanager**, **KSysGuard**
- **PlasmaActivities**, **PlasmaActivitiesStats**
- **Qt6 Base** + **Qt6 Declarative** + **Qt6 Wayland**
- **libepoxy**, **X11**, **XCB**

### Download toolchain

The installer pulls fonts, icons, cursors, and wallpapers from upstream mirrors on first run (cached afterwards). Skipped with `--no-download` if you've already fetched them.

- **`curl`**
- **`unzip`**
- **`fontconfig`** (`fc-cache`)

### Optional integrations

The installer probes for these and uses them if present; absence just disables the matching feature, never aborts.

- **Kvantum** (`kvantummanager`) — Qt widget theme. Without it, Qt apps fall back to plain Breeze widgets while keeping the rest of the theme.
- **Nautilus** — Tahoe Finder. Only relevant if you install with `--nautilus`.
- **`gsettings`** + **`gtk-update-icon-cache`** — GTK app integration (color-scheme hint, GTK 3/4 theme load).
- **`dolphin`**, **`spectacle`** — used by the "Report a Bug" → screenshot helper.

### Quick install hints

If your distro is supported and the preflight tells you a tool is missing:

| Distro | Qt6 tools | KDE Plasma 6 dev |
|--------|-----------|------------------|
| Arch / CachyOS / Manjaro / EndeavourOS / Garuda | `pacman -S qt6-tools` | `pacman -S extra-cmake-modules plasma-workspace kdecoration libplasma libnotificationmanager libksysguard plasma-activities-stats` |
| Gentoo | `emerge dev-qt/qttools:6` | `emerge kde-frameworks/extra-cmake-modules kde-plasma/plasma-workspace kde-plasma/kdecoration kde-plasma/libplasma kde-plasma/libnotificationmanager kde-plasma/libksysguard kde-plasma/plasma-activities-stats` |
| Fedora / Nobara / Bazzite / RHEL | `dnf install qt6-qttools-devel` | `dnf install extra-cmake-modules plasma-workspace-devel kdecoration-devel libplasma-devel knotifications-devel libksysguard-devel kf6-plasma-activities-devel` |
| openSUSE Tumbleweed | `zypper install qt6-tools-devel` | `zypper install extra-cmake-modules plasma6-workspace-devel kdecoration-devel libKF6Plasma-devel libnotificationmanager6-devel libksysguard6-devel libKF6PlasmaActivitiesStats6-devel` |

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

Use `--no-grub-modify` to keep the installer out of `/etc/default/grub`: the Plymouth step normally appends `splash` to `GRUB_CMDLINE_LINUX_DEFAULT` (with a `.mttkde.bak` backup) and runs `grub-mkconfig` so the boot splash actually renders. With the flag set, you get a warning + manual instructions instead.

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
    │   ├── paths.py            # repo-relative paths (REPO_ROOT, SRC_DIR, ...)
    │   ├── distro.py           # per-distro layer: Qt6 paths, package manager, install hints
    │   ├── preflight.py        # sudo escalation, destination paths, Qt6 plugin search, plasmoid IDs
    │   ├── log.py, state.py, step_runner.py, utils.py
    │   └── steps/              # one module per feature: install/uninstall/...
    │       ├── wallpapers.py, fonts.py, cursors.py, icons.py, ...
    │       └── (plasmoids, acrylic_glass, globalmenu, theme_switch, layout, …)
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
| **Global Menu** | Unified menu bar: system menu, app name with window controls, app menus | Qt6 plugin dir + QML dir (`qmake6`-reported, per distro) |
| **Dock Task Manager** | Icons-only dock task manager with macOS-style notification badges (solid red, white bold text) | Qt6 plugin dir + QML dir (`qmake6`-reported, per distro) |
| **Launcher** | App grid with categories and search | `~/.local/share/plasma/plasmoids/` |
| **Trashcan** | Dock trash widget with configurable icons | `~/.local/share/plasma/plasmoids/` |
| **Window Decorations** | macOS-style title bars (Aurorae) | `~/.local/share/aurorae/themes/` |
| **Nautilus** | Installs Nautilus, sets as default file manager, applies macOS-like Finder defaults | System package + `~/.config/mimeapps.list` |

### Effects and Services

| Component | What it installs | Location |
|-----------|-----------------|----------|
| **Acrylic Glass** | KWin blur + rounded corners effect (built from source) | Qt6 plugin dir / `kwin/effects/` (`qmake6`-reported, per distro) |
| **Theme Switcher** | One-shot user service + 06:00 / 18:00 timer, single entry point | `~/.local/bin/mac-tahoe-theme-switch` + systemd user units |
| **System Info Helper** | Powers the About panel's CPU / GPU / disk / network / OS fields with multi-source fallbacks | `~/.local/bin/mac-tahoe-about-info` |
| **Sounds** | Notification and event sounds | `~/.local/share/sounds/` |
| **SDDM** | macOS-style login screen | `/usr/share/sddm/themes/` |

### Config Files Modified

| File | What changes |
|------|-------------|
| `~/.config/kdeglobals` | Fonts, color scheme, icon theme, widget style, look-and-feel package |
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

[GPL-2.0](LICENSE) — open-source, copyleft. Forks welcome, but anything you redistribute has to stay open under the same license and keep the copyright notices intact. No warranty, no liability — use it at your own risk.

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to send changes back.

---

## Credits

Thanks to the open-source authors whose work this project draws from. Some pieces are bundled as starting points, others provide inspiration, references, or assets that the installer pulls on demand:

- **[EliverLara](https://github.com/EliverLara)** — TahoeLauncher, the original Plasma app-grid launcher the Launcher plasmoid was forked from (GPL-2.0).
- **[vinceliuice](https://github.com/vinceliuice)** — `MacTahoe-icon-theme`, the upstream icon and cursor source.
- **[ful1e5](https://github.com/ful1e5)** — `apple_cursor`, an alternate macOS-style cursor set.
- **[sahibjotsaggu](https://github.com/sahibjotsaggu)** — `San-Francisco-Pro-Fonts`, the SF Pro / SF Mono font bundle.
- **[512pixels.net](https://512pixels.net/projects/default-mac-wallpapers-in-5k/)** — high-resolution macOS wallpaper archive.

If a credit is missing, please [open an issue](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new).
