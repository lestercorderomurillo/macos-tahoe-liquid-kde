"""Host the installed Acrylic Glass editor inside the Settings window."""

from ctypes import CDLL, c_void_p
from functools import cache
import os
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtCore import QLibraryInfo
from PyQt6.QtWidgets import QWidget


@cache
def _loaded_editor():
    plugins = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
    backends = ("kwin-x11", "kwin") if os.environ.get("XDG_SESSION_TYPE") == "x11" else ("kwin", "kwin-x11")
    for backend in backends:
        module = plugins / backend / "effects/configs/kwin_liquidglass_config.so"
        if not module.is_file():
            continue
        try:
            library = CDLL(str(module))
            attach = library.mttkde_attach_glass_editor
        except (OSError, AttributeError):
            continue
        attach.argtypes = [c_void_p]
        attach.restype = None
        return library, attach
    return None


def create_acrylic_glass_editor(parent):
    loaded = _loaded_editor()
    if loaded is None:
        return None
    _, attach = loaded
    editor = QWidget(parent)
    editor.setObjectName("acrylicGlassEditor")
    attach(sip.unwrapinstance(editor))
    return editor
