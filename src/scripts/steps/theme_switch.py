"""Installer step: copy the Python theme-switch + systemd units into ~/.local."""

import shutil
import subprocess
from pathlib import Path

from paths import REPO_ROOT
from steps._helpers import HOME, kw_write, ok, offline, theme_mode, warn
from steps._scheduler import install_at_times, is_systemd, remove_periodic
from utils import run_user

BIN_DEST = HOME / ".local/bin/mac-tahoe-theme-switch"
SVC_DIR = HOME / ".config/systemd/user"
PY_SRC = REPO_ROOT / "src/scripts/theme_switch.py"

# XDG autostart launcher for the portal watcher that makes GTK apps follow the
# NATIVE light/dark toggle. Init-agnostic: Plasma runs ~/.config/autostart/*
# on both systemd and OpenRC sessions, so this is the one piece that works the
# same on Gentoo/OpenRC as on systemd (#46).
AUTOSTART_DIR = HOME / ".config/autostart"
GTK_SYNC_DESKTOP = "mac-tahoe-liquid-kde-gtk-sync.desktop"

# --auto only: oneshot service (fires 10s after plasmashell) + 06:00/18:00
# timer. --light/--dark pin the mode, so nothing is scheduled.
UNITS = (
    "mac-tahoe-liquid-kde-theme.service",
    "mac-tahoe-liquid-kde-theme.timer",
)

# crontab tag + fire times for the OpenRC backend, matching the systemd
# timer's OnCalendar (06:00 light, 18:00 dark). The binary derives the
# mode from the wall clock, so both fires run the same `auto` command.
CRON_TAG = "theme"
CRON_TIMES = [(6, 0), (18, 0)]


def deps():
    # OpenRC + auto mode needs crontab for the timed flip; systemd and
    # pinned modes need nothing extra.
    if is_systemd() or theme_mode() != "auto":
        return []
    return ["crontab"]


def _install_units() -> None:
    for u in UNITS:
        src = offline(u)
        if src.is_file():
            shutil.copy2(src, SVC_DIR / u)
    run_user(["systemctl", "--user", "daemon-reload"],
             check=False,
             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for verb in ("enable", "start"):
        run_user(
            ["systemctl", "--user", verb, *UNITS],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )


def _teardown_units() -> None:
    for unit in UNITS:
        run_user(
            ["systemctl", "--user", "disable", "--now", unit],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try: (SVC_DIR / unit).unlink()
        except FileNotFoundError: pass
        except OSError: pass
    run_user(["systemctl", "--user", "daemon-reload"],
             check=False,
             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _install_gtk_sync_autostart() -> None:
    """Drop the portal-watcher autostart .desktop so GTK apps follow the
    native light/dark toggle. Works on systemd and OpenRC alike — it's plain
    XDG autostart, not a systemd unit."""
    src = offline("autostart", GTK_SYNC_DESKTOP)
    if not src.is_file():
        return
    AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, AUTOSTART_DIR / GTK_SYNC_DESKTOP)


def _teardown_gtk_sync_autostart() -> None:
    try: (AUTOSTART_DIR / GTK_SYNC_DESKTOP).unlink()
    except FileNotFoundError: pass
    except OSError: pass


def install() -> None:
    BIN_DEST.parent.mkdir(parents=True, exist_ok=True)
    if PY_SRC.is_file():
        shutil.copy2(PY_SRC, BIN_DEST)
        BIN_DEST.chmod(0o755)
    SVC_DIR.mkdir(parents=True, exist_ok=True)
    # The GTK-follows-native-toggle watcher is useful in every mode (pinned or
    # auto): the user can still flip light/dark from System Settings.
    _install_gtk_sync_autostart()

    auto = theme_mode() == "auto"

    if auto:
        if is_systemd():
            _install_units()
        else:
            # OpenRC: fixed-time cron lines at 06:00/18:00. There is no
            # login-time oneshot equivalent, but the binary is idempotent
            # and the timed flips are what matter.
            if not install_at_times(CRON_TAG, CRON_TIMES, f"{BIN_DEST} auto"):
                warn("Theme switch: crontab write failed — "
                     "is a cron daemon installed?")
    else:
        # Pinned --light/--dark: tear down any schedule a previous --auto
        # install left so it can't fight the pinned mode at next login.
        _teardown_units()
        remove_periodic(CRON_TAG)

    if BIN_DEST.is_file() and BIN_DEST.stat().st_mode & 0o111:
        ok("Theme switcher installed")
    else:
        warn("Theme switcher not installed")


_LEGACY_BIN = HOME / ".local/bin/mactahoe-theme-switch"


def uninstall() -> None:
    # Include legacy unit names from earlier versions so an upgrade-then-
    # uninstall doesn't leave orphaned systemd files behind.
    legacy_units = (
        *UNITS,
        "mac-tahoe-liquid-kde-theme-apply.service",
        "mactahoe-theme-watcher.service",
    )
    for unit in legacy_units:
        run_user(
            ["systemctl", "--user", "disable", "--now", unit],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try: (SVC_DIR / unit).unlink()
        except FileNotFoundError: pass
        except OSError: pass
    run_user(["systemctl", "--user", "daemon-reload"],
             check=False,
             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Strip the OpenRC cron line too, so an uninstall on either init leaves
    # no orphaned schedule behind.
    remove_periodic(CRON_TAG)
    _teardown_gtk_sync_autostart()
    for p in (BIN_DEST, _LEGACY_BIN):
        try: p.unlink()
        except FileNotFoundError: pass
        except OSError: pass

    kw_write("--file", "kdeglobals", "--group", "KDE",
             "--key", "AutomaticLookAndFeel", "false")
    kw_write("--file", "kdeglobals", "--group", "KDE",
             "--key", "DefaultLightLookAndFeel", "--delete")
    kw_write("--file", "kdeglobals", "--group", "KDE",
             "--key", "DefaultDarkLookAndFeel", "--delete")
    ok("Theme switcher removed")
