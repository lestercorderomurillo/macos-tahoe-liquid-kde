"""Session recovery for sudo installs, without contacting the live desktop."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import utils


@pytest.fixture
def session(monkeypatch, tmp_path):
    # Recovery adds keys itself; restore the whole environment even when a
    # variable was already absent before this fixture started.
    monkeypatch.setattr(os, "environ", os.environ.copy())
    uid = os.getuid()
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    proc = tmp_path / "proc"
    proc.mkdir()
    sockets = {runtime / "bus", runtime / "wayland-0"}
    for path in sockets:
        path.touch()
    # AF_UNIX bind is forbidden in some CI sandboxes. Model only socket type;
    # discovery, ownership, environment merging and CLI sequencing stay real.
    monkeypatch.setattr(Path, "is_socket", lambda path: path in sockets)
    monkeypatch.setattr(utils, "_PROC_ROOT", proc)
    monkeypatch.setattr(
        utils, "Path",
        lambda value: runtime if value == f"/run/user/{uid}" else Path(value),
    )
    for key in utils._DESKTOP_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SUDO_UID", str(uid))
    monkeypatch.setenv("SUDO_GID", str(os.getgid()))

    def plasmashell(**env):
        process = proc / "123"
        process.mkdir()
        (process / "comm").write_text("plasmashell\n")
        (process / "environ").write_bytes(
            b"\0".join(os.fsencode(f"{key}={value}")
                       for key, value in env.items()) + b"\0")
        return process

    return SimpleNamespace(uid=uid, runtime=runtime, proc=proc,
                           sockets=sockets, plasmashell=plasmashell)


@pytest.mark.parametrize("initial", ["missing", "empty", "nonexistent", "relative"])
def test_sudo_recovers_runtime_and_bus(session, monkeypatch, initial):
    if initial == "empty":
        for key in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY"):
            monkeypatch.setenv(key, "")
    elif initial == "nonexistent":
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(session.runtime / "gone"))
    elif initial == "relative":
        monkeypatch.setenv("XDG_RUNTIME_DIR", ".")

    utils.restore_desktop_session_env()

    assert os.environ["XDG_RUNTIME_DIR"] == str(session.runtime)
    assert os.environ["DBUS_SESSION_BUS_ADDRESS"] == f"unix:path={session.runtime}/bus"
    assert os.environ["WAYLAND_DISPLAY"] == "wayland-0"


def test_sudo_ignores_runtime_owned_by_another_user(session, monkeypatch, tmp_path):
    foreign = tmp_path / "foreign-runtime"
    foreign.mkdir()
    real_stat = Path.stat

    def stat(path, *args, **kwargs):
        result = real_stat(path, *args, **kwargs)
        if path == foreign:
            return SimpleNamespace(st_uid=session.uid + 1, st_mode=result.st_mode)
        return result

    monkeypatch.setattr(Path, "stat", stat)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(foreign))

    utils.restore_desktop_session_env()

    assert os.environ["XDG_RUNTIME_DIR"] == str(session.runtime)
    assert os.environ["DBUS_SESSION_BUS_ADDRESS"] == f"unix:path={session.runtime}/bus"


def test_plasma_session_address_takes_precedence_over_socket_guess(session):
    session.plasmashell(DBUS_SESSION_BUS_ADDRESS="unix:abstract=plasma-bus",
                       WAYLAND_DISPLAY="wayland-2")

    utils.restore_desktop_session_env()

    assert os.environ["DBUS_SESSION_BUS_ADDRESS"] == "unix:abstract=plasma-bus"
    assert os.environ["WAYLAND_DISPLAY"] == "wayland-2"


def test_custom_plasma_runtime_is_used_for_socket_fallback(session, tmp_path):
    custom = tmp_path / "plasma-runtime"
    custom.mkdir(mode=0o700)
    session.sockets.add(custom / "bus")
    session.plasmashell(XDG_RUNTIME_DIR=str(custom))

    utils.restore_desktop_session_env()

    assert os.environ["XDG_RUNTIME_DIR"] == str(custom)
    assert os.environ["DBUS_SESSION_BUS_ADDRESS"] == f"unix:path={custom}/bus"


def test_explicit_session_values_are_preserved(session, monkeypatch, tmp_path):
    custom = tmp_path / "explicit-runtime"
    custom.mkdir(mode=0o700)
    expected = {"XDG_RUNTIME_DIR": str(custom),
                "DBUS_SESSION_BUS_ADDRESS": "unix:abstract=explicit-bus",
                "WAYLAND_DISPLAY": "wayland-7", "DISPLAY": ":9"}
    for key, value in expected.items():
        monkeypatch.setenv(key, value)
    session.plasmashell(XDG_RUNTIME_DIR=str(session.runtime),
                       DBUS_SESSION_BUS_ADDRESS="unix:abstract=other-bus",
                       WAYLAND_DISPLAY="wayland-2", DISPLAY=":1")

    utils.restore_desktop_session_env()

    assert {key: os.environ[key] for key in expected} == expected


def test_recovery_uses_only_same_user_plasma_and_allowed_keys(session, monkeypatch):
    process = session.plasmashell(DISPLAY=":8", LD_PRELOAD="/untrusted.so")
    monkeypatch.delenv("LD_PRELOAD", raising=False)
    utils.restore_desktop_session_env()
    assert os.environ["DISPLAY"] == ":8"
    assert "LD_PRELOAD" not in os.environ

    monkeypatch.delenv("DISPLAY")
    real_stat = Path.stat
    monkeypatch.setattr(Path, "stat", lambda path, *a, **kw:
                        SimpleNamespace(st_uid=session.uid + 1) if path == process
                        else real_stat(path, *a, **kw))
    utils.restore_desktop_session_env()
    assert "DISPLAY" not in os.environ


def test_unreadable_proc_does_not_block_runtime_fallback(session, monkeypatch):
    real_iterdir = Path.iterdir

    def iterdir(path):
        if path == session.proc:
            raise PermissionError("proc unavailable")
        return real_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", iterdir)
    utils.restore_desktop_session_env()
    assert os.environ["DBUS_SESSION_BUS_ADDRESS"] == f"unix:path={session.runtime}/bus"


def test_regular_file_is_not_mistaken_for_session_bus(session):
    session.sockets.clear()
    utils.restore_desktop_session_env()
    assert "DBUS_SESSION_BUS_ADDRESS" not in os.environ


@pytest.mark.parametrize("initial", ["missing", "empty"])
def test_cli_recovers_env_before_oled_and_theme_service_operations(
        session, monkeypatch, tmp_path, initial):
    import cli
    import pwd
    from steps import oled_care, theme_switch

    if initial == "empty":
        monkeypatch.setenv("XDG_RUNTIME_DIR", "")
        monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "")
    monkeypatch.setenv("SUDO_USER", "test-user")
    for key in ("HOME", "USER", "LOGNAME"):
        monkeypatch.setenv(key, "before-sudo-recovery")
    monkeypatch.setenv("MTTKDE_INIT", "systemd")
    monkeypatch.setattr(pwd, "getpwuid",
                        lambda uid: SimpleNamespace(pw_dir=str(tmp_path)))
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    dropped = []
    monkeypatch.setattr(os, "setegid", lambda gid: dropped.append("gid"))
    monkeypatch.setattr(os, "seteuid", lambda uid: dropped.append("uid"))
    calls = []

    def run(argv, **kwargs):
        assert dropped == ["gid", "uid"]
        assert kwargs["preexec_fn"] is utils.drop_privs_in_child
        assert os.environ["XDG_RUNTIME_DIR"] == str(session.runtime)
        assert os.environ["DBUS_SESSION_BUS_ADDRESS"] == f"unix:path={session.runtime}/bus"
        assert argv[:2] == ["systemctl", "--user"]
        calls.append(argv)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(utils.subprocess, "run", run)

    assert cli._require_root_and_drop_to_user()
    assert oled_care._user_service("disable", "--now", oled_care.TIMER_UNIT)
    assert theme_switch._user_service(
        "enable", "--now", "mac-tahoe-liquid-kde-theme.timer")
    assert len(calls) == 2
