# AGENTS.md

This file is the authoritative reference for working on
**macos-tahoe-liquid-kde**. Mirrors at `CLAUDE.md`, `CODEX.md`, and
`GEMINI.md` point back here so each agent finds the same content under
the filename it expects.

## Project Overview

> Disclaimer: This project is not affiliated with KDE, the KDE e.V.
> organization, or Apple Inc. It is an independent, community-driven
> theme set that gives KDE Plasma 6 a macOS Tahoe-inspired look. It
> must never pretend to be an official KDE or Apple product.

macos-tahoe-liquid-kde is an installer + theme pack that turns a stock
KDE Plasma 6 desktop into a macOS Tahoe lookalike: top menu bar, Dock,
Aurorae window decorations, Plasma + Kvantum + GTK + icon themes,
Acrylic Glass KWin effect, light/dark global theme with timed
switching, wallpapers, fonts, cursors, and a Plymouth boot splash.

**Target platforms.** KDE Plasma 6.6+ distros on either systemd or
OpenRC. The init system is a supported *dimension*, not a distro
boundary — the two scheduled features (OLED care, timed theme switch)
install a systemd user timer under systemd and a per-user `crontab`
line under OpenRC, chosen by `init_system()` in the distro layer.
OpenRC is supported generically across distros; it is verified by hand
in a Gentoo OpenRC VM (`./vm`), not in the container matrix. The
container matrix covers Arch, CachyOS, Manjaro, EndeavourOS, Garuda,
Gentoo, Fedora, Nobara, and openSUSE Tumbleweed on their default
(systemd) profiles; of these only **Arch and CachyOS are marked
*tested* in the README — every other distro is *testing* / work in
progress**. Immutable rpm-ostree distros
(Silverblue, Kinoite) are explicitly out of scope: the installer
writes into `/usr/lib*` and `/usr/share`, which are read-only on those
systems and need either an rpm/Flatpak-extension wrapper or an
rpm-ostree layering path that this project does not maintain. There is
no non-KDE path.

**Distribution target:** GitHub releases + AUR.
**License:** GPL-3.0 for the work as a whole — the bundled Acrylic
Glass fork and several theme assets are GPL-3, and every other
component's grant (GPL-2.0-or-later, LGPL-2.0-or-later, KDE
tri-license) is GPL-3-compatible. Individual files keep their original
SPDX headers; the Apple wallpaper imagery is not covered by the FOSS
license.
**Stack:** Python 3.10+ CLI installer dispatching into per-feature
steps; a PyQt6 graphical installer (`./installer`) that wraps the CLI;
QML plasmoids; C++ Qt6 plasmoids (Global Menu, Dock Task Manager) and
a KWin effect (Acrylic Glass) compiled at install time against the
host's Qt6 / KDE Frameworks 6. All theme assets are bundled offline in
`src/offline/` — the install pipeline has no download phase.

## Naming Convention

- **PascalCase** for theme names: `MacTahoeLiquidKde-Dark`,
  `MacTahoeLiquidKde-Light`.
- **kebab-case** for IDs: `org.kde.mac-tahoe-liquid-kde.<component>`.
- Plasmoid suffixes are simple nouns: `.menu`, `.launcher`, `.trashcan`
  — not compound words like `.kpplemenu`.
- The user-facing CLI binary is `mac-tahoe-theme-switch`. Repo entry
  points are `./install`, `./uninstall` (TUI wizard on a bare TTY run,
  classic flow otherwise), `./legacy-install`, `./legacy-uninstall`
  (always the classic confirm-and-flags flow), and `./installer`
  (graphical UI) — no `.sh` extension.

## Branding

- No external author references in metadata, configs, or QML headers
  — the user maintains attribution separately.
- Mirror files keep source URLs (functional, not attribution).
- README **Credits** section is managed manually by the user.
- Do NOT add "fork of X" or "based on Y" to README descriptions —
  use "inspired by" wording.
- Do NOT reference Pear OS.

## macOS Terminology

| KDE default        | Project uses     |
| ------------------ | ---------------- |
| Recent Applications| Suggestions      |
| Applications       | Apps             |
| Show more          | Show All         |

Menu plasmoid entries: About This Computer, System Settings, App
Store, Force Quit, Sleep, Restart, Shut Down, Lock Screen, Log Out.

## UI/UX Conventions

- Menu plasmoid dropdown items use icons (matches the macOS Tahoe
  Apple menu).
- Hover tiles: glass effect (semi-transparent fill, 0.5px micro
  border, 22px radius) — not outlined borders.
- System font always — never hardcode font names or sizes.
- Popup plasmoids are fixed-size, not resizable.
- Top panel is applets-only floating (not full-floating).
- Category switcher must support both mouse drag and wheel scroll.

## Repository Layout

| Path                          | Contents |
| ----------------------------- | -------- |
| `install` / `uninstall`       | Thin wrappers that exec `src/scripts/cli.py` with `tui=True`. Bare runs on a real TTY (no flags, no `MTTKDE_NO_CONFIRM`) open the curses selection wizard from `src/scripts/install_tui.py`; anything else falls through to the classic flow. Both require sudo. |
| `legacy-install` / `legacy-uninstall` | Same engine with `tui=False` — always the classic confirm-and-flags flow, never the wizard. Both require sudo. |
| `installer`                   | Graphical installer entry point; execs `src/installer/installer_ui.py`. |
| `vm`                          | Boots a graphical KDE Plasma VM per distro with the repo mounted (`./vm cachyos`, `./vm all`). |
| `test`                        | Pytest runner for the full suite. |
| `VERSION`                     | Single-line semver string read by `paths.read_version()`. |
| `features.json`               | Per-feature enable flags, written by `--only` / `--no-*` and read on the next run. |
| `src/scripts/`                | Installer Python. **Flat layout — no `installer/` subdir.** |
| `src/scripts/cli.py`          | Entry point. Parses flags, runs preflight, dispatches steps. |
| `src/scripts/install_tui.py`  | Curses selection wizard + live progress screen for bare `sudo ./install` / `sudo ./uninstall` TTY runs. Stdlib only (guarded import — openSUSE splits python3-curses); any failure falls back to the classic flow in `cli.py`. The progress screen runs the install body on a worker thread, redirects stdout/stderr to `/tmp/mttkde-install.log`, and polls the same progress file the GUI reads. |
| `src/scripts/preflight.py`    | 9-check fail-fast probe (sudo, paths, Qt6, Plasma, kwriteconfig6, DBus, kded6, disk, plasmoid IDs). |
| `src/scripts/distro.py`       | The ONLY module that knows per-distro paths and package manager commands. |
| `src/scripts/paths.py`        | Repo-relative paths only. Never shells out, never reads /etc/os-release. |
| `src/scripts/step_runner.py`  | Imports and runs per-phase functions on each step module. |
| `src/scripts/utils.py`        | `run_user`, `kw_write`, `kw_read`, `have`, `fetch`, `safe_copy`, `pkg_install`, `pkg_sync_install`, `qdbus_call`. |
| `src/scripts/theme_switch.py` | `mac-tahoe-theme-switch` implementation. Installed as a console script. |
| `src/scripts/oled_care.py`    | `mac-tahoe-oled-care` implementation — opt-in panel pixel shift for OLED monitors. |
| `src/scripts/state.py`        | `RunTracker` — writes the last-run summary (status, argv, timestamps) to `~/.local/state/mac-tahoe-liquid-kde/last-run.json`. |
| `src/scripts/log.py`          | `banner`, `step`, `ok`, `warn`, `info`, `note`, `fail` — single source of UI styling. |
| `src/scripts/steps/`          | One module per feature. Implements `deps`, `build`, `install`, `uninstall`, `restart_plasma` as needed. |
| `src/scripts/steps/_helpers.py` | `sudo_install_file`, `sudo_install_tree`, `sudo_remove`, `_as_root` context manager. |
| `src/installer/`              | Graphical installer UI: `installer_ui.py` (PyQt6) + QML windows + art. Wraps `./install` / `./uninstall`; the CLI stays the source of truth. |
| `src/offline/`                | All assets bundled in the repo: plasmoids, plasma theme, kwin-effects, aurorae, color-schemes, cursors, fonts, gtk, icons, kvantum, look-and-feel, layouts, plymouth, nautilus, wallpapers, plus the systemd unit + timer. |
| `src/offline/wallpapers/<id>/`| One folder per wallpaper, JPEG q90 + `metadata.json` (3840×2160 minimum). Fully offline — no `download()` phase. |
| `tests/`                      | pytest suite. `./test` is the runner. |
| `tests/containers/`           | One Dockerfile per supported distro + `run_in_container.py` + `run_matrix.sh`. |
| `tests/vm/`                   | Plymouth render-capture harness (output gitignored). |

## Step Module Contract

Each module under `src/scripts/steps/` implements any of these
functions; missing ones are skipped:

| Phase            | When run                                  | Purpose |
| ---------------- | ----------------------------------------- | ------- |
| `deps()`         | Before any other phase, install-time only | Return list of `cmd:pkg` tokens; `cli.py` resolves them via `distro.package_for()`, probes each package with `distro.package_installed()`, and installs ONLY the genuinely-missing ones (installing present packages would risk the partial-upgrade file-conflict trap). |
| `build()`        | After deps                                | Compile C++ (Global Menu, Task Manager, Acrylic Glass effect). |
| `install()`      | Main pass                                 | Copy files, write configs, register kwin/plasma settings. |
| `uninstall()`    | `./uninstall` run                         | Remove installed files; clean legacy `/usr/lib/qt6` artefacts. |
| `restart_plasma()` | Final pass of `./install`               | The one allowed plasmashell restart per session. |

Output convention inside `install()`:

1. Per-item `ok()` / `reinstall()` lines first.
2. Then any "Foo set to / applied" status lines.
3. The `info()` summary count is always the LAST line of the step.

## Architecture — Sudo Policy

Both `./install` and `./uninstall` require sudo. The compiled C++
plasmoids and the Acrylic Glass KWin effect land under the system Qt6
libdir (the dir `qmake6` reports — never hardcoded), because Qt6
doesn't walk `~/.local/lib/qt6` in a default Plasma session.

- The sudo precondition is checked in Python via `os.geteuid()`. If
  not root, `cli.py` exits immediately with the canonical
  `Re-run as: sudo ./install` line. The outer shell handles the actual
  sudo prompt so we sidestep the `pam_unix conversation failed`
  cascade that bricks terminals where sudo can't read the password
  (VSCode integrated, tmux+OSC133, sandboxes that pollute the TTY).
- After the euid check passes, the CLI drops effective UID to
  `SUDO_USER` via `os.setegid(SUDO_GID); os.seteuid(SUDO_UID)`. Files
  written from then on land with normal user ownership.
- The `sudo_install_file` / `sudo_install_tree` / `sudo_remove`
  helpers in `steps/_helpers.py` re-elevate via the `_as_root()`
  context manager (`seteuid(0)`) for the one operation that needs
  root, then drop back. Real UID stays at 0 the whole time so the
  trip back to root is always permitted.

## Architecture — Auto-Update on Install

`./install` checks GitHub releases on every launch.
`MAC_TAHOE_NO_UPDATE_CHECK=true` skips the check; `--check-update`
checks and exits. When a newer release exists and the repo is a clean
git checkout, `auto_update_and_reexec` pulls `--ff-only` as the
invoking user (never root — root-owned objects would wreck the user's
repo) and re-execs `./install` so the freshly-pulled code performs the
install. `MAC_TAHOE_UPDATED=1` is the recursion guard. A dirty
checkout, missing git, or a failed pull falls back to installing the
current version with a manual `git pull && ./install` hint.

## Architecture — Distro Detection Layer

`src/scripts/distro.py` is the ONLY file allowed to know per-distro
paths, package manager commands, or the host init system. Steps and
preflight must never hardcode `/usr/lib/qt6`, `pacman -S`, `dnf
install`, or probe for systemd/OpenRC themselves — call
`init_system()`.

| Function                              | Returns |
| ------------------------------------- | ------- |
| `current_distro()`                    | Lowercase `/etc/os-release` ID (`arch`, `cachyos`, `gentoo`, `fedora`, `opensuse-tumbleweed`, ...). |
| `distro_id_like()`                    | ID_LIKE chain so downstream distros (Nobara → fedora, Garuda → arch) inherit the parent's package map. |
| `init_system()`                       | `"systemd"` when `/run/systemd/system` is present, else `"openrc"`. The ONLY sanctioned init probe — the scheduled-feature steps branch on it to pick a systemd user timer vs. a per-user crontab line. |
| `qt6_plugins_dir()` / `qt6_qml_dir()` | Asks `qmake6` → `qtpaths6` → `pkg-config Qt6Core` in that order. Falls back to the per-distro libdir table only when that dir actually exists on disk. Otherwise raises `Qt6PathsMissing` with the distro-appropriate install hint. |
| `package_for(token)`                  | Translates an Arch package name from a step's `deps()` token into the equivalent on the current distro (`g++:gcc` → `gcc-c++` on Fedora, `sys-devel/gcc` on Gentoo). |
| `package_installed(pkg)`              | Direct package-database probe (`pacman -Q`, `rpm -q`, ...) so dep resolution installs only what's actually missing. |
| `package_manager_install_cmd()`       | Non-interactive install prefix for the current distro. |

Static guards in `tests/test_static.py`:

- `test_no_hardcoded_qt6_libdir` rejects any executable line outside
  `distro.py` / `paths.py` that mentions `/usr/lib/qt6` or
  `/usr/lib64/qt6`.
- `test_no_hardcoded_package_manager_outside_distro_layer` rejects
  `pacman -S` / `dnf install` / etc. anywhere else.

Don't fight these — add a row to `distro.py` instead.

## Architecture — Preflight

`src/scripts/preflight.py` runs before any step touches disk. Nine
checks, fail-fast:

1. **Sudo escalation hop.** Real UID 0, effective dropped to user, the
   round-trip back to root works.
2. **Destination paths inside allowed roots.** No step would write
   outside `$HOME` or the system Qt6 libdir.
3. **Qt6 plugin search agrees with where we'd write.**
4. **Plasma 6.6+.** Compiled plasmoids link against 6.6 headers.
5. **`kwriteconfig6` + `kreadconfig6` on PATH.**
6. **DBus session bus reachable** (env var or
   `$XDG_RUNTIME_DIR/bus` socket).
7. **kded6 running** (soft — warn but don't block).
8. **Disk space** (50 MB on the Qt6 libdir partition, 100 MB on
   `$HOME`).
9. **Plasmoid ID consistency** (skipped on uninstall).

Anything that calls Qt6 binaries from preflight MUST go through
`utils.run_user`. It sets `preexec_fn=drop_privs_in_child` so the fork
has matching real / effective / saved UIDs. Qt6 binaries refuse to
run when `getuid() != geteuid()` with `FATAL: The application binary
appears to be running setuid`. Never reach for `subprocess.run`
directly from preflight — `test_plasma_version_drops_privs_in_child`
is the guard against that regression returning.

## Architecture — Live Theme Switching

`mac-tahoe-theme-switch {light|dark|auto}` is the single entry point.
The same binary runs:

- inline at the end of `./install`,
- from the post-login systemd user service (`After=plasma-plasmashell.service`),
- from the 06:00 / 18:00 systemd user timer,
- by the user manually.

`./install` writes both the service and the timer (under
`~/.config/systemd/user/`) and enables them.

Light/dark switching applies:

1. Look-and-feel package (`plasma-apply-lookandfeel -a <pkg> --keep-auto`).
2. Plasma theme, color scheme, icon theme, cursor theme, Kvantum
   theme, Aurorae window decoration, GTK theme, wallpaper.
3. The Kvantum widget-style cycle (see below).

**Kvantum cycle.** Kvantum is a Qt style plugin and cannot reload its
kvconfig in a running app — only `QApplication::setStyle()`
re-instantiates the plugin. Confirmed upstream:
<https://github.com/tsujan/Kvantum/discussions/975>.
`cycle_widget_style_live(target)` writes `widgetStyle=Breeze`,
broadcasts `KGlobalSettings.notifyChange` + the xdg-portal
`SettingChanged` signal, then writes the target back and broadcasts
again. Run the cycle AFTER `apply_extras()` so `kvantummanager --set`
has rewritten the kvconfig; otherwise Kvantum re-instantiates against
the old config and the menu visuals stay stale.

**Look-and-feel retry schedule.** `_apply_lookandfeel_live` waits 2s
before the first attempt (DBus name registration race after
`After=plasma-plasmashell.service` clears), then 6s between retries.
Worst case: 2 + 6 + 6 = 14s of sleeps. Don't shorten the 2s lead-in
— `plasma-apply-lookandfeel` exits 0 against a not-yet-ready bus
without actually re-rendering.

## Architecture — OLED Care (opt-in)

`mac-tahoe-oled-care {shift|restore|status}` guards OLED panels against
burn-in. Off by default; `./install --oled-care` enables it. A systemd
user timer (`mac-tahoe-liquid-kde-oled.timer`) fires `shift` every 5
minutes: fill-length panels (the top bar) cycle height up in 2 px steps
(32 → 34 → … → 40 → 38 → …) — a full-width panel cannot slide sideways,
Plasma clamps its offset — and every other panel (the dock) cycles
offset both directions the same way. One
`plasmashell evaluateScript` call does the whole pass. Two install-time
knobs: `--oled-interval=N` (minutes, 1-59, stamped into the timer's
`OnCalendar`) and `--oled-max-shift=N` (px, 1-16, stamped into
`ExecStart=... --max-px N`); both persist in `features.json`. The
applied deltas are stored alongside the per-panel base geometry in
`~/.local/state/mac-tahoe-liquid-kde/oled-care.json`, so `restore`
stays correct even when the amplitude changed between runs. When
current geometry ≠ base + last delta the panel was moved deliberately,
so the base is re-captured instead of fought. `restore` undoes only the
currently-applied delta; the step's install() with the flag off tears
the units down, so a plain re-install is self-healing.

## Architecture — Wallpapers

Wallpapers are fully bundled. Every entry under
`src/offline/wallpapers/<id>/` is a JPEG q90 (re-encoded from 6K PNG
originals) plus `metadata.json`. Total bundled is ~50 MB.

PNG / JPEG re-compression with zip / xz / zstd was tested empirically
and saves 0% (the bytes are already entropy-coded). JPEG q90 is the
only viable size reduction.

The install pipeline has no download phase at all — icons, fonts, and
cursors are bundled the same way. The static test
`test_repo_ships_full_macos_wallpaper_set` enforces that every name in
`_FIXED_NAMES` ships a `3840x2160` (or larger) image with a metadata
file. Don't add a network-fetch fallback.

## Architecture — Dependency Guards

Every step that uses an external tool checks the tool exists before
invoking it and surfaces a `warn()` when it doesn't:

| Step                    | Guard |
| ----------------------- | ----- |
| `plymouth.py`           | `_grub_is_active_bootloader()` requires BOTH `/etc/default/grub` AND a regen binary (`grub-mkconfig` or `grub2-mkconfig`) on PATH. A leftover `/etc/default/grub` on a systemd-boot user is NOT a signal to patch GRUB. |
| `kvantum.py`, `window_decorations.py`, `plasma_theme.py` | `kw_write()` returns are checked; failure emits an explicit `warn()` mentioning `kwriteconfig6`. |
| `fonts.py`              | `fc-cache` is guarded by `have("fc-cache")`. Missing fontconfig is a warn, not a fail — fonts still copy and appear after re-login. |
| `acrylic_glass.py`      | Build deps declared via `deps()` tokens and probed with `distro.package_installed()` before invoking cmake/make. |

`tests/test_step_guards.py` covers the kwriteconfig6 missing path and
the fc-cache missing path; `tests/test_plymouth_step.py` covers the
bootloader probe.

## Architecture — Container CI Matrix

| File                         | Role |
| ---------------------------- | ---- |
| `tests/containers/Dockerfile.<distro>` | One per supported distro. CachyOS pulls both `archlinux-keyring` and `cachyos-keyring` after `pacman-key --init && pacman-key --populate archlinux cachyos`. |
| `tests/containers/Dockerfile.arch-kdeunstable` | Canary against Arch's `[kde-unstable]` staging repo — catches the next Plasma release early. `continue-on-error` in CI (like Gentoo). |
| `tests/containers/Dockerfile.gentoo-base` | Builds the GHCR base image `ghcr.io/lestercorderomurillo/mttkde-gentoo-base` so qtbase doesn't compile from source on every PR. |
| `tests/containers/run_in_container.py` | Per-distro probe: qmake6 resolves, the distro layer agrees with what qmake6 reports, every `package_for()` token resolves in the distro's repo (with a "transient network" skip so flaky upstream CDN edges don't tank CI), preflight destination checks, pytest. |
| `tests/containers/run_matrix.sh` | Local runner. CI runs the same workflow via `.github/workflows/test.yml`. |

When a probe fails, the script scans stderr for transient-network
markers (`"Failed to retrieve"`, `"Could not resolve host"`, repo
metadata errors) and emits `SKIP` instead of `FAIL`. Anything else is
a genuine missing package and fails CI.

## File Map — Steps

| Module                        | Responsibility |
| ----------------------------- | -------------- |
| `acrylic_glass.py`            | Compile and install the Acrylic Glass KWin effect (.so + QML + metadata to the system Qt6 libdir). |
| `apply.py`                    | Wraps `mac-tahoe-theme-switch` invocation from inside `install`. |
| `apps.py`                     | Misc app config tweaks (dolphin, konsole, etc.). |
| `color_schemes.py`            | Installs `MacTahoeLiquidKde-{Light,Dark}.colors` under `~/.local/share/color-schemes/`. |
| `cursors.py`                  | Cursor theme install. |
| `fonts.py`                    | SF Pro / SF Mono → `~/.local/share/fonts/`, `fc-cache` if available. |
| `globalmenu.py`               | Build + install the Global Menu C++ plasmoid. |
| `global_theme.py`             | Plasma look-and-feel package (`MacTahoeLiquidKde-{Light,Dark}`). |
| `gtk.py`                      | GTK 2/3/4 theme. |
| `icons.py`                    | macOS-style icon set. |
| `kvantum.py`                  | Kvantum Qt widget style. |
| `layout.py`                   | Top panel + dock layout. May be retried once after `restart_plasma` if the first pass raced plasmashell's plugin discovery. |
| `nautilus.py`                 | Nautilus integration (file manager set as default on KDE for users who prefer it). |
| `oled_care.py` (step)         | Installs the opt-in OLED-care binary + systemd user timer; flag off tears them down; uninstall restores panel geometry. |
| `plasma_theme.py`             | Translucent panels and dock SVGs. |
| `plasmoids.py`                | QML plasmoids: Menu, Launcher, Trashcan, IconTasks. |
| `plymouth.py`                 | Boot splash. GRUB patch behind `_grub_is_active_bootloader()`; `--no-grub-modify` opt-out exists. |
| `portals.py`                  | Route xdg-portal FileChooser / AppChooser to KDE (fixes stale dialog colors). |
| `sddm.py`                     | Login screen theme. |
| `sounds.py`                   | Notification and event sounds. |
| `theme_switch.py` (step)      | Installs the `mac-tahoe-theme-switch` binary, systemd user service, and timer. |
| `wallpapers.py`               | Copies the bundled wallpaper set. No network. |
| `window_decorations.py`       | Aurorae assembly (decoration.svg + rc + button icon SVGs + metadata per theme dir) + kwinrc `org.kde.kdecoration2`. |

## Logging Convention

`src/scripts/log.py` is the single source of UI styling.

- `banner(version)` — rainbow Apple logo + version line, ONCE per
  invocation, at the top.
- `step(n, total, name)` — `Step N/T: Foo...`.
- `ok("...")` — green check, per-item success.
- `reinstall("...")` — yellow arrow, per-item idempotent re-apply.
- `warn("...")` — yellow warning that does NOT abort.
- `note("...")` — neutral context line.
- `info("...")` — summary line. Always LAST in a step.
- `fail("...")` — red error, increments `errors`, may abort.

The rainbow palette is fixed:

```
green   yellow   orange   red   purple   blue
46      226      208      196   165      33   (256-color codes)
```

## Key Conventions

### Threading and subprocesses

- Every Qt6 binary call from inside install / preflight goes through
  `utils.run_user` so the fork's real/effective UIDs match and Qt6's
  setuid guard doesn't abort it.
- `kw_write` and `kw_read` wrap `kwriteconfig6` / `kreadconfig6`. Both
  return a bool; install steps must check it.
- `qdbus_cmd()` returns `qdbus6` when present, falls back to `qdbus`.
- Never restart plasmashell during a `mac-tahoe-theme-switch`
  invocation — only the explicit `restart_plasma` step at the end of
  `install` is allowed to do that.

### Path handling

- `paths.py` is repo-relative only. It must not shell out and must
  not read `/etc/os-release`.
- Everything system-related goes through `distro.py`.
- Step modules import from `paths` for asset locations and from
  `distro` for system-side write targets.

### File writes

- New files always go through `sudo_install_file` /
  `sudo_install_tree`. They re-elevate, copy, drop back. Direct
  `shutil.copy` to a system path will fail because effective UID is
  the user by the time a step runs.
- Removals on uninstall go through `sudo_remove`.

### Config writes

- All kwinrc / kdeglobals / plasmarc writes go through `kw_write`.
- Don't open and rewrite an INI file by hand — `kwriteconfig6`
  preserves comments and case.
- `plasma-apply-lookandfeel` writes into `~/.config/kdedefaults/<file>`.
  When reading, check `kdedefaults/` first before the top-level config
  (`_read_config_cascade` in the verifier).

### kdecoration2

- Window decorations go through kwinrc `org.kde.kdecoration2` group.
- Aurorae theme directory layout per side:
  `decoration.svg` + `rc` + button icon SVGs + `metadata.json`.

## Known Pitfalls

| Issue                                          | Detail |
| ---------------------------------------------- | ------ |
| Qt6 setuid abort                               | Calling `qmake6` / `qtpaths6` / `kreadconfig6` from a process where `getuid() != geteuid()` aborts with `FATAL: ... appears to be running setuid`. Use `utils.run_user`, never bare `subprocess.run`. |
| Kvantum signal-only refresh                    | Sending `KGlobalSettings.notifyChange(StyleChanged)` alone does NOT reload kvconfig. Use `cycle_widget_style_live()` — Qt apps observe the cycle, not just the signal. |
| `plasma-apply-lookandfeel` against cold bus    | Exits 0 against a not-yet-ready DBus session without actually re-rendering. The 2s lead-in in `_apply_lookandfeel_live` exists for this — don't shorten it. |
| `kdedefaults` cascade                          | The verifier must check `~/.config/kdedefaults/<file>` first, then the top-level config. `plasma-apply-lookandfeel` writes to the kdedefaults copy, so a naive `kreadconfig6 --file kdeglobals --key ColorScheme` returns empty. |
| Legacy `/usr/lib/qt6/.../*.so`                 | Pre-current-release installs wrote compiled plasmoids to `/usr/lib/qt6`. New installs don't, but uninstall has to remove those leftovers to leave the system in a clean Breeze state. That's why `./uninstall` also requires sudo. |
| Stale `/etc/default/grub`                      | A user who switched from GRUB to systemd-boot / Limine / rEFInd may have the file lying around. `GRUB_DEFAULT.is_file()` alone is NOT proof GRUB is active — `_grub_is_active_bootloader()` requires a regen binary on PATH too. |
| Layout race after plasmashell restart          | Applying the panel layout immediately after `plasmashell --replace` sometimes races plasmashell's plugin discovery. `layout.py` is retried once after `restart_plasma`. |
| GHCR Gentoo base                               | Gentoo Dockerfile pulls a pre-built base image. If qtbase changes major version upstream, rebuild the base via the dedicated workflow, NOT in the per-PR matrix run. |
| zip / xz / zstd on JPEG-or-PNG                 | Saves 0%. Don't add a wrapped-archive transport for wallpapers — re-encode to JPEG q90 instead. |
| `plasma-apply-lookandfeel` `--keep-auto`       | Required so the LaF apply doesn't blow away the user's color-scheme follow-the-system preference. |
| `pacman-key` on stale CachyOS images           | Container Dockerfile must run `pacman-key --init && pacman-key --populate archlinux cachyos` before `pacman -Sy archlinux-keyring cachyos-keyring`. |
| Apps vanish from launcher after theme switch   | `kbuildsycoca6` reads the app list from `mimeinfo.cache`; rebuilding sycoca against a stale cache drops apps. `_flush_caches()` runs `update-desktop-database` on both the user and system `applications/` dirs BEFORE `kbuildsycoca6` (`desktop-file-utils` is a base dep). |
| Pinned taskbar apps wiped on uninstall         | `plasma-apply-lookandfeel --resetLayout` rebuilds the panel from scratch. `layout.uninstall()` captures every `launchers=` list from appletsrc first (deduped, minus our own plasmoids) and writes it back onto the default panel's icontasks. |
| GTK popups never get compositor blur           | Client-side popups (Firefox menus, popovers) receive no KWin blur, so GTK CSS popup surfaces must keep mirrored light/dark rgba alpha — literal `transparent` renders see-through (issue #11). The gtk-4.0 sheets must also define every libadwaita named color they reference; only libadwaita apps define those at runtime. `test_static.py` guards both. |

## Testing

`./test` runs the full pytest suite. Always run it before commit,
merge, and release — see the project's release-flow rules.

Highlights:

- `tests/test_static.py` — no hardcoded Qt6 libdir; no hardcoded
  package manager outside `distro.py`; every wallpaper bundled with
  metadata.
- `tests/test_preflight.py` — all 9 preflight checks; the Qt6
  drop-privs guard regression test.
- `tests/test_step_guards.py` — kwriteconfig6 missing, fc-cache
  missing.
- `tests/test_plymouth_step.py` — bootloader probe, GRUB patch
  preserves quotes.
- `tests/test_theme_switch.py` — Kvantum cycle, LaF retry schedule,
  cascade-aware reads.
- `tests/test_apply_safety.py` — no plasmashell restart from
  `mac-tahoe-theme-switch`.
- `tests/test_oled_care.py` — shift state machine, rebase-on-change
  guards, unit files, step flag gating.
- `tests/test_cmake.py` — the C++ plasmoids and KWin effect build
  configure cleanly.
- `tests/containers/run_matrix.sh` — full per-distro probe.

## What NOT to Do

- Don't add scaled variants (1.25x, 1.5x) — keep only the base theme.
- Don't use fullscreen `Window` overlays for launchers — use popup
  representations.
- Don't add session / shutdown buttons inside the Launcher — that's
  the Menu plasmoid's job.
- Don't make commits referencing "Kmenu" or "Kpple" — use "Menu" and
  "Launcher".
- Don't bypass the widget-style cycle by trying to send
  `KGlobalSettings.notifyChange(StyleChanged)` alone.
- Don't restart plasmashell during a `mac-tahoe-theme-switch`
  invocation.
- Don't hardcode `/usr/lib/qt6` or call `pacman -S` / `dnf install`
  outside `distro.py` — static tests will reject it.
- Don't call Qt6 binaries from preflight with bare `subprocess.run`
  — use `utils.run_user`.
- Don't introduce a download phase for any step — all assets are
  bundled offline in `src/offline/`.
- Don't centre tile section headers in README — they're left-aligned
  plain markdown image syntax (`![Alt](url)`), not
  `<p align="center">`.
- Don't add `Co-Authored-By: Claude` (or any AI) trailers to commits.
- Don't `--amend` published commits. Don't `--no-verify` to skip
  hooks. Don't force-push to `main`.
