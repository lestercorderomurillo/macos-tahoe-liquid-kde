import re
import shutil
from pathlib import Path

from steps._helpers import (
    HOME, build_dir, cmake_build, fail, info, install_tree, ok, offline,
    temp_dir, warn,
)

SRC_DIR = offline("plasmoids")
DEST_DIR = HOME / ".local/share/plasma/plasmoids"

TASKMANAGER_SRC = SRC_DIR / "org.kde.mac.tahoe.liquid.taskmanager"
TASKMANAGER_BUILD = build_dir("plasmoids/org.kde.mac.tahoe.liquid.taskmanager")
# User-path install (matches globalmenu) — Qt6 searches
# ~/.local/lib/qt6/plugins/ before the system path, so the entire install
# stays sudo-free. Avoids the pam_unix / faillock cascade that bricked
# install on terminals where sudo prompts can't read the password.
TASKMANAGER_DEST_SO = HOME / (
    ".local/lib/qt6/plugins/plasma/applets/"
    "org.kde.mac.tahoe.liquid.taskmanager.so"
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


def _try_remove_root_owned(path: Path, label: str) -> None:
    if not path.exists() and not path.is_symlink():
        return
    try:
        path.unlink()
        ok(label)
    except PermissionError:
        warn(f"{label} (left in place — needs `sudo rm {path}` to clean up)")
    except OSError as exc:
        warn(f"{label} ({exc.__class__.__name__})")


def install() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    for name in LEGACY_DIRS:
        d = DEST_DIR / name
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
            ok(f"{name} (removed local override)")

    _migrate_appletsrc()

    # Older installs put the .so in /usr/lib (system path, root-owned).
    # Try to remove it so the user-path install is the only one Plasma
    # sees — best-effort, no sudo prompt.
    _try_remove_root_owned(LEGACY_TASKMANAGER_SYSTEM_SO,
                           f"Removed {LEGACY_TASKMANAGER_SYSTEM_SO.name} (legacy system path)")

    artifact = TASKMANAGER_BUILD / "bin/plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so"
    if artifact.is_file():
        TASKMANAGER_DEST_SO.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(artifact, TASKMANAGER_DEST_SO)
            ok("org.kde.mac.tahoe.liquid.taskmanager (installed compiled dock base)")
        except OSError as exc:
            fail(f"taskmanager .so install failed: {exc}")
        _install_taskmanager_package()
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
    _try_remove_root_owned(LEGACY_TASKMANAGER_SYSTEM_SO,
                           f"{LEGACY_TASKMANAGER_SYSTEM_SO.name} (legacy system path)")
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
