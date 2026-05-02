import os
import shutil
import subprocess

from steps._helpers import (
    HOME, fail, have, kw_write, offline, ok, reinstall,
)
from utils import run_user

DEST_DIR = HOME / ".config/Kvantum/mac-tahoe-liquid-kde"


def deps():
    return ["kvantummanager:kvantum"]


def install() -> None:
    src = offline("kvantum/mac-tahoe-liquid-kde")
    if not src.is_dir():
        fail(f"Kvantum theme source not found at {src}")
        return

    existed = DEST_DIR.is_dir() and any(DEST_DIR.glob("*.kvconfig"))
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    for pat in ("*.kvconfig", "*.svg"):
        for f in src.glob(pat):
            shutil.copy2(f, DEST_DIR / f.name)

    if any(DEST_DIR.glob("*.kvconfig")):
        if existed:
            reinstall("mac-tahoe-liquid-kde theme")
        else:
            ok("mac-tahoe-liquid-kde theme (installed)")
    else:
        fail("mac-tahoe-liquid-kde theme (copy failed)")
        return

    if kw_write("--file", "kdeglobals", "--group", "KDE",
                "--key", "widgetStyle", "kvantum"):
        ok("Widget style installed")


def uninstall() -> None:
    if not DEST_DIR.is_dir():
        ok("MacTahoeLiquidKde theme (not installed)")
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
    try:
        shutil.rmtree(DEST_DIR)
        ok("MacTahoeLiquidKde theme removed")
    except OSError:
        fail("MacTahoeLiquidKde theme")
