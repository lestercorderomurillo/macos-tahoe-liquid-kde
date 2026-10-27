"""OpenRC/dinit scheduling backend (init detection + crontab writer).

The two timed features (OLED care, timed theme switch) fall back to a
per-user crontab line on OpenRC hosts, where there is no
``systemctl --user``. These tests force the OpenRC branch on the
(systemd) CI host via ``MTTKDE_INIT`` and exercise the crontab
marker/replace/remove logic against an in-memory fake crontab, so the
maintainer's real crontab is never read or written.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

import distro
from steps import _scheduler


# ── init detection ───────────────────────────────────────────────────


@pytest.mark.parametrize("backend", ["openrc", "dinit"])
def test_init_system_env_override(monkeypatch, backend):
    monkeypatch.setenv("MTTKDE_INIT", backend)
    assert distro.init_system() == backend
    assert not _scheduler.is_systemd()
    monkeypatch.setenv("MTTKDE_INIT", "systemd")
    assert distro.init_system() == "systemd"
    assert _scheduler.is_systemd()


@pytest.mark.parametrize("backend", ["openrc", "dinit"])
def test_user_service_manager_command_is_init_gated(monkeypatch, backend):
    monkeypatch.setenv("MTTKDE_INIT", backend)
    assert distro.user_service_manager_command("restart", "example") is None
    monkeypatch.setenv("MTTKDE_INIT", "systemd")
    assert distro.user_service_manager_command("restart", "example") == [
        "systemctl", "--user", "restart", "example",
    ]


def test_init_system_ignores_garbage_override(monkeypatch):
    monkeypatch.setenv("MTTKDE_INIT", "upstart")
    # Falls through to the real probe rather than honoring a bad value.
    assert distro.init_system() in ("systemd", "openrc", "dinit")


@pytest.mark.parametrize("systemd,comm,executable,expected", [
    (False, "dinit", None, "dinit"),
    (False, "init", "/usr/bin/dinit", "dinit"),
    (False, "init", "/usr/bin/dinit (deleted)", "dinit"),
    (False, "init", "/sbin/openrc-init", "openrc"),
    (False, None, None, "openrc"),
    (True, "dinit", "/usr/bin/dinit", "systemd"),
])
def test_init_detection_uses_pid_one(
        monkeypatch, tmp_path, systemd, comm, executable, expected):
    proc = tmp_path / "proc"
    init = proc / "1"
    init.mkdir(parents=True)
    if comm is not None:
        (init / "comm").write_text(comm + "\n")
    if executable is not None:
        (init / "exe").symlink_to(executable)
    # A user dinit instance must never change the system backend.
    user = proc / "123"
    user.mkdir()
    (user / "comm").write_text("dinit\n")
    marker = tmp_path / "systemd"
    if systemd:
        marker.mkdir()
    monkeypatch.setattr(distro, "_PROC_ROOT", proc)
    monkeypatch.setattr(distro, "_SYSTEMD_MARKER", marker)
    monkeypatch.setattr(distro, "_INIT_CACHE", None)
    monkeypatch.delenv("MTTKDE_INIT", raising=False)
    assert distro.init_system() == expected
    assert (distro.user_service_manager_command("daemon-reload") is None) == (expected != "systemd")


def test_crontab_dep_resolves_per_distro(monkeypatch):
    monkeypatch.setattr(distro, "distro_id_like", lambda: ())
    monkeypatch.setattr(distro, "_DISTRO_CACHE", "arch")
    assert distro.package_for("crontab") == "cronie"
    monkeypatch.setattr(distro, "_DISTRO_CACHE", "artix")
    assert distro.package_for("crontab") == "cronie"


@pytest.mark.parametrize("backend", ["systemd", "openrc", "dinit"])
def test_cron_dependencies_only_for_enabled_schedules(monkeypatch, backend):
    from steps import oled_care, theme_switch

    monkeypatch.setenv("MTTKDE_INIT", backend)
    monkeypatch.setenv("THEME_MODE", "light")
    monkeypatch.setenv("FEAT_OLED_CARE", "false")
    assert theme_switch.deps() == []
    assert oled_care.deps() == []
    monkeypatch.setenv("THEME_MODE", "auto")
    monkeypatch.setenv("FEAT_OLED_CARE", "true")
    expected = [] if backend == "systemd" else ["crontab"]
    assert theme_switch.deps() == expected
    assert oled_care.deps() == expected


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


@pytest.fixture(params=["openrc", "dinit"])
def fake_cron(monkeypatch, request):
    fake = FakeCrontab()
    monkeypatch.setattr(_scheduler, "run_user", fake)
    # The fake stands in for a REAL crontab client, so report one present —
    # otherwise the _have_crontab() guard (which shutil.which's the binary,
    # absent on the CI host) short-circuits before the fake runs.
    monkeypatch.setattr(_scheduler, "_have_crontab", lambda: True)
    monkeypatch.setenv("MTTKDE_INIT", request.param)
    monkeypatch.setattr(_scheduler, "cron_daemon_running", lambda: True)
    return fake


@pytest.mark.parametrize("running", [False, True])
def test_scheduling_warns_if_cron_daemon_is_not_confirmed(
        fake_cron, monkeypatch, running):
    warnings = []
    monkeypatch.setattr(_scheduler, "cron_daemon_running", lambda: running)
    monkeypatch.setattr(_scheduler, "warn", warnings.append)
    assert _scheduler.install_periodic("oled", 5, "/bin/oled")
    assert _scheduler.install_at_times("theme", [(6, 0)], "/bin/theme")
    assert len(fake_cron.lines) == 2
    assert len(warnings) == (0 if running else 2)
    assert all("cron daemon" in message for message in warnings)


@pytest.mark.parametrize("name,uid,expected", [
    ("crond", 0, True), ("cron", 0, True), ("dcron", 0, True),
    ("crontab", 0, False), ("crond", 1000, False),
])
def test_cron_daemon_probe_checks_process_and_owner(
        monkeypatch, tmp_path, name, uid, expected):
    from types import SimpleNamespace

    process = tmp_path / "42"
    process.mkdir()
    (process / "comm").write_text(name + "\n")
    monkeypatch.setattr(distro, "_PROC_ROOT", tmp_path)
    original_stat = Path.stat
    monkeypatch.setattr(Path, "stat", lambda path, **kw:
                        SimpleNamespace(st_uid=uid) if path == process
                        else original_stat(path, **kw))
    assert distro.cron_daemon_running() is expected


def test_cron_daemon_probe_handles_inaccessible_proc(monkeypatch, tmp_path):
    monkeypatch.setattr(distro, "_PROC_ROOT", tmp_path / "missing")
    assert distro.cron_daemon_running() is False


# ── crontab writer ───────────────────────────────────────────────────


def test_install_periodic_writes_marked_interval_line(fake_cron):
    _scheduler.install_periodic("oled", 5, "/bin/oled shift")
    assert fake_cron.lines == [
        "*/5 * * * * /bin/oled shift # mac-tahoe-liquid-kde:oled"
    ]


def test_crontab_read_write_and_remove_force_c_locale(fake_cron, monkeypatch):
    calls: list[tuple[list[str], dict[str, str]]] = []
    real_call = fake_cron.__call__
    monkeypatch.setenv("LANG", "es_CR.UTF-8")
    monkeypatch.setenv("LC_ALL", "es_CR.UTF-8")
    monkeypatch.setenv("MTTKDE_CRON_ENV_SENTINEL", "preserved")

    def capture_env(argv, **kwargs):
        calls.append((list(argv), kwargs["env"]))
        return real_call(argv, **kwargs)

    monkeypatch.setattr(_scheduler, "run_user", capture_env)

    assert _scheduler.install_periodic("oled", 5, "/bin/oled") is True
    assert _scheduler.remove_periodic(
        "oled",
    ) == _scheduler.RemovalStatus.REMOVED

    assert [argv for argv, _env in calls] == [
        ["crontab", "-l"],
        ["crontab", "-"],
        ["crontab", "-l"],
        ["crontab", "-r"],
    ]
    assert all(env["LANG"] == "C" and env["LC_ALL"] == "C"
               for _argv, env in calls)
    assert all(env["MTTKDE_CRON_ENV_SENTINEL"] == "preserved"
               for _argv, env in calls)


def test_cron_command_quotes_shell_arguments_and_escapes_percent():
    rendered = _scheduler.cron_command(
        "/home/Test User/100%/bin/switcher", "auto", "quote'value",
    )

    assert r"\%" in rendered
    # Cron consumes the percent escape before passing the command to /bin/sh.
    import shlex
    assert shlex.split(rendered.replace(r"\%", "%")) == [
        "/home/Test User/100%/bin/switcher", "auto", "quote'value",
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
    assert _scheduler.remove_periodic("oled") == _scheduler.RemovalStatus.REMOVED
    assert fake_cron.lines == ["30 3 * * * /home/u/backup.sh"]
    # Idempotent: a second remove reports nothing was ours.
    assert _scheduler.remove_periodic("oled") == _scheduler.RemovalStatus.ABSENT


def test_remove_periodic_removes_empty_crontab_entirely(fake_cron):
    _scheduler.install_periodic("oled", 5, "/bin/oled")
    _scheduler.remove_periodic("oled")
    # Sole line was ours → crontab fully removed, not left blank.
    assert fake_cron.lines is None


def test_scheduler_is_noop_on_systemd(monkeypatch):
    fake = FakeCrontab()
    monkeypatch.setattr(_scheduler, "run_user", fake)
    # Make the intended no-client cleanup branch independent of the host
    # image: KDE neon ships ``crontab``, while several other CI images do not.
    monkeypatch.setattr(_scheduler, "_have_crontab", lambda: False)
    monkeypatch.setenv("MTTKDE_INIT", "systemd")
    # No-op on systemd, but still reports success so the caller doesn't warn.
    assert _scheduler.install_periodic("oled", 5, "/bin/oled") is True
    assert _scheduler.install_at_times("theme", [(6, 0)], "/bin/theme") is True
    # Nothing was installed; cleanup finds no marked line.
    assert fake.lines is None
    assert (_scheduler.remove_periodic("oled")
            == _scheduler.RemovalStatus.UNAVAILABLE)


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

    assert _scheduler.remove_periodic("oled") == _scheduler.RemovalStatus.REMOVED
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


def test_read_timeout_never_replaces_the_user_crontab(monkeypatch):
    """A failed read is not proof that the crontab is empty. In particular,
    never feed it into the read/modify/replace path and erase unrelated jobs."""
    calls: list[list[str]] = []

    def timeout(argv, **_kwargs):
        calls.append(argv)
        raise subprocess.TimeoutExpired(argv, 10)

    monkeypatch.setenv("MTTKDE_INIT", "openrc")
    monkeypatch.setattr(_scheduler, "_have_crontab", lambda: True)
    monkeypatch.setattr(_scheduler, "run_user", timeout)

    assert _scheduler.install_periodic("oled", 5, "/bin/oled") is False
    assert _scheduler.install_at_times(
        "theme", [(6, 0)], "/bin/theme auto",
    ) is False
    assert calls == [["crontab", "-l"], ["crontab", "-l"]]


def test_nonempty_crontab_read_error_never_triggers_a_write(monkeypatch):
    calls: list[list[str]] = []

    def denied(argv, **_kwargs):
        calls.append(argv)
        return _Result(2, "", "permission denied reading cron spool\n")

    monkeypatch.setenv("MTTKDE_INIT", "openrc")
    monkeypatch.setattr(_scheduler, "_have_crontab", lambda: True)
    monkeypatch.setattr(_scheduler, "run_user", denied)

    assert _scheduler.install_periodic("oled", 5, "/bin/oled") is False
    assert calls == [["crontab", "-l"]]


def test_remove_reports_write_timeout_and_preserves_existing_jobs(
        fake_cron, monkeypatch):
    fake_cron.lines = [
        "*/5 * * * * /bin/oled # mac-tahoe-liquid-kde:oled",
        "30 3 * * * /home/u/backup.sh",
    ]
    real_call = fake_cron.__call__

    def timeout_write(argv, **kwargs):
        if argv[1] == "-":
            raise subprocess.TimeoutExpired(argv, 10)
        return real_call(argv, **kwargs)

    monkeypatch.setattr(_scheduler, "run_user", timeout_write)

    assert _scheduler.remove_periodic("oled") == _scheduler.RemovalStatus.ERROR
    assert fake_cron.lines == [
        "*/5 * * * * /bin/oled # mac-tahoe-liquid-kde:oled",
        "30 3 * * * /home/u/backup.sh",
    ]


def test_remove_empty_crontab_propagates_remove_failure(fake_cron, monkeypatch):
    fake_cron.lines = [
        "*/5 * * * * /bin/oled # mac-tahoe-liquid-kde:oled",
    ]
    real_call = fake_cron.__call__

    def reject_remove(argv, **kwargs):
        if argv[1] == "-r":
            return _Result(1, "", "could not remove crontab\n")
        return real_call(argv, **kwargs)

    monkeypatch.setattr(_scheduler, "run_user", reject_remove)

    assert _scheduler.remove_periodic("oled") == _scheduler.RemovalStatus.ERROR
    assert fake_cron.lines is not None


# ── session-env fallback (OpenRC/cron path reaches the desktop) ───────


def test_session_env_runtime_dir_recovers_wayland_and_bus(monkeypatch, tmp_path):
    import oled_care

    xrd = tmp_path / "run-user"
    xrd.mkdir()
    # Model the Wayland + DBus sockets elogind lays out.  Some hardened test
    # sandboxes forbid AF_UNIX bind even below tmp_path, so keep this unit test
    # focused on discovery/selection and mock only the file-type predicate.
    sockets = {xrd / name for name in ("wayland-1", "wayland-0", "bus")}
    for path in sockets:
        path.touch()
    real_is_socket = Path.is_socket
    monkeypatch.setattr(
        Path, "is_socket",
        lambda path: path in sockets or real_is_socket(path),
    )
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
