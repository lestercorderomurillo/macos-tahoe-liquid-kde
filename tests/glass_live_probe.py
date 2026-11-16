"""Read the real native/QML background after a component Apply."""
import json
from pathlib import Path
import sys
from PyQt6.QtCore import QUrl, QObject, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusMessage
from PyQt6.QtWidgets import QApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtTest import QTest
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtCore import QRectF
sys.path.insert(0, str(Path(sys.argv[1]) / 'src/scripts'))
import glass_surface_settings as surfaces
import os
root = Path(os.environ['HOME'])
data, config, state = (Path(os.environ[k]) for k in ('XDG_DATA_HOME','XDG_CONFIG_HOME','XDG_STATE_HOME'))
materials = json.loads((root/'materials.json').read_text())
def apply():
    surfaces.apply(materials,data,config,state)
    surfaces.atomic_write(config/'kwinrc', ('[Effect-liquidglass]\nComponentMaterials='+json.dumps(materials,separators=(',',':'))+'\n').encode())
apply()
app=QApplication([])
class DockRegistry(QObject):
    entries = None
    @pyqtSlot(str)
    def changed(self, value):
        self.entries = json.loads(value)
registry = DockRegistry()
bus = QDBusConnection.sessionBus()
assert bus.connect('', '/org/kde/MacTahoe/Glass', 'org.kde.MacTahoe.Glass', 'windowsChanged', registry.changed)
engine=QQmlEngine()
qml = b'''import QtQuick
import org.kde.ksvg as KSvg
import org.kde.mac.tahoe.launcher as Native
Window {
 id: root; width: 240; height: 140; visible: true; color: "transparent"
 property alias surface: frame.imagePath
 property real fill: material.lightOpacity
 Native.GlassSettings { id: material; component: "apps"; window: root }
 KSvg.FrameSvgItem { id: frame; anchors.fill: parent; imagePath: "dialogs/background" }
}'''
source=root/'surface.qml'
source.write_bytes(qml)
c=QQmlComponent(engine,QUrl.fromLocalFile(str(source)))
assert c.isReady(),[e.toString() for e in c.errors()]
w=c.create()
assert w is not None,[e.toString() for e in c.errors()]
QTest.qWait(250)
initial=w.property('surface')
assert str(data) in initial,initial
assert abs(w.property('fill')-.55)<.001
materials['apps']['SurfaceTransparencyLight']=70
apply()
QTest.qWait(250)
updated=w.property('surface')
assert updated!=initial,(initial,updated)
assert abs(w.property('fill')-.3)<.001
image=QImage(64,64,QImage.Format.Format_ARGB32)
image.fill(0)
p=QPainter(image)
QSvgRenderer(updated).render(p,'center',QRectF(0,0,64,64))
p.end()
assert abs(image.pixelColor(32,32).alphaF()-.3)<.01
materials['dock']['SurfaceTransparencyLight']=40
apply()
QTest.qWait(250)
assert w.property('surface')==updated,'Dock update changed Apps background'
w.close()
# Plasma initializes the panel title after attaching its applets. A later
# show must retain the identity used by the compositor's component selector.
source.write_bytes(qml.replace(b'component: "apps"', b'component: "dock"').replace(b'dialogs/background', b'widgets/panel-background'))
engine.clearComponentCache()
dock_component=QQmlComponent(engine,QUrl.fromLocalFile(str(source)))
dock=dock_component.create()
assert dock is not None,[e.toString() for e in dock_component.errors()]
QTest.qWait(100)
dock.hide()
dock.setTitle("")
dock.show()
QTest.qWait(100)
assert dock.title() == "mttkde-dock",dock.title()
dock.setPosition(37, 53)
QTest.qWait(100)
assert registry.entries == [dict(pid=os.getpid(), x=37, y=53, width=240, height=140)],registry.entries
# An effect loaded after Plasma can request the current registry.
registry.entries = None
assert bus.send(QDBusMessage.createSignal('/org/kde/MacTahoe/Glass', 'org.kde.MacTahoe.Glass', 'requestWindows'))
QTest.qWait(100)
assert registry.entries and registry.entries[0]['x'] == 37,registry.entries
dock.close()
QTest.qWait(100)
assert registry.entries == [],registry.entries
print('LIVE_COMPONENT_SURFACE_OK')
