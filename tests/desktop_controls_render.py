"""Render the shipped floating Control Center on an isolated X11 display."""
import sys
from pathlib import Path
from PyQt6.QtCore import QUrl, Qt, QPoint
from PyQt6.QtGui import QColor
from PyQt6.QtQml import QQmlComponent
from PyQt6.QtQuick import QQuickView
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest

app = QApplication([])
view = QQuickView()
view.setColor(QColor('transparent'))
view.setFlags(Qt.WindowType.FramelessWindowHint)
engine = view.engine()
engine.rootContext().setContextProperty('i18n',engine.evaluate('(function(text) { return text; })'))
source = Path(sys.argv[1]) / 'src/offline/plasmoids/org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui/ControlView.qml'
component = QQmlComponent(engine,QUrl.fromLocalFile(str(source)))
assert component.isReady(), [e.toString() for e in component.errors()]
root = component.create();assert root is not None
view.setContent(QUrl.fromLocalFile(str(source)),component,root)
view.resize(320,round(root.property('implicitHeight')))
root.setWidth(view.width());root.setHeight(view.height())
glass_component = QQmlComponent(engine)
glass_component.setData(b'import org.kde.mac.tahoe.launcher\nControlGlass {}',QUrl())
assert glass_component.isReady(), [e.toString() for e in glass_component.errors()]
glass = glass_component.createWithInitialProperties({'window':view,'surfaces':root.property('surfaces').toVariant()})
assert glass is not None
view.show();QTest.qWait(500)
image=view.grabWindow();assert not image.isNull()
assert view.mask().contains(QPoint(42,42)) and not view.mask().contains(QPoint(5,5))
assert image.pixelColor(42,42).alpha() > 80
assert image.pixelColor(5,5).alpha() == 0
assert image.save(sys.argv[2])
print('CONTROL_CENTER_X11_RENDER_OK',view.width(),view.height())
view.close()
