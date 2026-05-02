import shutil
from pathlib import Path

from steps._helpers import (
    HOME, build_dir, cmake_build, fail, ok, offline, warn,
)

SRC = offline("plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu")
BUILD = build_dir("plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu")
# User-path install — Qt6 searches ~/.local/lib/qt6/plugins/ before the
# system path, so we never need sudo for the C++ plasmoid. This also
# sidesteps the entire pam_unix conversation-failed / faillock cascade
# that was making install unusable on terminals where sudo prompts can't
# read the password reliably.
DEST_SO = HOME / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so"

# Older builds wrote .so files at these paths, both system-wide and
# user-local. Duplicate IDs make plasmashell load the wrong applet on
# resume, so we clean them up. System-wide ones obviously need root, but
# we attempt the unlink anyway and only warn (not fail) on EACCES — the
# user can mop them up with ``sudo rm`` if they care.
LEGACY_SOS_SYSTEM = (
    "/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.menu.so",
    "/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.globalmenu.so",
    "/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.menu.so",
    "/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so",
)
LEGACY_SOS_USER = (
    HOME / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.menu.so",
    HOME / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.globalmenu.so",
    HOME / ".local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.menu.so",
)
LEGACY_QML = HOME / ".local/share/plasma/plasmoids/org.kde.mac-tahoe-liquid-kde.menu"


def deps():
    return ["cmake", "g++:gcc", "pkg-config:pkgconf"]


def build() -> None:
    cmake_build(SRC, BUILD, "Global Menu")


def _try_remove_root_owned(path: Path, label: str) -> None:
    """Best-effort unlink for a path that may be root-owned. Silent on
    'not there' and 'no permission' — just informative on PermissionError
    so the user knows to run ``sudo rm`` manually if they care about the
    leftover system-path .so."""
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
    for so in LEGACY_SOS_USER:
        if so.is_file():
            try:
                so.unlink()
                ok(f"Removed {so.name}")
            except OSError:
                pass
    for so in LEGACY_SOS_SYSTEM:
        _try_remove_root_owned(Path(so), f"Removed {Path(so).name}")
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


def uninstall() -> None:
    if DEST_SO.is_file():
        try:
            DEST_SO.unlink()
            ok("Global Menu .so removed")
        except OSError as exc:
            fail(f"Global Menu remove failed: {exc}")
    for so in LEGACY_SOS_USER:
        if so.is_file():
            try:
                so.unlink()
                ok(f"{so.name} removed")
            except OSError:
                pass
    for so in LEGACY_SOS_SYSTEM:
        _try_remove_root_owned(Path(so), f"{Path(so).name} removed")
    if LEGACY_QML.is_dir():
        shutil.rmtree(LEGACY_QML, ignore_errors=True)
        ok("Removed old QML menu")
