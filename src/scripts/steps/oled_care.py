"""Opt-in OLED-care pixel-shift service (binary + systemd user units).
install() reads the ``oled_care`` flag itself: a disabled run tears down
whatever a previous flagged install left, so a plain re-run is self-healing.
"""

import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from paths import REPO_ROOT
from distro import user_service_manager_command
from steps._helpers import HOME, fail, feat_enabled, info, ok, offline, warn
from steps._scheduler import (
    RemovalStatus, cron_command, install_periodic, is_systemd, remove_periodic,
)
from utils import run_user

# crontab tag identifying our managed line on OpenRC hosts.
CRON_TAG = "oled"

DEFAULT_INTERVAL_MINUTES = 5

BIN_DEST = HOME / ".local/bin/mac-tahoe-oled-care"
SVC_DIR = HOME / ".config/systemd/user"
PY_SRC = REPO_ROOT / "src/scripts/oled_care.py"

SERVICE_UNIT = "mac-tahoe-liquid-kde-oled.service"
TIMER_UNIT = "mac-tahoe-liquid-kde-oled.timer"
UNITS = (SERVICE_UNIT, TIMER_UNIT)

_PROC_ROOT = Path("/proc")
_LEGACY_DRAIN_SECONDS = 35.0
_LEGACY_DRAIN_POLL_SECONDS = 0.05


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


def _systemd_unit_neutralized(unit: str) -> bool:
    """Prove a failed stop left neither execution nor enablement live.

    A deleted unit file is not sufficient evidence: systemd can retain the
    loaded timer/service until a reload. Conversely, ``disable --now`` may
    return non-zero for an already-clean missing unit. Require both an
    explicit inactive state and a disabled/not-found/masked unit-file state.
    """
    states: list[str] = []
    for verb in ("is-active", "is-enabled"):
        command = user_service_manager_command(verb, unit)
        if command is None:
            return False
        try:
            result = run_user(
                command, check=False, capture_output=True, text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        states.append((result.stdout or "").strip())
    inactive = states[0] in {"inactive", "failed", "unknown"}
    disabled = states[1] in {
        "disabled", "not-found", "masked", "masked-runtime",
    }
    return inactive and disabled


def _quiesce_shifts() -> bool:
    """Drain an active helper and make every later shift a no-op."""
    try:
        import oled_care
        quiesced = oled_care.quiesce_shifts()
    except Exception as exc:
        warn(f"OLED care: panel shifts could not be quiesced ({exc})")
        return False
    if not quiesced:
        warn("OLED care: panel shifts could not be quiesced")
    return quiesced


def _enable_shifts() -> bool:
    """Enable mutations only after the replacement schedule is active."""
    try:
        import oled_care
        enabled = oled_care.enable_shifts()
    except Exception as exc:
        warn(f"OLED care: panel shifts could not be enabled ({exc})")
        return False
    if not enabled:
        warn("OLED care: panel shifts could not be enabled")
    return enabled


def _recovery_uncertain() -> bool:
    """Fail closed when the runtime cannot prove its saved geometry state."""
    try:
        import oled_care
        return oled_care.recovery_uncertain()
    except Exception as exc:
        warn(f"OLED care: recovery status could not be verified ({exc})")
        return True


def _replace_current_helper(*, required: bool) -> bool:
    """Atomically put the lock-aware helper behind the tombstone.

    A legacy process that already exec'd the old inode keeps running and is
    drained separately. Every later launch opens this audited replacement and
    observes the tombstone before touching Plasma.
    """
    exists = BIN_DEST.exists() or BIN_DEST.is_symlink()
    if not required and not exists:
        return True
    if not PY_SRC.is_file():
        warn("OLED care: current helper source is missing")
        return False
    tmp_path: Path | None = None
    fd = -1
    try:
        BIN_DEST.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{BIN_DEST.name}.", suffix=".tmp",
            dir=BIN_DEST.parent,
        )
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "wb") as target:
            fd = -1
            with PY_SRC.open("rb") as source:
                shutil.copyfileobj(source, target)
                target.flush()
                os.fchmod(target.fileno(), 0o755)
        os.replace(tmp_path, BIN_DEST)
        return True
    except OSError as exc:
        warn(f"OLED care: current helper could not be installed ({exc})")
        return False
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


def _helper_is_current() -> bool:
    try:
        return BIN_DEST.read_bytes() == PY_SRC.read_bytes()
    except OSError:
        return False


def _canonical_storage_initialized() -> bool:
    try:
        import oled_care
        return oled_care.canonical_storage_initialized()
    except Exception:
        return False


def _prepare_recovery_state(*, require_known_legacy: bool) -> bool:
    try:
        import oled_care
        prepared = oled_care.prepare_recovery_state(
            require_known_legacy=require_known_legacy,
        )
    except Exception as exc:
        warn(f"OLED care: recovery state could not be prepared ({exc})")
        return False
    if not prepared:
        warn("OLED care: recovery state could not be prepared")
    return prepared


def _recovery_signature() -> tuple[bytes, ...] | None:
    try:
        import oled_care
        return oled_care.recovery_state_signature()
    except Exception:
        return None


def _mark_recovery_uncertain() -> bool:
    try:
        import oled_care
        marked = oled_care.mark_recovery_uncertain()
    except Exception as exc:
        warn(f"OLED care: legacy recovery could not be guarded ({exc})")
        return False
    if not marked:
        warn("OLED care: legacy recovery could not be guarded")
    return marked


def _helper_user_uid() -> int:
    try:
        return int(os.environ.get("SUDO_UID") or os.geteuid())
    except ValueError:
        return os.geteuid()


def _is_exact_shift_argv(argv: list[str]) -> bool:
    expected = os.path.normpath(os.fspath(BIN_DEST))
    # Direct execution presents the script as argv[0] on some launchers;
    # a shebang interpreter normally presents it as argv[1].
    for index in (0, 1):
        if len(argv) <= index + 1:
            continue
        candidate = argv[index]
        if (os.path.isabs(candidate) and
                os.path.normpath(candidate) == expected and
                argv[index + 1] == "shift"):
            return True
    return False


def _running_legacy_shift_pids() -> set[int] | None:
    """Find only same-user processes executing our exact shift command."""
    uid = _helper_user_uid()
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
            # A same-user process whose command cannot be inspected cannot be
            # identified as our helper. Keep recovery rather than guessing.
            return None
        argv = [part.decode(errors="surrogateescape")
                for part in raw.split(b"\0") if part]
        if _is_exact_shift_argv(argv):
            found.add(pid)
    return found


def _wait_for_legacy_shifts(
    timeout: float = _LEGACY_DRAIN_SECONDS,
) -> tuple[bool, bool]:
    """Let pre-lock helpers finish naturally; never kill mid-transaction."""
    deadline = time.monotonic() + max(0.0, timeout)
    observed = False
    while True:
        pids = _running_legacy_shift_pids()
        if pids == set():
            return True, observed
        if pids:
            observed = True
        if pids is None or time.monotonic() >= deadline:
            if pids:
                warn("OLED care: timed out waiting for an older shift process")
            else:
                warn("OLED care: older shift processes could not be inspected")
            return False, observed
        time.sleep(min(_LEGACY_DRAIN_POLL_SECONDS,
                       max(0.0, deadline - time.monotonic())))


def _teardown_systemd_units(units: tuple[str, ...]) -> tuple[bool, bool]:
    """Stop/unlink units, reload, then prove every failed stop is inert."""
    removed = False
    complete = True
    systemd = is_systemd()
    had_unit_files = False
    failed_stops: list[str] = []
    for unit in units:
        unit_path = SVC_DIR / unit
        existed = unit_path.exists() or unit_path.is_symlink()
        had_unit_files = had_unit_files or existed
        stopped = _user_service("disable", "--now", unit)
        if systemd and not stopped:
            failed_stops.append(unit)
        try:
            unit_path.unlink()
            removed = True
        except FileNotFoundError:
            pass
        except OSError:
            if existed:
                complete = False
    if systemd and (had_unit_files or failed_stops):
        if not _user_service("daemon-reload"):
            complete = False
    for unit in failed_stops:
        if not _systemd_unit_neutralized(unit):
            complete = False
    return removed, complete


def _teardown_triggers() -> tuple[bool, bool]:
    """Stop timer/cron launch points without killing an active service."""
    removed, complete = _teardown_systemd_units((TIMER_UNIT,))
    systemd = is_systemd()

    cron_status = remove_periodic(CRON_TAG)
    if cron_status == RemovalStatus.REMOVED:
        removed = True
    elif cron_status == RemovalStatus.ERROR or (
            cron_status == RemovalStatus.UNAVAILABLE and not systemd):
        complete = False
        warn("OLED care: previous cron schedule could not be removed")
    return removed, complete


def _teardown_service() -> tuple[bool, bool]:
    return _teardown_systemd_units((SERVICE_UNIT,))


def _teardown_units() -> tuple[bool, bool]:
    """Compatibility helper: trigger first, then its service target."""
    trigger_removed, trigger_complete = _teardown_triggers()
    service_removed, service_complete = _teardown_service()
    return (trigger_removed or service_removed,
            trigger_complete and service_complete)


def _retire_runtime(*, require_helper: bool) -> tuple[bool, bool]:
    """Neutralise launches and drain legacy work before stopping service.

    Returns ``(removed_anything, safe_for_restore_or_reschedule)``. On every
    uncertain path the tombstone and recovery state are retained.
    """
    had_helper = BIN_DEST.exists() or BIN_DEST.is_symlink()
    had_units = any(
        (SVC_DIR / unit).exists() or (SVC_DIR / unit).is_symlink()
        for unit in UNITS
    )
    legacy_storage_possible = not _canonical_storage_initialized() and (
        (had_helper and not _helper_is_current()) or
        (not had_helper and had_units)
    )
    quiesced = _quiesce_shifts()
    replaced = quiesced and _replace_current_helper(required=require_helper)
    trigger_removed, triggers_stopped = _teardown_triggers()
    # A removed cron line is also an ownership signal. This matters when the
    # installed helper was manually deleted: an older cron fire may still have
    # written recovery data below a custom XDG_STATE_HOME.
    legacy_storage_possible = legacy_storage_possible or (
        not _canonical_storage_initialized() and trigger_removed
    )
    before = _recovery_signature() if replaced else None
    if replaced:
        drained, legacy_observed = _wait_for_legacy_shifts()
    else:
        drained, legacy_observed = False, False
    state_prepared = drained and _prepare_recovery_state(
        require_known_legacy=legacy_storage_possible,
    )
    after = _recovery_signature() if state_prepared else None
    legacy_outcome_safe = not legacy_observed or (
        before is not None and after is not None and before != after
    )
    if drained and not legacy_outcome_safe:
        _mark_recovery_uncertain()
    service_removed = False
    service_stopped = False
    if drained:
        service_removed, service_stopped = _teardown_service()
    recovery_safe = state_prepared and legacy_outcome_safe and \
        not _recovery_uncertain()
    safe = quiesced and replaced and triggers_stopped and drained and \
        service_stopped and recovery_safe
    return trigger_removed or service_removed, safe


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


def _schedule_cron(interval: int, max_px: int) -> bool:
    # OpenRC: no systemd user timer. The shift binary recovers the desktop
    # session env itself (see oled_care._sync_session_env), so a bare cron
    # environment still reaches plasmashell.
    command = cron_command(BIN_DEST, "shift", "--max-px", max_px)
    if not install_periodic(CRON_TAG, interval, command):
        warn("OLED care: crontab write failed — is a cron daemon installed?")
        return False
    info(f"Panels pixel-shift up to {max_px} px every {interval} min "
         "(user crontab)")
    return True


def _restore_panels() -> bool:
    """Put panel geometry back before the service goes away. In-process
    import — the installed binary may already be gone (or never existed)."""
    state_file = _state_file()
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
        removed, runtime_retired = _retire_runtime(require_helper=False)
        if not runtime_retired:
            fail("OLED care removal incomplete — active shifts or scheduling "
                 "could not be retired safely")
            info("OLED care panel recovery is pending")
            return
        restored = _restore_panels()
        if removed:
            ok("Previous OLED care service removed")
        if not restored:
            fail("OLED care removal incomplete — restore panel geometry "
                 "after logging in, then retry")
            info("OLED care disabled; panel recovery helper retained")
            return
        helper_removed, helper_neutralized = _remove_helper()
        removed = removed or helper_removed
        if not helper_neutralized:
            fail("OLED care removal incomplete — helper cleanup must be "
                 "retried")
            info("OLED care disabled; scheduler cleanup is pending")
            return
        info("OLED care disabled — enable with --oled-care")
        return

    if not PY_SRC.is_file():
        warn("OLED care script missing — skipping")
        return

    interval = _interval_minutes()
    max_px = _max_shift_px()
    # Install the current lock-aware helper behind the tombstone, stop launch
    # points, drain any already-exec'd legacy copy, then stop its service.
    _removed, runtime_retired = _retire_runtime(require_helper=True)
    if not runtime_retired:
        fail("OLED care not installed — previous runtime could not be retired; "
             "recovery state retained")
        return

    if is_systemd():
        scheduled = _schedule_systemd(interval, max_px)
    else:
        scheduled = _schedule_cron(interval, max_px)

    if not scheduled:
        _cleanup_removed, cleanup_safe = _retire_runtime(
            require_helper=False)
        if cleanup_safe:
            _remove_helper()
            fail("OLED care not installed — scheduler could not be enabled; "
                 "partial schedule removed and recovery state retained")
        else:
            fail("OLED care not installed — scheduler enable and cleanup were "
                 "incomplete; recovery state retained")
        return
    if not _enable_shifts():
        # Enabling may have failed before or after marker removal. Re-quiesce
        # and report cleanup as complete only when the full handshake proves it.
        _cleanup_removed, cleanup_safe = _retire_runtime(
            require_helper=False)
        if cleanup_safe:
            _remove_helper()
            fail("OLED care not installed — shifts could not be enabled; "
                 "schedule removed and recovery state retained")
        else:
            fail("OLED care enable outcome is uncertain — cleanup incomplete; "
                 "recovery state retained")
        return

    ok("OLED care service installed")


def uninstall() -> None:
    removed, runtime_retired = _retire_runtime(require_helper=False)
    if not runtime_retired:
        fail("OLED care removal incomplete — active shifts or scheduling "
             "could not be retired safely")
        info("OLED care panel recovery is pending")
        return
    restored = _restore_panels()
    if not restored:
        fail("OLED care removal incomplete — restore panel geometry after "
             "logging in, then retry")
        info("OLED care disabled; panel recovery helper retained")
        return
    helper_removed, helper_neutralized = _remove_helper()
    removed = removed or helper_removed
    if not helper_neutralized:
        fail("OLED care removal incomplete — helper cleanup must be retried")
        info("OLED care disabled; scheduler cleanup is pending")
        return
    if removed:
        ok("OLED care service removed")
    else:
        info("OLED care was not installed")
