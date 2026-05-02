"""File-existence, grep, JSON, and SVG validity checks."""

import gzip
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


# ── basic scripts and version ─────────────────────────────────────────────
def test_version_is_semver(repo):
    assert re.fullmatch(r"\d+\.\d+\.\d+", (repo / "VERSION").read_text().strip())


def test_install_entry_exists(repo):
    p = repo / "install"
    assert p.is_file() and p.stat().st_mode & 0o111


def test_uninstall_entry_exists(repo):
    p = repo / "uninstall"
    assert p.is_file() and p.stat().st_mode & 0o111


@pytest.mark.parametrize("script", ["install", "uninstall"])
def test_help_exits_zero(repo, script):
    rc = subprocess.run([str(repo / script), "--help"], check=False).returncode
    assert rc == 0


def test_installer_package(repo):
    assert (repo / "src/scripts/cli.py").is_file()
    assert (repo / "src/scripts/theme_switch.py").is_file()
    assert (repo / "src/scripts/set-transparency").is_file()
    assert (repo / "src/scripts/steps/__init__.py").is_file()


def test_theme_switch_python(repo):
    text = (repo / "src/scripts/theme_switch.py").read_text()
    assert "apply_color_groups_direct" in text
    assert ".colors" in text
    # Auto mode is strictly time-based — explicitly disables AutomaticLookAndFeel.
    assert "AutomaticLookAndFeel" in text and '"false"' in text


def test_set_transparency_entry_runs(repo):
    p = repo / "src/scripts/set-transparency"
    assert p.is_file() and p.stat().st_mode & 0o111
    rc = subprocess.run(
        [str(p), "--help"], check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode
    assert rc == 0


# ── mirrors json validity ─────────────────────────────────────────────────
@pytest.mark.parametrize("name", ["wallpapers", "fonts", "icons", "cursors"])
def test_mirror_json_valid(src, name):
    p = src / "mirrors" / f"{name}.json"
    assert p.is_file()
    json.loads(p.read_text())


# ── plasma theme dirs and SVGZ contents ──────────────────────────────────
_PLASMA_SVGS = (
    "dialogs/background", "widgets/background", "widgets/translucentbackground",
    "widgets/panel-background", "widgets/tooltip", "widgets/frame",
    "widgets/tasks", "widgets/button", "widgets/viewitem", "widgets/slider",
    "widgets/arrows", "widgets/checkmarks", "widgets/tabbar",
)


@pytest.mark.parametrize("variant", ["Dark", "Light"])
def test_plasma_theme_dir(offline, variant):
    base = offline / "plasma-theme" / f"MacTahoeLiquidKde-{variant}"
    assert base.is_dir()
    assert (base / "metadata.json").is_file()
    assert (base / "plasmarc").is_file()
    assert "defaultWallpaperTheme=MacTahoe" in (base / "plasmarc").read_text()


@pytest.mark.parametrize("variant", ["Dark", "Light"])
@pytest.mark.parametrize("svg", _PLASMA_SVGS)
def test_plasma_svg_decodes(offline, variant, svg):
    f = offline / "plasma-theme" / f"MacTahoeLiquidKde-{variant}" / f"{svg}.svgz"
    decoded = gzip.decompress(f.read_bytes())
    ET.fromstring(decoded)


def test_plasma_dark_light_svg_parity(offline):
    dark = sorted(p.relative_to(offline / "plasma-theme/MacTahoeLiquidKde-Dark")
                  for p in (offline / "plasma-theme/MacTahoeLiquidKde-Dark").rglob("*.svgz"))
    light = sorted(p.relative_to(offline / "plasma-theme/MacTahoeLiquidKde-Light")
                   for p in (offline / "plasma-theme/MacTahoeLiquidKde-Light").rglob("*.svgz"))
    assert dark, "no dark SVGs found"
    assert light, "no light SVGs found"
    assert dark == light


# ── color schemes ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("variant", ["Light", "Dark"])
def test_color_scheme_present(offline, variant):
    f = offline / "color-schemes" / f"MacTahoeLiquidKde{variant}.colors"
    assert f.is_file()
    assert "[General]" in f.read_text()


def test_color_scheme_key_parity(offline):
    def parse(p: Path):
        sections: dict[str, set[str]] = {}
        section = None
        for raw in p.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith(("#", ";")):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                sections.setdefault(section, set())
                continue
            if "=" in line and section is not None:
                sections[section].add(line.split("=", 1)[0].strip())
        return sections

    light = parse(offline / "color-schemes/MacTahoeLiquidKdeLight.colors")
    dark = parse(offline / "color-schemes/MacTahoeLiquidKdeDark.colors")
    diffs = []
    for sec in sorted(set(light) | set(dark)):
        lk = light.get(sec, set())
        dk = dark.get(sec, set())
        if lk != dk:
            diffs.append(f"[{sec}] light-only={sorted(lk - dk)} dark-only={sorted(dk - lk)}")
    assert not diffs, "\n".join(diffs)


# ── kvantum ───────────────────────────────────────────────────────────────
_KVANTUM_KEYS = ("reduce_menu_opacity", "layout_spacing", "blur_translucent")
_KVANTUM_SECTIONS = ("[Menu]", "[MenuItem]", "[Window]")


@pytest.mark.parametrize("name", ["mac-tahoe-liquid-kde", "mac-tahoe-liquid-kdeDark"])
def test_kvantum_files_present(offline, name):
    base = offline / "kvantum/mac-tahoe-liquid-kde"
    assert (base / f"{name}.kvconfig").is_file()
    assert (base / f"{name}.svg").is_file()


@pytest.mark.parametrize("name", ["mac-tahoe-liquid-kde", "mac-tahoe-liquid-kdeDark"])
def test_kvantum_required_settings(offline, name):
    text = (offline / f"kvantum/mac-tahoe-liquid-kde/{name}.kvconfig").read_text()
    for key in _KVANTUM_KEYS:
        assert re.search(rf"^{key}=", text, re.MULTILINE), f"{name} missing {key}"
    for sec in _KVANTUM_SECTIONS:
        assert sec.replace("[", "\\[").replace("]", "\\]")
        assert sec in text, f"{name} missing {sec}"


def test_kvantum_light_window_frames(offline):
    text = (offline / "kvantum/mac-tahoe-liquid-kde/mac-tahoe-liquid-kde.kvconfig").read_text()
    assert "frame.left=10" in text
    assert "frame.right=10" in text


# ── global theme + aurorae + gtk ─────────────────────────────────────────
@pytest.mark.parametrize("variant", ["Dark", "Light"])
def test_global_theme(offline, variant):
    base = offline / "look-and-feel" / f"MacTahoeLiquidKde-{variant}"
    assert base.is_dir()
    json.loads((base / "metadata.json").read_text())
    assert (base / "contents/defaults").is_file()
    assert (base / "contents/layouts/org.kde.plasma.desktop-layout.js").is_file()
    defaults = (base / "contents/defaults").read_text()
    assert f"ColorScheme=MacTahoeLiquidKde{variant}" in defaults
    assert f"name=MacTahoeLiquidKde-{variant}" in defaults
    assert f"MacTahoeLiquidKde-{variant}" in defaults
    assert "cursorTheme=" in defaults
    assert "Image=MacTahoe" in defaults


@pytest.mark.parametrize("variant", ["Dark", "Light"])
def test_aurorae(offline, variant):
    base = offline / "aurorae" / f"MacTahoeLiquidKde-{variant}"
    assert base.is_dir()
    assert (base / "decoration.svg").is_file()
    assert (offline / f"aurorae/MacTahoeLiquidKde-{variant}rc").is_file()


@pytest.mark.parametrize("variant", ["Dark", "Light"])
def test_gtk(offline, variant):
    base = offline / "gtk" / f"MacTahoeLiquidKde-{variant}"
    assert base.is_dir()
    assert (base / "gtk-3.0/gtk.css").is_file()
    assert (base / "gtk-4.0/gtk.css").is_file()
    assert (base / "gtk-4.0/gtk-Light.css").is_file()
    assert (base / "gtk-4.0/gtk-Dark.css").is_file()
    assert (base / "gtk-4.0/assets").is_dir()


# ── plasmoids ─────────────────────────────────────────────────────────────
def test_old_menu_removed(offline, steps_dir):
    assert not (offline / "plasmoids/org.kde.mac-tahoe-liquid-kde.menu").exists()
    assert not (steps_dir / "menu").exists()


_GLOBALMENU = "plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu"


@pytest.mark.parametrize("rel", [
    "CMakeLists.txt", "appmenuapplet.cpp", "appmenuapplet.h",
    "appmenumodel.cpp", "appmenumodel.h", "metadata.json",
    "qml/main.qml", "qml/MenuDelegate.qml", "qml/AboutWindow.qml",
    "qml/configSystemMenu.qml",
])
def test_globalmenu_files(offline, rel):
    assert (offline / _GLOBALMENU / rel).is_file()


def test_globalmenu_has_features(offline):
    main = (offline / _GLOBALMENU / "qml/main.qml").read_text()
    cpp = (offline / _GLOBALMENU / "appmenuapplet.cpp").read_text()
    h = (offline / _GLOBALMENU / "appmenuapplet.h").read_text()
    model = (offline / _GLOBALMENU / "appmenumodel.h").read_text()
    main_xml = (offline / _GLOBALMENU / "main.xml").read_text()
    delegate = (offline / _GLOBALMENU / "qml/MenuDelegate.qml").read_text()

    assert "appNameButton" in main
    assert "activeAppName" in model
    assert "systemMenuButton" in main
    assert "triggerSystemMenu" in cpp
    assert "aboutRequested" in h
    assert "_breeze_menu_seamless_edges" in cpp
    assert "cfg.readEntry" in cpp
    assert "triggerWindowMenu" in cpp
    for key in ("iconAbout", "iconAppStore", "iconLogOut", "menuIcon", "cmdSleep"):
        assert key in main_xml
    assert "font.weight" in delegate


def test_globalmenu_metadata_id(offline):
    text = (offline / _GLOBALMENU / "metadata.json").read_text()
    assert '"Id": "org.kde.mac.tahoe.liquid.globalmenu"' in text


def test_launcher_metadata(offline):
    p = offline / "plasmoids/org.kde.mac-tahoe-liquid-kde.launcher"
    json.loads((p / "metadata.json").read_text())
    assert (p / "contents/ui/main.qml").is_file()
    assert '"Id": "org.kde.mac-tahoe-liquid-kde.launcher"' in (p / "metadata.json").read_text()


def test_trashcan_metadata(offline):
    p = offline / "plasmoids/org.kde.mac-tahoe-liquid-kde.trashcan"
    json.loads((p / "metadata.json").read_text())
    assert (p / "contents/ui/main.qml").is_file()
    assert '"Id": "org.kde.mac-tahoe-liquid-kde.trashcan"' in (p / "metadata.json").read_text()


def test_dock_taskmanager(offline):
    p = offline / "plasmoids/org.kde.mac.tahoe.liquid.taskmanager"
    icontasks = offline / "plasmoids/org.kde.mac.tahoe.liquid.icontasks"
    json.loads((p / "metadata.json").read_text())
    json.loads((icontasks / "metadata.json").read_text())

    # Stock and legacy package overrides must NOT be shipped.
    for name in (
        "org.kde.plasma.taskmanager", "org.kde.plasma.icontasks",
        "org.kde.mac-tahoe-liquid-kde.taskmanager",
        "org.kde.mac-tahoe-liquid-kde.icontasks",
    ):
        assert not (offline / "plasmoids" / name).exists(), name

    assert not (icontasks / "contents").exists()
    assert (p / "CMakeLists.txt").is_file()
    for fn in ("backend.h", "backend.cpp",
               "smartlauncherbackend.h", "smartlauncherbackend.cpp",
               "smartlauncheritem.h", "smartlauncheritem.cpp",
               "kactivitymanagerd_plugins_settings.kcfg",
               "kactivitymanagerd_plugins_settings.kcfgc",
               "contents/ui/Badge.qml", "contents/ui/main.qml",
               "contents/ui/Task.qml", "contents/ui/TaskBadgeOverlay.qml",
               "contents/ui/LayoutMetrics.js",
               "contents/ui/TaskTools.js"):
        assert (p / fn).is_file(), fn

    assert not (p / "contents/ui/plasma/applet/org/kde/plasma/taskmanager/qmldir").is_file()

    icontasks_meta = (icontasks / "metadata.json").read_text()
    assert '"Id": "org.kde.mac.tahoe.liquid.icontasks"' in icontasks_meta
    assert '"X-Plasma-RootPath": "org.kde.mac.tahoe.liquid.taskmanager"' in icontasks_meta

    p_meta = (p / "metadata.json").read_text()
    assert '"Id": "org.kde.mac.tahoe.liquid.taskmanager"' in p_meta

    overlay = (p / "contents/ui/TaskBadgeOverlay.qml").read_text()
    assert "#ff3b30" in overlay
    assert "#ffffff" in overlay

    tooltip = (p / "contents/ui/ToolTipInstance.qml").read_text()
    assert "Kirigami.Badge" not in tooltip

    main = (p / "contents/ui/main.qml").read_text()
    assert "filterByVirtualDesktop:" in main
    assert "filterByCurrentVirtualDesktop" not in main
    assert "import plasma.applet.org.kde.mac.tahoe.liquid.taskmanager as TaskManagerApplet" in main
    assert 'import "LayoutMetrics.js" as LayoutMetrics' in main
    assert 'import "TaskTools.js" as TaskTools' in main

    task = (p / "contents/ui/Task.qml").read_text()
    assert "import plasma.applet.org.kde.mac.tahoe.liquid.taskmanager as TaskManagerApplet" in task
    assert ('Qt.createComponent("plasma.applet.org.kde.mac.tahoe.liquid.taskmanager"'
            ', "SmartLauncherItem")') in task


def test_taskmanager_badge_overlay_guardrails(offline):
    base = offline / "plasmoids/org.kde.mac.tahoe.liquid.taskmanager" / "contents/ui"
    overlay = (base / "TaskBadgeOverlay.qml").read_text()
    tooltip = (base / "ToolTipInstance.qml").read_text()
    task = (base / "Task.qml").read_text()

    # Only instantiate the badge overlay when the count bubble should exist.
    assert "active: height >= Kirigami.Units.iconSizes.small" in task
    assert "&& task.smartLauncherItem && task.smartLauncherItem.countVisible" in task
    assert 'source: "TaskBadgeOverlay.qml"' in task

    # Keep the dock badge self-contained and text-driven rather than relying
    # on Kirigami.Badge's dot/overlay internals, which have been crash-prone.
    assert "KGraphicalEffects.BadgeEffect" in overlay
    assert "Kirigami.Badge" not in overlay
    assert "visible: task.smartLauncherItem.countVisible" in overlay
    assert "live: false" in overlay
    assert "onVisibleChanged: maskShaderSource.scheduleUpdate()" in overlay
    assert "onYChanged: maskShaderSource.scheduleUpdate()" in overlay
    assert "width: Math.max(height, Math.round(badgeLabel.implicitWidth + horizontalPadding * 2))" in overlay
    assert "height: Math.max(14, Math.min(20, Math.round(icon.paintedHeight * 0.38)))" in overlay
    assert "textFormat: Text.PlainText" in overlay

    # The tooltip badge should stay visually in sync with the dock badge.
    assert "Keep parity with TaskBadgeOverlay (dock badge)" in tooltip
    assert "width: Math.max(height, Math.round(badgeLabel.implicitWidth + horizontalPadding * 2))" in tooltip
    assert "textFormat: Text.PlainText" in tooltip


# ── acrylic glass ─────────────────────────────────────────────────────────
_AG_KEYS = (
    "BlurStrength", "NoiseStrength", "BlurDecorations", "WindowCornerRadius",
    "DockCornerRadius", "PopupCornerRadius", "HighlightStrength",
    "HighlightWidth", "MagnifyGlassStrength", "RefractionWidth",
    "RgbDriftStrength",
)


def test_acrylic_glass_files(offline):
    base = offline / "kwin-effects/acrylic-glass"
    for fn in ("CMakeLists.txt", "src/effect.cpp", "src/effect.h",
               "src/glass.kcfg", "src/kcm/config.ui"):
        assert (base / fn).is_file(), fn


@pytest.mark.parametrize("key", _AG_KEYS)
def test_acrylic_glass_kcfg(offline, key):
    kcfg = (offline / "kwin-effects/acrylic-glass/src/glass.kcfg").read_text()
    assert f'name="{key}"' in kcfg


def test_acrylic_glass_kcm_layout(offline):
    ui = (offline / "kwin-effects/acrylic-glass/src/kcm/config.ui").read_text()
    for needle in ("QTabWidget",
                   "<string>Glass</string>",
                   "<string>Corners</string>",
                   "<string>Window Rules</string>",
                   'name="kcfg_BlurDecorations"',
                   'name="kcfg_NoiseStrength"'):
        assert needle in ui


def test_acrylic_glass_shaders(offline):
    base = offline / "kwin-effects/acrylic-glass/src/shaders"
    for fn in ("texture_core.frag", "upsample_core.frag", "downsample_core.frag",
               "noise_core.frag", "sdf.glsl", "blur.glsl",
               "distort.glsl", "highlight.glsl"):
        assert (base / fn).is_file(), fn
    glass = (base / "glass.glsl").read_text()
    for inc in ("sdf.glsl", "blur.glsl", "distort.glsl", "highlight.glsl"):
        assert f'#include "{inc}"' in glass


def test_acrylic_glass_cmake(offline):
    text = (offline / "kwin-effects/acrylic-glass/src/CMakeLists.txt").read_text()
    assert "preprocess_shader_includes" in text
    for fn in ("sdf.glsl", "blur.glsl", "distort.glsl", "highlight.glsl"):
        assert fn in text


def test_acrylic_glass_blur_scaling(offline):
    cpp = (offline / "kwin-effects/acrylic-glass/src/effect.cpp").read_text()
    assert "xScale(), 1.0) || !qFuzzyCompare(data.yScale(), 1.0)" in cpp


# ── layout / Acrylic preset / installer step references ──────────────────
_LAYOUT_PLUGINS = (
    "org.kde.mac.tahoe.liquid.globalmenu",
    "org.kde.mac-tahoe-liquid-kde.launcher",
    "org.kde.mac-tahoe-liquid-kde.trashcan",
    "org.kde.plasma.panelspacer",
    "org.kde.plasma.systemtray",
    "org.kde.plasma.digitalclock",
    "org.kde.mac.tahoe.liquid.icontasks",
    "luisbocanegra.panel.colorizer",
)


def test_layout_files(offline):
    assert (offline / "layouts/mac-tahoe.js").is_file()
    assert (offline / "layouts/default.js").is_file()


@pytest.mark.parametrize("plugin", _LAYOUT_PLUGINS)
def test_layout_references_plugin(offline, plugin):
    text = (offline / "layouts/mac-tahoe.js").read_text()
    assert plugin in text


_ACRYLIC_STEP_KEYS = (
    "BlurStrength", "HighlightStrength", "HighlightWidth", "DockCornerRadius",
    "WindowCornerRadius", "PopupCornerRadius", "RimStrength", "ShadowStrength",
)


@pytest.mark.parametrize("key", _ACRYLIC_STEP_KEYS)
def test_acrylic_step_sets_key(repo, key):
    text = (repo / "src/scripts/steps/acrylic_glass.py").read_text()
    assert key in text


def test_globalmenu_step_cleans_old(repo):
    text = (repo / "src/scripts/steps/globalmenu.py").read_text()
    assert "org.kde.mac.tahoe.liquid.menu.so" in text
    assert "org.kde.mac-tahoe-liquid-kde.menu" in text
    # Pre-rename plugins (April-1st builds, before "liquid" was added).
    assert "org.kde.mac.tahoe.globalmenu.so" in text


def test_layout_no_standalone_menu(offline):
    text = (offline / "layouts/mac-tahoe.js").read_text()
    assert "org.kde.mac.tahoe.liquid.menu" not in text


def test_cli_feature_lists(repo):
    text = (repo / "src/scripts/cli.py").read_text()
    for f in ("nautilus", "portals", "wallpapers", "fonts", "cursors",
              "icons", "plasmoids", "globalmenu", "layout"):
        assert f'"{f}"' in text, f


def test_features_json_has_keys(repo):
    feats = json.loads((repo / "features.json").read_text())
    for k in ("nautilus", "portals", "wallpapers", "fonts"):
        assert k in feats


# ── nautilus / portals python steps reference KDE/dolphin ────────────────
def test_nautilus_step(repo):
    text = (repo / "src/scripts/steps/nautilus.py").read_text()
    assert "XDG_CURRENT_DESKTOP" in text
    assert "org.gnome.Nautilus.desktop" in text
    assert "org.kde.dolphin.desktop" in text
    assert 'xdg-mime' in text


def test_portals_step(repo):
    text = (repo / "src/scripts/steps/portals.py").read_text()
    assert "kde-portals.conf" in text
    assert "FileChooser=kde" in text
    assert "AppChooser=kde" in text
    assert "Settings=gtk" in text
    # Regression guards: no default=kde (libadwaita can't read KDE's schema)
    # and Settings must NOT route to kde.
    assert not re.search(r"^\s*default=kde", text, re.MULTILINE)
    assert "xdg-desktop-portal" in text


# ── transparency / theme-switch python ───────────────────────────────────
def test_transparency_python(repo):
    p = repo / "src/scripts/set-transparency"
    text = p.read_text()
    assert "reduce_menu_opacity" in text
    assert "window.color" in text
    assert "svgz" in text
    assert "window_bg_color" in text
    assert "background.csd" in text
    assert "--dock" in text
    assert "--apply" in text
    assert "DEFAULT_DOCK_PCT = 12" in text
    assert "default: 12" in text


def test_theme_switch_invariants(repo):
    text = (repo / "src/scripts/theme_switch.py").read_text()
    assert "apply_color_groups_direct" in text
    assert "Auto = strictly time-based" in text or "detect_auto_target_mode" in text
    assert "AutomaticLookAndFeel" in text
    assert "refreshCurrentShell" not in text


# ── systemd unit invariants ───────────────────────────────────────────────
def test_theme_service(offline):
    s = (offline / "mac-tahoe-liquid-kde-theme.service").read_text()
    assert "WantedBy=graphical-session.target" in s
    assert "PartOf=graphical-session.target" in s


def test_theme_timer(offline):
    t = (offline / "mac-tahoe-liquid-kde-theme.timer").read_text()
    assert "WantedBy=timers.target" in t
    assert "After=graphical-session.target" not in t


def test_readme_documents_last_run(repo):
    assert "last-run.json" in (repo / "README.md").read_text()


# ── installer step naming convention ─────────────────────────────────────
def test_install_helpers_have_reinstall(repo):
    text = (repo / "src/scripts/log.py").read_text()
    assert re.search(r"def reinstall.*GREEN", text, re.DOTALL)


# ── per-step output ordering ─────────────────────────────────────────────
def test_window_decorations_summary_is_last(repo):
    """Step output convention: the ``info(...)`` summary count is the LAST
    line printed by an install step. Window decorations historically had
    the summary in the middle, sandwiched between per-item lines and the
    'Window decoration set to ...' status — easy regression to repeat
    when adding new ``ok()`` calls."""
    src = (repo / "src/scripts/steps/window_decorations.py").read_text()
    install_block = re.search(
        r"def install\(.*?(?=\n(?:def [A-Za-z_]|\Z))", src, re.DOTALL
    )
    assert install_block is not None
    body = install_block.group()
    info_pos = body.rfind("info(")
    last_ok_pos = body.rfind('ok(f"Window decoration set')
    assert info_pos != -1, "expected info() summary in install()"
    assert last_ok_pos != -1, "expected 'Window decoration set' ok() in install()"
    assert info_pos > last_ok_pos, (
        "info() summary must be the LAST line of install() — currently the "
        "'Window decoration set to ...' status is being printed AFTER the "
        "summary count, which is the regression we are guarding against."
    )


@pytest.mark.parametrize("step,marker", [
    ("cursors", "cursor themes installed"),
    ("gtk", "GTK themes installed"),
    ("plasmoids", "installed/reinstalled"),
    ("color_schemes", "color schemes"),
    ("plasma_theme", "Plasma themes"),
    ("icons", "installed/reinstalled"),
])
def test_step_summary_is_last_print(repo, step, marker):
    """Sister regression for the other steps that emit a summary count —
    no ``ok()`` / ``info()`` / ``warn()`` / ``fail()`` call may follow the
    summary inside the same install function."""
    src = (repo / f"src/scripts/steps/{step}.py").read_text()
    install_block = re.search(
        r"def install\(.*?(?=\n(?:def [A-Za-z_]|\Z))", src, re.DOTALL
    )
    assert install_block is not None, f"{step}: no install() function found"
    body = install_block.group()
    summary_pos = max(
        body.rfind("info(f\""),
        body.rfind("info(f'"),
    )
    assert summary_pos != -1, f"{step}: expected an info() summary line"
    tail = body[summary_pos + 1:]
    for forbidden in ("ok(", "info(", "fail(", "warn(", "reinstall("):
        assert forbidden not in tail, (
            f"{step}: found {forbidden!r} after the summary line — the "
            f"summary must be the LAST log emitted by install()"
        )
