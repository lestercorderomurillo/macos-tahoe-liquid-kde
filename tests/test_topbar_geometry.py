"""Exercise the real menu delegate geometry at varied panel heights and labels."""
import os
import subprocess
import sys


def test_topbar_highlight_preserves_hit_area_and_text(repo, tmp_path):
    probe = r'''
import sys
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtQml import QQmlEngine, QQmlComponent, QQmlProperty
app = QGuiApplication([])
engine = QQmlEngine()
component = QQmlComponent(engine, QUrl.fromLocalFile(sys.argv[1]))
button = component.create()
assert button is not None, component.errors()
for height in (24, 32, 48):
    for text in ('Files', 'Visual Studio Code', 'Window'):
        button.setProperty('text', text)
        button.setProperty('height', height)
        app.processEvents()
        button.setProperty('width', button.property('implicitWidth'))
        app.processEvents()
        background = QQmlProperty(button, 'background').read()
        content = QQmlProperty(button, 'contentItem').read()
        assert 0 < background.y() < height / 2
        assert background.height() == height - 2 * background.y()
        assert background.width() == button.width()
        assert background.property('radius') == background.height() / 2
        assert button.height() == height
        assert button.property('topPadding') == button.property('bottomPadding')
        assert content.width() >= content.property('implicitWidth') - 1
        assert button.property('leftPadding') == button.property('rightPadding')
        assert button.property('leftPadding') >= 12
'''
    qml = repo / 'src/offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu/qml/MenuDelegate.qml'
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
               HOME=str(tmp_path), XDG_CONFIG_HOME=str(tmp_path),
               DBUS_SESSION_BUS_ADDRESS='unix:path=/nonexistent')
    result = subprocess.run([sys.executable, '-c', probe, str(qml)], env=env,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
