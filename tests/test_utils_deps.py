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
