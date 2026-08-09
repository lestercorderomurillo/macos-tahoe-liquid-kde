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


def test_user_service_manager_command_is_init_gated(monkeypatch):
    monkeypatch.setenv("MTTKDE_INIT", "openrc")
    assert distro.user_service_manager_command("restart", "example") is None
    monkeypatch.setenv("MTTKDE_INIT", "systemd")
    assert distro.user_service_manager_command("restart", "example") == [
        "systemctl", "--user", "restart", "example",
    ]


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
    # Nothing was installed; cleanup finds no marked line.
    assert fake.lines is None
    assert _scheduler.remove_periodic("oled") is False


def test_systemd_cleanup_removes_cron_left_by_previous_openrc_boot(
        monkeypatch):
    fake = FakeCrontab()
    fake.lines = [
        "*/5 * * * * /bin/oled # mac-tahoe-liquid-kde:oled",
        "30 3 * * * /home/u/backup.sh",
    ]
    monkeypatch.setattr(_scheduler, "run_user", fake)
    monkeypatch.setattr(_scheduler, "_have_crontab", lambda: True)
    monkeypatch.setenv("MTTKDE_INIT", "systemd")

    assert _scheduler.remove_periodic("oled") is True
    assert fake.lines == ["30 3 * * * /home/u/backup.sh"]


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


def test_session_env_combines_runtime_and_process_sources(monkeypatch, tmp_path):
    """Scheduled jobs recover the session without querying an init-specific
    user manager: sockets provide DBus/Wayland and plasmashell fills X11."""
    import oled_care

    called = {"runtime": False, "process": False}
    monkeypatch.setattr(
        oled_care, "_sync_session_env_runtime_dir",
        lambda: called.__setitem__("runtime", True),
    )
    monkeypatch.setattr(
        oled_care, "_sync_session_env_from_plasmashell",
        lambda: called.__setitem__("process", True),
    )
    oled_care._sync_session_env()
    assert called == {"runtime": True, "process": True}


def test_generic_session_env_recovers_x11_from_plasmashell(
        monkeypatch, tmp_path):
    import utils

    proc = tmp_path / "proc"
    shell = proc / "123"
    shell.mkdir(parents=True)
    (shell / "comm").write_text("plasmashell\n")
    (shell / "environ").write_bytes(
        b"DISPLAY=:9\0XAUTHORITY=/tmp/xauth-test\0XDG_SESSION_TYPE=x11\0"
        b"XDG_MENU_PREFIX=plasma-\0")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setattr(utils, "_PROC_ROOT", proc)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    for key in ("DISPLAY", "XAUTHORITY", "XDG_SESSION_TYPE",
                "XDG_MENU_PREFIX"):
        monkeypatch.delenv(key, raising=False)

    utils.restore_desktop_session_env(os.getuid())

    assert os.environ["DISPLAY"] == ":9"
    assert os.environ["XAUTHORITY"] == "/tmp/xauth-test"
    assert os.environ["XDG_SESSION_TYPE"] == "x11"
    assert os.environ["XDG_MENU_PREFIX"] == "plasma-"


@pytest.mark.parametrize("module_name", ["oled_care", "theme_switch"])
def test_standalone_helpers_recover_x11_without_init_manager(
        monkeypatch, tmp_path, module_name):
    module = __import__(module_name)
    proc = tmp_path / f"proc-{module_name}"
    shell = proc / "321"
    shell.mkdir(parents=True)
    (shell / "comm").write_text("plasmashell\n")
    (shell / "environ").write_bytes(
        b"DISPLAY=:7\0XAUTHORITY=/tmp/xauth-standalone\0")
    monkeypatch.setattr(module, "_PROC_ROOT", proc)
    monkeypatch.setenv("SUDO_UID", str(os.getuid()))
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("XAUTHORITY", raising=False)

    module._sync_session_env_from_plasmashell()

    assert os.environ["DISPLAY"] == ":7"
    assert os.environ["XAUTHORITY"] == "/tmp/xauth-standalone"
