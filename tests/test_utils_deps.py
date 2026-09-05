import os
import signal
import subprocess
import sys
import textwrap

import pytest

import utils


# ── GUI cancellation token / process-group monitor ───────────────────


def test_cancel_token_is_empty_until_requested(monkeypatch, tmp_path):
    token = tmp_path / "cancel"
    token.write_text("")
    token.chmod(0o600)
    monkeypatch.setenv("MTTKDE_CANCEL_FILE", str(token))
    monkeypatch.delenv("SUDO_UID", raising=False)

    assert utils.cancellation_requested() is False
    token.write_text("cancel\n")
    assert utils.cancellation_requested() is True
    with pytest.raises(utils.CancellationRequested):
        utils.check_cancelled()


def test_cancel_token_fails_closed_when_missing_or_replaced(
        monkeypatch, tmp_path):
    token = tmp_path / "cancel"
    monkeypatch.setenv("MTTKDE_CANCEL_FILE", str(token))
    monkeypatch.delenv("SUDO_UID", raising=False)

    assert utils.cancellation_requested() is True

    victim = tmp_path / "victim"
    victim.write_text("")
    token.symlink_to(victim)
    assert utils.cancellation_requested() is True

    token.unlink()
    os.link(victim, token)
    assert utils.cancellation_requested() is True


def test_cancel_token_rejects_wrong_owner(monkeypatch, tmp_path):
    token = tmp_path / "cancel"
    token.write_text("")
    token.chmod(0o600)
    monkeypatch.setenv("MTTKDE_CANCEL_FILE", str(token))
    monkeypatch.setattr(utils, "_cancel_file_owner", lambda: os.getuid() + 1)

    assert utils.cancellation_requested() is True


def test_cancel_group_accepts_already_group_leader_when_setsid_fails(
        monkeypatch):
    monkeypatch.setattr(
        utils.os, "setsid",
        lambda: (_ for _ in ()).throw(PermissionError("already leader")),
    )
    monkeypatch.setattr(utils.os, "getpid", lambda: 4242)
    monkeypatch.setattr(utils.os, "getpgrp", lambda: 4242)

    assert utils._isolate_cancel_process_group() is True


def test_cancel_group_rejects_unisolated_shared_group(monkeypatch):
    monkeypatch.setattr(
        utils.os, "setsid",
        lambda: (_ for _ in ()).throw(PermissionError("blocked")),
    )
    monkeypatch.setattr(utils.os, "getpid", lambda: 4242)
    monkeypatch.setattr(utils.os, "getpgrp", lambda: 4000)

    assert utils._isolate_cancel_process_group() is False


def test_cancel_monitor_interrupts_long_child_and_exits_130(
        monkeypatch, tmp_path):
    """Real-process regression: cancellation reaches an active descendant.

    Run the session/process-group manipulation in a child so pytest's own
    process group and signal handlers can never be affected by a failure.
    """
    token = tmp_path / "cancel"
    token.write_text("")
    token.chmod(0o600)
    script = textwrap.dedent("""
        import subprocess
        from utils import CancellationRequested, cancellation_scope, check_cancelled

        try:
            with cancellation_scope():
                print("ready", flush=True)
                subprocess.run(["sleep", "30"], check=False)
                check_cancelled()
        except CancellationRequested:
            raise SystemExit(130)
        raise SystemExit(0)
    """)
    env = dict(os.environ)
    env["MTTKDE_CANCEL_FILE"] = str(token)
    env.pop("SUDO_UID", None)
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        env=env,
        cwd=os.path.dirname(utils.__file__),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == "ready"
        token.write_text("cancel\n")
        stdout, stderr = process.communicate(timeout=5)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            process.kill()
        process.wait(timeout=5)
        raise

    assert process.returncode == 130, (stdout, stderr)


# ── pkg_install / pkg_sync_install: non-interactive, db-refreshed ──────


@pytest.fixture
def _record_run(monkeypatch):
    """Capture every subprocess.run call utils makes, return a no-op success."""
    calls: list = []

    class _Ok:
        returncode = 0

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        return _Ok()

    monkeypatch.setattr(utils.subprocess, "run", fake_run)
    monkeypatch.setattr(utils.os, "geteuid", lambda: 0)  # no sudo prefix
    monkeypatch.setattr(
        utils, "_trusted_pkg_executable",
        lambda name: f"/usr/bin/{name}",
    )
    return calls


def test_pkg_install_appends_packages_to_distro_command(monkeypatch, _record_run):
    import distro
    monkeypatch.setattr(distro, "package_manager_install_cmd",
                        lambda: ["pacman", "-S", "--noconfirm", "--needed"])

    assert utils.pkg_install("vulkan-headers", "cmake") is True
    cmd = _record_run[0][0]
    assert cmd == ["/usr/bin/pacman", "-S", "--noconfirm", "--needed",
                   "vulkan-headers", "cmake"]


def test_pkg_install_is_non_interactive(monkeypatch, _record_run):
    import distro
    monkeypatch.setattr(distro, "package_manager_install_cmd",
                        lambda: ["pacman", "-S", "--noconfirm", "--needed"])

    utils.pkg_install("cmake")
    kw = _record_run[0][1]
    # stdin from /dev/null + non-interactive env so nothing can block on [Y/n].
    assert kw["stdin"] is subprocess.DEVNULL
    assert kw["env"]["DEBIAN_FRONTEND"] == "noninteractive"


def test_pkg_install_prepends_sudo_when_not_root(monkeypatch, _record_run):
    import distro
    monkeypatch.setattr(utils.os, "getuid", lambda: 1000)
    monkeypatch.setattr(utils.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(distro, "package_manager_install_cmd",
                        lambda: ["pacman", "-S", "--noconfirm", "--needed"])

    utils.pkg_install("cmake")
    assert _record_run[0][0][0] == "sudo"


def test_pkg_install_fails_gracefully_on_unsupported_distro(monkeypatch):
    import distro
    monkeypatch.setattr(distro, "package_manager_install_cmd",
                        lambda: (_ for _ in ()).throw(
                            distro.UnsupportedDistroError("nope")))
    assert utils.pkg_install("cmake") is False


def test_pkg_sync_install_syncs_then_installs(monkeypatch, _record_run):
    import distro
    monkeypatch.setattr(distro, "package_manager_sync_cmd",
                        lambda: ["pacman", "-Sy", "--noconfirm"])
    monkeypatch.setattr(distro, "package_manager_install_cmd",
                        lambda: ["pacman", "-S", "--noconfirm", "--needed"])

    assert utils.pkg_sync_install("vulkan-headers", "cmake") is True
    assert len(_record_run) == 2
    assert _record_run[0][0] == ["/usr/bin/pacman", "-Sy", "--noconfirm"]
    assert _record_run[1][0] == ["/usr/bin/pacman", "-S", "--noconfirm", "--needed",
                                 "vulkan-headers", "cmake"]


def test_pkg_sync_install_does_not_install_when_sync_fails(monkeypatch):
    import distro
    sync = ["package-manager", "sync"]
    install = ["package-manager", "install"]
    monkeypatch.setattr(distro, "package_manager_sync_cmd", lambda: sync)
    monkeypatch.setattr(distro, "package_manager_install_cmd", lambda: install)
    calls: list[tuple[list[str], tuple[str, ...]]] = []

    def fail_sync(base, *args):
        calls.append((base, args))
        return False

    monkeypatch.setattr(utils, "_run_pkg_cmd", fail_sync)

    assert utils.pkg_sync_install("cmake") is False
    assert calls == [(sync, ())]


def test_pkg_sync_install_skips_sync_when_none(monkeypatch, _record_run):
    import distro
    monkeypatch.setattr(distro, "package_manager_sync_cmd", lambda: None)
    monkeypatch.setattr(distro, "package_manager_install_cmd",
                        lambda: ["dnf", "install", "-y"])

    utils.pkg_sync_install("cmake")
    assert len(_record_run) == 1  # install only, no sync step
    assert _record_run[0][0] == ["/usr/bin/dnf", "install", "-y", "cmake"]


def test_pkg_install_hops_to_root_then_restores_effective_ids(monkeypatch):
    import distro

    ids = {"euid": 1000, "egid": 1000}
    transitions: list[tuple[str, int]] = []
    calls: list[tuple[list[str], dict]] = []

    class _Ok:
        returncode = 0

    def set_euid(value):
        transitions.append(("euid", value))
        ids["euid"] = value

    def set_egid(value):
        transitions.append(("egid", value))
        ids["egid"] = value

    def fake_run(cmd, **kwargs):
        assert ids == {"euid": 0, "egid": 0}
        calls.append((cmd, kwargs))
        return _Ok()

    monkeypatch.setattr(utils.os, "getuid", lambda: 0)
    monkeypatch.setattr(utils.os, "geteuid", lambda: ids["euid"])
    monkeypatch.setattr(utils.os, "getegid", lambda: ids["egid"])
    monkeypatch.setattr(utils.os, "seteuid", set_euid)
    monkeypatch.setattr(utils.os, "setegid", set_egid)
    monkeypatch.setattr(utils.subprocess, "run", fake_run)
    monkeypatch.setattr(utils, "_trusted_pkg_executable",
                        lambda _name: "/usr/bin/pacman")
    monkeypatch.setattr(distro, "package_manager_install_cmd",
                        lambda: ["pacman", "-S", "--noconfirm", "--needed"])

    assert utils.pkg_install("cmake") is True
    assert calls[0][0][0] == "/usr/bin/pacman"
    assert transitions == [
        ("euid", 0), ("egid", 0),
        ("egid", 1000), ("euid", 1000),
    ]
    assert ids == {"euid": 1000, "egid": 1000}


def test_pkg_root_hop_restores_uid_when_group_elevation_fails(monkeypatch):
    ids = {"euid": 1000, "egid": 1000}

    def set_euid(value):
        ids["euid"] = value

    def set_egid(value):
        if value == 0:
            raise PermissionError("setegid blocked")
        ids["egid"] = value

    monkeypatch.setattr(utils.os, "geteuid", lambda: ids["euid"])
    monkeypatch.setattr(utils.os, "getegid", lambda: ids["egid"])
    monkeypatch.setattr(utils.os, "seteuid", set_euid)
    monkeypatch.setattr(utils.os, "setegid", set_egid)

    with pytest.raises(PermissionError, match="setegid blocked"):
        with utils._pkg_cmd_root():
            raise AssertionError("unreachable")

    assert ids == {"euid": 1000, "egid": 1000}


def test_root_package_environment_excludes_user_injection_paths(
        monkeypatch, _record_run):
    import distro

    monkeypatch.setenv("PATH", "/tmp/user-bin")
    monkeypatch.setenv("HOME", "/home/tester")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/home/tester/.config")
    monkeypatch.setenv("PYTHONPATH", "/tmp/python-hook")
    monkeypatch.setenv("APT_CONFIG", "/tmp/apt.conf")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:8080")
    monkeypatch.setattr(distro, "package_manager_install_cmd",
                        lambda: ["pacman", "-S", "--noconfirm", "--needed"])

    assert utils.pkg_install("cmake") is True
    cmd, kwargs = _record_run[0]
    env = kwargs["env"]
    assert cmd[0] == "/usr/bin/pacman"
    assert env["PATH"] == utils._ROOT_PKG_PATH
    assert env["HOME"] == "/root"
    assert env["USER"] == env["LOGNAME"] == "root"
    assert env["HTTPS_PROXY"] == "http://proxy.example:8080"
    assert "XDG_CONFIG_HOME" not in env
    assert "PYTHONPATH" not in env
    assert "APT_CONFIG" not in env


# ── qdbus binary resolution (name varies per distro) ──────────────────


def _force_qdbus_binaries(monkeypatch, present):
    monkeypatch.setattr(utils, "have", lambda cmd: cmd in present)
    monkeypatch.setattr(utils, "_QDBUS_CACHE", None)


@pytest.mark.parametrize("present, expected", [
    ({"qdbus6"},     "qdbus6"),       # Arch/Alpine/Debian/openSUSE
    ({"qdbus-qt6"},  "qdbus-qt6"),    # Fedora/RHEL
    ({"qdbus"},      "qdbus"),        # older Qt5-era systems
])
def test_qdbus_cmd_resolves_per_distro_name(monkeypatch, present, expected):
    _force_qdbus_binaries(monkeypatch, present)
    assert utils.qdbus_cmd() == expected


def test_qdbus_cmd_none_when_no_variant_present(monkeypatch):
    _force_qdbus_binaries(monkeypatch, set())
    assert utils.qdbus_cmd() is None


# ── kw_write / kw_read: privilege drop + bounded hang ─────────────────


def _raise_timeout(cmd, **kw):
    raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 0))


def test_kw_write_drops_privs_and_bounds_timeout(monkeypatch):
    """kw_write children must drop to SUDO_USER (Qt6 setuid abort) AND
    carry a 5s bound so a hung kwriteconfig6 can't hang the installer."""
    seen: dict = {}

    def fake_run(cmd, **kw):
        seen.update(kw, cmd=cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(utils.subprocess, "run", fake_run)
    monkeypatch.setattr(utils, "have", lambda cmd: True)
    monkeypatch.setattr(utils, "_has_session_dbus", lambda: False)

    assert utils.kw_write("--file", "f", "--group", "g",
                          "--key", "k", "v") is True
    assert seen["cmd"][0] == "kwriteconfig6"
    assert seen["preexec_fn"] is utils.drop_privs_in_child
    assert seen["timeout"] == 5


def test_kw_write_returns_false_on_timeout(monkeypatch):
    monkeypatch.setattr(utils.subprocess, "run", _raise_timeout)
    monkeypatch.setattr(utils, "have", lambda cmd: True)
    monkeypatch.setattr(utils, "_has_session_dbus", lambda: False)
    assert utils.kw_write("--file", "f") is False


def test_kw_read_drops_privs_and_bounds_timeout(monkeypatch):
    seen: dict = {}

    def fake_run(cmd, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(cmd, 0, stdout=" value \n",
                                           stderr="")

    monkeypatch.setattr(utils.subprocess, "run", fake_run)
    monkeypatch.setattr(utils, "have", lambda cmd: True)
    assert utils.kw_read("f", "g", "k") == "value"
    assert seen["preexec_fn"] is utils.drop_privs_in_child
    assert seen["timeout"] == 5


def test_kw_read_returns_empty_on_timeout(monkeypatch):
    monkeypatch.setattr(utils.subprocess, "run", _raise_timeout)
    monkeypatch.setattr(utils, "have", lambda cmd: True)
    assert utils.kw_read("f", "g", "k") == ""


def test_has_session_dbus_returns_false_on_timeout(monkeypatch):
    """kw_write probes the session bus first; without a bound here it was
    still indirectly hangable before kwriteconfig6 even launched."""
    monkeypatch.setattr(utils, "_HAS_DBUS", None)
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/tmp/x")
    monkeypatch.setattr(utils, "have", lambda cmd: True)
    monkeypatch.setattr(utils.subprocess, "run", _raise_timeout)
    assert utils._has_session_dbus() is False
