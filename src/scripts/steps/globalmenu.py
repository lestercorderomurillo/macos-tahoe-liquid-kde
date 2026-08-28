import shutil
from pathlib import Path

from distro import qt6_plugins_dir, qt6_qml_dir
from paths import REPO_ROOT, read_version
from steps._helpers import (
    DATA_HOME, HOME, build_dir, cmake_build, fail, ok, offline,
    sudo_install_file, sudo_install_tree, sudo_remove, warn,
)

SRC = offline("plasmoids/org.kde.mac.tahoe.liquid.globalmenu")
BUILD = build_dir("plasmoids/org.kde.mac.tahoe.liquid.globalmenu")

# AboutWindow shells out to this helper; it lives in ~/.local/bin so the
# script side stays sudoless (only the C++ .so install needs root).
ABOUT_INFO_SRC = REPO_ROOT / "src/scripts/about_info.py"
ABOUT_INFO_DEST = HOME / ".local/bin/mac-tahoe-about-info"
# Qt6 never scans user paths for plugins/QML — the .so + QML module MUST
# live under the qmake6-reported libdir (qt6_*_dir() handles per-distro).
_SO_RELPATH = "plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so"
_QML_RELPATH = "plasma/applet/org/kde/mac/tahoe/liquid/globalmenu"

_LEGACY_SO_BASENAMES = (
    "org.kde.mac.tahoe.liquid.menu.so",
    "org.kde.mac.tahoe.globalmenu.so",
    "org.kde.mac.tahoe.menu.so",
)


def __getattr__(name: str):
    """Lazy resolution so a missing qmake6 surfaces as a preflight failure
    with a distro hint, not a module-import crash."""
    if name == "DEST_SO":
        return qt6_plugins_dir() / _SO_RELPATH
    if name == "DEST_QML_DIR":
        return qt6_qml_dir() / _QML_RELPATH
    if name == "LEGACY_SOS_SYSTEM":
        base = qt6_plugins_dir() / "plasma/applets"
        return tuple(base / fn for fn in _LEGACY_SO_BASENAMES)
    raise AttributeError(name)
# Leftovers from old sudoless installs under user paths. Plain unlink, no
# sudo — they belong to the invoking user.
LEGACY_SOS_USER = (
    HOME / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.menu.so",
    HOME / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.globalmenu.so",
    HOME / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.menu.so",
    HOME / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so",
)
LEGACY_QML = DATA_HOME / "plasma/plasmoids/org.kde.mac-tahoe-liquid-kde.menu"
LEGACY_QML_MODULES_USER = (
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/menu",
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/globalmenu",
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/globalmenu",
)


def deps():
    return [
        "qmake6:qt6-base",
        "qt6-gui-cmake:qt6-base",
        "qt6-widgets-cmake:qt6-base",
        "qt6-dbus-cmake:qt6-base",
        "qt6-qml-cmake:qt6-declarative",
        "cmake",
        "ecm:extra-cmake-modules",
        "make",
        "g++:gcc",
        "pkg-config:pkgconf",
        # KF6 components required by the globalmenu CMakeLists.
        "kf6-config-cmake:kconfig",
        "kf6-coreaddons-cmake:kcoreaddons",
        "kf6-i18n-cmake:ki18n",
        "kf6-windowsystem-cmake:kwindowsystem",
        "kf6-itemmodels-cmake:kitemmodels",
        # Plasma + plasma-workspace (provides LibTaskManager cmake config).
        "plasma-cmake:libplasma",
        "libtaskmanager-cmake:plasma-workspace",
    ]


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
    legacy_base = qt6_plugins_dir() / "plasma/applets"
    for fn in _LEGACY_SO_BASENAMES:
        so = legacy_base / fn
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
    dest_so = qt6_plugins_dir() / _SO_RELPATH
    if not sudo_install_file(artifact, dest_so, "Global Menu installed"):
        return

    module_src = BUILD / "bin/plasma/applet/org/kde/mac/tahoe/liquid/globalmenu"
    if not module_src.is_dir():
        fail("Global Menu runtime QML missing")
        return
    sudo_install_tree(module_src, qt6_qml_dir() / _QML_RELPATH,
                      "Global Menu runtime QML")

    _install_about_info()


def _install_about_info() -> None:
    if not ABOUT_INFO_SRC.is_file():
        warn("System info helper source missing")
        return
    ABOUT_INFO_DEST.parent.mkdir(parents=True, exist_ok=True)
    # Bake the version in: the installed copy sits outside the repo, so
    # About This Computer reports whatever version installed it.
    source = ABOUT_INFO_SRC.read_text(encoding="utf-8")
    ABOUT_INFO_DEST.write_text(
        source.replace("@THEME_VERSION@", read_version()), encoding="utf-8")
    ABOUT_INFO_DEST.chmod(0o755)
    ok("System info helper installed")


def uninstall() -> None:
    sudo_remove(qt6_plugins_dir() / _SO_RELPATH, "Global Menu .so removed")
    sudo_remove(qt6_qml_dir() / _QML_RELPATH, "Global Menu runtime QML removed")
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
