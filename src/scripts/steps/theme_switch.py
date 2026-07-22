"""Installer step: copy the Python theme-switch + schedulers into ~/.local."""

import os
import signal
import shutil
import subprocess
import time
from pathlib import Path

from paths import REPO_ROOT
from distro import user_service_manager_command
from steps._helpers import HOME, kw_write, ok, offline, theme_mode, warn
from steps._scheduler import install_at_times, is_systemd, remove_periodic
from utils import drop_privs_in_child, run_user

BIN_DEST = HOME / ".local/bin/mac-tahoe-theme-switch"
SVC_DIR = HOME / ".config/systemd/user"
PY_SRC = REPO_ROOT / "src/scripts/theme_switch.py"
STATE_DIR = HOME / ".local/state/mac-tahoe-liquid-kde"
MANAGED_STATE_FILES = (
    STATE_DIR / "wallpapers.json",
    STATE_DIR / "layout-installed",
)

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


def _watcher_pids() -> list[int]:
    """Same-user processes running our exact installed portal watcher."""
    try:
        uid = int(os.environ.get("SUDO_UID") or os.getuid())
    except ValueError:
        uid = os.getuid()
    found: list[int] = []
    try:
        processes = list(Path("/proc").iterdir())
    except OSError:
        return found
    for process in processes:
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != uid:
                continue
            argv = [
                part.decode(errors="replace")
                for part in (process / "cmdline").read_bytes().split(b"\0")
                if part
            ]
        except OSError:
            continue
        if str(BIN_DEST) in argv and "watch-portal" in argv:
            found.append(int(process.name))
    return found


def stop_gtk_sync_watcher() -> None:
    """Stop only this project's watcher, never a generic gdbus monitor."""
    for pid in _watcher_pids():
        # 0.36.x did not handle SIGTERM, so its gdbus child could otherwise
        # survive as an orphan on upgrade. Resolve direct children before
        # stopping the parent and terminate only the exact monitor command.
        children: list[int] = []
        try:
            raw = Path(
                f"/proc/{pid}/task/{pid}/children"
            ).read_text(encoding="utf-8")
            for value in raw.split():
                child = Path("/proc") / value
                argv = [
                    part.decode(errors="replace")
                    for part in (child / "cmdline").read_bytes().split(b"\0")
                    if part
                ]
                if len(argv) >= 3 and Path(argv[0]).name == "gdbus" \
                        and argv[1:3] == ["monitor", "--session"] \
                        and "org.freedesktop.portal.Desktop" in argv:
                    children.append(int(value))
        except (OSError, ValueError):
            pass
        for child_pid in children:
            try:
                os.kill(child_pid, signal.SIGTERM)
            except OSError:
                pass
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def start_gtk_sync_watcher() -> bool | None:
    """Start native appearance sync in the current Plasma session.

    The XDG autostart file covers later logins.  Starting here closes the gap
    between installation and the next login, which previously made the quick
    settings toggle appear unsupported. ``None`` means there is no live
    graphical session and autostart will handle it later.
    """
    if os.environ.get("MAC_TAHOE_SKIP_LIVE_APPLY", "").lower() == "true":
        return None
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS") or not (
            os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return None
    if not BIN_DEST.is_file() or not BIN_DEST.stat().st_mode & 0o111:
        return False

    # Replace a watcher from an older installed script so an upgrade takes
    # effect immediately. The standalone watcher also holds a lock to prevent
    # an install/autostart race from leaving duplicates behind.
    stop_gtk_sync_watcher()
    for _ in range(10):
        if not _watcher_pids():
            break
        time.sleep(0.05)
    try:
        process = subprocess.Popen(
            [str(BIN_DEST), "watch-portal"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=os.environ.copy(),
            start_new_session=True,
            preexec_fn=drop_privs_in_child,
        )
    except OSError:
        return False
    time.sleep(0.15)
    return process.poll() is None


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


def deps():
    # OpenRC + auto mode needs crontab for the timed flip; systemd and
    # pinned modes need nothing extra.
    if is_systemd() or theme_mode() != "auto":
        return []
    return ["crontab"]


def _install_units() -> bool:
    for u in UNITS:
        src = offline(u)
        if src.is_file():
            shutil.copy2(src, SVC_DIR / u)
    results = [_user_service("daemon-reload")]
    for verb in ("enable", "start"):
        results.append(_user_service(verb, *UNITS))
    return all(results)


def _teardown_units() -> None:
    for unit in UNITS:
        _user_service("disable", "--now", unit)
        try: (SVC_DIR / unit).unlink()
        except FileNotFoundError: pass
        except OSError: pass
    _user_service("daemon-reload")


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
    # An upgrade/reinstall can otherwise leave the watcher from the previous
    # release applying a portal event while this run replaces the binary and
    # writes the target theme. Keep it stopped until the final Plasma restart,
    # where steps.apply starts the freshly-installed watcher.
    stop_gtk_sync_watcher()
    for _ in range(40):
        if not _watcher_pids():
            break
        time.sleep(0.05)

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
            # A previous OpenRC boot may have left our marked cron lines.
            remove_periodic(CRON_TAG)
            if not _install_units():
                warn("Theme switch: user timer could not be enabled")
        else:
            # Conversely, remove stale user units before scheduling cron.
            _teardown_units()
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
        _user_service("disable", "--now", unit)
        try: (SVC_DIR / unit).unlink()
        except FileNotFoundError: pass
        except OSError: pass
    _user_service("daemon-reload")
    # Strip the OpenRC cron line too, so an uninstall on either init leaves
    # no orphaned schedule behind.
    remove_periodic(CRON_TAG)
    stop_gtk_sync_watcher()
    _teardown_gtk_sync_autostart()
    for p in (BIN_DEST, _LEGACY_BIN):
        try: p.unlink()
        except FileNotFoundError: pass
        except OSError: pass
    for p in MANAGED_STATE_FILES:
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
