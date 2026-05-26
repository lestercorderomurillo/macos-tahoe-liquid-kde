"""Static integration test for globalmenu.install().

Confirms the wiring: build artefact + runtime QML are copied to the
install destinations, and the install step does not crash. Sudo helpers
are stubbed with plain copies — the test runner is not root, so a real
``sudo_install_file`` (which calls ``_as_root()`` → ``seteuid(0)``) would
raise ``PermissionError``. The destination *paths* are still asserted
to live under whatever ``distro.qt6_plugins_dir()`` reports, which is
where Qt6 actually scans (per-distro; queried from qmake6).
"""
import shutil
from pathlib import Path

import distro
from steps import globalmenu


def _stub_qt6_paths(monkeypatch, tmp_path):
    """Pin the qmake6-reported Qt6 plugin / QML dirs to writable tmp
    locations for the duration of the test. Avoids depending on whether
    qmake6 is on PATH in the test env, and avoids writes landing under
    a real ``/usr/lib`` even when the sudo helpers are stubbed."""
    fake_plugins = tmp_path / "fake-qt6/plugins"
    fake_qml = tmp_path / "fake-qt6/qml"
    monkeypatch.setattr(distro, "_QT_PLUGINS_CACHE", fake_plugins)
    monkeypatch.setattr(distro, "_QT_QML_CACHE", fake_qml)
    return fake_plugins, fake_qml


def _stub_sudo_helpers(monkeypatch):
    """Replace ``sudo_install_file`` / ``sudo_install_tree`` with plain
    copies. The tests run as a normal user — ``_as_root()`` would try
    ``seteuid(0)`` and raise ``PermissionError``. The contract these
    helpers express (atomic copy + correct ownership at the destination)
    is real-system territory; in the test we just want to verify the
    install code targets the right paths and copies the right bytes."""
    def fake_install_file(src: Path, dest: Path, label: str) -> bool:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dest))
        return True

    def fake_install_tree(src: Path, dest: Path, label: str | None = None) -> bool:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(str(src), str(dest))
        return True

    def fake_remove(path: Path, label: str | None = None) -> bool:
        if not path.exists():
            return False
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return True

    monkeypatch.setattr(globalmenu, "sudo_install_file", fake_install_file)
    monkeypatch.setattr(globalmenu, "sudo_install_tree", fake_install_tree)
    monkeypatch.setattr(globalmenu, "sudo_remove", fake_remove)


def test_install_copies_globalmenu_runtime_qml(tmp_path, monkeypatch):
    home = tmp_path / "home"
    src = tmp_path / "offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu"
    build = tmp_path / "build/plasmoids/org.kde.mac.tahoe.liquid.globalmenu"
    artifact = build / "bin/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so"
    runtime_dir = build / "bin/plasma/applet/org/kde/mac/tahoe/liquid/globalmenu"

    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"so")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "qmldir").write_text("module plasma.applet.org.kde.mac.tahoe.liquid.globalmenu\n")
    (runtime_dir / "main.qml").write_text("import QtQuick\nItem {}\n")

    fake_plugins, fake_qml = _stub_qt6_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(globalmenu, "HOME", home)
    monkeypatch.setattr(globalmenu, "SRC", src)
    monkeypatch.setattr(globalmenu, "BUILD", build)
    monkeypatch.setattr(globalmenu, "LEGACY_QML", tmp_path / "no-legacy-qml")
    monkeypatch.setattr(globalmenu, "LEGACY_SOS_USER", ())
    monkeypatch.setattr(globalmenu, "LEGACY_QML_MODULES_USER", ())

    _stub_sudo_helpers(monkeypatch)

    failures = []
    monkeypatch.setattr(globalmenu, "fail", lambda msg: failures.append(msg))

    globalmenu.install()

    assert not failures, failures
    expected_so = fake_plugins / "plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so"
    expected_qml = fake_qml / "plasma/applet/org/kde/mac/tahoe/liquid/globalmenu"
    assert expected_so.is_file()
    assert (expected_qml / "qmldir").is_file()
    assert (expected_qml / "main.qml").is_file()


def test_globalmenu_dest_paths_anchor_to_qmake6_libdir(monkeypatch, tmp_path):
    """v0.15 contract: the .so + QML module land under whatever the Qt6
    plugin / QML dirs resolve to (qmake6-reported, per distro). The
    suffix is pinned so a refactor that mangles the package id can't
    silently ship to the wrong applet path; the prefix comes from the
    paths.py helper so this works on Arch (/usr/lib/qt6), Gentoo
    (/usr/lib64/qt6), and Debian-multiarch alike."""
    fake_plugins, fake_qml = _stub_qt6_paths(monkeypatch, tmp_path)
    assert globalmenu.DEST_SO == fake_plugins / (
        "plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so"
    )
    assert globalmenu.DEST_QML_DIR == fake_qml / (
        "plasma/applet/org/kde/mac/tahoe/liquid/globalmenu"
    )


def test_globalmenu_build_artifacts_match_install_sources():
    """``build_artifacts()`` must reference the exact files the install
    step then copies. If they drift, the upfront build phase greenlights
    a build whose outputs don't actually feed the install."""
    artifacts = globalmenu.build_artifacts()
    assert globalmenu.BUILD / "bin/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so" in artifacts
    assert globalmenu.BUILD / "bin/plasma/applet/org/kde/mac/tahoe/liquid/globalmenu" in artifacts
