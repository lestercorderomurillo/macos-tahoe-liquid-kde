#!/usr/bin/env python3
"""OLED care pixel-shift: `mac-tahoe-oled-care {shift|restore|status}`.
Fill-length panels cycle height (Plasma clamps their offset); others
cycle offset. When a panel's geometry != base + last delta the user
moved it — re-capture the base, never fight a deliberate change."""

import fcntl
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path


# Offsets walk a triangle wave around the base; heights use the |offset|
# wave so a panel only grows — it never renders thinner than its base.
DEFAULT_MAX_SHIFT_PX = 8
MAX_SHIFT_CEILING_PX = 16
SHIFT_STEP_PX = 2

_QDBUS_TIMEOUT_SECONDS = 15
_LOCK_WAIT_SECONDS = 35.0
_LOCK_POLL_SECONDS = 0.05

_MARKER_DISABLED = "disabled"
_MARKER_TRANSITION = "transition"
_MARKER_UNCERTAIN = "uncertain"
_EVAL_UNCERTAIN = object()


def clamp_max_px(value: object) -> int:
    try:
        px = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_MAX_SHIFT_PX
    return max(1, min(MAX_SHIFT_CEILING_PX, px))


def build_patterns(max_px: int) -> tuple[list[int], list[int]]:
    """Triangle wave 0→M→0→-M→0 in SHIFT_STEP_PX steps plus its
    absolute-value twin for the height knob. One index drives both."""
    max_px = clamp_max_px(max_px)
    s = SHIFT_STEP_PX
    offsets = (list(range(0, max_px, s)) + list(range(max_px, 0, -s)) +
               list(range(0, -max_px, -s)) + list(range(-max_px, 0, s)))
    return offsets, [abs(d) for d in offsets]


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _state_dir() -> Path:
    """Canonical OLED control/state root shared by every launch backend.

    Unlike ordinary diagnostic state, panel recovery is part of a transaction
    with live geometry. It cannot safely follow a sparse cron environment into
    a different XDG root, so this path deliberately matches the documented
    fixed location below the user's home.
    """
    return Path.home() / ".local/state/mac-tahoe-liquid-kde"


def _state_file() -> Path:
    return _state_dir() / "oled-care.json"


def _operation_lock_file() -> Path:
    """One lock shared by timer, manual, and installer recovery runs.

    Keep this in the canonical state directory rather than in
    ``XDG_RUNTIME_DIR``: cron, systemd, manual calls, and installer recovery
    must coordinate on the same inode even with different environments.
    """
    return _state_file().with_name("oled-care.lock")


def _disabled_file() -> Path:
    """Persistent tombstone preventing a retired helper from shifting.

    Unlinking an executable does not stop a process that cron/systemd already
    started.  Teardown writes this marker while holding the operation lock, so
    both an in-flight shift and a not-yet-scheduled helper are neutralised.
    """
    return _state_file().with_name("oled-care.disabled")


def _transition_file() -> Path:
    """Write-ahead record for a dispatched but not-yet-committed shift."""
    return _state_file().with_name("oled-care-transition.json")


def _storage_marker_file() -> Path:
    return _state_dir() / "oled-care-storage-v1"


def canonical_storage_initialized() -> bool:
    try:
        return _storage_marker_file().read_text(encoding="ascii") == \
            "canonical-v1\n"
    except (OSError, UnicodeError):
        return False


def _mark_storage_initialized_unlocked() -> None:
    if canonical_storage_initialized():
        return
    marker = _storage_marker_file()
    try:
        marker.lstat()
    except FileNotFoundError:
        pass
    else:
        raise _StateError("canonical OLED storage marker is invalid")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(marker, flags, 0o600)
    try:
        payload = b"canonical-v1\n"
        if os.write(fd, payload) != len(payload):
            raise OSError("short OLED storage-marker write")
        os.fsync(fd)
    except OSError:
        try:
            marker.unlink()
        except OSError:
            pass
        raise
    finally:
        os.close(fd)


@contextmanager
def _operation_lock(timeout: float):
    """Serialise the complete read -> Plasma -> state transaction.

    This lock is fail-closed: moving panel geometry without being able to
    coordinate with restore would make the recovery state untrustworthy.
    ``flock`` is released by close even when the process is killed; the lock
    file itself is deliberately never unlinked, because replacing its inode
    while another process holds it would split the lock domain.
    """
    path = _operation_lock_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    lock = None
    acquired = False
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(f"OLED operation lock is not a regular file: {path}")
        os.fchmod(fd, 0o600)
        lock = os.fdopen(fd, "r+", encoding="utf-8")
        fd = -1
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(_LOCK_POLL_SECONDS, remaining))
        yield acquired
    finally:
        if lock is not None:
            if acquired:
                try:
                    fcntl.flock(lock, fcntl.LOCK_UN)
                except OSError:
                    pass
            try:
                lock.close()
            except OSError:
                pass
        elif fd >= 0:
            os.close(fd)


def _marker_state_unlocked() -> str | None:
    """Read the tombstone without following links.

    Any malformed or unreadable entry is treated as an uncertain transition:
    denying this opt-in feature is safer than moving panels with recovery data
    whose relationship to the live geometry cannot be proved.
    """
    path = _disabled_file()
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return None
    except OSError:
        try:
            path.lstat()
        except FileNotFoundError:
            return None
        except OSError:
            pass
        return "uncertain"
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return "uncertain"
        raw = os.read(fd, 64)
    except OSError:
        return "uncertain"
    finally:
        os.close(fd)
    try:
        value = raw.decode("ascii").strip()
    except UnicodeDecodeError:
        return "uncertain"
    if value in {_MARKER_DISABLED, _MARKER_TRANSITION, _MARKER_UNCERTAIN}:
        return value
    return "uncertain"


def _disabled_unlocked() -> bool:
    return _marker_state_unlocked() is not None


def _recovery_uncertain_unlocked() -> bool:
    state = _marker_state_unlocked()
    return state not in {None, _MARKER_DISABLED}


def _disable_unlocked(reason: str = _MARKER_DISABLED) -> None:
    """Create a typed tombstone while the operation lock is held."""
    if reason not in {
        _MARKER_DISABLED, _MARKER_TRANSITION, _MARKER_UNCERTAIN,
    }:
        raise ValueError(f"invalid OLED tombstone reason: {reason}")
    marker = _disabled_file()
    if _disabled_unlocked():
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(marker, flags, 0o600)
    try:
        payload = f"{reason}\n".encode("ascii")
        if os.write(fd, payload) != len(payload):
            raise OSError("short OLED tombstone write")
        os.fsync(fd)
    except OSError:
        try:
            marker.unlink()
        except OSError:
            pass
        raise
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def _enable_unlocked() -> None:
    state = _marker_state_unlocked()
    if state is None:
        return
    if state != _MARKER_DISABLED:
        raise OSError("panel recovery is uncertain; refusing to enable shifts")
    try:
        _disabled_file().unlink()
    except FileNotFoundError:
        pass


def _finish_transition_unlocked() -> None:
    """Remove only the guard created by the current verified transition."""
    if _marker_state_unlocked() != _MARKER_TRANSITION:
        raise OSError("OLED transition guard changed unexpectedly")
    _disabled_file().unlink()


def quiesce_shifts() -> bool:
    """Drain the current operation and block every later ``shift`` call."""
    try:
        with _operation_lock(_LOCK_WAIT_SECONDS) as acquired:
            if not acquired:
                print("oled care: timed out waiting to quiesce panel shifts",
                      file=sys.stderr)
                return False
            _disable_unlocked()
        return True
    except OSError as exc:
        print(f"oled care: could not quiesce panel shifts ({exc})",
              file=sys.stderr)
        return False


def enable_shifts() -> bool:
    """Clear the tombstone after a replacement scheduler is fully active."""
    try:
        with _operation_lock(_LOCK_WAIT_SECONDS) as acquired:
            if not acquired:
                print("oled care: timed out waiting to enable panel shifts",
                      file=sys.stderr)
                return False
            _enable_unlocked()
        return True
    except OSError as exc:
        print(f"oled care: could not enable panel shifts ({exc})",
              file=sys.stderr)
        return False


def recovery_uncertain() -> bool:
    """Whether an earlier Plasma mutation lacks trustworthy recovery state."""
    try:
        with _operation_lock(_LOCK_WAIT_SECONDS) as acquired:
            return not acquired or _recovery_uncertain_unlocked()
    except OSError:
        return True


def mark_recovery_uncertain() -> bool:
    """Persist an unjournaled legacy-helper outcome as fail-closed."""
    try:
        with _operation_lock(_LOCK_WAIT_SECONDS) as acquired:
            if not acquired:
                return False
            marker = _disabled_file()
            state = _marker_state_unlocked()
            if state == _MARKER_UNCERTAIN:
                return True
            if state != _MARKER_DISABLED:
                return False
            flags = os.O_WRONLY | os.O_TRUNC | getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(marker, flags)
            try:
                payload = f"{_MARKER_UNCERTAIN}\n".encode("ascii")
                if os.write(fd, payload) != len(payload):
                    raise OSError("short OLED uncertainty-marker write")
                os.fsync(fd)
            finally:
                os.close(fd)
        return True
    except OSError as exc:
        print(f"oled care: could not persist uncertain recovery ({exc})",
              file=sys.stderr)
        return False


_SESSION_ENV_KEYS = frozenset({
    "DBUS_SESSION_BUS_ADDRESS",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "XAUTHORITY",
    "XDG_RUNTIME_DIR",
    "XDG_STATE_HOME",
})
_PROC_ROOT = Path("/proc")


def _sync_session_env_runtime_dir() -> None:
    """Reconstruct the session env from ``/run/user/$UID``.

    XDG_RUNTIME_DIR is provided by the session runtime (systemd-logind or
    elogind); its well-known Wayland and DBus sockets work without knowing
    which init launched the scheduled command.
    """
    xrd = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    if not Path(xrd).is_dir():
        return
    os.environ.setdefault("XDG_RUNTIME_DIR", xrd)

    if "WAYLAND_DISPLAY" not in os.environ:
        # Sockets are named wayland-0, wayland-1, …; pick the lowest that
        # exists. Store the bare name — Qt resolves it against XDG_RUNTIME_DIR.
        for sock in sorted(Path(xrd).glob("wayland-*")):
            if sock.is_socket() and not sock.name.endswith(".lock"):
                os.environ["WAYLAND_DISPLAY"] = sock.name
                break

    if "DBUS_SESSION_BUS_ADDRESS" not in os.environ:
        bus = Path(xrd) / "bus"
        if bus.is_socket():
            os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus}"


def _sync_session_env_from_plasmashell() -> bool:
    """Recover X11 and any missing values from a same-user Plasma shell."""
    try:
        uid = int(os.environ.get("SUDO_UID") or os.getuid())
    except ValueError:
        uid = os.getuid()
    try:
        processes = list(_PROC_ROOT.iterdir())
    except OSError:
        return False
    for process in processes:
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != uid:
                continue
            if (process / "comm").read_text().strip() != "plasmashell":
                continue
            raw = (process / "environ").read_bytes()
        except OSError:
            continue
        for entry in raw.split(b"\0"):
            key_raw, sep, value_raw = entry.partition(b"=")
            key = key_raw.decode(errors="ignore")
            if (not sep or key not in _SESSION_ENV_KEYS or
                    (key != "XDG_STATE_HOME" and os.environ.get(key))):
                continue
            value = value_raw.decode(errors="ignore")
            if value:
                os.environ[key] = value
        return True
    return False


def _sync_session_env() -> bool:
    """Best-effort recovery of the desktop session env for scheduled
    fires. Runtime sockets cover Wayland/DBus, while a same-user plasmashell
    supplies X11/Xauthority. Neither path depends on the host init system."""
    _sync_session_env_runtime_dir()
    return _sync_session_env_from_plasmashell()


def _plasmashell_has_owner(qdbus: str) -> bool:
    """Prove the remote name exists before a potentially mutating call."""
    try:
        result = subprocess.run(
            [qdbus, "org.freedesktop.DBus", "/org/freedesktop/DBus",
             "org.freedesktop.DBus.NameHasOwner", "org.kde.plasmashell"],
            check=False, capture_output=True, text=True,
            timeout=_QDBUS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def _evaluate_script(script: str) -> str | None | object:
    """Run a Plasma scripting snippet via qdbus; returns its print()
    output, or None when plasmashell is unreachable (normal early in boot)."""
    _sync_session_env()
    for q in ("qdbus6", "qdbus-qt6", "qdbus"):
        if not _have(q):
            continue
        # A missing owner is a proven no-op. Once an owner exists, a timeout or
        # non-zero method result is ambiguous: plasmashell could have applied
        # some setters before the reply was lost.
        if not _plasmashell_has_owner(q):
            return None
        try:
            res = subprocess.run(
                [q, "org.kde.plasmashell", "/PlasmaShell",
                 "org.kde.PlasmaShell.evaluateScript", script],
                check=False, capture_output=True, text=True,
                timeout=_QDBUS_TIMEOUT_SECONDS,
            )
        except OSError:
            return None
        except subprocess.TimeoutExpired:
            # The remote method may have changed geometry before the client
            # timed out. Callers must retain the transition guard.
            return _EVAL_UNCERTAIN
        return res.stdout if res.returncode == 0 else _EVAL_UNCERTAIN
    return None


class _StateError(Exception):
    """An existing recovery file could not safely drive a mutation."""


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_panels(panels: object) -> dict[str, dict[str, int]]:
    if not isinstance(panels, dict):
        raise _StateError("recovery state is invalid (bad panel map)")

    checked_panels: dict[str, dict[str, int]] = {}
    for panel_id, base in panels.items():
        # Plasma containment IDs are decimal integers. Restricting the JSON
        # keys also prevents names such as ``__proto__`` from changing the
        # semantics of the JavaScript object embedded in evaluateScript.
        if (not isinstance(panel_id, str) or not panel_id.isascii() or
                not panel_id.isdigit() or not isinstance(base, dict)):
            raise _StateError("recovery state is invalid (bad panel entry)")
        offset = base.get("offset")
        height = base.get("height")
        if (not _is_int(offset) or not -1_000_000 <= offset <= 1_000_000 or
                not _is_int(height) or not 1 <= height <= 1_000_000):
            raise _StateError(
                f"recovery state is invalid (bad panel {panel_id!r} base)")
        checked_panels[panel_id] = {"offset": offset, "height": height}
    return checked_panels


def _validate_state(data: object) -> dict:
    """Validate every value used to calculate or restore geometry."""
    if not isinstance(data, dict):
        raise _StateError("recovery state is invalid (expected an object)")
    index = data.get("index")
    last_off = data.get("last_off")
    last_h = data.get("last_h")
    if not _is_int(index) or index < 0:
        raise _StateError("recovery state is invalid (bad index)")
    if (not _is_int(last_off) or
            not -MAX_SHIFT_CEILING_PX <= last_off <= MAX_SHIFT_CEILING_PX):
        raise _StateError("recovery state is invalid (bad offset delta)")
    if (not _is_int(last_h) or
            not 0 <= last_h <= MAX_SHIFT_CEILING_PX):
        raise _StateError("recovery state is invalid (bad height delta)")
    return {
        "index": index,
        "last_off": last_off,
        "last_h": last_h,
        "panels": _validate_panels(data.get("panels")),
    }


def _read_existing_state(path: Path | None = None) -> dict | None:
    """Return ``None`` only when the state truly does not exist.

    An unreadable, corrupt, or structurally invalid existing file is recovery
    data, not an empty first run.  Refuse to move panels until it is repaired
    or deliberately removed.
    """
    path = path or _state_file()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError) as exc:
        raise _StateError(f"recovery state could not be read ({exc})") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _StateError(f"recovery state could not be read ({exc})") from exc
    return _validate_state(data)


def _legacy_state_candidate() -> tuple[Path, bool]:
    """Return the pre-v0.50.1 XDG path and whether its root is knowable.

    Older helpers followed ``XDG_STATE_HOME``. A live Plasma process is the
    authoritative source for sparse cron/sudo environments. An explicitly
    supplied non-default XDG root is also sufficient evidence when Plasma is
    offline; a synthesized default alone cannot rule out an older custom root.
    """
    before = os.environ.get("XDG_STATE_HOME")
    session_found = _sync_session_env()
    default_home = Path.home() / ".local/state"
    state_home = Path(os.environ.get("XDG_STATE_HOME") or default_home)
    known = session_found or (before is not None and state_home != default_home)
    return state_home / "mac-tahoe-liquid-kde/oled-care.json", known


def recovery_state_signature() -> tuple[bytes, ...] | None:
    """Comparable payload snapshot used while an old helper drains.

    Paths are intentionally excluded so migrating identical bytes from an XDG
    location to the canonical root is not mistaken for a successful legacy
    write. ``None`` means the outcome cannot be inspected safely.
    """
    legacy, _known = _legacy_state_candidate()
    payloads: set[bytes] = set()
    for path in {_state_file(), legacy}:
        try:
            payloads.add(path.read_bytes())
        except FileNotFoundError:
            continue
        except OSError:
            return None
    return tuple(sorted(payloads))


def _prepare_state_unlocked(*, require_known_legacy: bool = False) -> None:
    """Migrate the old XDG-aware recovery file into the canonical root.

    Conflicting copies are never guessed between. During an upgrade/uninstall,
    absence is accepted only when a live session or explicit custom root proves
    which legacy location was in use; otherwise the user can log in and retry.
    """
    canonical = _state_file()
    if canonical_storage_initialized():
        # Still validate an existing file before any mutation.
        _read_existing_state(canonical)
        return
    legacy, legacy_location_known = _legacy_state_candidate()
    canonical_state = _read_existing_state(canonical)
    if legacy == canonical:
        if require_known_legacy and not legacy_location_known:
            raise _StateError(
                "legacy recovery location is unknown while Plasma is offline"
            )
        _mark_storage_initialized_unlocked()
        return

    legacy_state = _read_existing_state(legacy)
    if canonical_state is not None and legacy_state is not None:
        if canonical_state != legacy_state:
            raise _StateError("multiple OLED recovery files disagree")
        try:
            legacy.unlink()
        except OSError as exc:
            raise _StateError(
                f"legacy recovery state could not be retired ({exc})"
            ) from exc
        _mark_storage_initialized_unlocked()
        return
    if legacy_state is not None:
        if not save_state(legacy_state):
            raise _StateError("legacy recovery state could not be migrated")
        try:
            legacy.unlink()
        except OSError as exc:
            raise _StateError(
                f"legacy recovery state could not be retired ({exc})"
            ) from exc
        _mark_storage_initialized_unlocked()
        return
    if require_known_legacy and not legacy_location_known:
        raise _StateError(
            "legacy recovery location is unknown while Plasma is offline"
        )
    _mark_storage_initialized_unlocked()


def prepare_recovery_state(*, require_known_legacy: bool = False) -> bool:
    """Installer handshake for legacy-state discovery after process drain."""
    try:
        with _operation_lock(_LOCK_WAIT_SECONDS) as acquired:
            if not acquired:
                print("oled care: timed out preparing recovery state",
                      file=sys.stderr)
                return False
            _prepare_state_unlocked(
                require_known_legacy=require_known_legacy,
            )
        return True
    except (OSError, _StateError) as exc:
        print(f"oled care: {exc}", file=sys.stderr)
        return False


def load_state() -> dict:
    """Applied deltas are stored, not recomputed — restore stays correct
    even when --oled-max-shift changed since the last shift."""
    state = _read_existing_state()
    if state is None:
        return {"index": 0, "last_off": 0, "last_h": 0, "panels": {}}
    return state


def save_state(state: dict) -> bool:
    path = _state_file()
    # Write-then-rename: this fires unattended on a timer indefinitely,
    # so a kill/crash mid-write shouldn't be able to leave a torn file
    # and a clean rename prevents a corrupt-then-reset blip. Failure is
    # reported to the caller: shift() has already rebased the panel(s)
    # on-screen at this point, so if the new offsets can't be
    # persisted, the caller must not report success — the next fire
    # would resume from stale state and mis-rebase.
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(state) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        return True
    except OSError as exc:
        print(f"oled care: could not save panel state ({exc})", file=sys.stderr)
        try:
            tmp.unlink()
        except OSError:
            pass
        return False


def _save_transition(state: dict, next_index: int,
                     next_off: int, next_h: int) -> bool:
    path = _transition_file()
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = {
        "version": 1,
        "prior": state,
        "target": {
            "index": next_index,
            "last_off": next_off,
            "last_h": next_h,
        },
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        return True
    except OSError as exc:
        print(f"oled care: could not save transition journal ({exc})",
              file=sys.stderr)
        try:
            tmp.unlink()
        except OSError:
            pass
        return False


def _read_transition() -> dict | None:
    path = _transition_file()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _StateError(
            f"transition journal could not be read ({exc})"
        ) from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise _StateError("transition journal is invalid")
    prior = _validate_state(payload.get("prior"))
    target = payload.get("target")
    if not isinstance(target, dict):
        raise _StateError("transition journal is invalid (bad target)")
    candidate = {
        "index": target.get("index"),
        "last_off": target.get("last_off"),
        "last_h": target.get("last_h"),
        "panels": prior["panels"],
    }
    checked_target = _validate_state(candidate)
    return {"prior": prior, "target": checked_target}


def _clear_transition_files_unlocked() -> None:
    try:
        _transition_file().unlink()
    except FileNotFoundError:
        pass
    _finish_transition_unlocked()


def build_shift_script(panels: dict, last_off: int, last_h: int,
                       next_off: int, next_h: int) -> str:
    """Rebase safely, or apply the next delta, in one Plasma event-loop pass.

    A newly discovered panel or a user geometry edit has a base which is not
    present in the write-ahead journal yet. In that case normalize the panels
    whose old bases are known, capture every current base, and do *not* shift
    the rebased panels on this fire. The next fire can then journal all bases
    before it mutates them. This avoids an un-restorable crash window between
    Plasma changing an unknown base and Python receiving the reply.
    """
    return f"""
var bases = {json.dumps(panels)};
var lastOff = {last_off}, nextOff = {next_off};
var lastH = {last_h}, nextH = {next_h};
var out = {{}};
var tracked = {{}};
var normalize = false;
var all = panels();
for (var i = 0; i < all.length; i++) {{
    var p = all[i];
    var key = String(p.id);
    var fill = false;
    try {{ fill = (p.lengthMode == "fill"); }} catch (e) {{}}
    var base = bases[key];
    var known = !!base;
    var matched = true;
    if (!base) {{
        base = {{offset: p.offset, height: p.height}};
        normalize = true;
    }}
    if (fill) {{
        if (known && p.height != base.height + lastH) {{
            base.height = p.height;
            matched = false;
            normalize = true;
        }}
        base.offset = p.offset;
    }} else {{
        if (known && p.offset != base.offset + lastOff) {{
            base.offset = p.offset;
            matched = false;
            normalize = true;
        }}
        base.height = p.height;
    }}
    out[key] = {{offset: base.offset, height: base.height}};
    tracked[key] = {{panel: p, fill: fill, known: known, matched: matched}};
}}
for (var key in tracked) {{
    var item = tracked[key];
    // Unknown and user-edited panels were not represented by the journal and
    // must remain untouched until their captured bases have been persisted.
    if (!item.known || !item.matched) continue;
    if (item.fill)
        item.panel.height = out[key].height + (normalize ? 0 : nextH);
    else
        item.panel.offset = out[key].offset + (normalize ? 0 : nextOff);
}}
print(JSON.stringify(out));
print(normalize ? "normalized" : "shifted");
"""


def build_restore_script(panels: dict, last_off: int, last_h: int) -> str:
    """Undo exactly the delta we applied. A panel whose geometry no
    longer matches base + delta was changed by the user — leave it."""
    return f"""
var bases = {json.dumps(panels)};
var lastOff = {last_off};
var lastH = {last_h};
var all = panels();
for (var i = 0; i < all.length; i++) {{
    var p = all[i];
    var base = bases[String(p.id)];
    if (!base) continue;
    var fill = false;
    try {{ fill = (p.lengthMode == "fill"); }} catch (e) {{}}
    if (fill) {{
        if (p.height == base.height + lastH) p.height = base.height;
    }} else {{
        if (p.offset == base.offset + lastOff) p.offset = base.offset;
    }}
}}
print("restored");
"""


def build_uncertain_restore_script(panels: dict, prior_off: int, prior_h: int,
                                   target_off: int, target_h: int) -> str:
    """Restore base from either side of an ambiguously-replied transition.

    The shift script only mutates panels with already-persisted bases, and it
    skips a panel on the same fire that detects a user edit. A rebase fire may
    normalize other tracked panels to delta zero, so prior, target, and zero
    are the complete set of possible project-owned geometries.
    """
    return f"""
var bases = {json.dumps(panels)};
var priorOff = {prior_off}, targetOff = {target_off};
var priorH = {prior_h}, targetH = {target_h};
var all = panels();
var unresolved = 0;
for (var i = 0; i < all.length; i++) {{
    var p = all[i];
    var base = bases[String(p.id)];
    // A panel absent from the journal was never mutated by this transition.
    if (!base) continue;
    var fill = false;
    try {{ fill = (p.lengthMode == "fill"); }} catch (e) {{}}
    if (fill) {{
        if (p.height == base.height ||
                p.height == base.height + priorH ||
                p.height == base.height + targetH)
            p.height = base.height;
        else if (p.height != base.height) unresolved++;
    }} else {{
        if (p.offset == base.offset ||
                p.offset == base.offset + priorOff ||
                p.offset == base.offset + targetOff)
            p.offset = base.offset;
        else if (p.offset != base.offset) unresolved++;
    }}
}}
print(unresolved == 0 ? "restored-uncertain" : "unresolved-uncertain");
"""


def _parse_panel_map(output: str) -> dict | None:
    for line in reversed((output or "").strip().splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            return None
        try:
            return _validate_panels(parsed)
        except _StateError:
            return None
    return None


def _shift_was_normalized(output: str) -> bool:
    """Whether the generated script captured bases instead of advancing."""
    return any(line.strip() == "normalized" for line in output.splitlines())


def _shift_unlocked(max_px: int) -> int:
    offsets, heights = build_patterns(max_px)
    try:
        _prepare_state_unlocked()
        state = load_state()
    except _StateError as exc:
        print(f"oled care: {exc}", file=sys.stderr)
        return 1
    # Arm the persistent tombstone before asking Plasma to mutate. A crash,
    # failed save, and failed rollback therefore cannot expose a later timer
    # fire to state which does not describe the on-screen geometry.
    try:
        _disable_unlocked(_MARKER_TRANSITION)
    except OSError as exc:
        print(f"oled care: could not guard panel transition ({exc})",
              file=sys.stderr)
        return 1
    next_index = (state["index"] + 1) % len(offsets)
    next_off, next_h = offsets[next_index], heights[next_index]
    if not _save_transition(state, next_index, next_off, next_h):
        try:
            _clear_transition_files_unlocked()
        except OSError as exc:
            print(f"oled care: transition guard cleanup failed ({exc})",
                  file=sys.stderr)
        return 1
    output = _evaluate_script(
        build_shift_script(state["panels"], state["last_off"],
                           state["last_h"], next_off, next_h))
    if output is None:
        # Nothing shifted — keep state so the next fire resumes here.
        try:
            _clear_transition_files_unlocked()
        except OSError as exc:
            print(f"oled care: transition guard cleanup failed ({exc})",
                  file=sys.stderr)
            return 1
        return 0
    if output is _EVAL_UNCERTAIN:
        print("oled care: plasmashell transition outcome is uncertain",
              file=sys.stderr)
        return 1
    assert isinstance(output, str)
    panels = _parse_panel_map(output)
    if panels is None:
        print("oled care: could not parse panel state from plasmashell",
              file=sys.stderr)
        # Plasma may have applied the script before emitting malformed output.
        # Retain the guard because no trustworthy recovery state was saved.
        return 1
    normalized = _shift_was_normalized(output)
    applied_index = 0 if normalized else next_index
    applied_off = 0 if normalized else next_off
    applied_h = 0 if normalized else next_h
    recovery_state = dict(state)
    recovery_state["panels"] = panels
    if not _save_transition(
        recovery_state, applied_index, applied_off, applied_h,
    ):
        # The original pre-dispatch journal remains intact after the atomic
        # update failure. It covers every panel this fire was allowed to
        # mutate; newly discovered or user-rebased panels were skipped. Keep
        # the tombstone so restore can resolve that journal conservatively.
        print("oled care: transition journal update failed; panel recovery "
              "is pending", file=sys.stderr)
        return 1
    if not save_state({"index": applied_index, "last_off": applied_off,
                       "last_h": applied_h, "panels": panels}):
        # The updated journal is now the authoritative recovery record. Do not
        # attempt a best-effort rollback: another ambiguous Plasma call would
        # add outcomes, while a confirmed rollback could still mistake a user
        # edit for project-owned geometry. Fail closed until restore consumes
        # the journal.
        print("oled care: state save failed; panel recovery is pending",
              file=sys.stderr)
        return 1
    try:
        _clear_transition_files_unlocked()
    except OSError as exc:
        print(f"oled care: transition guard cleanup failed ({exc})",
              file=sys.stderr)
        return 1
    return 0


def shift(max_px: int = DEFAULT_MAX_SHIFT_PX) -> int:
    """Apply one shift while excluding other shifts and recovery.

    The tombstone is checked only after taking the lock.  Therefore teardown
    can wait for a mutation already in progress, create the marker, and know
    that every process reaching this point later will leave geometry alone.
    """
    try:
        # Timer/manual shift calls never queue. The operation already holding
        # the lock owns this transition, so this fire can safely be skipped.
        with _operation_lock(0.0) as acquired:
            if not acquired:
                return 0
            if _disabled_unlocked():
                return 0
            return _shift_unlocked(max_px)
    except OSError as exc:
        print(f"oled care: operation lock unavailable ({exc})",
              file=sys.stderr)
        return 1


def _restore_unlocked() -> int:
    path = _state_file()
    try:
        _prepare_state_unlocked()
    except _StateError as exc:
        print(f"oled care: {exc}", file=sys.stderr)
        return 1
    marker_state = _marker_state_unlocked()
    if marker_state not in {None, _MARKER_DISABLED, _MARKER_TRANSITION}:
        print("oled care: the panel transition marker is invalid",
              file=sys.stderr)
        return 1
    if marker_state == _MARKER_TRANSITION:
        try:
            transition = _read_transition()
        except _StateError as exc:
            print(f"oled care: {exc}", file=sys.stderr)
            return 1
        if transition is None:
            # The journal is removed only after no dispatch or after the new
            # state/rollback has become trustworthy. A leftover typed marker
            # alone can therefore be cleared without touching geometry.
            try:
                _finish_transition_unlocked()
            except OSError as exc:
                print(f"oled care: transition cleanup failed ({exc})",
                      file=sys.stderr)
                return 1
        else:
            prior = transition["prior"]
            target = transition["target"]
            if not prior["panels"]:
                print("oled care: uncertain geometry has no persisted panel "
                      "bases; manual recovery is required", file=sys.stderr)
                return 1
            output = _evaluate_script(build_uncertain_restore_script(
                prior["panels"], prior["last_off"], prior["last_h"],
                target["last_off"], target["last_h"],
            ))
            if output is None or output is _EVAL_UNCERTAIN:
                print("oled care: plasmashell unreachable — uncertain "
                      "geometry not restored", file=sys.stderr)
                return 1
            assert isinstance(output, str)
            if not any(line.strip() == "restored-uncertain"
                       for line in output.splitlines()):
                print("oled care: plasmashell did not confirm uncertain "
                      "geometry restoration", file=sys.stderr)
                return 1
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError as exc:
                print(f"oled care: geometry restored but state cleanup "
                      f"failed ({exc})", file=sys.stderr)
                return 1
            try:
                _clear_transition_files_unlocked()
            except OSError as exc:
                print(f"oled care: transition cleanup failed ({exc})",
                      file=sys.stderr)
                return 1
            return 0
    try:
        state = _read_existing_state()
    except _StateError as exc:
        print(f"oled care: {exc}", file=sys.stderr)
        return 1
    if state is None:
        return 0
    if not state["panels"]:
        # A timer can legitimately fire while Plasma has no panels and save an
        # empty map. There is no geometry to undo, but the existing state file
        # must still be consumed so disable/uninstall does not wait forever.
        try:
            path.unlink()
        except OSError as exc:
            print(f"oled care: empty panel state cleanup failed ({exc})",
                  file=sys.stderr)
            return 1
        return 0
    output = _evaluate_script(
        build_restore_script(state["panels"], state["last_off"],
                             state["last_h"]))
    if output is None or output is _EVAL_UNCERTAIN:
        # Keep state so a later restore can correct the residue. This command
        # is also used by uninstall/disable, which must know not to delete the
        # only recovery data or helper binary yet.
        print("oled care: plasmashell unreachable — geometry not restored",
              file=sys.stderr)
        return 1
    if not any(line.strip() == "restored" for line in output.splitlines()):
        print("oled care: plasmashell did not confirm geometry restoration",
              file=sys.stderr)
        return 1
    try:
        path.unlink()
    except OSError as exc:
        print(f"oled care: geometry restored but state cleanup failed ({exc})",
              file=sys.stderr)
        return 1
    return 0


def restore() -> int:
    """Restore geometry under the same lock used by scheduled shifts."""
    try:
        with _operation_lock(_LOCK_WAIT_SECONDS) as acquired:
            if not acquired:
                print("oled care: timed out waiting to restore panel geometry",
                      file=sys.stderr)
                return 1
            return _restore_unlocked()
    except OSError as exc:
        print(f"oled care: operation lock unavailable ({exc})",
              file=sys.stderr)
        return 1


def status() -> int:
    try:
        with _operation_lock(_LOCK_WAIT_SECONDS) as acquired:
            if not acquired:
                print("oled care: timed out reading panel state",
                      file=sys.stderr)
                return 1
            _prepare_state_unlocked()
            if _recovery_uncertain_unlocked():
                print("recovery pending (previous transition is uncertain)")
                return 1
            state = load_state()
    except (OSError, _StateError) as exc:
        print(f"oled care: {exc}", file=sys.stderr)
        return 1
    if not state["panels"]:
        print("inactive (no panel state)")
        return 0
    print(json.dumps(state, indent=2))
    return 0


USAGE = "Usage: mac-tahoe-oled-care {shift [--max-px N]|restore|status}"


def _parse_max_px(args: list[str]) -> int:
    max_px = DEFAULT_MAX_SHIFT_PX
    i = 0
    while i < len(args):
        if args[i] == "--max-px" and i + 1 < len(args):
            max_px = args[i + 1]
            i += 2
            continue
        if args[i].startswith("--max-px="):
            max_px = args[i].split("=", 1)[1]
        i += 1
    return clamp_max_px(max_px)


def main(argv: list[str]) -> int:
    if not argv:
        print(USAGE, file=sys.stderr)
        return 1
    cmd = argv[0]
    if cmd == "shift":
        return shift(_parse_max_px(argv[1:]))
    if cmd == "restore":
        return restore()
    if cmd == "status":
        return status()
    print(USAGE, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
