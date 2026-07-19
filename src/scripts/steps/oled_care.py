"""Opt-in OLED-care pixel-shift service (binary + systemd user units).
install() reads the ``oled_care`` flag itself: a disabled run tears down
whatever a previous flagged install left, so a plain re-run is self-healing.
"""

import os
import re
import shutil
import subprocess

from paths import REPO_ROOT
from steps._helpers import HOME, feat_enabled, info, ok, offline, warn
from steps._scheduler import install_periodic, is_systemd, remove_periodic
from utils import run_user

# crontab tag identifying our managed line on OpenRC hosts.
CRON_TAG = "oled"

DEFAULT_INTERVAL_MINUTES = 5

BIN_DEST = HOME / ".local/bin/mac-tahoe-oled-care"
SVC_DIR = HOME / ".config/systemd/user"
PY_SRC = REPO_ROOT / "src/scripts/oled_care.py"
STATE_FILE = HOME / ".local/state/mac-tahoe-liquid-kde/oled-care.json"

UNITS = (
    "mac-tahoe-liquid-kde-oled.service",
    "mac-tahoe-liquid-kde-oled.timer",
)


def deps():
    # crontab is only needed on OpenRC, where the timer falls back to a
    # per-user cron line. systemd hosts schedule via the user manager and
    # need nothing extra. The flag gates it further — no --oled-care, no dep.
    if is_systemd() or not feat_enabled("oled_care", default=False):
        return []
    return ["crontab"]


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
    """Remove whatever backend a previous flagged install left — systemd
    units and/or the OpenRC cron line. Both are attempted regardless of
    the current init so a host that switched inits still cleans up fully."""
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
    if remove_periodic(CRON_TAG):
        removed = True
    return removed


def _schedule_systemd(interval: int, max_px: int) -> None:
    SVC_DIR.mkdir(parents=True, exist_ok=True)
    _write_units(interval, max_px)
    _systemctl("daemon-reload")
    _systemctl("enable", *UNITS)
    # Restart only the timer (also picks up a changed interval); the service
    # fires on its first boundary so the install's Plasma restart isn't raced.
    _systemctl("restart", "mac-tahoe-liquid-kde-oled.timer")
    info(f"Panels pixel-shift up to {max_px} px every {interval} min "
         "(systemd user timer)")


def _schedule_cron(interval: int, max_px: int) -> None:
    # OpenRC: no systemd user timer. The shift binary recovers the desktop
    # session env itself (see oled_care._sync_session_env), so a bare cron
    # environment still reaches plasmashell.
    command = f"{BIN_DEST} shift --max-px {max_px}"
    if not install_periodic(CRON_TAG, interval, command):
        warn("OLED care: crontab write failed — is a cron daemon installed?")
        return
    info(f"Panels pixel-shift up to {max_px} px every {interval} min "
         "(user crontab)")


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
        # Stop the timer BEFORE restoring geometry — a fire landing in
        # between would re-shift the panels we just put back.
        removed = _teardown_units()
        _restore_panels()
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
    if is_systemd():
        _schedule_systemd(interval, max_px)
    else:
        _schedule_cron(interval, max_px)

    ok("OLED care service installed")


def uninstall() -> None:
    # Same order as the disabled-install path: timer first, then restore.
    removed = _teardown_units()
    _restore_panels()
    try:
        BIN_DEST.unlink()
        removed = True
    except OSError:
        pass
    if removed:
        ok("OLED care service removed")
    else:
        info("OLED care was not installed")
