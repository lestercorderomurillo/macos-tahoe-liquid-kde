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
git clone --filter=blob:none https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde
cd macos-tahoe-liquid-kde

./installer          # graphical install wizard; requests privileges when needed
./uninstall          # graphical uninstall confirmation
./test               # full pytest suite
./test --vm          # plymouth render harness (requires root, see tests/vm/)
```

### Installer storage maintenance

Recommended clones use `--filter=blob:none`: full commit ancestry is available
while historical file contents download only when requested. Existing shallow
clones from older instructions acquire the full ancestry through a filtered
fetch only after the same clean, published-source audit passes; development
checkouts remain unchanged.

Both installers maintain their source storage on ordinary launches, including
launches after a manual `git pull`. `./installer --free-space` (also available
through `./install`) runs maintenance explicitly and reports allocated bytes
recovered without installing or updating either checkout. It may verify release
metadata online; `MAC_TAHOE_NO_UPDATE_CHECK=true` forbids these queries.

Only a clean, independent canonical clone at an exactly verified published
release can retire historical file caches. VERSION guides release ordering;
the published tag, commit and Git ancestry establish identity. Uncommitted,
staged, untracked, deleted or divergent work, private recovery objects, stashes,
private tags, active local branches, explicit source overrides, worktrees and
shared stores prevent this conversion. A newer or equal unpublished version is
never replaced. Ignored local files also block an update that would overwrite
them. Update fetches suppress uncontrolled Git auto-maintenance.

Maintenance keeps `.git`, the complete commit/tree graph, canonical tags,
main/dev positions, current branch snapshots and small historical sources.
Large obsolete files proven reachable from the published release become a
`blob:none` partial-clone cache backed by canonical origin. Historical lookups
can download those files again; ordinary main/dev pulls retain full ancestry,
including merges based on old releases, without refetching every old asset.
Only older-version branches already merged into the verified release are
retired. Active remote work remains. Retired reference IDs and original local
branch reflogs accumulate in `.git/tahoe-maintenance-journal.json`; recover a
branch with `git branch <name> <recorded-object-id>`.

Git writer locks, durable replacement packs/configuration, ref comparisons and
concurrent-state checks protect other processes. Unknown/private objects are
never classified as cache, and caches in new concurrent packs are not removed.
No reflog expiry, garbage collection or forced object pruning is used. A failed
maintenance run never blocks installation. Offline/unverified/development
sources receive only ordinary packing, preserving all their objects and refs.
Repacking needs temporary space; savings depend on the history and active tips.
Set `git config tahoe.maintenance compact` to retain all locally available
historical files, or `git config tahoe.maintenance off` to disable maintenance.
To materialize previously evicted history, use
`git fetch --refetch --no-filter origin`; historical lookups also hydrate it.

Golden Gate retires unused prepared sources and interrupted downloads only
after a replacement is ready, with leases protecting running installers.
Verified Rounded Corners downloads and disposable copy staging are cleaned by
their owning steps. Native builds reuse their component build location.
Desktop assets, settings, uninstall/browser recovery backups, arbitrary
untracked folders, developer VM images and capture evidence are preserved.

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
mac-tahoe-theme-switch auto      # apply the mode for the current time
```

In automatic mode, the systemd user service waits for enabled NTP to synchronize
before choosing light (06:00–18:00) or dark. This handles an incorrect dual-boot
RTC at login. Each wait is bounded to 30 seconds; exit status 75 retries after
15 seconds while preserving the current appearance. Manual choices, disabled
NTP and non-systemd scheduling retain their existing behavior. The switcher
never changes the hardware clock, timezone or NTP configuration.

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

Use `--compositor x11 --plugin /path/to/liquidglass_x11.so` for a private
KWin X11/Xvfb session; `--backend xcb` alone remains an Xwayland client in
KWin Wayland. X11 captures require Xvfb and currently use scale 1.
Add `--conflicts` to exercise the installer's live built-in blur handoff,
reinstall snapshot, active-effect recovery guard and restoration. Use
`--conflict-effect` to select another installed, ABI-compatible competitor.
A competitor that cannot load is a failed control, not a passing handoff.

`--renderer hardware` requires a render device accessible to the isolated
compositor. Inspect `support.txt` for the actual renderer: a container or
successful plugin build alone proves no rendering. `--screenshot-api dbus`
uses KWin's raw Wayland screenshot API when Spectacle cannot capture; it
requires python-dbus and relaxes screenshot authorization only in the spawned
private compositor. Never apply that environment setting to a desktop session.

Use `--application nautilus --material tahoe` (or `golden-gate`) to launch
real Nautilus with privately staged bundled GTK assets. Synthetic captures
remain the default. `--damage` compares a partial synthetic backdrop update
with a full repaint; a passing pre-fix control makes the regression claim
inconclusive. These captures do not replace full desktop lifecycle qualification.

For the Nautilus client fallback, use `--identity org.gnome.Nautilus
--expect changed --no-decoration-blur`. Repeat with `--backend xcb` to cover
resource-name matching. Add `--backing-tint --appearance light` or
`--backing-tint --appearance dark` to check the Tinted window material.
Classic and Tinted share their optical settings; Tinted blends a 45% white
or black backing over the blurred background beneath application windows.
Panels and menus retain their own materials. The KCM exposes this independently
of edition presets; the wizard shows it only with Nautilus and Acrylic Glass.
The probe checks `debug liquidglass status` for shader readiness as well as
plugin loading. These synthetic clients do not qualify the real Nautilus app.

Installation hands off from known competing blurs only after compilation and
material setup succeed, verifies their unload, and saves their settings under
`$XDG_STATE_HOME/mac-tahoe-liquid-kde/blur-conflicts.json` (default
`~/.local/state/mac-tahoe-liquid-kde/`). Activation failure and uninstall restore
those settings while preserving subsequent user changes.
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

Publish a fix after focused local checks and any component-scoped VM review.
Record commands, results, coverage limits and source fingerprint in
`release-evidence.json`; the workflow verifies this record, component hashes,
reviewed preview hashes, immutable tag/version and unchanged historical gallery
bytes before publishing. Full `test.yml` CI runs independently on remote branches;
report its actual status and offer the published release without waiting for the
matrix. Do not call a release fully qualified while that CI is pending or failed.

Focused previews may accompany a fix while the full documentation gallery remains
historical and explicitly labeled. Preserve its original provenance; do not
recapture unaffected pages or relabel old frames as new. Refresh the gallery
separately when needed, using the following capture tooling. Never use an older
image to conceal a rejected new capture. Main README desktop frames show Files
and About separately, each with only the featured application focused.

For a release that changes visual output:

1. Finish the source changes, set `VERSION`, and commit the release candidate.
2. Run `./release-screenshots capture --ref HEAD --vm-image /path/to/neon-base.qcow2 --output build/captures/vVERSION`.
   Add `--reuse build/captures/PREVIOUS` to retain reviewed, unaffected frames
   from an existing bundle. Dependency checks select the views that require
   new captures; unknown visual changes invalidate the full set. Retained
   frames keep their original source commit, version and hash-bound approval.
   The output directory must be new. The runner checks the VM SHA-256 against
   `src/scripts/release_capture_profile.json`, creates a fresh disposable overlay
   for each edition, installs the exact Git archive, and captures both modes
   sequentially. It never mounts the host home or sends input to the host.
3. Inspect every **new** PNG in `frames/` at full size. Reused frames retain
   their existing reviews. Record new decisions with
   `./release-screenshots review --bundle build/captures/vVERSION --approve FRAME...`
   or `--reject FRAME...`. Names are the PNG basenames without `.png`.
   Review is bound to the manifest and image hashes. A rejected or missing
   frame blocks publication of that image; fix the source and recapture.
4. Stage Tahoe with `./release-screenshots stage --bundle build/captures/vVERSION --edition tahoe --destination .`.
   Stage Golden Gate from the same reviewed bundle using `--edition golden-gate`
   and its checkout as `--destination`. Both versions must already match.
   Staging gives each image a filename containing its content SHA-256 prefix,
   updates README and TESTING URLs, and removes replaced images and obsolete aliases.
   Published images use WebP quality 92: README images fit within 2560 px,
   auxiliary images within 1280 px, and installer crops retain their resolution.
   Keep the original reviewed PNG bundle; export metadata binds each derivative
   to its original hash. Review compressed outputs before committing them.
5. Commit the screenshots. Further changes to visual inputs require recapture;
   nonvisual edits do not. Preserve the capture version and source in provenance.
   Run `./release-screenshots verify`. Push the version tag to trigger the
   release workflow after focused local evidence is recorded. Its title is exactly `vVERSION`.
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

## Base Dock applications

The three bundled layouts share this order: Dolphin, Firefox, Thunderbird,
Merkuro Calendar, Marknote, Gwenview, Elisa, Haruna, Discover and System Settings.
Plasma resolves installed desktop IDs when creating the layout; missing apps are
omitted and native/Flatpak/Snap alternatives occupy a single slot. The preset does
not install application packages. Both editions use the same list and retain
their own icon appearance and materials.

The installer restores existing pins after creating the layout, including an
intentionally empty Dock on an existing theme installation. The base list is
used when there are no saved pins and no previous theme layout. Declarative Nix
panels continue to use their explicit `panels.launchers` list.


## Dock icon appearance

In the custom installer, open **Desktop → Dock apps… → Dock appearance** and
choose **macOS-style Dock icons**. This is separate from optional app installation:
it uses installed Linux applications with consistent icons for Files, Browser,
Mail, Calendar, Notes, Photos, Music, Video, App Store and System Settings.
The tooltip retains the real application name. Other applications keep their
normal icons; launchers and running windows retain the same application identity.

**Keep current Dock icons** is the installer default and preserves each Dock's
choice, including during a layout reset. **Application icons** turns the option
off. It can also be toggled in the Dock widget's Appearance settings. Pins, their
order and the global icon theme are preserved. The bundled artwork has light and
dark variants and does not require changing the desktop icon theme.


### Dock migration in 0.64

Express uses automatic Dock appearance. Each Dock records `dockPresetRevision=3`
after applying the preset, installed application equivalents and macOS-style
role icons. Revisions 0, 1 and 2 migrate once, regardless of the release they
came from (including 0.61.0). The migration retains existing launchers in order
and appends missing installed roles; it never installs applications. Firefox
and other browsers retain their real application artwork and name.

An explicit layout reset reapplies the preset. Without reset, revision 3 keeps
removed pins and icon choices; explicit optional app requests can still add
the requested roles. `keep`, `native` and `macos` are explicit icon overrides;
`auto` applies the pictured icons only on initial migration or reset. Rebuilding
retains the revision per screen. Failed script execution can retry.


### Capsule highlights in 0.65

The global menu's system button and `MenuDelegate` use half the smaller
dimension as their QML radius, including hover and pressed states. Native
menu selections use circular SVG corner arcs and Kvantum frame expansion
large enough for the caps to meet at half the row height. Layout frames stay
at 3px; text margins, row height, icon sizes and separators are unchanged.
This follows Kvantum's [frame expansion contract](https://github.com/tsujan/Kvantum/blob/master/Kvantum/doc/Theme-Config).

`tests/test_menu_rounding.py` renders the actual Qt style in light and dark
mode, at scales 1, 1.5 and 2 with 9, 16 and 24 point fonts. It checks circular
edge profiles and unchanged geometry. Publication updates only menu/context
frames; separate top-bar previews verify the application-name hover.

### Top-bar proportions in 0.65.1

The Apple and Finder states in the [macOS Tahoe screenshot reference](https://512pixels.net/projects/aqua-screenshot-library/macos-26-tahoe/) guide the shared top bar: an inset capsule, symmetric text padding, a wider system-button capsule, regular menu labels and a bold application name. Keep the system font and full-height input area. Highlight height follows panel height with a bounded vertical inset; changing the visual inset must not move the popup anchor or reduce the clickable area.

`tests/test_topbar_geometry.py` loads the real QML delegate with short and long names at three panel heights, checking text fit, symmetric padding and independent highlight/input geometry.

### System menu proportions in 0.65.2

The [macOS Golden Gate Apple menu reference](https://512pixels.net/projects/aqua-screenshot-library/macos-27-golden-gate/) guides the system popup's 24px rows, 16px icon column, 12px separator rows, 6px selection corners and 288px minimum natural width. Metrics scale with the configured menu font; long translated labels and user names can widen the popup. The preset already selects SF Pro Text, and the popup uses regular weight without overriding a user's font family or size.

`SystemMenuStyle` owns a separate base style for this popup; it must never adopt or delete the application's shared style. The other menus retain their existing Kvantum rendering. Only About, System Settings and App Store have icons; other actions omit the icon column, as in Golden Gate. The default laptop, gear and App Store symbols use palette-aware vector drawing, while explicit custom icon choices retain their artwork. Recent Items remains absent. `tests/test_system_menu_style.py` compiles the actual style and checks geometry, selection rendering, style isolation and keyboard navigation.

## Incremental installation

Each payload is compared by content, permissions and symlink targets before
replacement, so changing one plasmoid leaves identical siblings in place.
Icon generation additionally keeps a successful-install receipt covering its
source archive, Python recipe dependencies, style, tint and installed outputs.
Missing or modified outputs cause regeneration. Receipts are an optimization,
not proof that configuration or a requested layout reset can be skipped.
Native builds retain their build graph and reconfigure against the current SDK.

After changing a component, run
`python src/scripts/component_manifest.py --write` and commit the resulting
`component-hashes.json`. The ledger is independent of VERSION and Git commit;
`python src/scripts/component_manifest.py` verifies it without writing.

### 0.66.1 validation evidence

Focused checks on Linux x86_64 with Python 3.14 covered component identity,
missing/corrupt receipts, changed tint, independent payloads, repair of deleted
files and a real CMake/Make rebuild with deliberately old source timestamps.
Commands and results:

- `python -m pytest -q -p no:cacheprovider tests/test_component_cache.py tests/test_release_screenshots.py`: 71 passed after portable source hashes and focused previews were added.
- The installer wizard, icon and copy-helper regressions passed in the earlier
  102-test development run; unaffected results were retained.
- Uninstall receipt invalidation and icon-step regressions: 3 passed.
- CI identified missing translations for incremental-install log messages; after
  completing all four catalogs, localization and component-cache checks: 49 passed.
- Golden Gate's `python -m pytest -q -p no:cacheprovider tests`: 97 passed.
- Against the prepared Golden Gate source, component-cache, wizard and icon
  regressions: 41 passed, including portable hashes across the edition staging.
- Shared step guards, icon, Kvantum and Rounded Corners regressions: 68 passed,
  one opt-in native Rounded Corners build skipped because its reviewed archive
  and host KWin SDK were not supplied to that test.

The four file-manager preview originals were captured from Tahoe commit
`b762888c` in a disposable overlay of the pinned KDE neon VM (Plasma 6.8.1,
Qt 6.11.1; image SHA-256
`412e7933f10add20b921b92c02709e7eea56acd14dc14cf654f58fba4ea3cc9d`).
A second installation in that overlay explicitly reported
`Icons unchanged — skipping generation and installation`, along with unchanged
individual plasmoid/runtime payloads. A frame whose geometry changed during
capture was rejected; all four accepted originals were individually reviewed.
Their hashes, source commit and before/after focus evidence are retained in
`src/installer/assets/sources.json` and
`build/captures/v0.66.1-file-previews/manifest.json`.

These checks do not qualify a new distro or prove all native SDK combinations.
For v0.66.1, the push CI matrix was a blocking publication gate. From v0.66.2
it runs asynchronously; focused local evidence permits publication without
claiming full remote qualification. The four affected installer-gallery
frames were captured separately from source `9053872` after installing each
edition in its own disposable VM overlay, preserving the pinned package
inventory. All four frames were reviewed; unrelated photographs retain their
original provenance. This was not a full distro or uninstall lifecycle run.

Runtime CI runs on `dev`, pull requests and manual dispatch. Promote the same
commit to `main` without a second suite or a polling job; send runtime changes
through `dev` first. Markdown and documentation-image-only changes do not start
the runtime matrix. Use command results as delivery evidence instead of repeated
publication or branch lookups. Golden Gate validates the immutable Tahoe tag and
archive once, without waiting for or querying the GitHub release page.
