import re
import shutil
from pathlib import Path

from distro import qt6_plugins_dir, qt6_qml_dir
from steps._helpers import (
    HOME, build_dir, cmake_build, fail, info, install_tree, ok, offline,
    remove_tree,
    sudo_install_file, sudo_install_tree, sudo_remove, temp_dir,
)

SRC_DIR = offline("plasmoids")
DEST_DIR = HOME / ".local/share/plasma/plasmoids"

TASKMANAGER_SRC = SRC_DIR / "org.kde.mac.tahoe.liquid.taskmanager"
TASKMANAGER_BUILD = build_dir("plasmoids/org.kde.mac.tahoe.liquid.taskmanager")
# Qt6 never scans user paths for plugins/QML — these go under the qmake6-
# reported libdir. Lazy __getattr__ keeps a missing qmake6 a preflight
# failure, not a module-import crash.
_TASKMANAGER_SO_RELPATH = "plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so"
_TASKMANAGER_QML_RELPATH = "plasma/applet/org/kde/mac/tahoe/liquid/taskmanager"


def __getattr__(name: str):
    if name == "TASKMANAGER_DEST_SO":
        return qt6_plugins_dir() / _TASKMANAGER_SO_RELPATH
    if name == "TASKMANAGER_DEST_QML":
        return qt6_qml_dir() / _TASKMANAGER_QML_RELPATH
    raise AttributeError(name)
# v0.8.4-0.8.6 sudoless leftover under user path.
LEGACY_TASKMANAGER_USER_SO = HOME / (
    ".local/lib/qt6/plugins/plasma/applets/"
    "org.kde.mac.tahoe.liquid.taskmanager.so"
)

LEGACY_DIRS = (
    "org.kde.mac.tahoe.liquid.taskmanager",
    "org.kde.plasma.taskmanager",
    "org.kde.plasma.icontasks",
    "org.kde.mac-tahoe-liquid-kde.taskmanager",
    "org.kde.mac-tahoe-liquid-kde.icontasks",
)
LEGACY_TASKMANAGER_QML_DIRS = (
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/plasma/taskmanager",
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/plasma/icontasks",
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/taskmanager",
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/icontasks",
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac-tahoe-liquid-kde/taskmanager",
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac-tahoe-liquid-kde/icontasks",
)

# Older releases used different dock IDs — rewrite appletsrc so the upgrade
# keeps the dock and the user's pinned launchers.
_APPLETSRC_RENAMES = (
    (r"org\.kde\.plasma\.icontasks", "org.kde.mac.tahoe.liquid.icontasks"),
    (r"org\.kde\.plasma\.taskmanager", "org.kde.mac.tahoe.liquid.taskmanager"),
    (r"org\.kde\.mac-tahoe-liquid-kde\.icontasks",
     "org.kde.mac.tahoe.liquid.icontasks"),
    (r"org\.kde\.mac-tahoe-liquid-kde\.taskmanager",
     "org.kde.mac.tahoe.liquid.taskmanager"),
)


def deps():
    return [
        "qmake6",
        "qt6-gui-cmake:qt6-base",
        "qt6-widgets-cmake:qt6-base",
        "qt6-dbus-cmake:qt6-base",
        "qt6-qml-cmake:qt6-declarative",
        "cmake",
        "ecm:extra-cmake-modules",
        "make",
        "g++:gcc",
        "pkg-config:pkgconf",
        # KF6 components required by the taskmanager CMakeLists.
        "kf6-config-cmake:kconfig",
        "kf6-coreaddons-cmake:kcoreaddons",
        "kf6-i18n-cmake:ki18n",
        "kf6-kio-cmake:kio",
        "kf6-notifications-cmake:knotifications",
        "kf6-service-cmake:kservice",
        "kf6-windowsystem-cmake:kwindowsystem",
        "kf6-itemmodels-cmake:kitemmodels",
        # Plasma / KSysGuard / plasma-workspace (provides
        # LibNotificationManager + LibTaskManager cmake config).
        "plasma-cmake:libplasma",
        "plasma-activities-cmake:plasma-activities",
        "plasma-activities-stats-cmake:plasma-activities-stats",
        "ksysguard-cmake:libksysguard",
        "libnotificationmanager-cmake:plasma-workspace",
    ]


def build_artifacts() -> list[Path]:
    return [
        TASKMANAGER_BUILD / "bin/plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so",
        TASKMANAGER_BUILD / "bin/plasma/applet/org/kde/mac/tahoe/liquid/taskmanager",
    ]


def build() -> None:
    if (TASKMANAGER_SRC / "CMakeLists.txt").is_file():
        cmake_build(TASKMANAGER_SRC, TASKMANAGER_BUILD, "Dock Task Manager")


def _migrate_appletsrc() -> None:
    appletsrc = HOME / ".config/plasma-org.kde.plasma.desktop-appletsrc"
    if not appletsrc.is_file():
        return
    text = appletsrc.read_text()
    if not any(re.search(p, text) for p, _ in _APPLETSRC_RENAMES):
        return
    for pat, repl in _APPLETSRC_RENAMES:
        text = re.sub(pat, repl, text)
    appletsrc.write_text(text)
    ok("dock config migrated to MacTahoe dock fork")


def _install_taskmanager_package() -> bool:
    """Install the dock applet's QML/runtime package. The .so alone is not
    enough: the icons-only wrapper resolves via X-Plasma-RootPath and needs
    the package metadata + contents/ in the local plasmoid dir too."""
    metadata = TASKMANAGER_SRC / "metadata.json"
    contents = TASKMANAGER_SRC / "contents"
    if not metadata.is_file():
        fail("org.kde.mac.tahoe.liquid.taskmanager (missing metadata.json)")
        return False
    if not contents.is_dir():
        fail("org.kde.mac.tahoe.liquid.taskmanager (missing contents/)")
        return False

    with temp_dir("mttkde-taskmanager-package") as tmp:
        runtime = tmp / TASKMANAGER_SRC.name
        runtime.mkdir(parents=True, exist_ok=True)
        shutil.copy2(metadata, runtime / "metadata.json")
        shutil.copytree(contents, runtime / "contents", symlinks=True)
        return install_tree(runtime, DEST_DIR / TASKMANAGER_SRC.name,
                            TASKMANAGER_SRC.name)


def _install_taskmanager_qml() -> bool:
    module_src = TASKMANAGER_BUILD / "bin/plasma/applet/org/kde/mac/tahoe/liquid/taskmanager"
    if not module_src.is_dir():
        fail("org.kde.mac.tahoe.liquid.taskmanager (missing runtime QML)")
        return False
    return sudo_install_tree(
        module_src, qt6_qml_dir() / _TASKMANAGER_QML_RELPATH,
        "org.kde.mac.tahoe.liquid.taskmanager (installed runtime QML)",
    )


def install() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    dest_qml = qt6_qml_dir() / _TASKMANAGER_QML_RELPATH
    for name in LEGACY_DIRS:
        d = DEST_DIR / name
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
            ok(f"{name} (removed local override)")
    for qml_dir in LEGACY_TASKMANAGER_QML_DIRS:
        if qml_dir != dest_qml:
            remove_tree(qml_dir, qml_dir.name)
    if LEGACY_TASKMANAGER_USER_SO.is_file():
        try:
            LEGACY_TASKMANAGER_USER_SO.unlink()
            ok(f"{LEGACY_TASKMANAGER_USER_SO.name} (user-path leftover)")
        except OSError:
            pass

    _migrate_appletsrc()

    artifact = TASKMANAGER_BUILD / "bin/plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so"
    if artifact.is_file():
        if sudo_install_file(
            artifact, qt6_plugins_dir() / _TASKMANAGER_SO_RELPATH,
            "org.kde.mac.tahoe.liquid.taskmanager (installed compiled dock base)",
        ):
            _install_taskmanager_package()
            _install_taskmanager_qml()
    else:
        fail("org.kde.mac.tahoe.liquid.taskmanager (missing build artifact)")

    n = 0
    for widget in sorted(SRC_DIR.glob("*/")):
        if not widget.is_dir():
            continue
        # C++ applets are installed via their own build steps.
        if (widget / "CMakeLists.txt").is_file():
            continue
        if not (widget / "metadata.json").is_file():
            fail(f"{widget.name} (no metadata.json — skipping)")
            continue
        if install_tree(widget, DEST_DIR / widget.name):
            n += 1
    label = "plasmoid" if n == 1 else "plasmoids"
    info(f"{n} {label} installed/reinstalled")


def uninstall() -> None:
    n = 0
    dest_so = qt6_plugins_dir() / _TASKMANAGER_SO_RELPATH
    dest_qml = qt6_qml_dir() / _TASKMANAGER_QML_RELPATH
    if sudo_remove(dest_so, dest_so.name):
        n += 1
    if sudo_remove(dest_qml, dest_qml.name):
        n += 1
    if LEGACY_TASKMANAGER_USER_SO.is_file():
        try:
            LEGACY_TASKMANAGER_USER_SO.unlink()
            ok(f"{LEGACY_TASKMANAGER_USER_SO.name} (user-path leftover)"); n += 1
        except OSError:
            pass
    targets = [
        DEST_DIR / "org.kde.mac.tahoe.liquid.taskmanager",
        DEST_DIR / "org.kde.mac.tahoe.liquid.icontasks",
        *DEST_DIR.glob("org.kde.mac-tahoe-liquid-kde.*"),
        *DEST_DIR.glob("org.kde.mactahoe-liquid-kde.*"),
        DEST_DIR / "org.kde.plasma.icontasks",
        DEST_DIR / "org.kde.plasma.taskmanager",
    ]
    for d in targets:
        if d.is_dir():
            try:
                shutil.rmtree(d)
                ok(d.name); n += 1
            except OSError:
                fail(d.name)
    info(f"{n} plasmoids removed")
