"""Opt-in clipboard history popup (Meta+V) with pinning and image previews.

Two user-level pieces, no root needed:

* ``mac-tahoe-clipd`` — a small C++ service built against KGuiAddons'
  ``KSystemClipboard``. It records text and images, skips anything a password
  manager marks secret, and serves the history over D-Bus
  (``org.mactahoe.Clipboard``). Started at login through an autostart entry.
* ``clipboard.py`` — the PyQt6 popup launched by the Meta+V global shortcut.

Plasma's own clipboard widget keeps working; only its Meta+V binding moves to
the popup (and is handed back on uninstall).

SPDX-License-Identifier: GPL-3.0-or-later
"""

from localization import tr

import os
import json
import re
import shlex
import time
import shutil
import subprocess
import tempfile
from pathlib import Path

from log import note
from steps._native_build import cmake_build
from steps._helpers import DATA_HOME, HOME, build_dir, fail, ok, offline, warn
from utils import drop_privs_in_child, have, kw_write, run_user

SRC = offline("clipboard")
DAEMON_SRC = SRC / "clipd"
BUILD = build_dir("clipboard/clipd")

BIN_DIR = HOME / ".local/bin"
DAEMON_DEST = BIN_DIR / "mac-tahoe-clipd"
LAUNCHER_DEST = BIN_DIR / "mac-tahoe-clipboard"
APP_DIR = DATA_HOME / "mac-tahoe-liquid-kde"
POPUP_DEST = APP_DIR / "clipboard.py"
HISTORY_DIR = APP_DIR / "clipboard"
DESKTOP_DEST = DATA_HOME / "applications/mac-tahoe-clipboard.desktop"
AUTOSTART_DEST = (Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config")
                  / "autostart/mac-tahoe-clipd.desktop")

SERVICE_ID = "mac-tahoe-clipboard.desktop"
SERVICE_BUS = "org.mactahoe.Clipboard"
# Qt::META | Qt::Key_V — the binding Plasma's own clipboard widget ships with.
META_V = 0x10000000 | 0x56

LAUNCHER_TEMPLATE = """#!/bin/sh
exec /usr/bin/env python3 {popup} "$@"
"""

DESKTOP_TEMPLATE = """[Desktop Entry]
Type=Application
Name=Clipboard
Comment=Minimal clipboard history with pinning
Exec={launcher}
Icon=edit-paste
NoDisplay=true
StartupNotify=false
X-KDE-StartupNotify=false
"""

AUTOSTART_TEMPLATE = """[Desktop Entry]
Type=Application
Name=Clipboard history service
Comment=Records clipboard text and images for the Meta+V popup
Exec={daemon}
Icon=edit-paste
NoDisplay=true
X-KDE-autostart-after=panel
"""


def deps():
    return [
        "cmake",
        "g++:gcc",
        "make",
        "qmake6:qt6-base",
        "qt6-gui-cmake:qt6-base",
        "qt6-dbus-cmake:qt6-base",
        "kf6-guiaddons-cmake:kguiaddons",
    ]


def build() -> None:
    if not (DAEMON_SRC / "CMakeLists.txt").is_file():
        return
    if not cmake_build(DAEMON_SRC, BUILD, "Clipboard service"):
        raise RuntimeError("Clipboard service build failed")


def _write_atomic(dest: Path, data: bytes | str, mode: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data if isinstance(data, bytes) else data.encode("utf-8"))
        os.chmod(tmp, mode)
        os.replace(tmp, dest)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _bus(*args: str) -> bool:
    """Best-effort D-Bus call on the user's session bus. False when the tool or session is missing."""
    if not have("dbus-send"):
        return False
    result = run_user(["dbus-send", "--session", "--print-reply", *args],
                      capture_output=True, text=True, check=False)
    return getattr(result, "returncode", 1) == 0


def _bind(component: str, action: str, friendly: str, key: int) -> bool:
    action_id = f"array:string:{component},{action},{friendly},{friendly}"
    keys = f"array:int32:{key}"
    return _bus("--dest=org.kde.kglobalaccel", "/kglobalaccel",
                "org.kde.KGlobalAccel.setForeignShortcut", action_id, keys)


def _shortcut_keys(component: str, action: str) -> list[int] | None:
    if not have("dbus-send"):
        return None
    result = run_user(["dbus-send", "--session", "--print-reply",
                       "--dest=org.kde.kglobalaccel", "/kglobalaccel",
                       "org.kde.KGlobalAccel.shortcut",
                       f"array:string:{component},{action},{component},{action}"],
                      capture_output=True, text=True, check=False)
    if result.returncode:
        return None
    return [int(key) for key in re.findall(r"int32\s+(-?\d+)", result.stdout)]


def _shortcut_state() -> Path:
    return APP_DIR / "clipboard-shortcut.json"


def _restore_plasma_keys(keys: list[int]) -> bool:
    return _bus("--dest=org.kde.kglobalaccel", "/kglobalaccel",
                "org.kde.KGlobalAccel.setForeignShortcut",
                "array:string:plasmashell,show-on-mouse-pos,Show Clipboard Items at Mouse Position,Show Clipboard Items at Mouse Position",
                "array:int32:" + ",".join(str(key) for key in (keys or [0])))


def _register_shortcuts() -> bool:
    """Move Meta+V from Plasma's clipboard widget to the popup, live and persistently."""
    previous = _shortcut_keys("plasmashell", "show-on-mouse-pos")
    if previous is None:
        return False
    if not _shortcut_state().exists():
        _write_atomic(_shortcut_state(), json.dumps({"keys": previous}), 0o600)
    if not _bus("--dest=org.kde.kglobalaccel", "/kglobalaccel", "org.kde.KGlobalAccel.doRegister",
                f"array:string:{SERVICE_ID},_launch,Clipboard,Clipboard"):
        return False
    remaining = [key for key in previous if key != META_V]
    freed = (META_V not in previous or _restore_plasma_keys(remaining))
    bound = _bind(SERVICE_ID, "_launch", "Clipboard", META_V)
    if bound:
        kw_write("--file", "kglobalshortcutsrc", "--group", "services", "--group", SERVICE_ID,
                 "--key", "_launch", "Meta+V")
    elif freed and META_V in previous:
        _restore_plasma_keys(previous)
    return freed and bound


def _stop_service() -> None:
    _bus(f"--dest={SERVICE_BUS}", "/Clipboard", "org.mactahoe.Clipboard.quit")
    if not have("dbus-send"):
        return
    for _ in range(30):
        result = run_user(["dbus-send", "--session", "--print-reply",
                           "--dest=org.freedesktop.DBus", "/org/freedesktop/DBus",
                           "org.freedesktop.DBus.NameHasOwner", f"string:{SERVICE_BUS}"],
                          capture_output=True, text=True, check=False)
        if result.returncode or "boolean true" not in result.stdout:
            return
        time.sleep(0.1)
    raise RuntimeError("Clipboard service did not stop")


def _desktop_exec(path: Path) -> str:
    value = str(path).replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$").replace("%", "%%")
    return '"' + value + '"'


def install() -> None:
    daemon_built = BUILD / "mac-tahoe-clipd"
    popup_src = SRC / "clipboard.py"
    if not daemon_built.is_file() or not popup_src.is_file():
        fail(tr('Clipboard: build artifacts missing — skipping install'))
        return
    try:
        import PyQt6.QtDBus, PyQt6.QtWidgets  # noqa: F401,E401
    except ImportError:
        warn(tr('Clipboard: PyQt6 (QtWidgets, QtDBus) is missing — the Meta+V popup will not start until it is installed'))

    # Capture ownership before desktop-file discovery can register the action.
    if not _shortcut_state().exists():
        previous = _shortcut_keys("plasmashell", "show-on-mouse-pos")
        if previous is not None:
            _write_atomic(_shortcut_state(), json.dumps({"keys": previous}), 0o600)
    _stop_service()   # a running copy keeps its inode; replace the files atomically
    _write_atomic(DAEMON_DEST, daemon_built.read_bytes(), 0o755)
    _write_atomic(POPUP_DEST, popup_src.read_bytes(), 0o644)
    _write_atomic(LAUNCHER_DEST, LAUNCHER_TEMPLATE.format(popup=shlex.quote(str(POPUP_DEST))), 0o755)
    _write_atomic(DESKTOP_DEST, DESKTOP_TEMPLATE.format(launcher=_desktop_exec(LAUNCHER_DEST)), 0o644)
    _write_atomic(AUTOSTART_DEST, AUTOSTART_TEMPLATE.format(daemon=_desktop_exec(DAEMON_DEST)), 0o644)
    ok(tr('Clipboard service and popup installed'))

    if have("update-desktop-database"):
        run_user(["update-desktop-database", str(DESKTOP_DEST.parent)],
                 capture_output=True, check=False)
    if have("kbuildsycoca6"):
        run_user(["kbuildsycoca6"], capture_output=True, check=False)

    # Start now so the history begins immediately; the autostart entry covers later logins.
    subprocess.Popen([str(DAEMON_DEST)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True,
                     preexec_fn=drop_privs_in_child)
    for _ in range(30):
        if _bus(f"--dest={SERVICE_BUS}", "/Clipboard", "org.mactahoe.Clipboard.version"):
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("Clipboard service did not become ready")
    if _register_shortcuts():
        ok(tr('Meta+V now opens the clipboard popup'))
    else:
        warn(tr('Clipboard: could not bind Meta+V live — assign the "Clipboard" entry in System Settings › Shortcuts'))
    note(tr('Clipboard history is stored privately in ~/.local/share/mac-tahoe-liquid-kde/clipboard'))


def uninstall() -> None:
    owned = any(path.exists() or path.is_symlink() for path in
                (DAEMON_DEST, LAUNCHER_DEST, POPUP_DEST, DESKTOP_DEST, AUTOSTART_DEST, _shortcut_state()))
    owned = owned or (HISTORY_DIR.is_dir() and not HISTORY_DIR.is_symlink())
    if not owned:
        return
    _stop_service()
    # Hand Meta+V back to Plasma's clipboard widget before dropping our entry.
    try:
        previous = json.loads(_shortcut_state().read_text())["keys"]
    except (OSError, ValueError, KeyError, TypeError):
        previous = None
    if not isinstance(previous, list) or not all(type(key) is int and 0 <= key <= 0x7fffffff for key in previous):
        previous = None
    current = _shortcut_keys("plasmashell", "show-on-mouse-pos")
    if previous is not None and META_V in previous:
        remaining = [key for key in previous if key != META_V]
        if current == remaining or (not remaining and current == [0]):
            _restore_plasma_keys(previous)
    _shortcut_state().unlink(missing_ok=True)
    _bus("--dest=org.kde.kglobalaccel", "/kglobalaccel", "org.kde.KGlobalAccel.unregister",
         f"string:{SERVICE_ID}", "string:_launch")
    removed = False
    for path in (DAEMON_DEST, LAUNCHER_DEST, POPUP_DEST, DESKTOP_DEST, AUTOSTART_DEST):
        if path.is_file() or path.is_symlink():
            path.unlink()
            removed = True
    if HISTORY_DIR.is_dir() and not HISTORY_DIR.is_symlink():
        # Failure must reach the installer; never report private history as
        # removed when permissions or I/O errors left it on disk. A retry can
        # still discover HISTORY_DIR after the other payloads were removed.
        shutil.rmtree(HISTORY_DIR)
        removed = True
    if removed:
        ok(tr('Clipboard popup and service removed'))
