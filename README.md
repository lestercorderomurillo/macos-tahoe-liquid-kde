<p align="center">
  <img src="src/screenshots/banner_v3.svg" alt="tahoe 26" width="360">
</p>

# macOS Tahoe Liquid Theme for Plasma 6.6/6.7+

[![release](https://img.shields.io/github/v/release/lestercorderomurillo/macos-tahoe-liquid-kde?label=release&color=blue)](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/releases) [![tests](https://img.shields.io/badge/tests-1280_passing-brightgreen)](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/workflows/test.yml) [![plasma](https://img.shields.io/badge/Plasma-6.6%2B-1d99f3?logo=kde)](https://kde.org/plasma-desktop/) [![license](https://img.shields.io/badge/license-GPL--3.0-blue)](LICENSE) [![report a bug](https://img.shields.io/badge/report-a%20bug-red?logo=github)](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new)

Bring a little Tahoe to your Linux desktop.

A macOS Tahoe-inspired theme for KDE Plasma 6.6 and 6.7+, with liquid glass, a top menu bar, a Dock, matching app themes, sounds, and a boot screen. Pick the parts you like in the installer.

> [!CAUTION]
> This project is experimental and under active development. Don't use it on a production system yet. KDE, KWin, or Kvantum updates may temporarily break parts of the theme; running `sudo ./install` again usually restores them. If something goes wrong, please [open an issue](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new).

<br>

![Features and screenshots](https://img.shields.io/badge/features-%26%20screenshots-4B6B8A?style=for-the-badge&logo=kde&logoColor=white)

### Acrylic Glass Tahoe Launcher

Find an app with a quick search, keep your favorites close, or browse with a choice of two views.

<p align="center">
  <img src="src/screenshots/launcher_v3.png" width="415">
  <img src="src/screenshots/launcher_dark_v3.png" width="415">
</p>

<br>

### Acrylic Glass Tahoe Dock

Your apps sit on a glass Dock that refracts the wallpaper, with hover zoom and notification badges to show what needs your attention.

<p align="center">
  <img src="src/screenshots/dock_1_v3.png" width="840">
</p>

<br>

### Acrylic Glass Tahoe Finder

Give Nautilus a familiar Finder feel, with a macOS-style sidebar and a simpler toolbar in both light and dark modes.

<p align="center">
  <img src="src/screenshots/finder_v3.png" width="415">
  <img src="src/screenshots/finder_dark_v3.png" width="415">
</p>

<br>

### Acrylic Glass Tahoe Menu

Keep the system menu, active app name, and window controls together in the top bar, with app menus available for applications that support the global menu.

<p align="center">
  <img src="src/screenshots/menu_v3.png" width="415">
  <img src="src/screenshots/menu_dark_v3.png" width="415">
</p>

<br>

### System Information

Check your computer's details in a glass window that fits the rest of the desktop.

<p align="center">
  <img src="src/screenshots/about_v3.png" width="415">
  <img src="src/screenshots/about_dark_v3.png" width="415">
</p>

<br>

### Plasma Theme

Even the desktop's right-click menu gets the glass treatment, with a translucent background and blur.

<p align="center">
  <img src="src/screenshots/context_menu_v3.png" width="415">
  <img src="src/screenshots/context_menu_dark_v3.png" width="415">
</p>

<br>

### Boot Splash

An Apple-style logo sits at the center of each monitor, scaling to fit displays from 1080p to 4K. A progress bar appears during startup; shutdown and reboot keep the same layout without it. If your disk uses LUKS2 encryption, Plymouth shows a masked passphrase field below the logo.

<p align="center">
  <img src="src/screenshots/boot_v3.png" width="415">
  <img src="src/screenshots/boot_shutdown_v3.png" width="415">
</p>

<br>

![Contributors](https://img.shields.io/badge/contributors-4B6B8A?style=for-the-badge&logo=github&logoColor=white)

Thanks to everyone helping with code, translations, bug reports, and testing.

<p>
  <a href="https://github.com/lestercorderomurillo"><img src="https://avatars.githubusercontent.com/u/24488981?v=4&amp;s=160" width="40" height="40" alt="@lestercorderomurillo" title="@lestercorderomurillo"></a>
  <a href="https://github.com/yanhenrique-dev"><img src="https://avatars.githubusercontent.com/u/228758946?v=4&amp;s=160" width="40" height="40" alt="@yanhenrique-dev" title="@yanhenrique-dev"></a>
  <a href="https://github.com/tuxkt"><img src="https://avatars.githubusercontent.com/u/194412810?v=4&amp;s=160" width="40" height="40" alt="@tuxkt" title="@tuxkt"></a>
  <a href="https://github.com/caioniehues"><img src="https://avatars.githubusercontent.com/u/66445709?v=4&amp;s=160" width="40" height="40" alt="@caioniehues" title="@caioniehues"></a>
  <a href="https://github.com/404-not-found129"><img src="https://avatars.githubusercontent.com/u/215424551?v=4&amp;s=160" width="40" height="40" alt="@404-not-found129" title="@404-not-found129"></a>
</p>

[All contributors](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/graphs/contributors)

Want to help? Take a look at [CONTRIBUTING.md](CONTRIBUTING.md). You don't need to write code to contribute.

<br>

![Getting started](https://img.shields.io/badge/getting-started-3B7B5B?style=for-the-badge&logo=gnubash&logoColor=white)

Open the graphical installer and choose what you'd like to install or remove:

```bash
./installer
```

For the same choices in a terminal wizard:

```bash
sudo ./install
sudo ./uninstall
```

Both installers show live progress and support English, Spanish, and Simplified Chinese. Run `sudo ./install --help` for all options.

<br>

<details>
<summary><b>Requirements</b></summary>

- KDE Plasma 6.6+
- Python 3.10+
- `sudo`
- Qt 6 development tools
- KDE and Qt 6 development packages for the compiled plasmoids and KWin effects
- `cmake`, `g++`, and `pkg-config` when compiled features are selected
- `dbus-send`
- `systemctl` or `crontab` for scheduled features

Theme assets are bundled. The optional KDE Rounded Corners effect needs an internet connection; the rest installs without it.

| Distro | Qt 6 tools | KDE Plasma 6 development packages |
|--------|------------|-----------------------------------|
| Arch family | `pacman -S qt6-tools` | `pacman -S extra-cmake-modules plasma-workspace kdecoration libplasma libnotificationmanager libksysguard plasma-activities-stats` |
| Gentoo | `emerge dev-qt/qttools:6` | `emerge kde-frameworks/extra-cmake-modules kde-plasma/plasma-workspace kde-plasma/kdecoration kde-plasma/libplasma kde-plasma/libnotificationmanager kde-plasma/libksysguard kde-plasma/plasma-activities-stats` |
| Fedora family | `dnf install qt6-qttools-devel` | `dnf install extra-cmake-modules plasma-workspace-devel kdecoration-devel libplasma-devel knotifications-devel libksysguard-devel kf6-plasma-activities-devel` |
| openSUSE Tumbleweed | `zypper install qt6-tools-devel` | `zypper install extra-cmake-modules plasma6-workspace-devel kdecoration-devel libKF6Plasma-devel libnotificationmanager6-devel libksysguard6-devel libKF6PlasmaActivitiesStats6-devel` |

</details>

<details>
<summary><b>Choose features and theme mode</b></summary>

Any flag skips the terminal wizard. Use `--no-<name>` to leave out a component, or `--only` to install or remove selected components:

```bash
sudo ./install --no-gtk --no-sddm
sudo ./install --only --fonts --icons
sudo ./uninstall --only --cursors
```

Available feature names:

`wallpapers`, `fonts`, `cursors`, `plasma-theme`, `window-decorations`, `kvantum`, `color-schemes`, `icons`, `plasmoids`, `globalmenu`, `acrylic-glass`, `rounded-corners`, `global-theme`, `layout`, `sounds`, `gtk`, `firefox`, `sddm`, `apps`, `nautilus`, `nautilus-bookmarks`, `portals`, `oled-care`, `plymouth`.

Choose the initial theme mode:

```bash
sudo ./install          # automatic light/dark schedule
sudo ./install --light
sudo ./install --dark
```

Switch later with:

```bash
mac-tahoe-theme-switch light
mac-tahoe-theme-switch dark
mac-tahoe-theme-switch auto
```

Save or reset installer choices:

```bash
sudo ./install --no-gtk --dark --save
sudo ./install --reset
```

Useful maintenance options:

- `--preflight` checks the system without installing.
- `--no-apply-theme` stages files without switching the desktop.
- `--no-grub-modify` leaves `/etc/default/grub` unchanged.
- Theme changes keep any wallpaper you've chosen for each monitor.
- `--reset-wallpapers` returns all monitors to the bundled light/dark wallpapers.
- `./legacy-install` and `./legacy-uninstall` use the classic prompt instead of the terminal wizard.

</details>

<details>
<summary><b>Firefox theme and profile safety</b></summary>

The Firefox theme works with native, Flatpak, and Snap profiles. Your browser data and existing customizations are preserved. Restart the browser to see the changes.

UI settings are backed up before changes, and uninstall removes the theme's additions. Backups remain in `~/.local/state/mac-tahoe-liquid-kde/firefox/snapshots/` for recovery.

</details>

<details>
<summary><b>OLED care</b></summary>

OLED care is off by default. Enable it in the graphical feature picker or from the command line:

```bash
sudo ./install --oled-care
sudo ./install --oled-care --save
sudo ./install --no-oled-care
sudo ./install --oled-care --oled-interval=3 --oled-max-shift=4
```

Manual controls:

```bash
mac-tahoe-oled-care shift
mac-tahoe-oled-care restore
mac-tahoe-oled-care status
```

</details>

<details>
<summary><b>Test in a virtual machine</b></summary>

Try the theme in a disposable Plasma VM:

```bash
./vm <os>
```

**Choose your OS:** `cachyos` · `arch` · `manjaro` · `endeavouros` · `garuda` · `fedora` · `nobara` · `opensuse` · `neon` · `gentoo` · `gentoo-openrc`

Use `all` to launch every distro.

</details>

<br>

![Compatibility](https://img.shields.io/badge/compatibility-system%20support-4B6B8A?style=for-the-badge&logo=linux&logoColor=white)

**Distributions**

Tested on Arch and CachyOS. The other distributions still need more testing.

| | Name | Status |
|:--:|------|---------|
| <img src="https://cdn.simpleicons.org/cachyos" alt="CachyOS" width="22"> | CachyOS | ![Tested](https://img.shields.io/badge/tested-1A7F37) |
| <img src="https://cdn.simpleicons.org/archlinux" alt="Arch Linux" width="22"> | Arch Linux | ![Tested](https://img.shields.io/badge/tested-1A7F37) |
| <img src="https://cdn.simpleicons.org/endeavouros" alt="EndeavourOS" width="22"> | EndeavourOS | ![Testing](https://img.shields.io/badge/testing-D4A72C) |
| <img src="https://cdn.simpleicons.org/fedora" alt="Fedora" width="22"> | Fedora | ![Testing](https://img.shields.io/badge/testing-D4A72C) |
| <img src="https://cdn.simpleicons.org/manjaro" alt="Manjaro" width="22"> | Manjaro | ![Testing](https://img.shields.io/badge/testing-D4A72C) |
| <img src="https://cdn.simpleicons.org/linux" alt="Linux" width="22"> | Garuda Linux | ![Testing](https://img.shields.io/badge/testing-D4A72C) |
| <img src="https://cdn.simpleicons.org/nobaralinux" alt="Nobara" width="22"> | Nobara | ![Testing](https://img.shields.io/badge/testing-D4A72C) |
| <img src="https://cdn.simpleicons.org/opensuse" alt="openSUSE" width="22"> | openSUSE Tumbleweed | ![Testing](https://img.shields.io/badge/testing-D4A72C) |
| <img src="https://cdn.simpleicons.org/gentoo" alt="Gentoo" width="22"> | Gentoo | ![Testing](https://img.shields.io/badge/testing-D4A72C) |
| <img src="https://cdn.simpleicons.org/kde" alt="KDE" width="22"> | KDE neon | ![Testing](https://img.shields.io/badge/testing-D4A72C) |

<br>

**Init systems**

| Init system | Support | Testing |
|-------------|---------|---------|
| systemd | Supported | Completed |
| OpenRC | Supported | In progress |

<br>

**Plasma versions**

| Plasma | Support | Since |
|--------|---------|-------|
| 6.5 and older | Not supported | Not applicable |
| 6.6 | Supported | v0.1.0 |
| 6.7+ | Supported | v0.19.0 |

<br>

![Roadmap](https://img.shields.io/badge/project-roadmap-6B4B8A?style=for-the-badge&logo=github&logoColor=white)

Still to come: icon polish, broader distro testing, and more app themes and widgets.

<details>
<summary><b>Open the full roadmap</b></summary>

| Component | Description | Status |
|-----------|-------------|:------:|
| Color Schemes | Light and dark colors that carry across the desktop | Available |
| Wallpapers | Bundled Tahoe Iridescence and Landscape wallpapers | Available |
| Fonts | SF Pro Display, Text, Rounded, and Mono | Available |
| Cursors | Tahoe-style pointers to match the desktop | Available |
| Plasma Theme | Glass panels and desktop menus | Available |
| Kvantum Theme | A matching look for Qt apps in light and dark modes | Available |
| GTK Theme | Matching themes for GTK 2, 3, and 4 apps | Available |
| Acrylic Glass | Blur and wallpaper refraction for the glass look | Available |
| KDE Rounded Corners | Rounded window corners | Available |
| Auto Theme Switcher | Light at 06:00, dark at 18:00, while keeping wallpapers you choose | Available |
| OLED Care | Small, optional panel shifts to help reduce burn-in risk | Available |
| Installer UI | Choose what to install or remove in a graphical window | Available |
| Installer TUI | Make the same choices in the terminal and follow live progress | Available |
| Localization | Installers and widgets in English, Spanish, and Simplified Chinese | Available |
| Aurorae Decorations | macOS-style title bars and window buttons | Available |
| Global Menu | Menus from compatible apps in the top bar | Available |
| Dock Task Manager | Your pinned apps, hover zoom, and notification badges | Available |
| Nautilus | A Finder-style layout for browsing your files | Available |
| Launcher | Search for apps or browse the grid | Available |
| Trash | Open or empty the Trash from the Dock | Available |
| Sounds | Matching notification and system sounds | Available |
| Boot Screen | A logo on every monitor, a progress bar, and a masked LUKS2 unlock prompt | Available |
| Shutdown Screen | The same splash during shutdown and reboot, without the progress bar | Available |
| Firefox Theme | Matching browser styling, with backups and cleanup for each profile | Available |
| Icons | Light and dark icons are bundled; coverage and consistency still need polish | In progress |
| Multi-Distro Support | More desktop testing across the listed distros, including KDE neon | In progress |
| OpenRC Testing | Scheduled theme changes and OLED care on OpenRC | In progress |
| Konsole Theme | A terminal profile that matches the desktop | Planned |
| Kate Theme | Matching colors for the text editor | Planned |
| SDDM Theme | A matching login screen | Planned |
| Calendar | A calendar you can open from the top bar | Planned |
| Control Center | Quick access to common desktop settings | Planned |
| System Preferences | A macOS-style launcher for system settings | Planned |
| OS Selector | A boot menu for choosing your operating system | Planned |

</details>

<br>

![Contributing](https://img.shields.io/badge/contributing-A04B4B?style=for-the-badge&logo=github&logoColor=white)

Bug reports are the most valuable contribution right now: **[open an issue](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new)** or choose **Apple menu → About This Computer → Report a Bug…** from the desktop.

Please include:

- Your Plasma version: `plasmashell --version`
- Your distro: `grep PRETTY_NAME /etc/os-release`
- The theme version: `cat VERSION`
- A screenshot or recording for visual issues

Pull requests are welcome. Keep them focused and test them with the `./vm` harness before submitting. See [CONTRIBUTING.md](CONTRIBUTING.md) for the project workflow.

<br>

![Disclaimer](https://img.shields.io/badge/disclaimer-not%20affiliated%20with%20apple-6B6B6B?style=for-the-badge&logo=apple&logoColor=white)

This is an independent reimplementation inspired by the macOS aesthetic. It is not affiliated with or endorsed by Apple or KDE. "macOS" and "Apple" are trademarks of Apple Inc.

The bundled wallpapers, system sounds, and SF Pro / SF Mono fonts remain Apple's property and are not covered by this project's license. All other code and theme assets are original or derived from compatibly licensed open-source work.

Licensed [GPL-3.0](LICENSE).

<br>

![Credits and inspiration](https://img.shields.io/badge/credits-%26%20inspiration-8A6B4B?style=for-the-badge&logo=apple&logoColor=white)

Thanks to the open-source projects that inspired this one or fed assets into it. Everything here is maintained independently:

- **[EliverLara](https://github.com/EliverLara/TahoeLauncher)**: `TahoeLauncher`, the inspiration for the Launcher plasmoid.
- **[vinceliuice](https://github.com/vinceliuice)**: `MacTahoe-icon-theme` for the icons, cursors, and GTK inspiration; and the [`MacTahoe-gtk-theme` Firefox CSS/SVG](https://github.com/vinceliuice/MacTahoe-gtk-theme/tree/main/other/firefox), maintained here as an MIT-licensed fork and integrated with this project's profile backup and restore system.
- **[taj-ny](https://github.com/taj-ny/kwin-effects-forceblur)** and **[4v3ngR](https://github.com/4v3ngR/kwin-effects-glass)**: Better Blur and its glass fork, the starting point of the Acrylic Glass effect (the KWin blur authors stay credited in the source headers).
- **[luisbocanegra](https://github.com/luisbocanegra/plasma-panel-colorizer)**: `plasma-panel-colorizer` v7.3.0, bundled offline and installed by the layout step to tint the panels (GPL-3.0, license shipped alongside).
- **[Matin Lotfaliei / KDE-Rounded-Corners](https://github.com/matinlotfali/KDE-Rounded-Corners)**: the GPL-3.0 KWin rounded-window effect, fetched from the pinned v0.9.0 release and built online against the host KWin SDK (license installed alongside).
- **[ful1e5](https://github.com/ful1e5)**: `apple_cursor`, inspiration for an alternate macOS-style cursor.
- **[sahibjotsaggu](https://github.com/sahibjotsaggu)**: `San-Francisco-Pro-Fonts`, where the SF Pro / SF Mono bundle comes from.
- **[Lucide](https://github.com/lucide-icons/lucide)**: copy icons bundled in the global menu (ISC, © Lucide Contributors).
- **[512pixels.net](https://512pixels.net/projects/default-mac-wallpapers-in-5k/)**: high-resolution macOS wallpaper archive.

Please support their efforts too: star their repos, report bugs upstream, and contribute back when you can.

If a credit is missing, please [open an issue](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new).
