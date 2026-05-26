"""Static integration test for plasmoids.install().

Confirms the wiring: taskmanager build artefact + runtime QML are
copied to ``TASKMANAGER_DEST_SO`` / ``TASKMANAGER_DEST_QML``, and the
package metadata + contents/ tree end up under ``DEST_DIR``. Sudo
helpers are stubbed (the test runner is not root) — the real
``sudo_install_file`` would call ``_as_root()`` → ``seteuid(0)`` and
raise ``PermissionError``. The Qt6 plugin / QML dirs come from
:mod:`distro` and are stubbed to a tmp tree so the test never writes
under a real ``/usr/lib`` even when the sudo helpers are no-ops.
"""
import shutil
from pathlib import Path

import distro
from steps import plasmoids


def _stub_qt6_paths(monkeypatch, tmp_path):
    fake_plugins = tmp_path / "fake-qt6/plugins"
    fake_qml = tmp_path / "fake-qt6/qml"
    monkeypatch.setattr(distro, "_QT_PLUGINS_CACHE", fake_plugins)
    monkeypatch.setattr(distro, "_QT_QML_CACHE", fake_qml)
    return fake_plugins, fake_qml


def _stub_sudo_helpers(monkeypatch):
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

    monkeypatch.setattr(plasmoids, "sudo_install_file", fake_install_file)
    monkeypatch.setattr(plasmoids, "sudo_install_tree", fake_install_tree)
    monkeypatch.setattr(plasmoids, "sudo_remove", fake_remove)


def test_install_copies_taskmanager_runtime_package(tmp_path, monkeypatch):
    home = tmp_path / "home"
    src = tmp_path / "offline/plasmoids"
    dest = home / ".local/share/plasma/plasmoids"

    taskmanager = src / "org.kde.mac.tahoe.liquid.taskmanager"
    artifact = (taskmanager / "build/bin/plasma/applets" /
                "org.kde.mac.tahoe.liquid.taskmanager.so")
    runtime_qml = (
        taskmanager / "build/bin/plasma/applet/org/kde/mac/tahoe/liquid/taskmanager"
    )
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"so")
    runtime_qml.mkdir(parents=True, exist_ok=True)
    (runtime_qml / "qmldir").write_text(
        "module plasma.applet.org.kde.mac.tahoe.liquid.taskmanager\n"
    )
    (runtime_qml / "main.qml").write_text("import QtQuick\nItem {}\n")
    (taskmanager / "metadata.json").write_text(
        '{"KPlugin":{"Id":"org.kde.mac.tahoe.liquid.taskmanager"}}\n'
    )
    (taskmanager / "contents/ui").mkdir(parents=True, exist_ok=True)
    (taskmanager / "contents/ui/main.qml").write_text("import QtQuick\nItem {}\n")
    (taskmanager / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.16)\n")

    icontasks = src / "org.kde.mac.tahoe.liquid.icontasks"
    icontasks.mkdir(parents=True, exist_ok=True)
    (icontasks / "metadata.json").write_text(
        '{"KPlugin":{"Id":"org.kde.mac.tahoe.liquid.icontasks"}}\n'
    )

    (home / ".config").mkdir(parents=True, exist_ok=True)

    fake_plugins, fake_qml = _stub_qt6_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(plasmoids, "HOME", home)
    monkeypatch.setattr(plasmoids, "SRC_DIR", src)
    monkeypatch.setattr(plasmoids, "DEST_DIR", dest)
    monkeypatch.setattr(plasmoids, "TASKMANAGER_SRC", taskmanager)
    monkeypatch.setattr(plasmoids, "TASKMANAGER_BUILD", taskmanager / "build")
    # v0.10: ``LEGACY_TASKMANAGER_USER_SO`` is the v0.8.4-0.8.6 sudoless
    # leftover under ``~/.local/lib/qt6/...``. Point it at a sandbox path
    # that doesn't exist so the cleanup path no-ops.
    monkeypatch.setattr(
        plasmoids,
        "LEGACY_TASKMANAGER_USER_SO",
        tmp_path / "fake-user-lib/no-such-taskmanager.so",
    )

    _stub_sudo_helpers(monkeypatch)

    failures = []
    monkeypatch.setattr(plasmoids, "fail", lambda msg: failures.append(msg))

    plasmoids.install()

    expected_so = fake_plugins / (
        "plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so"
    )
    expected_qml = fake_qml / (
        "plasma/applet/org/kde/mac/tahoe/liquid/taskmanager"
    )
    runtime = dest / "org.kde.mac.tahoe.liquid.taskmanager"
    assert expected_so.is_file()
    assert (expected_qml / "qmldir").is_file()
    assert expected_so.read_bytes() == b"so"
    assert not failures, failures
    assert (runtime / "metadata.json").is_file()
    assert (runtime / "contents/ui/main.qml").is_file()
    assert not (runtime / "build").exists()


def test_taskmanager_dest_paths_anchor_to_qmake6_libdir(monkeypatch, tmp_path):
    """v0.15 contract: the dock taskmanager .so + QML module land
    under whatever the Qt6 plugin / QML dirs resolve to (qmake6-
    reported, per distro). The suffix is pinned so a refactor that
    mangles the package id can't silently ship to the wrong applet
    path; the prefix comes from distro.qt6_* so this works on Arch
    (/usr/lib/qt6), Gentoo (/usr/lib64/qt6), and Debian-multiarch
    alike."""
    fake_plugins, fake_qml = _stub_qt6_paths(monkeypatch, tmp_path)
    assert plasmoids.TASKMANAGER_DEST_SO == fake_plugins / (
        "plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so"
    )
    assert plasmoids.TASKMANAGER_DEST_QML == fake_qml / (
        "plasma/applet/org/kde/mac/tahoe/liquid/taskmanager"
    )


def test_taskmanager_build_artifacts_match_install_sources():
    artifacts = plasmoids.build_artifacts()
    assert plasmoids.TASKMANAGER_BUILD / "bin/plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so" in artifacts
    assert plasmoids.TASKMANAGER_BUILD / "bin/plasma/applet/org/kde/mac/tahoe/liquid/taskmanager" in artifacts
