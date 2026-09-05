"""Installer step: copy the Python theme-switch + schedulers into ~/.local."""

import os
import signal
import shutil
import subprocess
import time
from pathlib import Path

from paths import REPO_ROOT
from distro import user_service_manager_command
from steps._helpers import HOME, fail, kw_write, ok, offline, theme_mode, warn
from steps._scheduler import (
    RemovalStatus, cron_command, install_at_times, is_systemd, remove_periodic,
)
from utils import run_user

BIN_DEST = HOME / ".local/bin/mac-tahoe-theme-switch"
SVC_DIR = HOME / ".config/systemd/user"
PY_SRC = REPO_ROOT / "src/scripts/theme_switch.py"
LAYOUT_STATE_FILE = HOME / ".local/state/mac-tahoe-liquid-kde/layout-installed"


def _managed_state_files() -> tuple[Path, Path]:
    state_home = Path(os.environ.get("XDG_STATE_HOME") or
                      HOME / ".local/state")
    wallpaper_state = state_home / "mac-tahoe-liquid-kde/wallpapers.json"
    return wallpaper_state, LAYOUT_STATE_FILE

# Legacy 0.36.x-0.38.x portal watcher. Current installs remove this autostart
# and stop the process; the names stay here solely for upgrade cleanup.
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

_PROC_ROOT = Path("/proc")
_SWITCHER_DRAIN_SECONDS = 35.0
_SWITCHER_DRAIN_POLL_SECONDS = 0.05


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


def _systemd_unit_state(unit: str, query: str) -> str | None:
    """Return one explicit systemd state, or ``None`` on manager failure."""
    command = user_service_manager_command(query, unit)
    if command is None:
        return None
    try:
        result = run_user(
            command, check=False, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (result.stdout or "").strip() or None


def _systemd_unit_stopped_and_disabled(unit: str) -> bool:
    """Prove that ``unit`` cannot run after a failed stop attempt.

    ``disable --now`` can fail merely because an already-clean unit has no
    file, but file absence alone is not proof: systemd may still have a
    deleted unit loaded. Keep manager/bus failures distinct from explicit
    stopped and disabled/not-found states. Both probes are required: an
    inactive but enabled timer can fire later, while a disabled active service
    is already executing.
    """
    active_state = _systemd_unit_state(unit, "is-active")
    enabled_state = _systemd_unit_state(unit, "is-enabled")
    inactive = active_state in {"inactive", "failed", "unknown"}
    not_enabled = enabled_state in {
        "disabled", "masked", "masked-runtime", "not-found",
    }
    return inactive and not_enabled


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


def _teardown_units(units=UNITS) -> bool:
    complete = True
    systemd = is_systemd()
    had_unit_files = False
    failed_stops: list[str] = []
    # Stop every trigger before its service. Otherwise a timer can fire after
    # the service stop returned but before the timer itself is stopped.
    ordered_units = sorted(units, key=lambda unit: not unit.endswith(".timer"))
    for unit in ordered_units:
        unit_path = SVC_DIR / unit
        existed = unit_path.exists() or unit_path.is_symlink()
        had_unit_files = had_unit_files or existed
        stopped = _user_service("disable", "--now", unit)
        if systemd and not stopped:
            # Even with no file on disk, the manager can retain a deleted unit
            # until reload. Probe its runtime and enablement states first, then
            # reload after all local definitions have been removed.
            failed_stops.append(unit)
        try: unit_path.unlink()
        except FileNotFoundError: pass
        except OSError:
            if existed:
                complete = False
    if systemd and (had_unit_files or failed_stops) \
            and not _user_service("daemon-reload"):
        complete = False
    for unit in failed_stops:
        if not _systemd_unit_stopped_and_disabled(unit):
            complete = False
    return complete


def _cron_removal_complete(status: RemovalStatus) -> bool:
    if status in (RemovalStatus.REMOVED, RemovalStatus.ABSENT):
        return True
    # A systemd-only host commonly has no crontab client at all. There is no
    # runnable OpenRC backend to clean in that case; an actual read/write error
    # from a present client remains unsafe.
    return status == RemovalStatus.UNAVAILABLE and is_systemd()


def _neutralize_switcher() -> bool:
    try:
        BIN_DEST.unlink()
        return True
    except FileNotFoundError:
        return True
    except OSError as exc:
        warn(f"Theme switcher could not be neutralized ({exc})")
        return False


def _teardown_gtk_sync_autostart() -> None:
    try: (AUTOSTART_DIR / GTK_SYNC_DESKTOP).unlink()
    except FileNotFoundError: pass
    except OSError: pass


def install() -> None:
    # 0.36.x-0.38.x installed a portal watcher that could replay a stale
    # appearance value over the scheduled/install target. It is no longer part
    # of the product: kill it and remove its autostart on every upgrade.
    stop_gtk_sync_watcher()
    for _ in range(40):
        if not _watcher_pids():
            break
        time.sleep(0.05)
    _teardown_gtk_sync_autostart()

    BIN_DEST.parent.mkdir(parents=True, exist_ok=True)
    if PY_SRC.is_file():
        shutil.copy2(PY_SRC, BIN_DEST)
        BIN_DEST.chmod(0o755)
    SVC_DIR.mkdir(parents=True, exist_ok=True)

    auto = theme_mode() == "auto"

    if auto:
        if is_systemd():
            # A previous OpenRC boot may have left our marked cron lines.
            cron_status = remove_periodic(CRON_TAG)
            if not _cron_removal_complete(cron_status):
                warn("Theme switch: previous cron schedule could not be "
                     "removed; duplicate auto transitions may remain")
            if not _install_units():
                warn("Theme switch: user timer could not be enabled")
        else:
            # Conversely, remove stale user units before scheduling cron.
            if not _teardown_units():
                warn("Theme switch: stale systemd unit files could not be "
                     "removed")
            # OpenRC: fixed-time cron lines at 06:00/18:00. There is no
            # login-time oneshot equivalent, but the binary is idempotent
            # and the timed flips are what matter.
            command = cron_command(BIN_DEST, "auto")
            if not install_at_times(CRON_TAG, CRON_TIMES, command):
                warn("Theme switch: crontab write failed — "
                     "is a cron daemon installed?")
    else:
        # Pinned --light/--dark: tear down any schedule a previous --auto
        # install left so it can't fight the pinned mode at next login.
        units_stopped = _teardown_units()
        cron_status = remove_periodic(CRON_TAG)
        if not units_stopped or not _cron_removal_complete(cron_status):
            # An unremoved schedule calling this binary would override the
            # pinned choice later. Remove its command target and fail closed.
            neutralized = _neutralize_switcher()
            drained = _wait_for_switchers() if neutralized else False
            if neutralized and drained:
                detail = " (switcher neutralized)"
            elif neutralized:
                detail = " (running switcher still draining)"
            else:
                detail = ""
            fail("Theme switch pinned mode not installed — previous schedule "
                 f"could not be stopped safely{detail}")
            return

    if BIN_DEST.is_file() and BIN_DEST.stat().st_mode & 0o111:
        ok("Theme switcher installed")
    else:
        warn("Theme switcher not installed")


_LEGACY_BIN = HOME / ".local/bin/mactahoe-theme-switch"


def _running_switcher_pids() -> set[int] | None:
    """Find same-user processes executing either installed switcher path."""
    try:
        uid = int(os.environ.get("SUDO_UID") or os.geteuid())
    except ValueError:
        uid = os.geteuid()
    targets = {
        os.path.normpath(os.fspath(BIN_DEST)),
        os.path.normpath(os.fspath(_LEGACY_BIN)),
    }
    try:
        entries = list(_PROC_ROOT.iterdir())
    except OSError:
        return None
    found: set[int] = set()
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == os.getpid():
            continue
        try:
            if entry.stat().st_uid != uid:
                continue
            raw = (entry / "cmdline").read_bytes()
        except (FileNotFoundError, ProcessLookupError):
            continue
        except OSError:
            return None
        argv = [part.decode(errors="surrogateescape")
                for part in raw.split(b"\0") if part]
        for index in (0, 1):
            if len(argv) <= index:
                continue
            candidate = argv[index]
            if (os.path.isabs(candidate) and
                    os.path.normpath(candidate) in targets):
                found.add(pid)
                break
    return found


def _wait_for_switchers(timeout: float = _SWITCHER_DRAIN_SECONDS) -> bool:
    """Wait for already-exec'd switchers after their launch paths are gone."""
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        pids = _running_switcher_pids()
        if pids == set():
            return True
        if pids is None or time.monotonic() >= deadline:
            return False
        time.sleep(min(_SWITCHER_DRAIN_POLL_SECONDS,
                       max(0.0, deadline - time.monotonic())))


def uninstall() -> None:
    # Include legacy unit names from earlier versions so an upgrade-then-
    # uninstall doesn't leave orphaned systemd files behind.
    legacy_units = (
        *UNITS,
        "mac-tahoe-liquid-kde-theme-apply.service",
        "mactahoe-theme-watcher.service",
    )
    units_stopped = _teardown_units(legacy_units)
    # Strip the OpenRC cron line too, so an uninstall on either init leaves
    # no orphaned schedule behind.
    cron_status = remove_periodic(CRON_TAG)
    cron_complete = _cron_removal_complete(cron_status)
    stop_gtk_sync_watcher()
    _teardown_gtk_sync_autostart()
    binaries_neutralized = True
    for p in (BIN_DEST, _LEGACY_BIN):
        try: p.unlink()
        except FileNotFoundError: pass
        except OSError:
            binaries_neutralized = False

    schedules_stopped = units_stopped and cron_complete
    switchers_drained = _wait_for_switchers() if binaries_neutralized else False
    cleanup_complete = schedules_stopped and binaries_neutralized \
        and switchers_drained
    if not cleanup_complete:
        if not binaries_neutralized:
            detail = "installed command could not be neutralized"
        elif not switchers_drained:
            detail = "an already-running switcher could not be drained"
        else:
            detail = "installed command was neutralized"
        fail("Theme switch removal incomplete — a previous schedule could "
             f"not be removed safely ({detail})")
        # Unlinking a script does not stop a process which already exec'd it.
        # Until both the schedule and command are proven inert, retain the
        # ownership/config state that such a process can still read or rewrite.
        return

    state_cleanup_ok = True
    for p in _managed_state_files():
        try: p.unlink()
        except FileNotFoundError: pass
        except OSError as exc:
            warn(f"Theme switch state could not be removed ({p}: {exc})")
            state_cleanup_ok = False

    config_cleanup_ok = all((
        kw_write("--file", "kdeglobals", "--group", "KDE",
                 "--key", "AutomaticLookAndFeel", "false"),
        kw_write("--file", "kdeglobals", "--group", "KDE",
                 "--key", "DefaultLightLookAndFeel", "--delete"),
        kw_write("--file", "kdeglobals", "--group", "KDE",
                 "--key", "DefaultDarkLookAndFeel", "--delete"),
    ))
    if not state_cleanup_ok or not config_cleanup_ok:
        fail("Theme switch removal incomplete — local state or KDE settings "
             "could not be cleared")
        return
    ok("Theme switcher removed")
