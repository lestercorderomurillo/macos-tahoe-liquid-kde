import re
import subprocess
import time

from steps._helpers import HOME, fail, have, ok, offline, qdbus_call, warn
from utils import qdbus_cmd

LAYOUT_SCRIPT = offline("layouts/mac-tahoe.js")
LAYOUT_RESET = offline("layouts/default.js")
COLORIZER_DIR = HOME / ".local/share/plasma/plasmoids/luisbocanegra.panel.colorizer"


def deps():
    return ["qdbus6:qt6-tools"]


def _ensure_panel_colorizer() -> None:
    if COLORIZER_DIR.is_dir():
        ok("Panel Colorizer")
        return
    warn("Panel Colorizer not found — installing...")
    if have("kpackagetool6"):
        for args in (
            ["-i", "https://store.kde.org/p/2130967", "-t", "Plasma/Applet"],
            ["--install", "luisbocanegra.panel.colorizer", "-t", "Plasma/Applet"],
        ):
            if subprocess.run(["kpackagetool6", *args], check=False,
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0:
                break
    if not COLORIZER_DIR.is_dir():
        for pm in ("paru", "yay"):
            if have(pm):
                subprocess.run(
                    [pm, "-S", "--noconfirm", "plasma6-applets-panel-colorizer"],
                    check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                break
    if COLORIZER_DIR.is_dir():
        ok("Panel Colorizer (installed)")
    else:
        warn("Panel Colorizer not installed — top bar won't be transparent. "
             "Install manually from KDE Store.")


def _evaluate_layout(script_path) -> bool:
    q = qdbus_cmd()
    if q is None:
        warn("qdbus not found — layout not installed")
        return False
    script = script_path.read_text()
    # plasmashell may still be restarting from the apply step — retry a few times.
    for _ in range(5):
        if subprocess.run(
            [q, "org.kde.plasmashell", "/PlasmaShell",
             "org.kde.PlasmaShell.evaluateScript", script],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0:
            return True
        time.sleep(3)
    return False


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
    if not LAYOUT_SCRIPT.is_file():
        warn("Layout script not found — skipping")
        return
    if _evaluate_layout(LAYOUT_SCRIPT):
        ok("Layout installed")
    else:
        warn("layout failed — set layout manually")
    time.sleep(3)
    _patch_plasmashellrc()


def uninstall() -> None:
    if not LAYOUT_RESET.is_file():
        return
    if _evaluate_layout(LAYOUT_RESET):
        ok("Layout reset")
    else:
        warn("layout reset failed")
