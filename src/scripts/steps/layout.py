from localization import tr
import json
import re
import subprocess
import time
from pathlib import Path

from launcher_defaults import (
    LAUNCHER_ID, applied_edition, default_launcher_preset, edition_name,
    edition_state_file, record_applied_edition, remember_installed_edition,
)

from steps._helpers import (
    DATA_HOME, HOME, have, install_tree, kw_write, ok, offline, qdbus_call, remove_tree, warn,
)
from utils import qdbus_cmd, run_user

LAYOUT_SCRIPT = offline("layouts/mac-tahoe.js")
LAYOUT_RESET = offline("layouts/default.js")
DOCK_MIGRATION = offline("layouts/migrate-dock-preset.js")
_DISCOVER_DESKTOP = "applications:org.kde.discover.desktop"
COLORIZER_ID = "luisbocanegra.panel.colorizer"
COLORIZER_SRC = offline("plasmoids") / COLORIZER_ID
MAC_TASKS_ID = "org.kde.mac.tahoe.liquid.icontasks"
DEFAULT_TASKS_ID = "org.kde.plasma.icontasks"


def _colorizer_dirs() -> list[Path]:
    dirs = [DATA_HOME / "plasma/plasmoids" / COLORIZER_ID]
    for base in ("/usr/local/share", "/usr/share"):
        dirs.append(Path(base) / "plasma/plasmoids" / COLORIZER_ID)
    return dirs


def _colorizer_version(path: Path) -> tuple[int, ...] | None:
    """Return a comparable version from a Panel Colorizer package."""
    try:
        version = json.loads(
            (path / "metadata.json").read_text(encoding="utf-8")
        )["KPlugin"]["Version"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return None
    if (
        not isinstance(version, str)
        or not re.fullmatch(r"\d+(?:\.\d+)*", version)
    ):
        return None
    parts = tuple(int(part) for part in version.split("."))
    return parts + (0,) * (3 - len(parts))


def deps():
    return ["qdbus6:qt6-tools"]


def _ensure_panel_colorizer() -> None:
    # A user package shadows system packages, so check it first. Replace an
    # outdated user copy; otherwise preserve an equal/newer installed release.
    bundled_version = _colorizer_version(COLORIZER_SRC)
    if bundled_version is None:
        warn(tr('Panel Colorizer not installed — bundled metadata is invalid.'))
        return

    dirs = _colorizer_dirs()
    dest = dirs[0]
    user_version = _colorizer_version(dest)
    if user_version is not None and user_version >= bundled_version:
        ok(tr('Panel Colorizer'))
        return

    if user_version is None and not dest.exists():
        for path in dirs[1:]:
            installed_version = _colorizer_version(path)
            if (
                installed_version is not None
                and installed_version >= bundled_version
            ):
                ok(tr('Panel Colorizer'))
                return

    if install_tree(COLORIZER_SRC, dest, tr('Panel Colorizer')):
        return
    warn(tr("Panel Colorizer not installed — top bar won't be transparent. Install manually from KDE Store."))


def _evaluate_layout_script(script: str) -> bool:
    if qdbus_cmd() is None:
        warn(tr('qdbus not found — layout not installed'))
        return False
    # plasmashell may still be restarting from the apply step — retry a few times.
    for _ in range(5):
        if qdbus_call(
            "org.kde.plasmashell",
            "/PlasmaShell",
            "org.kde.PlasmaShell.evaluateScript",
            script,
        ):
            return True
        time.sleep(3)
    return False


def _discover_is_installed() -> bool:
    """Check if org.kde.discover.desktop exists in any XDG applications dir."""
    for prefix in (DATA_HOME, Path("/usr/local/share"), Path("/usr/share")):
        if (prefix / "applications/org.kde.discover.desktop").is_file():
            return True
    return False


def _evaluate_layout(script_path) -> bool:
    script = script_path.read_text()
    if not _discover_is_installed():
        script = script.replace(_DISCOVER_DESKTOP + ",", "")
        script = script.replace("," + _DISCOVER_DESKTOP, "")
    return _evaluate_layout_script(script)


def _capture_pinned_launchers() -> list[str]:
    """User-pinned launchers from appletsrc, deduped in order; MacTahoe's
    own plasmoids are dropped so a reinstall doesn't double them."""
    appletsrc = HOME / ".config/plasma-org.kde.plasma.desktop-appletsrc"
    if not appletsrc.is_file():
        return []
    try:
        text = appletsrc.read_text()
    except OSError:
        return []
    seen: list[str] = []
    for m in re.finditer(r"^launchers=(.*)$", text, re.MULTILINE):
        for entry in m.group(1).split(","):
            entry = entry.strip()
            if entry and (entry == "applications:org.kde.mac-tahoe-liquid-kde.apps.desktop"
                          or ("mac.tahoe" not in entry and "mac-tahoe" not in entry)):
                if entry not in seen:
                    seen.append(entry)
    return seen


def _append_launcher_restore(
        script: str, pins: list[str], widget_type: str, *,
        preserve_empty: bool = False) -> str:
    if widget_type == DEFAULT_TASKS_ID:
        pins = [pin for pin in pins if pin != "applications:org.kde.mac-tahoe-liquid-kde.apps.desktop"]
    if pins or preserve_empty:
        joined = json.dumps(pins)
        widget = repr(widget_type)
        script += (
            "\n(function () {\n"
            "  var ps = panels();\n"
            "  for (var i = 0; i < ps.length; i++) {\n"
            "    var ws = ps[i].widgetIds;\n"
            "    for (var j = 0; j < ws.length; j++) {\n"
            "      var w = ps[i].widgetById(ws[j]);\n"
            f"      if (w && w.type === {widget}) {{\n"
            "        w.currentConfigGroup = ['General'];\n"
            f"        w.writeConfig('launchers', {joined});\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "})();\n"
        )
    return script


def _layout_script_with_launchers(
        script_path: Path, pins: list[str], widget_type: str) -> str | None:
    if not script_path.is_file():
        return None
    script = script_path.read_text()
    if script_path == LAYOUT_SCRIPT:
        preset = default_launcher_preset() if applied_edition(HOME) != edition_name() else 0
        from installer_choices import selected, use_user_launcher
        choices = selected()
        if use_user_launcher():
            pins = [pin for pin in pins if pin != "applications:org.kde.mac-tahoe-liquid-kde.apps.desktop"]
            script = user_launcher_script() + script
        if choices:
            preset = 2 if choices["launcher"] == "golden" else 1
            script = (f"var mttkdeTopPanel = {str(choices['panel']).lower()};\n"
                      f"var mttkdeDock = {str(choices['dock']).lower()};\n" + script)
        script = f"var mttkdeLauncherPreset = {preset};\n" + script
    if not _discover_is_installed():
        script = script.replace(_DISCOVER_DESKTOP + ",", "")
        script = script.replace("," + _DISCOVER_DESKTOP, "")
    script = _append_launcher_restore(
        script, pins, widget_type,
        preserve_empty=script_path == LAYOUT_SCRIPT and _layout_has_any_theme_widget(),
    )

    if script_path == LAYOUT_SCRIPT:
        script += "\n" + _dock_migration_script()
    return script


def user_launcher_script() -> str:
    import os
    launchers = {"org.kde.plasma.kickoff", "org.kde.plasma.kicker", "org.kde.plasma.kickerdash"}
    roots = [DATA_HOME, *map(Path, os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":"))]
    for root in roots:
        for path in (root / "plasma/plasmoids").glob("*/metadata.json"):
            try:
                meta = json.loads(path.read_text())["KPlugin"]
                if meta.get("Category") == "Application Launchers" and meta["Id"] != LAUNCHER_ID:
                    launchers.add(meta["Id"])
            except (OSError, ValueError, KeyError):
                continue
    return "var userLauncherTypes = " + json.dumps(sorted(launchers)) + ";\n"


def replace_project_launcher() -> None:
    script = user_launcher_script() + """
const panelList = panels();
for (const panel of panelList) {
    const current = panel.widgets();
    const ours = current.filter(w => w.type === "org.kde.mac-tahoe-liquid-kde.launcher");
    if (!ours.length) continue;
    if (!panelList.some(p => p.screen === panel.screen && p.widgets().some(w => userLauncherTypes.includes(w.type)))) {
        const replacement = panel.addWidget("org.kde.plasma.kickoff");
        if (!replacement) throw Error("Could not restore the Plasma launcher");
        replacement.index = ours[0].index;
    }
    for (const widget of ours) widget.remove();
}
"""
    if not _evaluate_layout_script(script):
        raise RuntimeError("Could not replace the installed launcher")


def configure_dock() -> None:
    from installer_choices import dock_visibility, dock_visibility_preference, selected
    choices = selected()
    if not choices.get("dock", True):
        return
    mode = choices.get("dock_visibility", dock_visibility())
    script = """
    (function () {
        for (const panel of panels()) {
            if (panel.screen >= 0 && panel.screen < screenCount && panel.location === "bottom" && panel.widgets().some(
                    widget => widget.type === "org.kde.mac.tahoe.liquid.icontasks")) {
                panel.hiding = MODE;
            }
        }
    })()
    """.replace("MODE", json.dumps(mode))
    if not _evaluate_layout_script(script):
        warn(tr("Dock preset update failed"))
        return
    if choices:
        preference = dock_visibility_preference()
        preference.parent.mkdir(parents=True, exist_ok=True)
        preference.write_text(mode + "\n")
    script_id = "mttkde-dock-follows-screen"
    if install_tree(offline("kwin-scripts", script_id), DATA_HOME / "kwin/scripts" / script_id,
                    "Dock follows screen"):
        kw_write("--file", "kwinrc", "--group", "Plugins", "--key", script_id + "Enabled", "true")
        qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")


def _dock_migration_script() -> str:
    from installer_choices import dock_visibility, selected
    choices = selected()
    requested = choices.get("dock_apps", []) if choices.get("dock", True) else []
    appearance = choices.get("dock_appearance", "auto") if choices.get("dock", True) else "keep"
    return ("var mttkdeResetDock = " + json.dumps(choices.get("reset_layout", False)) + ";\n"
            + "var mttkdeDockVisibility = " + json.dumps(choices.get("dock_visibility", dock_visibility())) + ";\n"
            + "var mttkdeDockAppearance = " + json.dumps(appearance) + ";\n"
            + "var mttkdeRequestedDockApps = " + json.dumps(requested) + ";\n"
            + DOCK_MIGRATION.read_text())


def migrate_status_controls() -> None:
    """Remove duplicated controls without rebuilding an existing themed bar."""
    from installer_choices import selected
    choices = selected()
    if choices and not choices["panel"]:
        return
    if not _evaluate_layout_script(offline("layouts/migrate-status-controls.js").read_text()):
        warn(tr('layout failed — set layout manually'))


def migrate_dock_preset() -> None:
    """Upgrade existing Docks without rebuilding panels or changing their geometry."""
    from installer_choices import selected
    choices = selected()
    if choices and not choices["dock"]:
        return
    if not _evaluate_layout_script(_dock_migration_script()):
        warn(tr('Dock preset update failed'))


def _evaluate_layout_with_launchers(
        script_path: Path, pins: list[str], widget_type: str) -> bool:
    script = _layout_script_with_launchers(script_path, pins, widget_type)
    return script is not None and _evaluate_layout_script(script)


def _restore_pins(pins: list[str], widget_type: str) -> bool:
    if not pins:
        return True
    return _evaluate_layout_script(
        _append_launcher_restore("", pins, widget_type),
    )


def _reset_with_pins(pins: list[str]) -> bool:
    """Build the bundled Breeze panel and restore only user launchers."""
    script = _layout_script_with_launchers(
        LAYOUT_RESET, pins, DEFAULT_TASKS_ID,
    )
    if script is None:
        return False
    return _evaluate_layout_script(script)


def _reset_layout_builtin() -> bool:
    if not have("plasma-apply-lookandfeel"):
        return False
    try:
        res = run_user(
            ["plasma-apply-lookandfeel", "-a", "org.kde.breeze.desktop", "--resetLayout"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired:
        return False
    if res.returncode != 0:
        return False
    blob = "\n".join(part for part in (res.stdout, res.stderr) if part)
    if "Usage: plasma-apply-lookandfeel" in blob:
        return False
    return True


_DEFAULT_PANEL_NEEDLES = (
    "plugin=org.kde.plasma.kickoff",
    "plugin=org.kde.plasma.pager",
    "plugin=org.kde.plasma.icontasks",
    "plugin=org.kde.plasma.systemtray",
    "plugin=org.kde.plasma.digitalclock",
    "plugin=org.kde.plasma.showdesktop",
)
_CUSTOM_PANEL_NEEDLES = (
    "plugin=org.kde.mac.tahoe.liquid.globalmenu",
    "plugin=org.kde.mac.tahoe.liquid.icontasks",
    "plugin=org.kde.mac-tahoe-liquid-kde.launcher",
    "plugin=org.kde.mac-tahoe-liquid-kde.trashcan",
)
_THEME_PLUGIN_RE = re.compile(
    r"^plugin=org\.kde\.(?:"
    r"mac-tahoe-liquid-kde|"
    r"mac\.tahoe(?:\.liquid)?|"
    r"mactahoe-liquid-kde"
    r")\.",
    re.MULTILINE,
)


def _layout_marker() -> Path:
    return HOME / ".local/state/mac-tahoe-liquid-kde/layout-installed"


def _mark_layout_installed() -> None:
    marker = _layout_marker()
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("1\n", encoding="utf-8")
    except OSError:
        pass


def _clear_layout_marker() -> None:
    try:
        _layout_marker().unlink()
    except OSError:
        pass


def _layout_has_any_theme_widget() -> bool:
    appletsrc = HOME / ".config/plasma-org.kde.plasma.desktop-appletsrc"
    try:
        text = appletsrc.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return _THEME_PLUGIN_RE.search(text) is not None


def _layout_looks_reset() -> bool:
    """'Reset' = no MacTahoe plugin IDs left in appletsrc. Default Breeze
    needles may land asynchronously (plasma-apply-lookandfeel), so their
    presence is not required."""
    appletsrc = HOME / ".config/plasma-org.kde.plasma.desktop-appletsrc"
    if not appletsrc.is_file():
        return True
    try:
        text = appletsrc.read_text()
    except OSError:
        return False
    return _THEME_PLUGIN_RE.search(text) is None


def _layout_looks_installed() -> bool:
    appletsrc = HOME / ".config/plasma-org.kde.plasma.desktop-appletsrc"
    if not appletsrc.is_file():
        return False
    try:
        text = appletsrc.read_text()
    except OSError:
        return False
    from installer_choices import selected, use_user_launcher
    choices = selected()
    needles = _CUSTOM_PANEL_NEEDLES
    if use_user_launcher():
        needles = tuple(needle for needle in needles if LAUNCHER_ID not in needle)
    if choices:
        needles = tuple(needle for needle in needles
                        if (choices["panel"] if "globalmenu" in needle else choices["dock"]))
    return all(needle in text for needle in needles)


def _wait_for_layout_install(timeout_seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _layout_looks_installed():
            return True
        time.sleep(0.2)
    return _layout_looks_installed()


# The layout sets the Dock's live opacity. Also persist panel glass settings
# here, including floatingApplets, after Plasma creates the views.
_PRC_PANEL_RE = re.compile(
    r"(\[PlasmaViews\]\[Panel \d+\]\n(?:[^\[]*\n)*)", re.MULTILINE,
)


def _patch_plasmashellrc() -> None:
    prc = HOME / ".config/plasmashellrc"
    if not prc.is_file():
        return
    text = prc.read_text()

    def fix(m: re.Match) -> str:
        section = m.group(0)
        # Force Translucent (2) on every panel so the top bar doesn't fall
        # back to Plasma's Adaptive default, which turns opaque whenever a
        # window touches the screen edge under it — defeating the glass look
        # on the one panel that isn't floating.
        if "panelOpacity=" in section:
            section = re.sub(r"panelOpacity=\d+", "panelOpacity=2", section)
        else:
            section = section.rstrip() + "\npanelOpacity=2\n"
        if "floating=0" in section:
            # Keep the top bar applets-only floating while Panel Colorizer
            # hides the continuous native panel background (see mac-tahoe.js).
            if "floatingApplets=" in section:
                section = re.sub(r"floatingApplets=\d+", "floatingApplets=1", section)
            else:
                section = section.rstrip() + "\nfloatingApplets=1\n"
        return section

    new_text = _PRC_PANEL_RE.sub(fix, text)
    if new_text != text:
        prc.write_text(new_text)
        ok(tr('Panel glass forced translucent'))


def _reset_plasmashellrc() -> bool:
    """Remove only the panel values written by this project.

    Rebuilding the panel layout does not clear ``plasmashellrc``'s per-panel
    view state.  Plasma can reuse the same panel id for the new Breeze panel,
    so our translucent opacity survives uninstall unless it is removed
    explicitly.  Values other than our exact preset are user-owned and stay.
    """
    prc = HOME / ".config/plasmashellrc"
    if not prc.is_file():
        return False
    try:
        text = prc.read_text()
    except OSError:
        return False

    def reset(m: re.Match) -> str:
        section = m.group(0)
        section = re.sub(r"^panelOpacity=2\n?", "", section,
                         flags=re.MULTILINE)
        section = re.sub(r"^floatingApplets=1\n?", "", section,
                         flags=re.MULTILINE)
        return section

    new_text = _PRC_PANEL_RE.sub(reset, text)
    if new_text == text:
        return False
    try:
        prc.write_text(new_text)
    except OSError:
        return False
    return True


def install() -> None:
    # A failed rebuild must leave is_installed() false so cli.py retries after
    # Plasma restarts instead of trusting a marker from the previous run.
    _clear_layout_marker()
    remember_installed_edition(HOME, DATA_HOME / "plasma/plasmoids" / LAUNCHER_ID)
    _ensure_panel_colorizer()
    if not LAYOUT_SCRIPT.is_file():
        warn(tr('Layout script not found — skipping'))
        return
    pins = _capture_pinned_launchers()
    applied = _evaluate_layout_with_launchers(
        LAYOUT_SCRIPT, pins, MAC_TASKS_ID,
    )
    if applied and _wait_for_layout_install():
        record_applied_edition(HOME, edition_name())
        _mark_layout_installed()
        ok(tr("Layout installed (kept {count} pinned apps)", count=len(pins)) if pins
           else tr("Layout installed"))
    else:
        warn(tr('layout failed — set layout manually'))
        return
    time.sleep(3)
    _patch_plasmashellrc()


def is_installed() -> bool:
    return _layout_marker().is_file() or _layout_looks_installed()


def uninstall() -> None:
    from installer_choices import dock_visibility_preference
    script_id = "mttkde-dock-follows-screen"
    if (DATA_HOME / "kwin/scripts" / script_id).exists():
        kw_write("--file", "kwinrc", "--group", "Plugins", "--key", script_id + "Enabled", "false")
        qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
        remove_tree(DATA_HOME / "kwin/scripts" / script_id, "Dock follows screen")
    dock_visibility_preference().unlink(missing_ok=True)
    has_theme_widgets = _layout_has_any_theme_widget()
    _clear_layout_marker()
    if _reset_plasmashellrc():
        ok(tr('Panel transparency reset'))
    if not has_theme_widgets:
        edition_state_file(HOME).unlink(missing_ok=True)
        ok(tr('Layout already clean'))
        return
    # Always remove the Mac top bar and Dock. Preserve only the applications
    # the user pinned; Launcher and Trash are widgets and disappear with Dock.
    pins = _capture_pinned_launchers()
    if _reset_with_pins(pins):
        edition_state_file(HOME).unlink(missing_ok=True)
        ok(tr("Layout reset (kept {count} pinned apps)", count=len(pins)) if pins
           else tr("Layout reset"))
        return

    if _reset_layout_builtin():
        edition_state_file(HOME).unlink(missing_ok=True)
        if _restore_pins(pins, DEFAULT_TASKS_ID):
            ok(tr("Layout reset (kept {count} pinned apps)", count=len(pins)) if pins
               else tr("Layout reset"))
        else:
            warn(tr('Layout reset, but pinned applications could not be restored'))
        return
    if _layout_looks_reset():
        warn(tr('Layout reset fallback was not confirmed; pinned applications may need to be restored manually'))
        return
    warn(tr('layout reset failed'))
