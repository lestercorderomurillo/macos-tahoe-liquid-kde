# USELESS: monkeypatches DEST_SO/DEST_QML_DIR + sudo helpers — production user-path destinations Qt6 does not search are not asserted
from pathlib import Path

from steps import globalmenu


def test_install_copies_globalmenu_runtime_qml(tmp_path, monkeypatch):
    home = tmp_path / "home"
    src = tmp_path / "offline/plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu"
    build = tmp_path / "build/plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu"
    artifact = build / "bin/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so"
    runtime_dir = build / "bin/plasma/applet/org/kde/mac/tahoe/liquid/globalmenu"

    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"so")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "qmldir").write_text("module plasma.applet.org.kde.mac.tahoe.liquid.globalmenu\n")
    (runtime_dir / "main.qml").write_text("import QtQuick\nItem {}\n")

    monkeypatch.setattr(globalmenu, "HOME", home)
    monkeypatch.setattr(globalmenu, "SRC", src)
    monkeypatch.setattr(globalmenu, "BUILD", build)
    monkeypatch.setattr(
        globalmenu,
        "DEST_SO",
        home / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so",
    )
    monkeypatch.setattr(
        globalmenu,
        "DEST_QML_DIR",
        home / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/globalmenu",
    )
    monkeypatch.setattr(globalmenu, "LEGACY_QML", tmp_path / "no-legacy-qml")
    monkeypatch.setattr(globalmenu, "LEGACY_SOS_SYSTEM", ())
    monkeypatch.setattr(globalmenu, "LEGACY_SOS_USER", ())
    monkeypatch.setattr(globalmenu, "LEGACY_QML_MODULES", ())

    failures = []
    monkeypatch.setattr(globalmenu, "fail", lambda msg: failures.append(msg))

    globalmenu.install()

    assert not failures
    assert globalmenu.DEST_SO.is_file()
    assert (globalmenu.DEST_QML_DIR / "qmldir").is_file()
    assert (globalmenu.DEST_QML_DIR / "main.qml").is_file()
