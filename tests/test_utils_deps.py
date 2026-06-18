from pathlib import Path
from types import SimpleNamespace

import utils


def test_dep_available_treats_ecm_as_cmake_package(monkeypatch):
    seen = []

    monkeypatch.setattr(utils, "have", lambda cmd: cmd == "cmake")

    def fake_run_user(cmd, **kwargs):
        cmakelists = Path(cmd[2]) / "CMakeLists.txt"
        seen.append(cmakelists.read_text())
        seen.append(cmd)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(utils, "run_user", fake_run_user)

    assert utils._dep_available("ecm") is True
    assert len(seen) == 2
    assert "project(mttkde_dep_probe LANGUAGES CXX)" in seen[0]
    assert "find_package(ECM CONFIG QUIET)" in seen[0]
    assert seen[1][0] == "cmake"
    assert seen[1][1] == "-S"


def test_dep_available_reports_ecm_missing_when_cmake_cannot_find_it(monkeypatch):
    monkeypatch.setattr(utils, "have", lambda cmd: cmd == "cmake")
    monkeypatch.setattr(
        utils,
        "run_user",
        lambda *a, **kw: SimpleNamespace(returncode=1),
    )

    assert utils._dep_available("ecm") is False


def test_dep_available_treats_qt6_gui_cmake_as_component_probe(monkeypatch):
    seen = []

    monkeypatch.setattr(utils, "have", lambda cmd: cmd == "cmake")

    def fake_run_user(cmd, **kwargs):
        cmakelists = Path(cmd[2]) / "CMakeLists.txt"
        seen.append(cmakelists.read_text())
        seen.append(cmd)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(utils, "run_user", fake_run_user)

    assert utils._dep_available("qt6-gui-cmake") is True
    assert len(seen) == 2
    assert "find_package(Qt6Gui CONFIG QUIET)" in seen[0]
    assert seen[1][0] == "cmake"
    assert seen[1][1] == "-S"


def test_dep_available_reports_qt6_qml_missing_when_probe_fails(monkeypatch):
    monkeypatch.setattr(utils, "have", lambda cmd: cmd == "cmake")
    monkeypatch.setattr(
        utils,
        "run_user",
        lambda *a, **kw: SimpleNamespace(returncode=1),
    )

    assert utils._dep_available("qt6-qml-cmake") is False


def test_dep_available_treats_qt6_uitools_as_cmake_package(monkeypatch):
    seen = []

    monkeypatch.setattr(utils, "have", lambda cmd: cmd == "cmake")

    def fake_run_user(cmd, **kwargs):
        cmakelists = Path(cmd[2]) / "CMakeLists.txt"
        seen.append(cmakelists.read_text())
        seen.append(cmd)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(utils, "run_user", fake_run_user)

    assert utils._dep_available("qt6-uitools-cmake") is True
    assert len(seen) == 2
    assert "find_package(Qt6UiTools CONFIG QUIET)" in seen[0]
    assert seen[1][0] == "cmake"
    assert seen[1][1] == "-S"


def _force_qdbus_binaries(monkeypatch, present):
    """Pin which qdbus binary names ``have()`` reports and drain the
    module-level qdbus cache so the new set is actually consulted."""
    monkeypatch.setattr(utils, "have", lambda cmd: cmd in present)
    monkeypatch.setattr(utils, "_QDBUS_CACHE", None)


def test_dep_available_finds_qdbus_under_fedora_binary_name(monkeypatch):
    # Regression: the dep token is ``qdbus6`` but Fedora/RHEL ship the
    # tool on PATH as ``qdbus-qt6``. A literal have("qdbus6") missed it
    # and auto_dep() then ran a noisy no-op reinstall on every run.
    # _dep_available must route the token through the same multi-name
    # resolver the runtime callers use.
    _force_qdbus_binaries(monkeypatch, {"qdbus-qt6"})

    assert utils.have("qdbus6") is False  # the literal name is genuinely absent
    assert utils._dep_available("qdbus6") is True


def test_dep_available_finds_qdbus_under_qt5_fallback_name(monkeypatch):
    # Older systems expose only the Qt5-era ``qdbus``.
    _force_qdbus_binaries(monkeypatch, {"qdbus"})

    assert utils._dep_available("qdbus6") is True


def test_dep_available_finds_qdbus_under_canonical_name(monkeypatch):
    _force_qdbus_binaries(monkeypatch, {"qdbus6"})

    assert utils._dep_available("qdbus6") is True


def test_dep_available_reports_qdbus_missing_when_no_variant_present(monkeypatch):
    _force_qdbus_binaries(monkeypatch, set())

    assert utils._dep_available("qdbus6") is False


def test_auto_dep_skips_reinstall_when_qdbus_present_under_alias(monkeypatch):
    # End-to-end: with only the Fedora-named binary present, auto_dep
    # must take the already-satisfied path (ok, no install) rather than
    # the warn → pkg_install path that produced the noisy log.
    _force_qdbus_binaries(monkeypatch, {"qdbus-qt6"})
    installed = []
    monkeypatch.setattr(utils, "pkg_install", lambda *p: installed.append(p) or True)

    assert utils.auto_dep("qdbus6", "qt6-tools") is True
    assert installed == []
