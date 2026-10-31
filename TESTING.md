# Installer testing

Native installer screens for Tahoe 0.61.11, captured in a disposable KDE Plasma VM.
Dark appearance was selected for this installation test.
The gallery is captured from the release source and reviewed before publication.
Release checks cover both editions, theme switching, installation, reboot and removal.

For test commands and the capture workflow, see [CONTRIBUTING.md](CONTRIBUTING.md).

## v0.61.8 focused validation

On 2026-10-27, 171 focused checks passed on the shared Tahoe source and the
same 171 passed on prepared Golden Gate content `9d2e8e8532812762e034`.
The checks used Python 3.14 with offscreen Qt on the maintainer's Linux host:
window controls, shadows, GTK upgrade/geometry, wizard navigation and summary,
installer supervision, CLI choices and Nix staging. No native ABI changed.
Existing component and VM evidence below remains applicable to unchanged code.
The required full CI runs on the exact release commits; no duplicate local
container matrix is used.

## Glassy reference refinement

The v0.61.8 controls follow the maintainer's supplied button close-up with
saturated faces, narrow rim highlights and heavier hover glyphs. It removes
the broad reflection and separate lower arc from the stronger lens design.
It keeps the high-DPI GTK canvas, all interaction states, Flat artwork, frame geometry, shadow choices
and installer navigation unchanged. Fork capture findings and exact source
links are recorded in [window controls](docs/window-controls.md#fork-capture-investigation).

The affected generator is shared by Aurorae and GTK 3/4 in both editions. On
the maintainer's Linux environment with offscreen Qt, 19 component checks passed:

```sh
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider \
  tests/test_window_controls.py tests/test_gtk_upgrade.py tests/test_gtk_window_geometry.py
```

These exercise every rendered control state, install/reinstall/removal, explicit
Flat/Glassy choices in both editions, light/dark/light selection and GTK URL
handling. The rendered regression now checks that highlights stay at the rim
without a bright patch across the upper face. Native Nautilus previews are
recaptured in the pinned disposable VM. The 28 wizard checks also passed with
the replaced, content-addressed preview assets. Golden Gate prepared source
`c7373c857bddd3a70717` passed the same 47 affected checks:

```sh
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider \
  tests/test_window_controls.py tests/test_gtk_upgrade.py tests/test_gtk_window_geometry.py \
  tests/test_installer_wizard.py
```

The native chooser was captured and visually reviewed in both editions and
both modes, using the updated Nautilus crops. Capture source archive SHA-256:
`5ee79bb64e3786d62de67d61651c2ebe3d3547efdfc8cb7d59b21e5c57d40f44`.

Release v0.61.8 includes a fresh complete capture from the pinned disposable VM.
Publication requires successful exact-commit CI on both `main` and `dev`.

## Window controls: Nautilus and separate shadows

Version 0.61.8 adds the Flat/Glassy chooser and the separate Window shadows
page. Version 0.61.7 did not contain the chooser.

This earlier candidate used a broad upper reflection and a lower caustic;
the reference refinement above supersedes that treatment.
GTK SVGs retain their logical button size while using a larger intrinsic canvas
for sharp high-DPI rasterization. The wizard has a separate Window shadows page
with four screenshot cards and its own editable summary row.

Twelve reviewed Nautilus crops replace the Dolphin control previews and add
all four shadow levels in both modes. They were captured sequentially in the
pinned disposable KDE neon VM at 3840×2160, 4× scale. Every capture verifies
the active Nautilus window; the shadow comparisons use identical geometry and
neutral backgrounds. Their hashes and crop bounds are in
`src/installer/assets/sources.json`.

Focused validation on the maintainer's Linux environment with offscreen Qt:

```sh
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider \
  tests/test_window_controls.py tests/test_window_shadows.py \
  tests/test_gtk_upgrade.py tests/test_gtk_window_geometry.py \
  tests/test_release_screenshots.py tests/test_screenshot_checks.py \
  tests/test_nix.py tests/test_step_guards.py
# 84 passed
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider \
  tests/test_installer_wizard.py tests/test_installer_ui.py tests/test_cli.py
# 140 passed
```

The wizard checks cover both edition defaults, all four shadow selections,
summary editing, retained transaction choices and page layout without scrolling.
The final summary spacing also passed the 28 wizard checks, including the
larger-font regression found during native VM review. Prepared Golden Gate
content `8c490c88acf4b742b098` passed 171 checks (wizard, installer UI, CLI,
window controls, shadows, GTK upgrade/geometry and Nix); after the summary-only
adjustment, all 28 wizard checks passed again in `444c9a1a9e1329ca8fa1`.

Native VM review covered Controls, Shadows, Effects and Summary in both
editions and both modes. The first summary overflow was rejected and fixed;
all four final summaries report zero vertical scroll. Final summary capture
source archive SHA-256: `81c104bfbb32e826c147d447bcef958ae08b950308359a887ec09945f04df962`.

No native backend or ABI changed. These focused checks are not release evidence.
The gallery below is generated from the complete 90-frame release bundle at
the final source/version; every frame is reviewed before staging.

### Initial chooser development evidence

The native wizard offers Flat and Glassy window controls, with the source
edition's default first. Navigation and summary editing preserve the explicit
choice for one transaction. The standalone switcher keeps the installed choice
across light/dark transitions. Both Aurorae families remain installed, while GTK
and global-theme staging follow the same selection.

On the maintainer's Linux environment with offscreen Qt, 172 component checks
passed for wizard navigation, input validation, Aurorae install/reinstall/removal,
GTK styling, global-theme defaults, configuration verification, shadows, Nix
asset assembly and screenshot validation:

```sh
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider \
  tests/test_screenshot_checks.py tests/test_release_screenshots.py \
  tests/test_installer_wizard.py tests/test_cli.py tests/test_window_controls.py \
  tests/test_window_shadows.py tests/test_nix.py tests/test_step_guards.py
```

Golden Gate prepared content `ee41404ae82e135c7d39` also passed 261 affected
checks with the same code and preview assets, including GTK upgrades and the
standalone switcher's existing scheduling paths:

```sh
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider \
  tests/test_installer_wizard.py tests/test_cli.py tests/test_window_controls.py \
  tests/test_window_shadows.py tests/test_screenshot_checks.py tests/test_nix.py \
  tests/test_step_guards.py tests/test_gtk_upgrade.py tests/test_theme_switch.py
```

The run passed 260 checks under filesystem isolation; the Unix-socket scheduling
case passed separately with permission to bind its temporary local socket.

The initial four chooser previews were captured sequentially in a disposable overlay
of the pinned KDE neon VM (Plasma 6.8.1, Qt 6.11.1, Wayland), at 3840×2160 and
4× scale. The probe installed both styles, checked the selected Aurorae family
and matching GTK assets, and captured focused Dolphin windows in both modes.
Those Dolphin crops have since been replaced by the Nautilus candidate above. Source hashes and crop rectangles are in
`src/installer/assets/sources.json`. The complete release bundle separately uses
the fixed 2× profile and includes the new installer page for both editions and
both modes. It requires visual review and exact-commit CI before publication.

See [window-control construction and rendering limits](docs/window-controls.md).

## v0.61.5 reset default validation

The shared wizard now starts with **Reset Dock and panel customization** checked
in both editions. Unchecking it survives page navigation and keeps the existing
layout; checking it enables the layout cards and schedules the rebuild.

Focused development checks on the maintainer's Linux environment, with offscreen
Qt, cover source defaults, native wizard navigation, privileged option routing,
layout retry gating and the existing install/reinstall/uninstall component paths:

```sh
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider \
  tests/test_installer_wizard.py tests/test_cli.py tests/test_installer_ui.py \
  tests/test_layout_step.py tests/test_static.py::test_readme_tests_count_badge_matches_collected_count
```

All 161 focused checks passed across the initial run and the affected CLI rerun
after updating its old default expectation. The same four component files passed
160 checks in Golden Gate prepared content `f4438e729918882ada4b`. No native
backend or layout implementation changed; the v0.61.4 explicit reset/preserve
VM evidence below remains applicable. The new release capture separately checks
both editions in light and dark mode in the pinned disposable KDE neon VM.
Exact-commit CI and reviewed fresh captures remain publication requirements.

## v0.61.4 focused validation

Installer changes were checked from Tahoe commits `217277a`, `78a5907` and
`3fdcba1` on the maintainer's Linux development environment, using offscreen
Qt for wizard navigation. The final shadow renderer passed all nine component
regressions, including rendered active/inactive SVG pixels, both appearance
modes, reinstall regeneration and uninstall cleanup.

```sh
QT_QPA_PLATFORM=offscreen python -m pytest -q \
  tests/test_window_shadows.py tests/test_installer_wizard.py tests/test_cli.py \
  tests/test_installer_ui.py tests/test_step_guards.py tests/test_release_screenshots.py
QT_QPA_PLATFORM=offscreen python -m pytest -q \
  tests/test_gtk_upgrade.py tests/test_gtk_window_geometry.py \
  tests/test_theme_switch.py tests/test_apply_safety.py
```

The first group passed 187 checks before the two rendered-shadow regressions
were added; the final shadow component then passed nine checks. The second
group passed 125 checks. Golden Gate's prepared source passed the affected
wizard/GTK checks (38), followed by all nine final shadow regressions. Its
wrapper suite passed 40 checks.

A disposable KDE neon VM (Plasma 6.8.1, Qt 6.11.1, Wayland) verified that a full
reinstall preserves customized panel IDs, widgets, Dock height and hiding
behavior, while an explicit reset restores the default layout. Skipping
Nautilus preserved the existing Dolphin MIME associations. Light/dark/light
configuration transitions passed. Shadow visual checks use the same pinned
VM image as the release capture profile; the release gallery has its own
complete capture and review gate.

The final candidate also exercises release selection before opening the wizard:
`tests/test_release_update.py tests/test_cli.py tests/test_installer_ui.py`
passed 115 checks. Temporary Git repositories verify the published tag and its
`VERSION`, reject dirty/diverged checkouts and mismatched versions, and ensure
an unpublished branch tip is not installed. Golden Gate's updated wrapper
suite passed 45 checks.

### Arch reproduction of issue #112

A disposable Arch VM used KWin 6.8.1-2, Plasma Workspace 6.8.1-1, Qt 6.12.0,
Mesa 26.2.5-1, Firefox 158.0.1-1 and Linux 7.2.11.arch1-1 on Wayland. These
match the reported software versions; the VM uses VirGL, not the reporter's
physical RX 9060 XT. Its official cloud image was checked against the published
SHA-256 before use. No host desktop settings were changed.

The install/switch/reboot sequence exposed a real appearance regression: a
legacy KConfig update erased the active inherited Plasma defaults at login,
leaving part of the desktop on Breeze. Commit `6f23ac7` retires that update and
makes its old no-argument invocation harmless. Explicit install/uninstall
cleanup remains available. The corrected VM passed native build and
`liquidglass` load verification, dark/light/dark application checks, a real
reboot and post-login theme checks. The KConfig/theme-switch/apply-safety group
passed 129 checks across the initial run and a separately permitted Unix-socket
case; the final expanded KConfig component passed all 10 checks.

Full installs and reinstalls separately verified preserving customized panel
IDs, widgets, Dock height and hiding behavior, and restoring defaults only with
an explicit reset. With Nautilus removed before installation, choosing to keep
the current file manager left Nautilus absent and preserved Dolphin MIME
associations. Light/dark/light checks passed. All four shadow levels were
captured and visually reviewed on Dolphin and Nautilus in both modes, with
unchanged frame geometry and increasing shadow intensity. Wizard, shadow and
release-update regressions passed 42 checks in Arch across two runs; the second
installed a missing Git test dependency and reran the five affected cases.

The first uninstall screenshot exposed a Firefox crash that the old validator
had missed. The SSH test launcher had omitted Plasma's `GTK3_MODULES` setting,
so Firefox lacked the existing appmenu lifetime protection. Commit `e173997`
recovers that setting and requires a responsive browser after uninstall. The
corrected run retained the same Firefox process and passed interactive
Marionette navigation, typing and click checks after full removal; its final
screenshot was reviewed. Session-environment, GTK appmenu and VM-validation
regressions passed 58 checks. This does not establish the cause of every freeze
on the reporter's physical GPU.

Development evidence is retained in `/tmp/issue112-arch/qualification-fixed`,
`/tmp/issue112-arch/options` and `/tmp/issue112-arch/firefox-retention`. The first
uninstall image is rejected and superseded by the final browser-retention run.
The drivers use `tests/vm/qualify.py` and `tests/vm/desktop_apps.py`; the layout
and shadow driver additionally records the chosen options and resource values.
Golden Gate's prepared source containing `e173997` passed 112 affected checks:

```sh
GOLDEN_GATE_TAHOE_SOURCE=/path/to/macos-tahoe-liquid-kde ./installer --prepare
# From the returned prepared source:
QT_QPA_PLATFORM=offscreen python -m pytest -q \
  tests/test_release_update.py tests/test_installer_wizard.py \
  tests/test_installer_ui.py tests/test_kconf_update.py \
  tests/test_session_env.py tests/test_window_shadows.py
```

These focused results supplement the required full distro matrix and exact
release-commit push CI on both `main` and `dev`; they do not replace those gates.
The release gallery requires a fresh complete capture after these changes.

## Installation steps

Scroll horizontally through the installation steps.

<table>
<tr>
  <td align="center"><img src="src/screenshots/installer-welcome_dark_v4-d51e674d4141.png" alt="Welcome" width="500"><br>Welcome</td>
  <td align="center"><img src="src/screenshots/installer-appearance_dark_v4-a6f5633f614d.png" alt="Appearance" width="500"><br>Appearance</td>
  <td align="center"><img src="src/screenshots/installer-icons_dark_v4-fb1bad1909be.png" alt="Icons and color" width="500"><br>Icons and color</td>
  <td align="center"><img src="src/screenshots/installer-wallpaper_dark_v4-7ee3602eddd1.png" alt="Wallpaper" width="500"><br>Wallpaper</td>
  <td align="center"><img src="src/screenshots/installer-launcher_dark_v4-28b8fff306a0.png" alt="Launcher" width="500"><br>Launcher</td>
  <td align="center"><img src="src/screenshots/installer-layout_dark_v4-609c79632293.png" alt="Top bar and Dock" width="500"><br>Top bar and Dock</td>
  <td align="center"><img src="src/screenshots/installer-effects_dark_v4-37b69a1dc300.png" alt="Effects" width="500"><br>Effects</td>
  <td align="center"><img src="src/screenshots/installer-window_controls_dark_v4-cba3352b022c.png" alt="Flat or Glassy window controls" width="500"><br>Window controls</td>
  <td align="center"><img src="src/screenshots/installer-shadows_dark_v4-aa2aed4e457f.png" alt="Window shadow comparison" width="500"><br>Window shadows</td>
  <td align="center"><img src="src/screenshots/installer-fonts_dark_v4-523d7c630b5d.png" alt="Fonts" width="500"><br>Fonts</td>
  <td align="center"><img src="src/screenshots/installer-firefox_dark_v4-71fbb08207e7.png" alt="Firefox" width="500"><br>Firefox</td>
  <td align="center"><img src="src/screenshots/installer-files_dark_v4-dfae21b14c3f.png" alt="File manager" width="500"><br>File manager</td>
  <td align="center"><img src="src/screenshots/installer-boot_dark_v4-2fb5ea08e3d6.png" alt="Boot animation" width="500"><br>Boot animation</td>
  <td align="center"><img src="src/screenshots/installer-oled_dark_v4-446f97633da9.png" alt="OLED protection" width="500"><br>OLED protection</td>
  <td align="center"><img src="src/screenshots/installer-summary_dark_v4-64bdc98e7f16.png" alt="Summary" width="500"><br>Summary</td>
</tr>
</table>


## v0.61.10: version-aware updates

Validated on 2026-10-28 with Python 3.14.7, using disposable Git repositories
and offscreen Qt. Scope: wrapper startup, automatic sibling selection, release
version comparison, verified fast-forwards, preservation of dirty/divergent
development checkouts, explicit source overrides and read-only entry points.
No desktop installation, native backend or visual appearance change is involved.

- Golden Gate wrapper: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests -q -p no:cacheprovider`: 80 passed.
- Tahoe: `QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_auto_update.py tests/test_cli.py tests/test_installer_ui.py -q -p no:cacheprovider`: 129 passed.
- The same 129 checks passed in prepared Golden Gate source `43473c1c0176893cc6d1`.
- Real Git tests cover clean upgrades from 0.61.9 to 0.61.10, equal/newer local
  versions, staged/unstaged/untracked/deleted files, committed experiments,
  concurrent edits, failed fetches, mismatched archive versions and offline use.
- `git diff --check` passed in both checkouts. No live host installer was run.

The maintainer approved the local installer behavior for release on 2026-10-28.
Release preparation excludes unrelated Downloads Stack and battery-icon work.
Publication requires successful `test.yml` push runs on both `main` and `dev`
for the exact release commits in both repositories. Reviewed screenshot
provenance is retained when visual inputs are unchanged.

The first v0.61.9 CI candidate caught four missing updater messages in the
Portuguese and German catalogs. Both catalogs now include those messages.
Focused validation expanded to `tests/test_multilanguage.py` alongside the
updater, CLI and installer tests: **160 passed** on Python 3.14.7 with offscreen
Qt. The corrected candidate receives new exact-commit CI runs before publication;
console translation fixes do not change the desktop or installer appearance.


Release screenshot policy, 2026-10-28: visual tests and VM captures run only
for a clear change to visible output. v0.61.10 changes updater behavior,
console translations and release validation, and keeps Downloads out of the
Dock. It excludes the separate battery-icon work. Existing reviewed v0.61.9
captures retain their original source, version and hashes. The redundant
translation-only capture was stopped; its partial output is not published.
The release verifier checks unchanged visual inputs, original review hashes,
VM/profile/effect identity and focused application frames. New tests cover
reuse across version/documentation changes, console updater changes, rejection
of UI translation/runtime changes, and publication using the current version
without relabeling old images. Exact-commit CI remains mandatory.


The first final CI run exposed an Arch package ABI mismatch: the distribution
Node binary required `libsimdjson.so.34`, which was absent from its freshly
installed dependency set. The primary job now uses the official
`actions/setup-node@v5` Node 24 runtime and checks `node --version` before
running every JavaScript regression. No test is skipped or disabled. The
release verifier treats CI metadata as nonvisual input; its reuse regression
includes that case. The README count is 2017 collected cases.


## v0.61.11: status icons

Battery and other status icons now use the correct symbolic Mac-style artwork
and follow light/dark palette changes, including generated icon appearances.
See the [black/white battery proof and validation report](tests/native/status_icons_validation.md)
for reviewed VM renderings, source hashes, focused checks, prepared Golden Gate
results and coverage limits. Full exact-commit branch CI remains the release gate.
