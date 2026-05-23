import shutil
from pathlib import Path

from paths import REPO_ROOT
from steps._helpers import (
    HOME, build_dir, cmake_build, fail, ok, offline,
    sudo_install_file, sudo_install_tree, sudo_remove, warn,
)

SRC = offline("plasmoids/org.kde.mac.tahoe.liquid.globalmenu")
BUILD = build_dir("plasmoids/org.kde.mac.tahoe.liquid.globalmenu")

# AboutWindow shells out to this helper for system info. It is plain
# Python and lives in ~/.local/bin so the install stays sudoless for
# the script side (only the C++ .so install above needs root).
ABOUT_INFO_SRC = REPO_ROOT / "src/scripts/about_info.py"
ABOUT_INFO_DEST = HOME / ".local/bin/mac-tahoe-about-info"
# System-path install — Qt6's default plugin/QML search is
# /usr/lib/qt6/{plugins,qml}/. User paths are NOT walked (no
# QT_PLUGIN_PATH / QML_IMPORT_PATH set in a default Plasma session),
# so the .so + QML module MUST live under /usr/lib for plasmashell to
# discover them. Sudo upfront via the CLI gate; sudo_install_file/tree
# hop back to root via _as_root() for these writes.
DEST_SO = Path("/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so")
DEST_QML_DIR = Path("/usr/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/globalmenu")

LEGACY_SOS_SYSTEM = (
    Path("/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.menu.so"),
    Path("/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.globalmenu.so"),
    Path("/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.menu.so"),
)
# v0.8.4-0.8.6 sudoless leftovers under user paths. Plain unlink, no
# sudo — they belong to the invoking user.
LEGACY_SOS_USER = (
    HOME / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.menu.so",
    HOME / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.globalmenu.so",
    HOME / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.menu.so",
    HOME / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so",
)
LEGACY_QML = HOME / ".local/share/plasma/plasmoids/org.kde.mac-tahoe-liquid-kde.menu"
LEGACY_QML_MODULES_USER = (
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/menu",
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/globalmenu",
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/globalmenu",
)


def deps():
    return ["cmake", "g++:gcc", "pkg-config:pkgconf"]


def build_artifacts() -> list[Path]:
    return [
        BUILD / "bin/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so",
        BUILD / "bin/plasma/applet/org/kde/mac/tahoe/liquid/globalmenu",
    ]


def build() -> None:
    cmake_build(SRC, BUILD, "Global Menu")


def _drop_legacy() -> None:
    for so in LEGACY_SOS_USER:
        if so.is_file():
            try:
                so.unlink()
                ok(f"Removed {so.name} (user-path leftover)")
            except OSError:
                pass
    for qml_dir in LEGACY_QML_MODULES_USER:
        if qml_dir.is_dir():
            shutil.rmtree(qml_dir, ignore_errors=True)
            ok(f"Removed {qml_dir.name} (user-path QML)")
    for so in LEGACY_SOS_SYSTEM:
        if so.is_file():
            sudo_remove(so, f"{so.name} (legacy)")


def install() -> None:
    _drop_legacy()
    if LEGACY_QML.is_dir():
        shutil.rmtree(LEGACY_QML, ignore_errors=True)
        ok("Removed old QML menu")

    artifact = BUILD / "bin/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so"
    if not artifact.is_file():
        fail("Global Menu build artifact missing")
        return
    if not sudo_install_file(artifact, DEST_SO, "Global Menu installed"):
        return

    module_src = BUILD / "bin/plasma/applet/org/kde/mac/tahoe/liquid/globalmenu"
    if not module_src.is_dir():
        fail("Global Menu runtime QML missing")
        return
    sudo_install_tree(module_src, DEST_QML_DIR, "Global Menu runtime QML")

    _install_about_info()


def _install_about_info() -> None:
    if not ABOUT_INFO_SRC.is_file():
        warn("System info helper source missing")
        return
    ABOUT_INFO_DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ABOUT_INFO_SRC, ABOUT_INFO_DEST)
    ABOUT_INFO_DEST.chmod(0o755)
    ok("System info helper installed")


def uninstall() -> None:
    sudo_remove(DEST_SO, "Global Menu .so removed")
    sudo_remove(DEST_QML_DIR, "Global Menu runtime QML removed")
    try:
        ABOUT_INFO_DEST.unlink()
        ok("System info helper removed")
    except FileNotFoundError:
        pass
    except OSError:
        pass
    _drop_legacy()
    if LEGACY_QML.is_dir():
        shutil.rmtree(LEGACY_QML, ignore_errors=True)
        ok("Removed old QML menu")
