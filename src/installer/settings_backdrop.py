"""Request compositor blur for the Settings sidebar in logical client pixels."""

from ctypes import CDLL, c_bool, c_int, c_void_p
from functools import cache

from PyQt6 import sip
from PyQt6.QtCore import QLibraryInfo
from PyQt6.QtGui import QGuiApplication


@cache
def _window_effects():
    platform = QGuiApplication.platformName()
    if platform != "xcb" and not platform.startswith("wayland"):
        return None
    if "/PyQt6/Qt6/" in QLibraryInfo.path(QLibraryInfo.LibraryPath.LibrariesPath) + "/":
        return None  # A PyPI Qt runtime cannot use the system KDE platform plugin.
    try:
        library = CDLL("libKF6WindowSystem.so.6")
        # PyQt has no binding for these two public KWindowEffects functions.
        available = library._ZN14KWindowEffects17isEffectAvailableENS_6EffectE
        available.argtypes = [c_int]
        available.restype = c_bool
        blur = library._ZN14KWindowEffects16enableBlurBehindEP7QWindowbRK7QRegion
        blur.argtypes = [c_void_p, c_bool, c_void_p]
        blur.restype = None
    except (OSError, AttributeError):
        return None
    return library, available, blur


def set_window_blur(window, region):
    effects = _window_effects()
    if effects is None:
        return False
    _, available, blur = effects
    enabled = not region.isEmpty()
    blur(sip.unwrapinstance(window), enabled, sip.unwrapinstance(region))
    return enabled and available(7)  # KWindowEffects::BlurBehind
