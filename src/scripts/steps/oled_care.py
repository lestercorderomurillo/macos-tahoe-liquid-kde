"""Installer step: opt-in OLED-care pixel-shift service (binary + timer).

Runs unconditionally from the install/uninstall flow (like the theme
switcher). ``install()`` reads the ``oled_care`` flag itself: enabled
installs the binary + systemd user units; disabled tears down whatever
a previous flagged install left behind, so a plain re-run without the
flag is self-healing.
"""

import os
import re
import shutil
import subprocess

from paths import REPO_ROOT
from steps._helpers import HOME, feat_enabled, info, ok, offline, warn
from utils import run_user

DEFAULT_INTERVAL_MINUTES = 5

BIN_DEST = HOME / ".local/bin/mac-tahoe-oled-care"
SVC_DIR = HOME / ".config/systemd/user"
PY_SRC = REPO_ROOT / "src/scripts/oled_care.py"
STATE_FILE = HOME / ".local/state/mac-tahoe-liquid-kde/oled-care.json"

UNITS = (
    "mac-tahoe-liquid-kde-oled.service",
    "mac-tahoe-liquid-kde-oled.timer",
)


def _interval_minutes() -> int:
    try:
        n = int(os.environ.get("OLED_INTERVAL", ""))
    except ValueError:
        return DEFAULT_INTERVAL_MINUTES
    return max(1, min(59, n))


def _max_shift_px() -> int:
    import oled_care
    return oled_care.clamp_max_px(os.environ.get("OLED_MAX_SHIFT"))


def _write_units(interval: int, max_px: int) -> None:
    """Copy the unit templates, stamping the configured cadence into the
    timer and the configured amplitude into the service's ExecStart."""
    for unit in UNITS:
        src = offline(unit)
        if not src.is_file():
            continue
        text = src.read_text(encoding="utf-8")
        if unit.endswith(".timer"):
            text = re.sub(r"(?m)^OnCalendar=.*$",
                          f"OnCalendar=*:0/{interval}", text)
        else:
            text = re.sub(r"(?m)^ExecStart=(.+)$",
                          rf"ExecStart=\1 --max-px {max_px}", text)
        (SVC_DIR / unit).write_text(text, encoding="utf-8")


def _systemctl(*args: str) -> None:
    run_user(["systemctl", "--user", *args],
             check=False,
             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _teardown_units() -> bool:
    removed = False
    for unit in UNITS:
        _systemctl("disable", "--now", unit)
        try:
            (SVC_DIR / unit).unlink()
            removed = True
        except FileNotFoundError:
            pass
        except OSError:
            pass
    _systemctl("daemon-reload")
    return removed


def _restore_panels() -> None:
    """Put panel geometry back before the service goes away. In-process
    import — the installed binary may already be gone (or never existed)."""
    if not STATE_FILE.is_file():
        return
    try:
        import oled_care
        oled_care.restore()
    except Exception:
        pass
    try:
        STATE_FILE.unlink()
    except OSError:
        pass


def install() -> None:
    if not feat_enabled("oled_care", default=False):
        _restore_panels()
        removed = _teardown_units()
        try:
            BIN_DEST.unlink()
            removed = True
        except OSError:
            pass
        if removed:
            ok("Previous OLED care service removed")
        info("OLED care disabled — enable with --oled-care")
        return

    BIN_DEST.parent.mkdir(parents=True, exist_ok=True)
    if not PY_SRC.is_file():
        warn("OLED care script missing — skipping")
        return
    shutil.copy2(PY_SRC, BIN_DEST)
    BIN_DEST.chmod(0o755)

    interval = _interval_minutes()
    max_px = _max_shift_px()
    SVC_DIR.mkdir(parents=True, exist_ok=True)
    _write_units(interval, max_px)
    _systemctl("daemon-reload")
    _systemctl("enable", *UNITS)
    # Only the timer starts (restart also picks up a changed interval);
    # the service fires on its first boundary so the install's own
    # Plasma restart isn't raced.
    _systemctl("restart", "mac-tahoe-liquid-kde-oled.timer")

    ok("OLED care service installed")
    info(f"Panels pixel-shift up to {max_px} px every {interval} min "
         "(systemd user timer)")


def uninstall() -> None:
    _restore_panels()
    removed = _teardown_units()
    try:
        BIN_DEST.unlink()
        removed = True
    except OSError:
        pass
    if removed:
        ok("OLED care service removed")
    else:
        info("OLED care was not installed")
