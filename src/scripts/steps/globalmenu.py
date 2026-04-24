import shutil

from steps._helpers import (
    HOME, build_dir, cmake_build, fail, ok, offline, sudo_install_file, sudo_remove,
)

SRC = offline("plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu")
BUILD = build_dir("plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu")
DEST_SO = "/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so"

# Plasmoid IDs left by older builds. Their .so files cause duplicate-Id
# warnings from plasmashell and may load the wrong applet on resume.
LEGACY_SOS = (
    "/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.menu.so",
    "/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.globalmenu.so",
    "/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.menu.so",
)
LEGACY_QML = HOME / ".local/share/plasma/plasmoids/org.kde.mac-tahoe-liquid-kde.menu"


def deps():
    return ["cmake", "g++:gcc", "pkg-config:pkgconf"]


def build() -> None:
    cmake_build(SRC, BUILD, "Global Menu")


def install() -> None:
    from pathlib import Path
    for so in LEGACY_SOS:
        sudo_remove(Path(so), label=f"Removed {Path(so).name}")
    if LEGACY_QML.is_dir():
        shutil.rmtree(LEGACY_QML, ignore_errors=True)
        ok("Removed old QML menu")

    artifact = BUILD / "bin/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so"
    if not artifact.is_file():
        return
    from pathlib import Path
    sudo_install_file(artifact, Path(DEST_SO), "Global Menu installed")


def uninstall() -> None:
    from pathlib import Path
    sudo_remove(Path(DEST_SO), "Global Menu .so removed")
    for so in LEGACY_SOS:
        sudo_remove(Path(so), label=f"{Path(so).name} removed")
    if LEGACY_QML.is_dir():
        shutil.rmtree(LEGACY_QML, ignore_errors=True)
        ok("Removed old QML menu")
