import os
import shutil
import subprocess

from steps._helpers import (
    HOME, fail, have, kw_write, offline, ok, reinstall, warn,
)
from utils import run_user

DEST_DIR = HOME / ".config/Kvantum/mac-tahoe-liquid-kde"
DEST_DIR_DARK = HOME / ".config/Kvantum/mac-tahoe-liquid-kdeDark"

_THEMES = ("mac-tahoe-liquid-kde", "mac-tahoe-liquid-kdeDark")


def deps():
    return ["kvantummanager:kvantum"]


def _install_one(name: str) -> None:
    src = offline("kvantum/mac-tahoe-liquid-kde")
    dst = (DEST_DIR_DARK if "Dark" in name else DEST_DIR)
    dst.mkdir(parents=True, exist_ok=True)
    for ext in (".kvconfig", ".svg"):
        f = src / f"{name}{ext}"
        if f.is_file():
            shutil.copy2(f, dst / f.name)
        else:
            warn(f"Kvantum file {f.name} not found")


def install() -> None:
    src = offline("kvantum/mac-tahoe-liquid-kde")
    if not src.is_dir():
        fail(f"Kvantum theme source not found at {src}")
        return

    existed = any(
        (d.is_dir() and any(d.glob("*.kvconfig")))
         for d in (DEST_DIR, DEST_DIR_DARK)
    )

    for name in _THEMES:
        _install_one(name)

    if any((DEST_DIR / f"{_THEMES[0]}{e}").is_file() for e in (".kvconfig", ".svg")):
        ok("mac-tahoe-liquid-kde theme (installed)")
    else:
        fail("mac-tahoe-liquid-kde theme (copy failed)")
        return

    if any((DEST_DIR_DARK / f"{_THEMES[1]}{e}").is_file() for e in (".kvconfig", ".svg")):
        if existed:
            reinstall("mac-tahoe-liquid-kdeDark theme")
        else:
            ok("mac-tahoe-liquid-kdeDark theme (installed)")
    else:
        fail("mac-tahoe-liquid-kdeDark theme (copy failed)")
        return

    if kw_write("--file", "kdeglobals", "--group", "KDE",
                "--key", "widgetStyle", "kvantum"):
        ok("Widget style installed")
    else:
        warn("Widget style not applied — kwriteconfig6 unavailable "
             "(install plasma-workspace or your distro's equivalent)")


def uninstall() -> None:
    any_was_installed = False
    for d in (DEST_DIR, DEST_DIR_DARK):
        if d.is_dir():
            any_was_installed = True
    if not any_was_installed:
        ok("MacTahoeLiquidKde themes (not installed)")
        return

    if kw_write("--file", "kdeglobals", "--group", "KDE",
                "--key", "widgetStyle", "Breeze"):
        ok("Widget style reset to Breeze")
    if have("kvantummanager"):
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        run_user(
            ["kvantummanager", "--set", "Default"],
            check=False, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    for d in (DEST_DIR, DEST_DIR_DARK):
        try:
            shutil.rmtree(d)
        except OSError:
            pass
    if any(d.is_dir() for d in (DEST_DIR, DEST_DIR_DARK)):
        fail("MacTahoeLiquidKde themes (some leftovers)")
    else:
        ok("MacTahoeLiquidKde themes removed")
