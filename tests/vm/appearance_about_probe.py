#!/usr/bin/env python3
"""Observe both real About windows through live changes in a disposable VM."""
import json
import sys
from pathlib import Path
from PyQt6.QtCore import QObject, QTimer, QUrl
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtWidgets import QApplication
import configparser

if Path('/sys/class/dmi/id/product_name').read_text().strip() != 'MTTKDE release capture':
    raise SystemExit('This probe requires the disposable capture VM')
app = QApplication(sys.argv[:1])
engine = QQmlApplicationEngine()
source = Path(__file__).resolve().parents[2] / 'src/offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu/qml'
output = Path.home() / 'appearance-probe/about.json'
output.unlink(missing_ok=True)
def theme_path():
    config = configparser.ConfigParser()
    config.read([Path.home() / '.config/kdedefaults/plasmarc', Path.home() / '.config/plasmarc'])
    name = config.get('Theme', 'name')
    return str(Path.home() / '.local/share/plasma/desktoptheme' / name)
engine.rootContext().setContextProperty('probeThemePath', theme_path())
for name in ('AboutWindow.qml', 'ApplicationAboutWindow.qml'):
    # Standalone QQml lacks Plasma's KSvg image-set context. Supply its current
    # theme path while preserving the source window's material logic.
    content = (source / name).read_text().replace('imagePath: \"dialogs/background\"', 'imagePath: probeThemePath + \"/dialogs/background.svgz\"')
    engine.loadData(content.encode(), QUrl.fromLocalFile(str(source / name)))
assert len(engine.rootObjects()) == 2
windows = engine.rootObjects()
for window in windows:
    window.show()
def record():
    engine.rootContext().setContextProperty('probeThemePath', theme_path())
    values = []
    for window in windows:
        surface = window.findChild(QObject, 'aboutGlassSurface')
        color = surface.property('color')
        values.append({'title': window.title(), 'dark': window.property('isDarkTheme'),
                       'surface': [color.redF(), color.greenF(), color.blueF(), color.alphaF()],
                       'controls': window.property('windowControlPath')})
    path = Path.home() / 'appearance-probe/about.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(values)); temporary.replace(path)
timer = QTimer(); timer.timeout.connect(record); timer.start(250)
app.exec()
