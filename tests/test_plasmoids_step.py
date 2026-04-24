from pathlib import Path

from steps import plasmoids


def test_install_copies_taskmanager_runtime_package(tmp_path, monkeypatch):
    home = tmp_path / "home"
    src = tmp_path / "offline/plasmoids"
    dest = home / ".local/share/plasma/plasmoids"

    taskmanager = src / "org.kde.mac.tahoe.liquid.taskmanager"
    artifact = (taskmanager / "build/bin/plasma/applets" /
                "org.kde.mac.tahoe.liquid.taskmanager.so")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"so")
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
    monkeypatch.setattr(
        plasmoids,
        "TASKMANAGER_DEST_SO",
        tmp_path / "usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so",
    )

    installed = []
    failures = []
    monkeypatch.setattr(
        plasmoids,
        "sudo_install_file",
        lambda src, dest, label: installed.append((Path(src), Path(dest), label)) or True,
    )
    monkeypatch.setattr(plasmoids, "fail", lambda msg: failures.append(msg))

    plasmoids.install()

    runtime = dest / "org.kde.mac.tahoe.liquid.taskmanager"
    assert installed
    assert not failures
    assert (runtime / "metadata.json").is_file()
    assert (runtime / "contents/ui/main.qml").is_file()
    assert not (runtime / "build").exists()
