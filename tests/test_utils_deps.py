import subprocess

import pytest

import utils


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
    return calls


def test_pkg_install_appends_packages_to_distro_command(monkeypatch, _record_run):
    import distro
    monkeypatch.setattr(distro, "package_manager_install_cmd",
                        lambda: ["pacman", "-S", "--noconfirm", "--needed"])

    assert utils.pkg_install("vulkan-headers", "cmake") is True
    cmd = _record_run[0][0]
    assert cmd == ["pacman", "-S", "--noconfirm", "--needed",
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
    assert _record_run[0][0] == ["pacman", "-Sy", "--noconfirm"]
    assert _record_run[1][0] == ["pacman", "-S", "--noconfirm", "--needed",
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
    assert _record_run[0][0] == ["dnf", "install", "-y", "cmake"]


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
