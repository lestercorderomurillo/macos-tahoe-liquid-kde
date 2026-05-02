from pathlib import Path

from steps import plasmoids


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

    monkeypatch.setattr(plasmoids, "HOME", home)
    monkeypatch.setattr(plasmoids, "SRC_DIR", src)
    monkeypatch.setattr(plasmoids, "DEST_DIR", dest)
    monkeypatch.setattr(plasmoids, "TASKMANAGER_SRC", taskmanager)
    monkeypatch.setattr(plasmoids, "TASKMANAGER_BUILD", taskmanager / "build")
    # User-path .so destination, sandboxed under tmp_path. The real
    # value is ``~/.local/lib/qt6/plugins/...`` — same shape, just under
    # the test home so we don't actually write to the dev's plugin dir.
    monkeypatch.setattr(
        plasmoids,
        "TASKMANAGER_DEST_SO",
        home / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so",
    )
    monkeypatch.setattr(
        plasmoids,
        "TASKMANAGER_DEST_QML",
        home / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/taskmanager",
    )
    # Legacy /usr/lib path: redirect to a sandbox path that doesn't
    # exist so the legacy-cleanup ``sudo_remove`` becomes a silent no-op
    # (without it, the test would try to ``seteuid(0)`` against a real
    # root-owned file on the dev's filesystem and fail).
    monkeypatch.setattr(
        plasmoids,
        "LEGACY_TASKMANAGER_SYSTEM_SO",
        tmp_path / "fake-usr-lib/no-such-taskmanager.so",
    )

    failures = []
    monkeypatch.setattr(plasmoids, "fail", lambda msg: failures.append(msg))

    plasmoids.install()

    runtime = dest / "org.kde.mac.tahoe.liquid.taskmanager"
    # User-path .so install (no sudo for the new file) — lands at the
    # user-path destination, never under /usr/lib.
    assert plasmoids.TASKMANAGER_DEST_SO.is_file(), (
        "expected the .so to land at the user-path destination — install "
        "is sudoless for new files, /usr/lib only gets touched for the "
        "legacy-cleanup unlink"
    )
    assert (home / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/taskmanager/qmldir").is_file()
    assert plasmoids.TASKMANAGER_DEST_SO.read_bytes() == b"so"
    assert not failures
    assert (runtime / "metadata.json").is_file()
    assert (runtime / "contents/ui/main.qml").is_file()
    assert not (runtime / "build").exists()
