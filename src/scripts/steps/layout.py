import re
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

from steps._helpers import HOME, fail, have, install_tree, ok, offline, qdbus_call, warn
from utils import qdbus_cmd, run_user

LAYOUT_SCRIPT = offline("layouts/mac-tahoe.js")
LAYOUT_RESET = offline("layouts/default.js")
COLORIZER_ID = "luisbocanegra.panel.colorizer"
COLORIZER_RELEASE_URL = (
    "https://github.com/luisbocanegra/plasma-panel-colorizer/"
    "archive/refs/tags/v7.0.1.tar.gz"
)


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


def _install_panel_colorizer_from_release() -> bool:
    dest = HOME / ".local/share/plasma/plasmoids" / COLORIZER_ID
    with tempfile.TemporaryDirectory(prefix="mttkde-colorizer-") as tmpdir:
        archive = Path(tmpdir) / "colorizer.tar.gz"
        try:
            with urllib.request.urlopen(COLORIZER_RELEASE_URL, timeout=30) as resp:
                archive.write_bytes(resp.read())
        except OSError:
            return False
        try:
            with tarfile.open(archive, "r:gz") as tf:
                tf.extractall(tmpdir, filter="data")
        except (tarfile.TarError, OSError):
            return False
        package_dirs = list(Path(tmpdir).glob("*/package"))
        if not package_dirs:
            return False
        package_dir = package_dirs[0]
        metadata = package_dir / "metadata.json"
        contents = package_dir / "contents"
        if not metadata.is_file() or not contents.is_dir():
            return False
        return install_tree(package_dir, dest, "Panel Colorizer")


def deps():
    return ["qdbus6:qt6-tools"]


def _ensure_panel_colorizer() -> None:
    if _has_panel_colorizer():
        ok("Panel Colorizer")
        return
    warn("Panel Colorizer not found — installing...")
    if have("kpackagetool6"):
        for args in (
            ["-i", "https://store.kde.org/p/2130967", "-t", "Plasma/Applet"],
            ["--install", COLORIZER_ID, "-t", "Plasma/Applet"],
        ):
            if run_user(["kpackagetool6", *args], check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL).returncode == 0:
                break
    if not _has_panel_colorizer():
        for pm in ("paru", "yay"):
            if have(pm):
                run_user(
                    [pm, "-S", "--noconfirm", "plasma6-applets-panel-colorizer"],
                    check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                break
    if not _has_panel_colorizer():
        _install_panel_colorizer_from_release()
    if _has_panel_colorizer():
        ok("Panel Colorizer (installed)")
    else:
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


def _evaluate_layout(script_path) -> bool:
    return _evaluate_layout_script(script_path.read_text())


def _capture_pinned_launchers() -> list[str]:
    """User-pinned taskbar launchers from appletsrc, deduped in order.
    Our own MacTahoe plasmoids are dropped so a reinstall doesn't double
    them; preferred:// and applications: entries are kept."""
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
        # Append a restore block: find the icontasks the reset just added
        # and write the captured launchers onto it.
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


def _layout_looks_reset() -> bool:
    """Layout is 'reset' when our custom widgets are gone from
    appletsrc. We don't require the full default Breeze panel needles
    to be present — plasma-apply-lookandfeel may write the layout
    asynchronously and the final plasmashell restart picks up the
    rest. The thing that actually matters here is: no MacTahoe-specific
    plugin IDs left behind to fail loading on next start."""
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


# Plasma's JS scripting API doesn't expose panelOpacity / floatingApplets,
# so the layout JS can't set them. Patch them into plasmashellrc directly
# after the layout runs.
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
    if _layout_looks_installed():
        ok("Layout installed")
        _patch_plasmashellrc()
        return
    if not LAYOUT_SCRIPT.is_file():
        warn("Layout script not found — skipping")
        return
    applied = _evaluate_layout(LAYOUT_SCRIPT)
    if applied and _wait_for_layout_install():
        ok("Layout installed")
    else:
        warn("layout failed — set layout manually")
        return
    time.sleep(3)
    _patch_plasmashellrc()


def is_installed() -> bool:
    return _layout_looks_installed()


def uninstall() -> None:
    if _layout_looks_reset():
        ok("Layout reset")
        return

    # Capture the user's pinned taskbar apps before any reset wipes them,
    # then restore them onto the default panel. --resetLayout / default.js
    # rebuild the panel from scratch, so without this the pins are lost.
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
