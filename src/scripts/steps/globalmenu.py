import shutil
from pathlib import Path

from steps._helpers import (
    HOME, build_dir, cmake_build, fail, install_tree, ok, offline, remove_tree,
    sudo_remove, temp_dir,
)

SRC = offline("plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu")
BUILD = build_dir("plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu")
# User-path install — Qt6 searches ~/.local/lib/qt6/plugins/ first, so
# the new install never writes outside the user's tree. Sudo only comes
# in for cleaning up legacy .so files that older releases dropped under
# /usr/lib (root-owned).
DEST_SO = HOME / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so"
DEST_QML_DIR = HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/globalmenu"

LEGACY_SOS_SYSTEM = (
    Path("/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.menu.so"),
    Path("/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.globalmenu.so"),
    Path("/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.menu.so"),
    Path("/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so"),
)
LEGACY_SOS_USER = (
    HOME / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.menu.so",
    HOME / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.globalmenu.so",
    HOME / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.menu.so",
)
LEGACY_QML = HOME / ".local/share/plasma/plasmoids/org.kde.mac-tahoe-liquid-kde.menu"
LEGACY_QML_MODULES = (
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/menu",
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/globalmenu",
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/globalmenu",
)


def deps():
    return ["cmake", "g++:gcc", "pkg-config:pkgconf"]


def build() -> None:
    cmake_build(SRC, BUILD, "Global Menu")


def _drop_user_legacy() -> None:
    for so in LEGACY_SOS_USER:
        if so.is_file():
            try:
                so.unlink()
                ok(f"Removed {so.name}")
            except OSError:
                pass
    for qml_dir in LEGACY_QML_MODULES:
        if qml_dir != DEST_QML_DIR:
            remove_tree(qml_dir, qml_dir.name)


def _install_runtime_qml() -> bool:
    module_src = BUILD / "bin/plasma/applet/org/kde/mac/tahoe/liquid/globalmenu"
    if not module_src.is_dir():
        fail("Global Menu runtime QML missing")
        return False
    with temp_dir("mttkde-globalmenu-qml") as tmp:
        runtime = tmp / DEST_QML_DIR.name
        shutil.copytree(module_src, runtime, symlinks=True)
        return install_tree(runtime, DEST_QML_DIR, "Global Menu runtime QML")


def install() -> None:
    # Sudoless install: only the user-path leftovers and the QML
    # plasmoid dir. Legacy ``/usr/lib`` .so files are uninstall()'s
    # problem — install never asks for root.
    _drop_user_legacy()
    if LEGACY_QML.is_dir():
        shutil.rmtree(LEGACY_QML, ignore_errors=True)
        ok("Removed old QML menu")

    artifact = BUILD / "bin/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so"
    if not artifact.is_file():
        return
    DEST_SO.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(artifact, DEST_SO)
        ok("Global Menu installed")
    except OSError as exc:
        fail(f"Global Menu install failed: {exc}")
        return
    _install_runtime_qml()


def uninstall() -> None:
    if DEST_SO.is_file():
        try:
            DEST_SO.unlink()
            ok("Global Menu .so removed")
        except OSError as exc:
            fail(f"Global Menu remove failed: {exc}")
    _drop_user_legacy()
    for so in LEGACY_SOS_SYSTEM:
        sudo_remove(so, f"{so.name} (legacy /usr/lib)")
    remove_tree(DEST_QML_DIR, "Global Menu runtime QML")
    if LEGACY_QML.is_dir():
        shutil.rmtree(LEGACY_QML, ignore_errors=True)
        ok("Removed old QML menu")
