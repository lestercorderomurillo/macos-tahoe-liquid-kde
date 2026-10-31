# Contributing

Thanks for considering a contribution. The project as a whole is GPL-3.0; individual component licenses remain applicable. Preserve copyright and license notices, identify distributed modifications, and meet the applicable source-distribution obligations. See [LICENSING.md](LICENSING.md) and [NOTICE](NOTICE). Contributors retain ownership of their work; no copyright assignment is requested. The applicable licenses describe the warranty and liability limits.

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

./installer          # graphical install wizard; requests privileges when needed
./uninstall          # graphical uninstall confirmation
./test               # full pytest suite
./test --vm          # plymouth render harness (requires root, see tests/vm/)
```

### Installer storage maintenance

After a verified update, both installers ask Git to perform maintenance only
when its own thresholds require it. `./installer --free-space` (also available
through `./install`) requests a full, ordinary Git repack and reports the actual
allocated space recovered. It does not launch an installation or query releases.
Golden Gate also retires its unused prepared sources after a replacement is
ready, preserving snapshots still used by another installer.

Maintenance preserves `.git`, commits, branches, tags, stashes, reflogs, index
contents and working files. It disables object pruning and reflog expiry even
when local Git settings enable them. Linked worktrees and shared object stores
are left alone; a maintenance failure never prevents an otherwise valid update.
Compaction needs temporary disk space and may recover little from an already
packed clone. Historical assets referenced by retained commits remain stored;
use a new shallow clone when a smaller history is desired, after saving local
work. Archives have no Git history to compact. No installed desktop assets,
settings, uninstall backups or arbitrary build directories are removed.

For the focused dinit integration probe, build and run the official Artix image
with dinit as PID 1 and a real cron daemon. The repository mount stays read-only;
the jobs run as the disposable `tester` user. No privileged container is needed:

```sh
docker build -f tests/containers/Dockerfile.artix-dinit -t mttkde-test-artix-dinit tests/containers
docker run -d --name mttkde-dinit-probe --network none -v "$PWD:/repo:ro" mttkde-test-artix-dinit
docker exec mttkde-dinit-probe dinitctl --system is-started cronie
docker exec -u tester mttkde-dinit-probe python /repo/tests/containers/dinit_scheduler_probe.py
docker rm -f mttkde-dinit-probe
```

The probe takes up to two minutes and checks real scheduled execution, user
identity, reinstall and cleanup. It does not establish live Plasma compatibility;
dinit still needs a complete desktop VM qualification.

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
installer               Graphical installer and uninstaller
install / uninstall     Aliases for the graphical installer and uninstaller
```

The graphical wizard invokes `src/scripts/installer_backend.py` with the selected options. The backend dispatches the shared step modules; there is no separate terminal wizard.

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

For the desktop-redirection and corner-overlap regressions (#77/#89), the
isolated capture probe also supports these modes (use a new output directory
for every run):

```sh
python tests/acrylic_glass_capture.py --plugin /path/to/kwin4_effect_shapecorners.so --rounded-shaders /path/to/built/shaders --companion-plugin /path/to/liquidglass.so --identity org.kde.dolphin --output /tmp/corners-combined
python tests/acrylic_glass_capture.py --plugin /path/to/kwin4_effect_shapecorners.so --rounded-shaders /path/to/built/shaders --desktop-surface --backend xcb --identity plasmashell --output /tmp/corners-desktop
```

The combined probe verifies visible glass inside a translucent client and zero
leakage into the corner cutouts, with grain enabled. Repeat with `--scale 2`
and an unpatched Acrylic Glass control. The desktop probe uses a synthetic
Xwayland desktop surface explicitly included in ShapeCorners; it must remain
pixel-identical with the effect enabled. An unpatched Rounded Corners control
must fail. This does not reproduce Plasma's complete edit-mode UI or qualify
NVIDIA hardware. `MTTKDE_ROUNDED_CORNERS_ARCHIVE` also enables the native
eligibility regression in `tests/test_corner_rendering.py`.

For menu and SVG visual checks, build the two unprivileged probe helpers:

```sh
cmake -S tests/native -B build/menu-probe
cmake --build build/menu-probe -j 2
python tests/menu_visual_probe.py --glass /path/to/liquidglass.so --rounded /path/to/kwin4_effect_shapecorners.so --shaders /path/to/built/shaders --output build/menu-capture
QT_QPA_PLATFORM=offscreen build/menu-probe/menu-svg-frames "$PWD/src/offline/plasma-theme/MacTahoeLiquidKde-Light" build/plasma-frames.png
```

The menu probe requires KWayland, KSvg, PyQt6, GTK3/GTK4 introspection,
KWin, Xwayland, Spectacle, qdbus6 and kbuildsycoca6. It stages bundled assets
and the installer preset in a private home/configuration and D-Bus session;
it never installs plugins or changes the running desktop. The pointer helper
verifies the private compositor's D-Bus PID before sending input. Output must
be a new directory. `--pointer` can select a helper built elsewhere.

Repeat with `--mode Dark`, `--backend xcb` and `--scale 1.25`.
`--cases` selects individual menu, context, submenu, combo, tooltip, dialog,
Plasma, GTK3 menu/popover and GTK4 popover cases. Each successful case records
real effect-on/off screenshots; the probe also verifies the mapped plugin's
path and inode. The Qt clients request a second paint after asynchronous
blur-capability discovery, so these are settled-state captures, not a claim
that every external application's first frame already requests blur correctly.
The SVG helper renders five frame families through KSvg, including tooltip,
dialog and panel backgrounds. See [recorded validation](tests/native/menu_visual_validation.md)
for results and limits.

For a Rounded Corners release-pin update, review the full upstream diff and
verify the tag, commit and archive SHA-256 together. Run the opt-in native
build test in an unprivileged, network-disabled container with the target
KWin SDK and a read-only copy of the reviewed archive:

```sh
MTTKDE_ROUNDED_CORNERS_ARCHIVE=/path/to/reviewed-release.tar.gz python -m pytest tests/test_rounded_corners_step.py -k verified_release_builds
```

This verifies and extracts the archive into pytest's temporary directory,
compiles the effect and KCM, and checks both plugins and shaders without
installing or loading them. Test both a stable SDK and the reported failing
SDK when fixing an API incompatibility (issue #94: KWin 6.7.91).

For Acrylic Glass rendering changes, run the opt-in pixel probe as well:

```sh
cmake -S src/offline/kwin-effects/acrylic-glass -B build/capture-build -DCMAKE_BUILD_TYPE=Release
cmake --build build/capture-build -j 2
python tests/acrylic_glass_capture.py --plugin build/capture-build/src/liquidglass.so --output build/acrylic-capture --scale 2
```

It starts a separate KWin/Wayland compositor with private configuration and
D-Bus, loads the specified plugin without installing it, and captures a
synthetic transparent `VirtualBoxVM` surface with the effect off and on.
KWin, Spectacle, qdbus6, PyQt6 and Pillow are required. The output directory
must be new. PNGs, plugin identity, compositor logs and pixel counts remain
there for review. A fixed build must leave every pixel unchanged; run a
reviewed pre-fix build with `--expect changed` as the positive control.
Add `--backend xcb` to exercise Xwayland clients (requires Xwayland), or
`--identity VirtualBox --expect changed` to verify that the manager's identity
still receives glass. The probe checks the compositor's D-Bus owner PID
before toggling effects. This checks the glass interference from #90, not
a real VirtualBox guest.

For a general blur regression, use `--identity AcrylicProbe --expect changed`.
Use `--renderer hardware` and expose a render node in containers when KWin
requires one (6.8); this does not connect to the host's desktop session.
The probe builds a private desktop-entry cache for Spectacle authorization.

For Rounded Corners, pass its built plugin with
`--rounded-shaders /path/to/build/src/shaders`. The probe draws an opaque
window with an asymmetric decoration shadow and a red outline, then checks
that the outline meets the window bottom. Run a v0.10.0 build as the control
as well: on the affected 6.8 path it displaces the outline by 24 pixels.
The pinned v0.11.0 shader must align the outline on 6.6, 6.7 and 6.8.

## Icon generation toolset

`./icon-toolset` builds application-icon appearances from our bundled base for
both Tahoe and Golden Gate. It is a maintainer tool, separate from installation:
it never changes the desktop, invokes another project's installer, downloads
artwork, or changes the installed icon choice. Python 3.10+, Pillow,
`rsvg-convert` (librsvg), and `zstd` are required. The generator supports every
24-bit RGB tint through `--tint '#RRGGBB'`, not a fixed palette.

```sh
# Review a small sample first. Use a new output directory on every build.
./icon-toolset build --output build/icons/sample --sizes 128 --tint '#ff7a18' \
  --icons firefox org.kde.dolphin org.kde.konsole visual-studio-code spotify
./icon-toolset preview build/icons/sample --output build/icons/sample-preview.png

# Generate the complete base, including aliases, in all eight appearances.
./icon-toolset build --output build/icons/full --tint '#6796d2'
./icon-toolset verify build/icons/full
./icon-toolset pack build/icons/full --output build/icons/full.tar.gz
```

`--variants` accepts `light`, `dark`, `black`, `white`, `clear-light`,
`clear-dark`, `tinted-light`, and `tinted-dark`. Light/Dark preserve colored
application artwork and branded color tiles. Black/White use dark/light tiles
and tonal monochrome symbols. Clear/Tinted use translucent materials with
separate light/dark foreground treatments. These are static icon appearances;
they do not refract the live desktop. `--sizes` selects ordinary icon sizes
(32, 64, 128, 256); default outputs are 64, 128 and 256 pixel PNGs.

The generator identifies large SVG background layers and surrounding rim layers,
then renders foreground artwork separately at double the largest output size.
This avoids replacing every white or dark pixel inside a logo. Flattened artwork
uses conservative edge-connected neutral-background detection. Unrecognized
backgrounds retain their geometry and alpha; their classification is recorded
for review rather than being presented as successfully separated glass layers.
External SVG image references are omitted, counted and reported: the current
base's `lact.svg` contains an unavailable localhost image. Other external SVG
resources, scripts, entities and imports are rejected. No external data is fetched.

For a missing application or an icon requiring precise layer separation, supply
`--overrides path/to/overrides.json`. Each icon name maps to local artwork and its
notice; paths are relative to that JSON file:

```json
{
  "my-app": {
    "source": "my-app.svg",
    "kind": "glyph",
    "notice": "my-app-NOTICE.txt"
  }
}
```

Use `glyph` for an isolated symbol to place on a new material tile, or `icon`
for complete artwork. Overrides can replace existing names or add new names.
The bundle carries override sources and notices. It also carries both unchanged
base themes; generated themes inherit their interface, folder and status icons.
All implementation and generated assets belong in Tahoe; Golden Gate only
documents the shared workflow.

`manifest.json` records the input archive hash, generator source hashes, renderer
versions, tint, classifications, source hashes, output hashes and alias targets.
Verification detects modified/missing/extra files and unsafe links, and validates
theme inheritance and image dimensions. Builds never overwrite existing output.
Pack normalizes timestamps and ownership for reproducible archives; identical
inputs and renderer versions are needed for identical generated pixels.
`--icons` marks a sample bundle partial; packaging it requires `--allow-partial`.
Preview produces synthetic artwork contact sheets, not desktop screenshots.

Our existing icon archive's provenance gaps remain documented in
`THIRD_PARTY_NOTICES.md`; generation does not resolve or relicense those assets.
Carry all supplied notices and review artwork before redistributing a generated
pack. Packaging is not release approval. This tool does not alter installer
defaults or publish its experimental output as the default icon theme.

Visual references, inspected at immutable revisions, informed the feature design:
[MacOS-Like](https://github.com/Scrimas/MacOS-Like/tree/efbc63d48d52bbaf52e9a70fb18e0d0c3c0719b2)
for consistent light/dark tiles and missing-app coverage, and
[MacTahoe Tinted Glass](https://github.com/Johan-Ardila/MacTahoe-tinted-glass-Icons-for-KDE-plasma/tree/789bfe8ded8d01435145a8f35b73d61f375f61c9)
for tonal translucent appearances. Their code and icon packs are not included
or used as build/runtime dependencies. The generator uses our own base artwork.

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
- Use `Kirigami.Theme.*` for colors, not hardcoded hex.

### Naming

- **PascalCase** for theme names: `MacTahoeLiquidKde-Dark`, `MacTahoeLiquidKde-Light`.
- **kebab-case** for IDs: `org.kde.mac-tahoe-liquid-kde.<component>`.
- Plasmoid suffixes are simple nouns: `.menu`, `.launcher`, `.trashcan` — not compound words.

See [CLAUDE.md](CLAUDE.md) for the full convention list.

## i18n

User-facing widget strings use KDE's native `i18n()` catalogs. Keep category
identity and other control flow independent of translated display names.
Inherited Dock strings retain KDE's taskmanager domain; project-specific
strings use the project's own domains.

The installer supports English, Spanish, Simplified Chinese, Brazilian Portuguese
and German. Brazilian Portuguese and German also cover project-owned CLI logs,
help, recovery diagnostics and Acrylic Glass settings. Maintain their complete
message catalogs in `src/scripts/locales/pt_BR.json` and `de.json`. Use
`tr("Complete message: {path}", path=path)` before logging; never interpolate
before translation. Translate display labels separately, preserving commands,
paths, configuration values and external tool diagnostics. `step()` translates
its own message and records a stable source key for progress classification.

After editing widget or Acrylic Glass strings, run
`python3 src/scripts/build_translations.py` with gettext's `msgfmt` available.
Commit the generated `.po` and `.mo` files together. Update localized metadata
alongside its English source. `tests/test_multilanguage.py` checks coverage,
placeholders, locale aliases, progress classification and installed helpers
without access to the checkout. Check both languages visually for clipped text.
Standalone theme-switch and OLED-care executables embed the localization runtime
at installation; Nix installs the runtime and catalogs beside the scripts.

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

## Documentation screenshots

Keep the installer gallery in [TESTING.md](TESTING.md); the README links to it
without embedding installer screenshots. Desktop and Dock photographs stay in the README.

New captures are required only when the diff clearly changes visible output.
For nonvisual releases, retain the reviewed images and their original capture
version and source; run `./release-screenshots verify` without starting a VM.
The verifier conservatively rejects changed visual inputs and unknown source
changes. Console updater logic/messages, documentation, tests, release
verification tools and a version bump alone do not invalidate visual evidence.
When new captures are needed, use `./release-screenshots` for publication. The release workflow
verifies committed provenance before creating the GitHub release. Never use
old images to fill a failed or rejected case. Main README desktop galleries
show Files and About This Computer separately in both modes. Each frame must
contain only its featured application with that window focused; capture and
release validation reject combined or unfocused desktops. Distro qualification
screenshots are outside this gallery rule.

For a release that changes visual output:

1. Finish the source changes, set `VERSION`, and commit the release candidate.
2. Run `./release-screenshots capture --ref HEAD --vm-image /path/to/neon-base.qcow2 --output build/captures/vVERSION`.
   The output directory must be new. The runner checks the VM SHA-256 against
   `src/scripts/release_capture_profile.json`, creates a fresh disposable overlay
   for each edition, installs the exact Git archive, and captures both modes
   sequentially. It never mounts the host home or sends input to the host.
3. Inspect **every** PNG in `frames/` at full size. Record decisions with
   `./release-screenshots review --bundle build/captures/vVERSION --approve FRAME...`
   or `--reject FRAME...`. Names are the PNG basenames without `.png`.
   Review is bound to the manifest and image hashes. A rejected or missing
   frame blocks staging and publication; fix the source and recapture.
4. Stage Tahoe with `./release-screenshots stage --bundle build/captures/vVERSION --edition tahoe --destination .`.
   Stage Golden Gate from the same reviewed bundle using `--edition golden-gate`
   and its checkout as `--destination`. Both versions must already match.
   Staging gives each image a filename containing its content SHA-256 prefix,
   updates README and TESTING URLs, and removes replaced images and obsolete aliases.
5. Commit the screenshots. Further changes to visual inputs require recapture;
   nonvisual edits do not. Preserve the capture version and source in provenance.
   Run `./release-screenshots verify`. Push the version tag to trigger the
   gated release workflow. Its release title is exactly `vVERSION`.
   Pin Golden Gate to that published Tahoe commit and verified archive, commit
   its screenshots and pin, then run the Tahoe tool with
   `--repo /path/to/golden-gate verify --tahoe-repo /path/to/tahoe` before its tag.

The sealed reference image is a maintainer artifact, not a downloaded rolling
image. Keep a backup matching the profile checksum. It contains the KDE neon
SDK, screenshot/Plymouth tools and the fixed desktop app inventory. Installation
must not change its package inventory. Replacing it requires an explicit
profile/checksum update and a fresh reviewed capture. The local reference copy
is `build/release-capture/neon-base.qcow2`; provide `--vm-image` on other hosts.
The capture host needs Python with Pillow, QEMU with KVM and EGL/virgl support,
OpenSSH and `sshpass`. Publication additionally requires an authenticated `gh`.

The profile fixes 3840×2160 output, 2× scale, locale, timezone, clock, Documents
fixtures, pinned apps, window positions and pointer position. Each frame must
settle to two identical consecutive captures. The active effect identity must
match the captured source. Provenance excludes screenshot outputs and normalizes
README/TESTING screenshot filename hashes to avoid a circular commit hash. This makes the capture procedure repeatable; it does
not promise identical pixels across different host GPUs/QEMU versions. Keep
the same capture host for comparisons and retain each bundle with its logs.

Capture only in a disposable VM. `src/scripts/screenshots` refuses a host
session and checks Plasma, Qt, Kvantum, GTK preferences and the active GTK 4
stylesheet before capturing. A successful theme-switch command alone is not
proof that applications changed appearance. Stale or custom CSS must be
reviewed in the guest; the checker never overwrites it.

Full-desktop captures must also call `screenshot_checks.check_files_pixels`
with the captured image, requested mode, native window metadata and output
scale. The Documents fixture uses folders in its first row and an empty lower
content area. The check requires the actual Nautilus Documents window and
rejects a dark Files surface in a light capture, or the reverse. Keep a rejected
mixed-theme frame as a negative control. Do not apply the brightness check to
the Dock or translucent popups: their material can show the wallpaper through
it. Review every image before replacing published screenshots.
