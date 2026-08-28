import json
import re
import subprocess
import time
from pathlib import Path

from steps._helpers import (
    DATA_HOME, HOME, have, install_tree, ok, offline, qdbus_call, warn,
)
from utils import qdbus_cmd, run_user

LAYOUT_SCRIPT = offline("layouts/mac-tahoe.js")
LAYOUT_RESET = offline("layouts/default.js")
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
        warn("Panel Colorizer not installed — bundled metadata is invalid.")
        return

    dirs = _colorizer_dirs()
    dest = dirs[0]
    user_version = _colorizer_version(dest)
    if user_version is not None and user_version >= bundled_version:
        ok("Panel Colorizer")
        return

    if user_version is None and not dest.exists():
        for path in dirs[1:]:
            installed_version = _colorizer_version(path)
            if (
                installed_version is not None
                and installed_version >= bundled_version
            ):
                ok("Panel Colorizer")
                return

    if install_tree(COLORIZER_SRC, dest, "Panel Colorizer"):
        return
    warn("Panel Colorizer not installed — top bar won't be transparent. "
         "Install manually from KDE Store.")


def _evaluate_layout_script(script: str) -> bool:
    if qdbus_cmd() is None:
        warn("qdbus not found — layout not installed")
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
            if entry and "mac.tahoe" not in entry and "mac-tahoe" not in entry:
                if entry not in seen:
                    seen.append(entry)
    return seen


def _append_launcher_restore(
        script: str, pins: list[str], widget_type: str) -> str:
    if pins:
        joined = repr(",".join(pins))
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
    if not _discover_is_installed():
        script = script.replace(_DISCOVER_DESKTOP + ",", "")
        script = script.replace("," + _DISCOVER_DESKTOP, "")
    return _append_launcher_restore(script, pins, widget_type)


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
    return all(needle in text for needle in _CUSTOM_PANEL_NEEDLES)


def _wait_for_layout_install(timeout_seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _layout_looks_installed():
            return True
        time.sleep(0.2)
    return _layout_looks_installed()


# Plasma's JS API doesn't expose panelOpacity / floatingApplets, so they
# are patched into plasmashellrc directly after the layout runs.
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
        ok("Panel glass forced translucent")


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
    _ensure_panel_colorizer()
    if not LAYOUT_SCRIPT.is_file():
        warn("Layout script not found — skipping")
        return
    pins = _capture_pinned_launchers()
    applied = _evaluate_layout_with_launchers(
        LAYOUT_SCRIPT, pins, MAC_TASKS_ID,
    )
    if applied and _wait_for_layout_install():
        _mark_layout_installed()
        ok(f"Layout installed (kept {len(pins)} pinned app(s))" if pins
           else "Layout installed")
    else:
        warn("layout failed — set layout manually")
        return
    time.sleep(3)
    _patch_plasmashellrc()


def is_installed() -> bool:
    return _layout_marker().is_file() or _layout_looks_installed()


def uninstall() -> None:
    has_theme_widgets = _layout_has_any_theme_widget()
    _clear_layout_marker()
    if _reset_plasmashellrc():
        ok("Panel transparency reset")
    if not has_theme_widgets:
        ok("Layout already clean")
        return
    # Always remove the Mac top bar and Dock. Preserve only the applications
    # the user pinned; Launcher and Trash are widgets and disappear with Dock.
    pins = _capture_pinned_launchers()
    if _reset_with_pins(pins):
        ok(f"Layout reset (kept {len(pins)} pinned app(s))" if pins
           else "Layout reset")
        return

    if _reset_layout_builtin():
        if _restore_pins(pins, DEFAULT_TASKS_ID):
            ok(f"Layout reset (kept {len(pins)} pinned app(s))" if pins
               else "Layout reset")
        else:
            warn("Layout reset, but pinned applications could not be restored")
        return
    if _layout_looks_reset():
        warn("Layout reset fallback was not confirmed; pinned applications "
             "may need to be restored manually")
        return
    warn("layout reset failed")
