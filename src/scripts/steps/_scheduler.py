"""Init-agnostic scheduling for the two timed features (OLED care, timed
theme switch). Under systemd each feature installs a user timer; under
OpenRC there is no ``systemctl --user``, so we fall back to a per-user
``crontab`` line running the same binary on the same cadence.

The backend is chosen once by :func:`distro.init_system`. Steps call
:func:`install_periodic` / :func:`remove_periodic` and stay ignorant of
which init is live. The crontab writer is marker-delimited so it only
ever touches its own block — a user's unrelated cron lines are preserved.
"""

import shutil
import subprocess

from distro import init_system
from utils import run_user


def is_systemd() -> bool:
    return init_system() == "systemd"


def _have_crontab() -> bool:
    """Whether a crontab client is on PATH. OpenRC hosts without a cron
    daemon (and the CI runner) have none — calling it would raise
    FileNotFoundError, so every crontab op guards on this first."""
    return shutil.which("crontab") is not None


# ── crontab backend ──────────────────────────────────────────────────
#
# Each managed line is tagged with a trailing marker comment so we can
# find and strip exactly our own entry without a fragile grep on the
# command. The whole crontab is read, filtered, and written back atomically
# via ``crontab -`` (stdin) — there is no per-line crontab edit primitive.


def _marker(tag: str) -> str:
    return f"# mac-tahoe-liquid-kde:{tag}"


def _read_crontab() -> list[str]:
    """Current user crontab lines, or [] when none is installed. A missing
    crontab exits non-zero with "no crontab for <user>" on stderr — that's
    not an error, it's the empty case. No crontab client at all (no cron
    daemon / CI) is also just the empty case, not a crash."""
    if not _have_crontab():
        return []
    res = run_user(
        ["crontab", "-l"],
        check=False, capture_output=True, text=True,
    )
    if res.returncode != 0:
        return []
    return res.stdout.splitlines()


def _write_crontab(lines: list[str]) -> bool:
    """Replace the user crontab. An empty list removes it entirely
    (``crontab -r``) rather than installing a blank one. Returns False when
    no crontab client is available (nothing was scheduled) so the caller can
    warn instead of crashing."""
    if not _have_crontab():
        return False
    if not any(line.strip() for line in lines):
        run_user(
            ["crontab", "-r"],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    body = "\n".join(lines).rstrip("\n") + "\n"
    res = run_user(
        ["crontab", "-"],
        check=False, input=body, text=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return res.returncode == 0


def _strip_tag(lines: list[str], tag: str) -> list[str]:
    marker = _marker(tag)
    return [line for line in lines if not line.rstrip().endswith(marker)]


def _cron_install(tag: str, minutes: int, command: str) -> bool:
    """Install (or replace) a ``*/minutes`` cron line for ``tag``. Clamped
    to 1..59 so the ``*/N`` field stays valid."""
    minutes = max(1, min(59, minutes))
    lines = _strip_tag(_read_crontab(), tag)
    lines.append(f"*/{minutes} * * * * {command} {_marker(tag)}")
    return _write_crontab(lines)


def _cron_install_at(tag: str, times: list[tuple[int, int]], command: str) -> bool:
    """Install one fixed-time (``MM HH * * *``) cron line per (hour, minute)
    in ``times``, replacing any previous lines for ``tag``."""
    lines = _strip_tag(_read_crontab(), tag)
    for hour, minute in times:
        h = max(0, min(23, hour))
        m = max(0, min(59, minute))
        lines.append(f"{m} {h} * * * {command} {_marker(tag)}")
    return _write_crontab(lines)


def _cron_remove(tag: str) -> bool:
    before = _read_crontab()
    after = _strip_tag(before, tag)
    if after == before:
        return False
    _write_crontab(after)
    return True


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


def remove_periodic(tag: str) -> bool:
    """Remove the crontab line for ``tag`` if present. Safe to call on
    systemd (returns False — nothing was ours to remove)."""
    if is_systemd():
        return False
    return _cron_remove(tag)
