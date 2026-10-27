"""Capture synchronization and standalone About labels."""
import importlib.machinery
import importlib.util
import os
import shutil
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture
def capture_module(repo):
    loader = importlib.machinery.SourceFileLoader('screenshot_workflow', str(repo / 'src/scripts/screenshots'))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_capture_rejects_overlapping_workflows(capture_module, tmp_path, monkeypatch):
    monkeypatch.setattr(capture_module.tempfile, 'gettempdir', lambda: str(tmp_path))
    with capture_module._capture_lock():
        with pytest.raises(RuntimeError, match='already running'):
            with capture_module._capture_lock():
                pytest.fail('A second capture acquired the lock')
    with capture_module._capture_lock():
        pass


def test_about_capture_never_runs_when_preview_is_not_ready(capture_module, monkeypatch):
    class Process:
        pass
    process = Process()
    events = []
    monkeypatch.setattr(capture_module.shutil, 'which', lambda name: name)
    monkeypatch.setattr(capture_module, '_spawn', lambda *a, **kw: process)
    def not_ready(proc):
        raise RuntimeError('not ready')
    monkeypatch.setattr(capture_module, '_wait_ready', not_ready)
    monkeypatch.setattr(capture_module, '_spectacle_activewindow', lambda path: events.append('capture'))
    monkeypatch.setattr(capture_module, '_kill_group', lambda proc: events.append('cleanup'))
    with pytest.raises(RuntimeError, match='not ready'):
        capture_module.shoot_about('light')
    assert events == ['cleanup']


@pytest.mark.parametrize("edition", ["MacTahoe", "MacGoldenGate"])
@pytest.mark.parametrize("initial_mode", ["Light", "Dark"])
def test_about_labels_and_surface_follow_appearance(repo, tmp_path, monkeypatch, edition, initial_mode):
    import configparser
    import json
    import glass_surfaces
    pytest.importorskip('PyQt6.QtQuick')
    from PyQt6.QtCore import QLibraryInfo
    imports = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.QmlImportsPath))
    if not (imports / 'org/kde/ki18n/qmldir').is_file():
        pytest.skip('KDE QML translations are not installed')
    probe = r'''
import sys, json
from PyQt6.QtCore import QObject, QUrl, pyqtSlot
from PyQt6.QtGui import QGuiApplication, QColor, QImage, QPainter
from PyQt6.QtQml import QQmlApplicationEngine, QQmlComponent, QQmlProperty, QQmlExpression
from PyQt6.QtQuick import QQuickItem
class EmptyTranslations(QObject):
    @pyqtSlot(str, result=str)
    def i18n(self, message):
        return ''
app = QGuiApplication([])
engine = QQmlApplicationEngine()
# Initialize Plasma's SVG image set as the plasmashell host does.
host_component = QQmlComponent(engine)
host_component.setData(b'import org.kde.plasma.core as PlasmaCore; PlasmaCore.Dialog { visible: false }', QUrl())
host = host_component.create()
assert host is not None, host_component.errors()
errors = []
engine.warnings.connect(lambda warnings: errors.extend(w.toString() for w in warnings))
context = EmptyTranslations()
engine.rootContext().setContextObject(context)
engine.setInitialProperties({'visible': False, 'fetcherCommand': 'true'})
engine.load(QUrl.fromLocalFile(sys.argv[1]))
assert engine.rootObjects(), 'About window failed to load: ' + '\n'.join(errors)
texts = set()
def visit(item):
    text = item.property('text')
    if isinstance(text, str):
        texts.add(text)
    for child in item.childItems():
        visit(child)
visit(engine.rootObjects()[0].contentItem())
expected = {'Chip', 'Cores', 'Memory', 'Graphics', 'Startup disk', 'Network',
            'Serial number', 'OS', 'More Info…', 'Report a Bug…'}
assert expected <= texts, f'Missing labels: {expected - texts}'
window = engine.rootObjects()[0]
surface = window.findChild(QQuickItem, 'aboutGlassSurface')
highlight = window.findChild(QQuickItem, 'aboutGlassHighlight')
assert surface is not None and highlight is not None
def luminance(color):
    def linear(value):
        return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
    return sum(weight * linear(value) for weight, value in zip(
        (.2126, .7152, .0722), (color.redF(), color.greenF(), color.blueF())))

palette = json.loads(sys.argv[3])
for mode, foreground in [('white', 255), ('black', 0), ('white', 255)]:
    expression = QQmlExpression(engine.contextForObject(window), window,
                               'Kirigami.Theme.backgroundColor = '+repr(mode)
                               + '; Kirigami.Theme.textColor = ' + repr(palette[mode]))
    expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    app.processEvents()
    fill = surface.property('color')
    clear = sys.argv[2] == 'MacGoldenGate'
    secondary = window.property('secondaryTextColor')
    assert fill.red() == fill.green() == fill.blue() == (255 if clear else foreground)
    expected_alpha = (.01 if foreground == 0 else .60) if clear else (.48 if foreground == 0 else .55)
    assert abs(fill.alphaF() - expected_alpha) < .005, (sys.argv[2], mode, fill.getRgbF())
    assert abs(secondary.alphaF() - (.90 if clear and foreground == 255 else .85)) < .005
    assert secondary.name() == palette[mode]
    if clear and foreground == 255:
        # Composite the actual QML fill over the reported black backdrop.
        # Include secondary labels' alpha, not just the primary text.
        image = QImage(2, 1, QImage.Format.Format_ARGB32)
        image.fill(QColor('black'))
        painter = QPainter(image)
        painter.fillRect(image.rect(), fill)
        painter.fillRect(0, 0, 1, 1, secondary)
        painter.end()
        contrast = (luminance(image.pixelColor(1, 0)) + .05) / (luminance(image.pixelColor(0, 0)) + .05)
        assert contrast >= 4.5, contrast
    assert QQmlProperty(surface, 'border.width').read() == .75
    assert QQmlProperty(highlight, 'border.width').read() == .75
    outer = QQmlProperty(surface, 'border.color').read()
    inner = QQmlProperty(highlight, 'border.color').read()
    assert outer.red() == 0 and abs(outer.alphaF() - .18) < .005
    assert inner.red() == 255 and abs(inner.alphaF() - .22) < .005
    assert highlight.property('radius') == surface.property('radius') - .75
'''
    qml = repo / 'src/offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu/qml/AboutWindow.qml'
    name = 'MacTahoeLiquidKde-' + initial_mode
    theme = tmp_path / 'data/plasma/desktoptheme' / name
    shutil.copytree(repo / 'src/offline/plasma-theme' / name, theme)
    monkeypatch.setattr(glass_surfaces, 'default_wallpaper', lambda: edition)
    glass_surfaces.apply_plasma_surface_defaults(theme)
    (tmp_path / 'plasmarc').write_text('[Theme]\nname=' + name + '\n')
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
               LANGUAGE='en', LC_ALL='C.UTF-8', HOME=str(tmp_path),
               XDG_DATA_HOME=str(tmp_path / 'data'),
               XDG_CONFIG_HOME=str(tmp_path), DBUS_SESSION_BUS_ADDRESS='unix:path=/nonexistent')
    palette = {}
    for mode, key in [('Light', 'white'), ('Dark', 'black')]:
        scheme = configparser.ConfigParser()
        scheme.read(repo / f'src/offline/color-schemes/MacTahoeLiquidKde{mode}.colors')
        rgb = map(int, scheme['Colors:Window']['ForegroundNormal'].split(','))
        palette[key] = '#' + ''.join(f'{value:02x}' for value in rgb)
    result = subprocess.run([sys.executable, '-c', probe, str(qml), edition, json.dumps(palette)], env=env,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr

def test_capture_refuses_host_before_switch(capture_module, monkeypatch):
    import screenshot_checks as checks
    monkeypatch.setattr(checks.subprocess, 'run', lambda *a, **kw:
                        subprocess.CompletedProcess(a, 1, 'none\n', ''))
    monkeypatch.setattr(capture_module, '_switch_theme', lambda _: pytest.fail('Host theme changed'))
    with pytest.raises(RuntimeError, match='disposable VM'):
        capture_module.main(['about'])
