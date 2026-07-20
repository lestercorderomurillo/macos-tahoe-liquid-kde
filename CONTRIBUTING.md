# Contributing

Thanks for considering a contribution. This project is GPL-3.0 — forks are welcome, but anything you redistribute has to stay open under the same license and keep the copyright notices intact. No warranty, no liability.

## Before you start

- **Open an issue first** for anything bigger than a one-line fix. I'd rather discuss the approach than reject a finished PR over scope.
- **One concern per PR.** Bugfix + refactor + new feature in the same PR is three PRs.
- **AI assistants are fine** — just review what they produce. You're the author on the PR; make sure you can explain the change and that it actually fits the codebase.

## Setup

### Dependencies (Arch-based)

```sh
sudo pacman -S python kwriteconfig6 kreadconfig6 qdbus6 kvantum \
    plasma-workspace plasma-framework6 \
    cmake extra-cmake-modules ninja qt6-base
```

KDE Plasma 6.6+ is required to actually exercise the desktop pieces. Most static + step tests run anywhere with `python3` + `kwriteconfig6`.

### Install / uninstall / test

```sh
git clone https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde
cd macos-tahoe-liquid-kde

sudo ./install       # installs user assets plus compiled system Qt6 plugins
sudo ./uninstall     # removes current and legacy system Qt6 plugins
./test               # full pytest suite (~20s)
./test --vm          # plymouth render harness (requires root, see tests/vm/)
```

Live theme switch without restarting the session:

```sh
mac-tahoe-theme-switch dark      # explicit
mac-tahoe-theme-switch light
mac-tahoe-theme-switch auto      # re-enable the 06:00 / 18:00 timer
```

Reload Plasma after a manual fix without a full logout:

```sh
kquitapp6 plasmashell
sleep 1
kstart plasmashell
```

## Project layout

```
src/
  scripts/              Python installer (CLI + step modules)
    cli.py              Top-level dispatcher
    theme_switch.py     Light/dark switcher (also installed as ~/.local/bin/mac-tahoe-theme-switch)
    steps/              One module per install/uninstall step
      apply.py          Live LAF + colour scheme apply
      plymouth.py       Boot splash
      acrylic_glass.py  Bundled KWin glass effect
      rounded_corners.py  Verified online KWin rounded-corners build
      layout.py         Panel + applet layout
      theme_switch.py   Installs the theme-switch units + bin
      ...
  offline/              Bundled assets (Rounded Corners is the sole online exception)
    plasmoids/          Self-contained QML plasmoids (menu, launcher, trashcan, ...)
    color-schemes/      MacTahoeLiquidKdeLight.colors / Dark.colors
    look-and-feel/      LAF packages (light + dark)
    plasma-theme/       Plasma SVG themes
    aurorae/            Window decoration assets
    kvantum/            Kvantum widget style
    gtk/                GTK 2/3/4 themes
    plymouth/           Boot splash assets
    kwin-effects/       Acrylic Glass C++ effect source
    wallpapers/         Bundled MacTahoe wallpaper packs
  build/                Compiled artefacts (gitignored)
tests/                  Pytest suite
  conftest.py           Sandbox fixture + live-state safety net
  test_*.py             One file per concern
  vm/                   Plymouth render harness (root-required)
install / uninstall     Python entry points (chmod +x), dispatch into src/scripts/cli.py
```

Two entry points, one codebase. The shell wrappers `install` / `uninstall` at the repo root invoke `src/scripts/cli.py` with the correct phase.

Feature-based, NOT layer-based: a step owns its slice end-to-end. Don't dump every step's logic into a single `steps.py`.

## Tests

**Run `./test` before every PR.** No exceptions. The suite is fast (~20s, 900+ tests).

The session-scoped safety net in [tests/conftest.py](tests/conftest.py) snapshots live KDE config + systemd unit state at session start and restores any drift on teardown. If your change leaks, you'll see a `LIVE-STATE LEAK DETECTED` banner naming the file or unit that moved. Track it down — don't suppress the warning.

Add a regression test for every bug you fix and every behaviour you add. PRs without tests get bounced unless there's a real reason testing is impossible (and that reason goes in the PR description).

If you add a step that talks to the live session (`user_service_manager_command`, `kvantummanager`, `plasma-apply-*`, dconf), shim it via `make_live_shim_dir` in `tests/conftest.py` — don't let tests touch the maintainer's real desktop.

```sh
./test                                          # full suite
./test tests/test_theme_switch.py               # one file
./test -k "test_apply_finishes_cycle"           # one test
MAC_TAHOE_SKIP_LIVE_SAFETY_NET=1 ./test         # CI / no-live-session
```

## Branching and commits

- `main` is always releasable. Direct commits are fine for small fixes.
- For larger features, open a short-lived branch and merge via PR.
- Commit messages follow the project style — area prefix, em-dash, summary:

```
Release v0.13.9 — fix corner-rendered shutdown splash detection
README: move Tahoe Finder above Menu
acrylic-glass: softer blur, more grain, stronger RGB drift defaults
plymouth: tighter logo+bar layout + render harness fix
```

- Subject under ~70 chars, imperative mood (`Fix corner-rendered shutdown splash`, not `Fixed`).
- Body explains *why* — the bug, the trade-offs, what you rejected.
- **No `Co-Authored-By: Claude` (or any AI tool) trailer.**

## Code style

### Python (`src/scripts/`)

- Stdlib only. No new third-party dependencies without a discussion.
- 4-space indent, type hints on public functions.
- Docstrings only where the *why* is non-obvious — name-driven self-documentation otherwise.
- Read existing files to match the tone. `theme_switch.py` and `steps/plymouth.py` are good references.
- Blocking subprocess calls go through `utils.run_user` (drops privs + Qt6 setuid guard) or `subprocess.run` with an explicit `timeout=`.
- Never shell out to `openssl`, `sed`, `awk` from inside Python — use stdlib `re` / `configparser` / `pathlib`.

### QML (`src/offline/plasmoids/`)

- Match the surrounding plasmoid. Each plasmoid is self-contained — no shared QML library between them.
- **Plasmoids must NOT depend on third-party C++ plugins.** The only exception is `org.kde.plasma.private.kicker` (ships with plasma-workspace, always present).
- Always system font — never hardcode font names or sizes.
- Hover tiles use the glass effect (semi-transparent fill, 0.5px border, 22px radius), not outlined borders.
- Keep corner-radius families distinct: normal windows and the bottom Dock are 22px, dialogs/tooltips are 14px, and compact controls/popup assets retain their smaller values. SVG radii must be compared after applying their group transform.
- Use `Kirigami.Theme.*` for colors, not hardcoded hex.

### Naming

- **PascalCase** for theme names: `MacTahoeLiquidKde-Dark`, `MacTahoeLiquidKde-Light`.
- **kebab-case** for IDs: `org.kde.mac-tahoe-liquid-kde.<component>`.
- Plasmoid suffixes are simple nouns: `.menu`, `.launcher`, `.trashcan` — not compound words.

See [CLAUDE.md](CLAUDE.md) for the full convention list.

## i18n

User-facing strings in QML go through `i18n("…")` from `org.kde.kirigami` / `QtCore`. Don't hardcode English (or any other language) strings in plasmoid UI. The installer's CLI output (`ok()` / `info()` / `warn()` / `fail()`) is English-only by design — keep messages short and actionable.

## What NOT to do

- Don't bypass `./test` with `--no-verify` or skip the safety net.
- Don't `--amend` published commits or force-push to `main` / `master`.
- Don't add external author names to file headers, plasmoid metadata, or screenshots. Attribution lives in the README and is managed by the maintainer.
- Don't reference any third-party operating system or vendor by name in code, comments, commit messages, or PR titles. The README is the only place that mentions inspirations.
- Don't add EAS / paid services / phone-home telemetry / network calls outside the release updater and the pinned, checksum-verified Rounded Corners download step.
- Don't open a PR that disables tests instead of fixing them.
- Don't auto-edit `/etc/mkinitcpio.conf`, `/etc/default/grub`, or other system files outside the explicit `sudo_install_file` / `sudo_remove` helpers in `steps/_helpers.py` — the `_check_prereqs` policy is detect-and-warn, not auto-fix.

## Reporting bugs

Open an issue with:

1. Your distro + Plasma version (`plasmashell --version`, `cat /etc/os-release | grep PRETTY_NAME`).
2. The project version (`cat VERSION` in the repo).
3. What you ran, what you expected, what happened. Include the exact terminal output if any.
4. Logs from `journalctl --user -b -1` if the problem touches the theme switcher or systemd units.

Triage is best-effort — this project runs on the side. PRs always move faster than issues.

## Code of conduct

Be a decent human. I'll close anything abusive, off-topic, or trying to drag this project into a fight that isn't about the code.
