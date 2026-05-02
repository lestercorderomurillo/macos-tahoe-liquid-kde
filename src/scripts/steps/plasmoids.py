import re
import shutil
from pathlib import Path

from steps._helpers import (
    HOME, build_dir, cmake_build, fail, info, install_tree, ok, offline,
    remove_tree,
    sudo_remove, temp_dir,
)

SRC_DIR = offline("plasmoids")
DEST_DIR = HOME / ".local/share/plasma/plasmoids"

TASKMANAGER_SRC = SRC_DIR / "org.kde.mac.tahoe.liquid.taskmanager"
TASKMANAGER_BUILD = build_dir("plasmoids/org.kde.mac.tahoe.liquid.taskmanager")
# User-path install — Qt6 searches ~/.local/lib/qt6/plugins/ before the
# system path, so the new install never writes outside the user's tree.
# Sudo is still demanded by the CLI entry point, but only because we
# need root to *remove* the leftover /usr/lib .so from older releases.
TASKMANAGER_DEST_SO = HOME / (
    ".local/lib/qt6/plugins/plasma/applets/"
    "org.kde.mac.tahoe.liquid.taskmanager.so"
)
TASKMANAGER_DEST_QML = HOME / (
    ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/taskmanager"
)
LEGACY_TASKMANAGER_SYSTEM_SO = Path(
    "/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so"
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

# Older versions installed the dock under different IDs. Migrate any
# existing plasma-org.kde.plasma.desktop-appletsrc references so the dock
# survives the upgrade with the user's pinned launchers intact.
_APPLETSRC_RENAMES = (
    (r"org\.kde\.plasma\.icontasks", "org.kde.mac.tahoe.liquid.icontasks"),
    (r"org\.kde\.plasma\.taskmanager", "org.kde.mac.tahoe.liquid.taskmanager"),
    (r"org\.kde\.mac-tahoe-liquid-kde\.icontasks",
     "org.kde.mac.tahoe.liquid.icontasks"),
    (r"org\.kde\.mac-tahoe-liquid-kde\.taskmanager",
     "org.kde.mac.tahoe.liquid.taskmanager"),
)


def deps():
    return ["cmake", "g++:gcc", "pkg-config:pkgconf"]


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
    """Install the QML/runtime package for the compiled dock applet.

    The .so alone is not enough: the icons-only wrapper resolves through
    X-Plasma-RootPath and Plasma expects the taskmanager package metadata +
    contents/ tree to exist in the local plasmoid dir as well.
    """
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
    with temp_dir("mttkde-taskmanager-qml") as tmp:
        runtime = tmp / TASKMANAGER_DEST_QML.name
        shutil.copytree(module_src, runtime, symlinks=True)
        return install_tree(runtime, TASKMANAGER_DEST_QML,
                            "org.kde.mac.tahoe.liquid.taskmanager (installed runtime QML)")


def install() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    for name in LEGACY_DIRS:
        d = DEST_DIR / name
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
            ok(f"{name} (removed local override)")
    for qml_dir in LEGACY_TASKMANAGER_QML_DIRS:
        if qml_dir != TASKMANAGER_DEST_QML:
            remove_tree(qml_dir, qml_dir.name)

    _migrate_appletsrc()

    # Note: legacy ``/usr/lib`` cleanup intentionally lives in
    # ``uninstall()`` only — install is sudoless and only writes new
    # artefacts under the user's home. ``./uninstall`` is the path
    # that's allowed to ask for root and clean up old root-owned files.

    artifact = TASKMANAGER_BUILD / "bin/plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so"
    if artifact.is_file():
        TASKMANAGER_DEST_SO.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(artifact, TASKMANAGER_DEST_SO)
            ok("org.kde.mac.tahoe.liquid.taskmanager (installed compiled dock base)")
        except OSError as exc:
            fail(f"taskmanager .so install failed: {exc}")
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
    if TASKMANAGER_DEST_SO.is_file():
        try:
            TASKMANAGER_DEST_SO.unlink()
            ok(TASKMANAGER_DEST_SO.name); n += 1
        except OSError as exc:
            fail(f"{TASKMANAGER_DEST_SO.name} ({exc})")
    sudo_remove(LEGACY_TASKMANAGER_SYSTEM_SO,
                f"{LEGACY_TASKMANAGER_SYSTEM_SO.name} (legacy /usr/lib)")
    targets = [
        TASKMANAGER_DEST_QML,
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
