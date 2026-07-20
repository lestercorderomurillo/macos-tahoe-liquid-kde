import os
import re
import subprocess
import time
from pathlib import Path

from steps._helpers import HOME, have, install_tree, ok, offline, qdbus_call, warn
from utils import qdbus_cmd, run_user

LAYOUT_SCRIPT = offline("layouts/mac-tahoe.js")
LAYOUT_RESET = offline("layouts/default.js")
_DISCOVER_DESKTOP = "applications:org.kde.discover.desktop"
COLORIZER_ID = "luisbocanegra.panel.colorizer"
COLORIZER_SRC = offline("plasmoids") / COLORIZER_ID


def _colorizer_dirs() -> list[Path]:
    dirs = [HOME / ".local/share/plasma/plasmoids" / COLORIZER_ID]
    for base in ("/usr/local/share", "/usr/share"):
        dirs.append(Path(base) / "plasma/plasmoids" / COLORIZER_ID)
    return dirs


def _has_panel_colorizer() -> bool:
    for path in _colorizer_dirs():
        metadata = path / "metadata.json"
        if path.is_dir() and metadata.is_file():
            return True
    return False


def deps():
    return ["qdbus6:qt6-tools"]


def _ensure_panel_colorizer() -> None:
    # Bundled offline like every other asset — a copy already
    # present system-wide or user-side is left untouched.
    if _has_panel_colorizer():
        ok("Panel Colorizer")
        return
    dest = HOME / ".local/share/plasma/plasmoids" / COLORIZER_ID
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
    for prefix in (HOME / ".local/share", Path("/usr/local/share"), Path("/usr/share")):
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


def _reset_with_pins(pins: list[str]) -> bool:
    """Run the default-layout reset, then pin the user's launchers onto the
    fresh icontasks so they survive --resetLayout's panel rebuild."""
    if not LAYOUT_RESET.is_file():
        return False
    script = LAYOUT_RESET.read_text()
    if pins:
        joined = ",".join(pins)
        # Restore block: write the captured launchers onto the fresh icontasks.
        script += (
            "\n(function () {\n"
            "  var ps = panels();\n"
            "  for (var i = 0; i < ps.length; i++) {\n"
            "    var ws = ps[i].widgetIds;\n"
            "    for (var j = 0; j < ws.length; j++) {\n"
            "      var w = ps[i].widgetById(ws[j]);\n"
            "      if (w && w.type === 'org.kde.plasma.icontasks') {\n"
            "        w.currentConfigGroup = ['General'];\n"
            f"        w.writeConfig('launchers', '{joined}');\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "})();\n"
        )
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
    return any(needle in text for needle in _CUSTOM_PANEL_NEEDLES)


def _preserve_existing_layout() -> bool:
    if os.environ.get("MTTKDE_RESET_LAYOUT", "").lower() == "true":
        return False
    if _layout_marker().is_file() or _layout_has_any_theme_widget():
        return True
    return os.environ.get("MTTKDE_EXISTING_INSTALL", "").lower() == "true"


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
    return not any(needle in text for needle in _CUSTOM_PANEL_NEEDLES)


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
        if "floating=1" in section:
            if "panelOpacity=" in section:
                section = re.sub(r"panelOpacity=\d+", "panelOpacity=2", section)
            else:
                section = section.rstrip() + "\npanelOpacity=2\n"
        if "floating=0" in section:
            if "floatingApplets=" in section:
                section = re.sub(r"floatingApplets=\d+", "floatingApplets=1", section)
            else:
                section = section.rstrip() + "\nfloatingApplets=1\n"
        return section

    new_text = _PRC_PANEL_RE.sub(fix, text)
    if new_text != text:
        prc.write_text(new_text)
        ok("Dock installed")


def install() -> None:
    _ensure_panel_colorizer()
    if _preserve_existing_layout():
        _mark_layout_installed()
        ok("Layout preserved")
        _patch_plasmashellrc()
        return
    if not LAYOUT_SCRIPT.is_file():
        warn("Layout script not found — skipping")
        return
    applied = _evaluate_layout(LAYOUT_SCRIPT)
    if applied and _wait_for_layout_install():
        _mark_layout_installed()
        ok("Layout installed")
    else:
        warn("layout failed — set layout manually")
        return
    time.sleep(3)
    _patch_plasmashellrc()


def is_installed() -> bool:
    return _layout_marker().is_file() or _layout_looks_installed()


def uninstall() -> None:
    _clear_layout_marker()
    if _layout_looks_reset():
        ok("Layout reset")
        return

    # --resetLayout / default.js rebuild the panel from scratch — capture
    # the user's pinned apps first or they're lost.
    pins = _capture_pinned_launchers()
    if _reset_with_pins(pins):
        ok(f"Layout reset (kept {len(pins)} pinned app(s))" if pins
           else "Layout reset")
        return

    if _reset_layout_builtin():
        ok("Layout reset")
        return
    if _layout_looks_reset():
        ok("Layout reset")
        return
    if LAYOUT_RESET.is_file() and _evaluate_layout(LAYOUT_RESET):
        ok("Layout reset")
        return
    if _layout_looks_reset():
        ok("Layout reset")
        return
    warn("layout reset failed")
