"""Exercise the real generic About window, without changing the desktop."""
import argparse
import json
from pathlib import Path
import sys

from PyQt6.QtCore import QMetaObject, QObject, QStandardPaths, Qt, QUrl, Q_RETURN_ARG
from PyQt6.QtGui import QIcon, QPalette
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtQuick import QQuickWindow
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('light', 'dark'), default='light')
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--preview', action='store_true', help='Open a standalone preview without installing anything')
    parser.add_argument('--icon-theme')
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    if args.icon_theme:
        QIcon.setThemeSearchPaths([str(Path(p) / 'icons') for p in QStandardPaths.standardLocations(QStandardPaths.StandardLocation.GenericDataLocation)])
        QIcon.setThemeName(args.icon_theme)
    palette = app.palette()
    dark = args.mode == 'dark'
    for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base, QPalette.ColorRole.Button):
        palette.setColor(role, Qt.GlobalColor.black if dark else Qt.GlobalColor.white)
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(role, Qt.GlobalColor.white if dark else Qt.GlobalColor.black)
    app.setPalette(palette)
    engine = QQmlApplicationEngine()
    errors = []
    engine.warnings.connect(lambda warnings: errors.extend(str(w.toString()) for w in warnings))
    source = Path(__file__).resolve().parents[1] / 'src/offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu/qml/ApplicationAboutWindow.qml'
    engine.load(QUrl.fromLocalFile(str(source)))
    assert engine.rootObjects(), '\n'.join(errors)
    window = engine.rootObjects()[0]
    samples = [
        {'name': 'Files', 'description': 'File Manager', 'icon': QIcon.fromTheme('system-file-manager'),
         'executable': '/usr/bin/nautilus', 'desktopFile': '/usr/share/applications/org.gnome.Nautilus.desktop',
         'applicationId': 'org.gnome.Nautilus', 'processId': '1042'},
        {'name': 'Firefox', 'description': 'Web Browser', 'icon': QIcon.fromTheme('firefox'),
         'executable': '/usr/lib/firefox/firefox', 'applicationId': 'firefox', 'processId': '1043'},
        {'name': '<Editor> & Notes', 'description': '<b>Plain text, not markup</b>',
         'executable': '/a very long path/áéíóú/应用/' + 'directory/' * 40 + 'editor',
         'applicationId': 'org.example.' + 'LongName' * 30},
        {'name': 'Sandboxed app', 'desktopFile': '/var/lib/flatpak/exports/share/applications/org.example.App.desktop'},
        {},
    ]
    if args.preview:
        window.setProperty('applicationInfo', samples[0])
        window.show()
        window.requestActivate()
        app.exec()
        return
    for info in samples:
        window.setProperty('applicationInfo', info)
        window.show()
        window.requestActivate()
        QTest.qWait(120)
        assert window.isVisible()
        assert window.flags() & Qt.WindowType.FramelessWindowHint
        assert window.color().alpha() == 0
        assert window.findChild(QObject, 'aboutDragArea') is not None
        surface = window.findChild(QObject, 'aboutGlassSurface')
        assert 0 < surface.property('color').alphaF() < 1
        assert window.findChild(QObject, 'aboutButtonFace') is not None
        name = window.findChild(QObject, 'applicationName')
        location = window.findChild(QObject, 'applicationLocation')
        assert name.property('text') == info.get('name', 'Application')
        assert location.property('text') == info.get('executable', info.get('desktopFile', 'Not Available'))
        assert window.minimumWidth() == window.maximumWidth()
        assert location.property('width') <= window.width()
        details = QMetaObject.invokeMethod(window, 'detailsText', Q_RETURN_ARG(str))
        assert info.get('name', 'Application') in details
        assert info.get('executable', '') in details
        copy = window.findChild(QObject, 'copyApplicationDetails')
        assert copy is not None
        QMetaObject.invokeMethod(copy, 'clicked')
        QTest.qWait(30)
        assert app.clipboard().text() == details
        QTest.keyClick(window, Qt.Key.Key_Escape)
        QTest.qWait(30)
        assert not window.isVisible()
    window.setProperty('applicationInfo', samples[0])
    window.show()
    window.requestActivate()
    QTest.qWait(250)
    if args.capture:
        assert window.grabWindow().save(str(args.capture))
    QTest.keyClick(window, Qt.Key.Key_W, Qt.KeyboardModifier.ControlModifier)
    QTest.qWait(30)
    assert not window.isVisible()
    assert not errors, '\n'.join(errors)
    print(json.dumps({'result': 'passed', 'mode': args.mode, 'applications': len(samples),
                      'checks': 'metadata, plain text, long paths, fixed size, clipboard, Escape, Ctrl+W, reopening'}))


if __name__ == '__main__':
    main()
