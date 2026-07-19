"""OpenRC scheduling backend (init_system detection + crontab writer).

The two timed features (OLED care, timed theme switch) fall back to a
per-user crontab line on OpenRC hosts, where there is no
``systemctl --user``. These tests force the OpenRC branch on the
(systemd) CI host via ``MTTKDE_INIT`` and exercise the crontab
marker/replace/remove logic against an in-memory fake crontab, so the
maintainer's real crontab is never read or written.
"""

from __future__ import annotations

import os

import pytest

import distro
from steps import _scheduler


# ── init detection ───────────────────────────────────────────────────


def test_init_system_env_override(monkeypatch):
    monkeypatch.setenv("MTTKDE_INIT", "openrc")
    assert distro.init_system() == "openrc"
    assert not _scheduler.is_systemd()
    monkeypatch.setenv("MTTKDE_INIT", "systemd")
    assert distro.init_system() == "systemd"
    assert _scheduler.is_systemd()


def test_init_system_ignores_garbage_override(monkeypatch):
    monkeypatch.setenv("MTTKDE_INIT", "upstart")
    # Falls through to the real probe rather than honoring a bad value.
    assert distro.init_system() in ("systemd", "openrc")


def test_crontab_dep_resolves_per_distro(monkeypatch):
    monkeypatch.setattr(distro, "_DISTRO_CACHE", "arch")
    assert distro.package_for("crontab") == "cronie"
    monkeypatch.setattr(distro, "_DISTRO_CACHE", "gentoo")
    assert distro.package_for("crontab") == "sys-process/cronie"


# ── fake crontab harness ─────────────────────────────────────────────


class FakeCrontab:
    """Stand-in for the user crontab. Intercepts the exact ``crontab``
    argv shapes the scheduler uses (-l read, -r remove, - stdin write)."""

    def __init__(self):
        self.lines: list[str] | None = None  # None = no crontab installed

    def __call__(self, argv, **kwargs):
        assert argv[0] == "crontab"
        flag = argv[1]
        if flag == "-l":
            if self.lines is None:
                return _Result(1, "", "no crontab for tester\n")
            return _Result(0, "\n".join(self.lines) + "\n", "")
        if flag == "-r":
            self.lines = None
            return _Result(0, "", "")
        if flag == "-":
            body = kwargs.get("input", "")
            self.lines = [ln for ln in body.splitlines() if ln.strip()]
            return _Result(0, "", "")
        raise AssertionError(f"unexpected crontab argv: {argv}")


class _Result:
    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture
def fake_cron(monkeypatch):
    fake = FakeCrontab()
    monkeypatch.setattr(_scheduler, "run_user", fake)
    # The fake stands in for a REAL crontab client, so report one present —
    # otherwise the _have_crontab() guard (which shutil.which's the binary,
    # absent on the CI host) short-circuits before the fake runs.
    monkeypatch.setattr(_scheduler, "_have_crontab", lambda: True)
    monkeypatch.setenv("MTTKDE_INIT", "openrc")
    return fake


# ── crontab writer ───────────────────────────────────────────────────


def test_install_periodic_writes_marked_interval_line(fake_cron):
    _scheduler.install_periodic("oled", 5, "/bin/oled shift")
    assert fake_cron.lines == [
        "*/5 * * * * /bin/oled shift # mac-tahoe-liquid-kde:oled"
    ]


def test_install_periodic_clamps_interval(fake_cron):
    _scheduler.install_periodic("oled", 0, "/bin/oled")
    assert fake_cron.lines[0].startswith("*/1 ")
    _scheduler.install_periodic("oled", 999, "/bin/oled")
    assert fake_cron.lines[0].startswith("*/59 ")


def test_install_at_times_writes_one_line_per_time(fake_cron):
    _scheduler.install_at_times("theme", [(6, 0), (18, 0)], "/bin/theme auto")
    assert fake_cron.lines == [
        "0 6 * * * /bin/theme auto # mac-tahoe-liquid-kde:theme",
        "0 18 * * * /bin/theme auto # mac-tahoe-liquid-kde:theme",
    ]


def test_install_replaces_our_own_tag_only(fake_cron):
    # A pre-existing unrelated user line must survive our rewrite.
    fake_cron.lines = ["30 3 * * * /home/u/backup.sh"]
    _scheduler.install_periodic("oled", 5, "/bin/oled")
    # Re-install with a new interval — our old line is replaced, not stacked.
    _scheduler.install_periodic("oled", 10, "/bin/oled")
    ours = [ln for ln in fake_cron.lines if "mac-tahoe-liquid-kde:oled" in ln]
    assert len(ours) == 1 and ours[0].startswith("*/10 ")
    assert "30 3 * * * /home/u/backup.sh" in fake_cron.lines


def test_remove_periodic_strips_only_our_line(fake_cron):
    fake_cron.lines = ["30 3 * * * /home/u/backup.sh"]
    _scheduler.install_periodic("oled", 5, "/bin/oled")
    assert _scheduler.remove_periodic("oled") is True
    assert fake_cron.lines == ["30 3 * * * /home/u/backup.sh"]
    # Idempotent: a second remove reports nothing was ours.
    assert _scheduler.remove_periodic("oled") is False


def test_remove_periodic_removes_empty_crontab_entirely(fake_cron):
    _scheduler.install_periodic("oled", 5, "/bin/oled")
    _scheduler.remove_periodic("oled")
    # Sole line was ours → crontab fully removed, not left blank.
    assert fake_cron.lines is None


def test_scheduler_is_noop_on_systemd(monkeypatch):
    fake = FakeCrontab()
    monkeypatch.setattr(_scheduler, "run_user", fake)
    monkeypatch.setenv("MTTKDE_INIT", "systemd")
    # No-op on systemd, but still reports success so the caller doesn't warn.
    assert _scheduler.install_periodic("oled", 5, "/bin/oled") is True
    assert _scheduler.install_at_times("theme", [(6, 0)], "/bin/theme") is True
    # Never touched crontab at all.
    assert fake.lines is None
    assert _scheduler.remove_periodic("oled") is False


def test_install_reports_failure_when_crontab_write_fails(monkeypatch):
    """No cron daemon → the write fails and install returns False so the
    step can warn instead of silently scheduling nothing."""
    monkeypatch.setenv("MTTKDE_INIT", "openrc")

    def failing(argv, **kwargs):
        if argv[1] == "-l":
            return _Result(1, "", "no crontab\n")
        return _Result(1, "", "crontab: command not found\n")

    monkeypatch.setattr(_scheduler, "run_user", failing)
    assert _scheduler.install_periodic("oled", 5, "/bin/oled") is False
    assert _scheduler.install_at_times("theme", [(6, 0)], "/bin/x") is False


# ── session-env fallback (OpenRC/cron path reaches the desktop) ───────


def test_session_env_runtime_dir_recovers_wayland_and_bus(monkeypatch, tmp_path):
    import oled_care

    xrd = tmp_path / "run-user"
    xrd.mkdir()
    # A wayland socket + dbus bus, as elogind lays them out.
    import socket
    for name in ("wayland-1", "wayland-0", "bus"):
        s = socket.socket(socket.AF_UNIX)
        s.bind(str(xrd / name))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(xrd))
    for k in ("WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS"):
        monkeypatch.delenv(k, raising=False)

    oled_care._sync_session_env_runtime_dir()
    # Lowest-numbered wayland socket wins; bare name (Qt resolves it).
    assert os.environ["WAYLAND_DISPLAY"] == "wayland-0"
    assert os.environ["DBUS_SESSION_BUS_ADDRESS"] == f"unix:path={xrd / 'bus'}"


def test_session_env_falls_back_when_systemd_query_fails(monkeypatch, tmp_path):
    """_sync_session_env tries systemd first; when that fails (OpenRC has
    no user manager) it must reach the runtime-dir probe."""
    import oled_care

    monkeypatch.setattr(oled_care, "_sync_session_env_systemd", lambda: False)
    called = {"runtime": False}
    monkeypatch.setattr(
        oled_care, "_sync_session_env_runtime_dir",
        lambda: called.__setitem__("runtime", True),
    )
    oled_care._sync_session_env()
    assert called["runtime"] is True
