"""Static integration test for globalmenu.install().

Confirms the wiring: build artefact + runtime QML are copied to the
install destinations, and the install step does not crash. Sudo helpers
are stubbed with plain copies — the test runner is not root, so a real
``sudo_install_file`` (which calls ``_as_root()`` → ``seteuid(0)``) would
raise ``PermissionError``. The destination *paths* are still asserted
against the v0.10 ``DEST_SO`` / ``DEST_QML_DIR`` constants, which point
at ``/usr/lib/qt6/...`` in production — those are validated separately
by the preflight Qt6 path check.
"""
import shutil
from pathlib import Path

from steps import globalmenu


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

    monkeypatch.setattr(globalmenu, "HOME", home)
    monkeypatch.setattr(globalmenu, "SRC", src)
    monkeypatch.setattr(globalmenu, "BUILD", build)
    monkeypatch.setattr(
        globalmenu,
        "DEST_SO",
        tmp_path / "fake-usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so",
    )
    monkeypatch.setattr(
        globalmenu,
        "DEST_QML_DIR",
        tmp_path / "fake-usr/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/globalmenu",
    )
    monkeypatch.setattr(globalmenu, "LEGACY_QML", tmp_path / "no-legacy-qml")
    monkeypatch.setattr(globalmenu, "LEGACY_SOS_SYSTEM", ())
    monkeypatch.setattr(globalmenu, "LEGACY_SOS_USER", ())
    # v0.10: legacy user-path QML modules — v0.8.4-0.8.6 leftovers.
    monkeypatch.setattr(globalmenu, "LEGACY_QML_MODULES_USER", ())

    _stub_sudo_helpers(monkeypatch)

    failures = []
    monkeypatch.setattr(globalmenu, "fail", lambda msg: failures.append(msg))

    globalmenu.install()

    assert not failures, failures
    assert globalmenu.DEST_SO.is_file()
    assert (globalmenu.DEST_QML_DIR / "qmldir").is_file()
    assert (globalmenu.DEST_QML_DIR / "main.qml").is_file()


def test_globalmenu_dest_paths_target_qt6_system_dirs():
    """v0.10 contract: the .so + QML module land under the directory
    Qt6 actually scans (``/usr/lib/qt6/{plugins,qml}/``). User paths
    are not on Qt's discovery list — the v0.8.4-0.9.0 regression
    that left the global menu unloaded came from shipping to
    ``~/.local/lib/qt6/`` instead. Pin the production paths here so a
    refactor that drifts them gets caught at test time, not after a
    user-facing release."""
    assert str(globalmenu.DEST_SO) == (
        "/usr/lib/qt6/plugins/plasma/applets/"
        "org.kde.mac.tahoe.liquid.globalmenu.so"
    )
    assert str(globalmenu.DEST_QML_DIR) == (
        "/usr/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/globalmenu"
    )


def test_globalmenu_build_artifacts_match_install_sources():
    """``build_artifacts()`` must reference the exact files the install
    step then copies. If they drift, the upfront build phase greenlights
    a build whose outputs don't actually feed the install."""
    artifacts = globalmenu.build_artifacts()
    assert globalmenu.BUILD / "bin/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so" in artifacts
    assert globalmenu.BUILD / "bin/plasma/applet/org/kde/mac/tahoe/liquid/globalmenu" in artifacts
