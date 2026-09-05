"""Opt-in OLED-care pixel-shift service (binary + systemd user units).
install() reads the ``oled_care`` flag itself: a disabled run tears down
whatever a previous flagged install left, so a plain re-run is self-healing.
"""

import os
import re
import shutil
import subprocess

from paths import REPO_ROOT
from distro import user_service_manager_command
from steps._helpers import HOME, fail, feat_enabled, info, ok, offline, warn
from steps._scheduler import (
    RemovalStatus, install_periodic, is_systemd, remove_periodic,
)
from utils import run_user

# crontab tag identifying our managed line on OpenRC hosts.
CRON_TAG = "oled"

DEFAULT_INTERVAL_MINUTES = 5

BIN_DEST = HOME / ".local/bin/mac-tahoe-oled-care"
SVC_DIR = HOME / ".config/systemd/user"
PY_SRC = REPO_ROOT / "src/scripts/oled_care.py"

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


def _state_file():
    """Use the runtime helper's XDG-aware recovery path as source of truth."""
    import oled_care
    return oled_care._state_file()


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


def _user_service(*args: str) -> bool:
    command = user_service_manager_command(*args)
    if command is None:
        return False
    try:
        return run_user(
            command, check=False, timeout=10,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _teardown_units() -> tuple[bool, bool]:
    """Remove whatever backend a previous flagged install left — systemd
    units and/or the OpenRC cron line. Both are attempted regardless of
    the current init so a host that switched inits still cleans up fully.

    Return ``(removed_anything, complete)``. A failed scheduler stop must not
    be mistaken for an already-clean state while panel recovery is pending.
    """
    removed = False
    complete = True
    systemd = is_systemd()
    had_unit_files = False
    for unit in UNITS:
        unit_path = SVC_DIR / unit
        existed = unit_path.exists() or unit_path.is_symlink()
        had_unit_files = had_unit_files or existed
        stopped = _user_service("disable", "--now", unit)
        if systemd and existed and not stopped:
            complete = False
        try:
            unit_path.unlink()
            removed = True
        except FileNotFoundError:
            pass
        except OSError:
            if existed:
                complete = False
    if systemd and had_unit_files and not _user_service("daemon-reload"):
        complete = False

    cron_status = remove_periodic(CRON_TAG)
    if cron_status == RemovalStatus.REMOVED:
        removed = True
    elif cron_status == RemovalStatus.ERROR or (
            cron_status == RemovalStatus.UNAVAILABLE and not systemd):
        complete = False
        warn("OLED care: previous cron schedule could not be removed")
    return removed, complete


def _remove_helper() -> tuple[bool, bool]:
    existed = BIN_DEST.exists() or BIN_DEST.is_symlink()
    try:
        BIN_DEST.unlink()
        return True, True
    except FileNotFoundError:
        return False, True
    except OSError as exc:
        if existed:
            warn(f"OLED care: helper could not be removed ({exc})")
            return False, False
        return False, True


def _schedule_systemd(interval: int, max_px: int) -> bool:
    SVC_DIR.mkdir(parents=True, exist_ok=True)
    _write_units(interval, max_px)
    results = [
        _user_service("daemon-reload"),
        _user_service("enable", *UNITS),
    ]
    # Restart only the timer (also picks up a changed interval); the service
    # fires on its first boundary so the install's Plasma restart isn't raced.
    results.append(
        _user_service("restart", "mac-tahoe-liquid-kde-oled.timer"))
    scheduled = all(results)
    if scheduled:
        info(f"Panels pixel-shift up to {max_px} px every {interval} min "
             "(systemd user timer)")
    return scheduled


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


def _restore_panels() -> bool:
    """Put panel geometry back before the service goes away. In-process
    import — the installed binary may already be gone (or never existed)."""
    state_file = _state_file()
    if not state_file.is_file():
        return True
    try:
        import oled_care
        restored = oled_care.restore() == 0
    except Exception as exc:
        warn(f"OLED care: panel geometry restore failed ({exc})")
        return False
    if not restored or state_file.exists():
        warn("OLED care: panel geometry not restored — recovery state "
             "retained for retry")
        return False
    return True


def install() -> None:
    if not feat_enabled("oled_care", default=False):
        # Stop the timer BEFORE restoring geometry — a fire landing in
        # between would re-shift the panels we just put back.
        removed, schedule_stopped = _teardown_units()
        helper_removed, helper_neutralized = _remove_helper()
        removed = removed or helper_removed
        # If scheduler teardown was uncertain, removing its command target is
        # an equally strong stop before restoring geometry. If neither action
        # succeeded, leave recovery state untouched to avoid a re-shift race.
        if not schedule_stopped and not helper_neutralized:
            fail("OLED care removal incomplete — active scheduling could not "
                 "be neutralized")
            info("OLED care panel recovery is pending")
            return
        restored = _restore_panels()
        if removed:
            ok("Previous OLED care service removed")
        if not schedule_stopped or not helper_neutralized or not restored:
            fail("OLED care removal incomplete — restore panel geometry "
                 "after logging in, then retry")
            pending = "panel recovery is pending" if not restored else \
                "scheduler cleanup must be retried"
            info(f"OLED care disabled; {pending}")
            return
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
    # Clean whichever backend a previous boot used, then install exactly one
    # active scheduler for the init system detected by the distro layer.
    _removed, teardown_complete = _teardown_units()
    if not teardown_complete:
        _remove_helper()
        fail("OLED care not installed — previous scheduling could not be "
             "removed safely")
        return
    if is_systemd():
        if not _schedule_systemd(interval, max_px):
            warn("OLED care: systemd user timer could not be enabled")
    else:
        _schedule_cron(interval, max_px)

    ok("OLED care service installed")


def uninstall() -> None:
    # Same order as the disabled-install path: timer first, then restore.
    removed, schedule_stopped = _teardown_units()
    helper_removed, helper_neutralized = _remove_helper()
    removed = removed or helper_removed
    if not schedule_stopped and not helper_neutralized:
        fail("OLED care removal incomplete — active scheduling could not be "
             "neutralized")
        info("OLED care panel recovery is pending")
        return
    restored = _restore_panels()
    if not schedule_stopped or not helper_neutralized or not restored:
        fail("OLED care removal incomplete — restore panel geometry after "
             "logging in, then retry")
        pending = "panel recovery is pending" if not restored else \
            "scheduler cleanup must be retried"
        info(f"OLED care disabled; {pending}")
        return
    if removed:
        ok("OLED care service removed")
    else:
        info("OLED care was not installed")
