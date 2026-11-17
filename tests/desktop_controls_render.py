"""Exercise the shipped popup lifecycle, native blur request and transparent gaps."""
import sys
import ctypes
import ctypes.util
from pathlib import Path
from PyQt6.QtCore import QUrl, QPoint, QRect, QMetaObject, Qt
from PyQt6.QtGui import QRegion
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickWindow
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest

app = QApplication([])
engine = QQmlEngine()
engine.rootContext().setContextProperty('i18n',engine.evaluate('(function(text) { return text; })'))
source = Path(sys.argv[1]) / 'src/offline/plasmoids/org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui'
component = QQmlComponent(engine)
component.setData(('''import QtQuick
import org.kde.plasma.core as PlasmaCore
import org.kde.mac.tahoe.launcher as Native
import "'''+source.as_uri()+'''" as Controls
PlasmaCore.Dialog {
    id: popup
    visible: false
    backgroundHints: PlasmaCore.Dialog.NoBackground
    mainItem: Controls.ControlView { id: controls; width: implicitWidth; height: implicitHeight }
    property var glass: Native.ControlGlass { window: popup; surfaces: controls.surfaces }
    function refreshTheme() {
        backgroundHints = PlasmaCore.Dialog.StandardBackground;
        backgroundHints = PlasmaCore.Dialog.NoBackground;
    }
}
''').encode(),QUrl.fromLocalFile(str(source/'render-probe.qml')))
assert component.isReady(), [e.toString() for e in component.errors()]
view = component.create();assert view is not None
root = view.property('mainItem')
view.show();QTest.qWait(500)

def published_blur_region():
    # Inspect the real X11 request, not just the helper's input mask. libX11
    # is already required by the native X11 test environment; no CLI dependency.
    x11 = ctypes.CDLL(ctypes.util.find_library('X11'))
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]; x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XInternAtom.argtypes = [ctypes.c_void_p,ctypes.c_char_p,ctypes.c_int]; x11.XInternAtom.restype = ctypes.c_ulong
    x11.XGetWindowProperty.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long,
        ctypes.c_long, ctypes.c_int, ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
    ]
    x11.XFree.argtypes = [ctypes.c_void_p]; x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    display = x11.XOpenDisplay(None); assert display
    data = ctypes.POINTER(ctypes.c_ubyte)()
    try:
        atom = x11.XInternAtom(display,b'_KDE_NET_WM_BLUR_BEHIND_REGION',False)
        kind=ctypes.c_ulong();format=ctypes.c_int();count=ctypes.c_ulong();remaining=ctypes.c_ulong()
        assert x11.XGetWindowProperty(display,int(view.winId()),atom,0,65536,False,0,ctypes.byref(kind),ctypes.byref(format),ctypes.byref(count),ctypes.byref(remaining),ctypes.byref(data)) == 0
        assert format.value == 32 and count.value > 0 and count.value % 4 == 0, 'Popup has no explicit compositor blur region'
        values=ctypes.cast(data,ctypes.POINTER(ctypes.c_ulong));region=QRegion()
        for i in range(0,count.value,4):region |= QRegion(QRect(*[values[i+j] for j in range(4)]))
        return region
    finally:
        if data:x11.XFree(data)
        x11.XCloseDisplay(display)

def assert_islands():
    assert view.mask().contains(QPoint(42,42)), 'Plasma cleared the control mask'
    assert not view.mask().contains(QPoint(5,5)), 'Transparent margin intercepts input'
    surfaces = [s for s in root.property('surfaces').toVariant() if s.get('width', 0) > 0]
    top = min(s['y'] for s in surfaces)
    first, second = sorted((s for s in surfaces if s['y'] == top), key=lambda s:s['x'])[:2]
    right = first['x'] + first['width']
    assert second['x'] - right >= 2, 'Controls have no transparent gap'
    gap = QPoint(round((right + second['x'])/2), round(top + min(first['height'], second['height'])/2))
    assert not view.mask().contains(gap), 'Gap between controls intercepts input'
    assert published_blur_region() == view.mask(), 'Compositor blur and input islands disagree'

assert_islands()
# NoBackground explicitly clears blur and mask after a live theme update.
# This is the production regression that a plain QQuickView cannot exercise.
QMetaObject.invokeMethod(view, 'refreshTheme', Qt.ConnectionType.DirectConnection)
assert view.mask().isEmpty(), 'Regression did not exercise Plasma clearing its background'
QTest.qWait(300)
assert_islands()
view.hide();QTest.qWait(50);view.show();QTest.qWait(300)
assert_islands()
image=view.grabWindow();assert not image.isNull()
assert 0 < image.pixelColor(42,42).alpha() < 255, 'Glass centre must stay translucent'
assert image.pixelColor(5,5).alpha() == 0
assert image.save(sys.argv[2])
print('CONTROL_CENTER_X11_RENDER_OK',view.width(),view.height())
view.close()
