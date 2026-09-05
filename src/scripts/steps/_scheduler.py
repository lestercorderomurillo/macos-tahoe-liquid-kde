"""Init-agnostic scheduling for the two timed features (OLED care, timed
theme switch). Under systemd each feature installs a user timer; under
OpenRC there is no user service manager, so we fall back to a per-user
``crontab`` line running the same binary on the same cadence.

The backend is chosen once by :func:`distro.init_system`. Steps call
:func:`install_periodic` / :func:`remove_periodic` and stay ignorant of
which init is live. The crontab writer is marker-delimited so it only
ever touches its own block — a user's unrelated cron lines are preserved.
"""

import os
import shlex
import shutil
import subprocess
from enum import Enum

from distro import init_system
from utils import run_user


class RemovalStatus(str, Enum):
    """Outcome of removing one managed cron entry.

    ``ABSENT`` is a proven clean state; ``UNAVAILABLE`` means no crontab
    client exists to inspect the spool; ``ERROR`` means a present client
    failed to read or rewrite it. Callers need this distinction when an old
    schedule could keep invoking a retained helper.
    """

    REMOVED = "removed"
    ABSENT = "absent"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


def is_systemd() -> bool:
    return init_system() == "systemd"


def _have_crontab() -> bool:
    """Whether a crontab client is on PATH. OpenRC hosts without a cron
    daemon (and the CI runner) have none — calling it would raise
    FileNotFoundError, so every crontab op guards on this first."""
    return shutil.which("crontab") is not None


def _crontab_env() -> dict[str, str]:
    """Preserve the user environment but stabilize crontab diagnostics.

    ``crontab -l`` uses a non-zero status for both an empty spool and real
    errors, so the ordinary "no crontab" message is the only portable way to
    distinguish them. Force that one subprocess family to the C locale so a
    translated diagnostic cannot turn a first install into a false failure.
    """
    env = os.environ.copy()
    env["LANG"] = "C"
    env["LC_ALL"] = "C"
    return env


def cron_command(*argv: object) -> str:
    """Render argv for cron's shell without losing valid path characters.

    Cron treats an unescaped ``%`` as a newline before invoking the shell,
    even inside quotes. Quote each argument for the shell first, then escape
    percent signs for cron's own parser.
    """
    return " ".join(shlex.quote(str(arg)).replace("%", r"\%") for arg in argv)


# ── crontab backend ──────────────────────────────────────────────────
#
# Each managed line is tagged with a trailing marker comment so we can
# find and strip exactly our own entry without a fragile grep on the
# command. The whole crontab is read, filtered, and written back atomically
# via ``crontab -`` (stdin) — there is no per-line crontab edit primitive.


def _marker(tag: str) -> str:
    return f"# mac-tahoe-liquid-kde:{tag}"


def _read_crontab() -> list[str] | None:
    """Current user crontab lines, ``[]`` when none is installed, or
    ``None`` when the current crontab could not be read safely.

    Read failure must stay distinct from an empty crontab: callers perform a
    read/modify/replace operation, so treating a timeout or arbitrary error as
    empty would replace all unrelated user jobs with only our managed line.
    """
    if not _have_crontab():
        return None
    try:
        res = run_user(
            ["crontab", "-l"],
            check=False, capture_output=True, text=True, timeout=10,
            env=_crontab_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        # Cron implementations differ slightly, but all supported clients
        # include "no crontab" in the ordinary first-use diagnostic. Refuse
        # to rewrite on every other error (locked/corrupt spool, permissions,
        # daemon failure, etc.).
        if "no crontab" in (res.stderr or "").lower():
            return []
        return None
    return res.stdout.splitlines()


def _write_crontab(lines: list[str]) -> bool:
    """Replace the user crontab. An empty list removes it entirely
    (``crontab -r``) rather than installing a blank one. Returns False when
    no crontab client is available (nothing was scheduled) so the caller can
    warn instead of crashing."""
    if not _have_crontab():
        return False
    try:
        if not any(line.strip() for line in lines):
            res = run_user(
                ["crontab", "-r"],
                check=False, timeout=10,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=_crontab_env(),
            )
            return res.returncode == 0
        body = "\n".join(lines).rstrip("\n") + "\n"
        res = run_user(
            ["crontab", "-"],
            check=False, input=body, text=True, timeout=10,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=_crontab_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return res.returncode == 0


def _strip_tag(lines: list[str], tag: str) -> list[str]:
    marker = _marker(tag)
    return [line for line in lines if not line.rstrip().endswith(marker)]


def _cron_install(tag: str, minutes: int, command: str) -> bool:
    """Install (or replace) a ``*/minutes`` cron line for ``tag``. Clamped
    to 1..59 so the ``*/N`` field stays valid."""
    minutes = max(1, min(59, minutes))
    current = _read_crontab()
    if current is None:
        return False
    lines = _strip_tag(current, tag)
    lines.append(f"*/{minutes} * * * * {command} {_marker(tag)}")
    return _write_crontab(lines)


def _cron_install_at(tag: str, times: list[tuple[int, int]], command: str) -> bool:
    """Install one fixed-time (``MM HH * * *``) cron line per (hour, minute)
    in ``times``, replacing any previous lines for ``tag``."""
    current = _read_crontab()
    if current is None:
        return False
    lines = _strip_tag(current, tag)
    for hour, minute in times:
        h = max(0, min(23, hour))
        m = max(0, min(59, minute))
        lines.append(f"{m} {h} * * * {command} {_marker(tag)}")
    return _write_crontab(lines)


def _cron_remove(tag: str) -> RemovalStatus:
    if not _have_crontab():
        return RemovalStatus.UNAVAILABLE
    before = _read_crontab()
    if before is None:
        return RemovalStatus.ERROR
    after = _strip_tag(before, tag)
    if after == before:
        return RemovalStatus.ABSENT
    if not _write_crontab(after):
        return RemovalStatus.ERROR
    return RemovalStatus.REMOVED


# ── public API ───────────────────────────────────────────────────────


def install_periodic(tag: str, minutes: int, command: str) -> bool:
    """OpenRC-only: schedule ``command`` every ``minutes`` via crontab.
    On systemd this is a no-op returning True — the caller installs a
    user timer instead. Returns False if the crontab write failed (e.g.
    no cron daemon), so the caller can warn instead of silently no-op'ing."""
    if is_systemd():
        return True
    return _cron_install(tag, minutes, command)


def install_at_times(tag: str, times: list[tuple[int, int]], command: str) -> bool:
    """OpenRC-only: schedule ``command`` at each fixed ``(hour, minute)``
    via crontab. On systemd this is a no-op returning True — the caller
    installs a user timer with the equivalent ``OnCalendar`` lines instead.
    Returns False if the crontab write failed."""
    if is_systemd():
        return True
    return _cron_install_at(tag, times, command)


def remove_periodic(tag: str) -> RemovalStatus:
    """Remove our crontab line regardless of the currently-running init.

    A user can switch init systems between installs. Looking only at today's
    backend would strand an old OpenRC cron entry on a later systemd boot.
    The marker filter touches no unrelated user lines.
    """
    return _cron_remove(tag)
