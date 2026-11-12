"""Dock-only artwork resolution and opt-in installer lifecycle."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
import dock_apps
import installer_choices
import steps.layout as layout
from tests.test_dock_defaults import HARNESS, RUNNER, existing_dock

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'src/offline/plasmoids/org.kde.mac.tahoe.liquid.taskmanager'


def evaluate(script):
    pytest.importorskip('PyQt6.QtQml')
    result = subprocess.run([sys.executable, '-c', RUNNER], input=script,
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def test_resolves_all_installed_equivalents_and_preserves_unknown_apps():
    js = (PACKAGE / 'contents/ui/DockRoles.js').read_text().replace('.pragma library', '')
    cases = []
    for role, candidates in dock_apps.CANDIDATES.items():
        for desktop in candidates:
            for url, app_id in [('applications:' + desktop, ''),
                                ('file:///var/lib/flatpak/exports/share/applications/' + desktop, ''),
                                ('', desktop.removesuffix('.desktop')),
                                ('applications:' + desktop + '?icon=custom', '')]:
                cases.append([url, app_id, role])
    cases += [['preferred://browser', '', 'browser'], ['preferred://filemanager', '', 'files'],
              ['preferred://mailer', '', 'mail'], ['applications:my-firefox.desktop', '', ''],
              ['file:///tmp/unknown.desktop', 'org.example.App', ''], ['', '', ''],
              ['applications:%ZZ.desktop', '', '']]
    result = evaluate(js + '\nJSON.stringify(' + json.dumps(cases) + '.map(c => roleFor(c[0], c[1])));')
    assert result == [c[2] for c in cases]


@pytest.mark.parametrize('appearance,initial,expected', [('keep', True, True), ('keep', False, False),
                                                        ('macos', False, True), ('native', True, False)])
@pytest.mark.parametrize('rebuild', [False, True])
def test_appearance_preserves_pins_and_survives_rebuild(monkeypatch, appearance, initial, expected, rebuild):
    monkeypatch.setenv('MTTKDE_WIZARD_OPTIONS', json.dumps({'dock_appearance': appearance, 'reset_layout': False}))
    monkeypatch.setattr(layout, '_discover_is_installed', lambda: True)
    pins = ['applications:my-app.desktop', 'preferred://browser']
    script = 'var installed = [];\n' + HARNESS + existing_dock(pins, revision=3)
    script += 'task.writeConfig("macOSDockIcons", ' + json.dumps(initial) + ');\n'
    script += existing_dock(pins, revision=3, screen=1)
    script += 'task.writeConfig("macOSDockIcons", ' + json.dumps(initial) + ');\n'
    if rebuild:
        script += layout._layout_script_with_launchers(layout.LAYOUT_SCRIPT, pins, layout.MAC_TASKS_ID)
    else:
        script += layout._dock_migration_script()
    script += '''
JSON.stringify(created.filter(p => p.location === "bottom").map(p =>
 p.widgetIds.map(id => p.widgetById(id)).filter(w => w.type === "org.kde.mac.tahoe.liquid.icontasks")
 .map(w => ({pins:w.config.launchers, icons:w.config.macOSDockIcons}))));'''
    result = evaluate(script)
    assert result
    for panel in result:
        assert panel == [{'pins': pins, 'icons': expected}]


def test_appearance_default_does_not_consent_to_apps(monkeypatch):
    choices = installer_choices.validate({})
    assert choices['dock_appearance'] == 'auto'
    assert choices['dock_apps'] == []
    assert not installer_choices.features({'dock_appearance':'macos'}, {}, existing_install=True)['apps']
    with pytest.raises(ValueError):
        installer_choices.validate({'dock_appearance':'unexpected'})
    monkeypatch.setenv('MTTKDE_WIZARD_OPTIONS', json.dumps({'dock': False, 'dock_appearance':'macos'}))
    assert 'var mttkdeDockAppearance = "keep";' in layout._dock_migration_script()


def test_dock_artwork_is_self_contained_and_matches_bundled_sources():
    import xml.etree.ElementTree as ET
    icons = PACKAGE / 'contents/icons'
    manifest = json.loads((icons / 'sources.json').read_text())
    assert hashlib.sha256((ROOT / manifest['archive']).read_bytes()).hexdigest() == manifest['archive_sha256']
    assert set(manifest['files']) == {f'{mode}/{role}.svg' for mode in ('light','dark') for role in dock_apps.CANDIDATES}
    for name, info in manifest['files'].items():
        data = (icons / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == info['sha256']
        tree = ET.fromstring(data)
        assert tree.tag.endswith('svg')
        for element in tree.iter():
            for key, value in element.attrib.items():
                if key.endswith('href'):
                    assert value.startswith(('#', 'data:image/png;base64,')), (name, value)
    task = (PACKAGE / 'contents/ui/Task.qml').read_text()
    assert 'mainItem.appName = Qt.binding(() => model.AppName)' in task
    assert 'mainItem.launcherUrl = Qt.binding(() => model.LauncherUrlWithoutIcon)' in task
    assert 'task.dockRoleLabel || model.GenericName' in task
    assert 'Kirigami.Theme.backgroundColor.hslLightness' in task


@pytest.mark.parametrize('family,expected', [
    ('arch','qt6-svg'), ('debian','qt6-svg-plugins'), ('ubuntu','qt6-svg-plugins'),
    ('neon','qt6-svg'), ('fedora','qt6-qtsvg'), ('opensuse','libQt6Svg6'),
])
def test_svg_icon_engine_dependency_respects_package_layout(monkeypatch, family, expected):
    import distro
    import steps.plasmoids as plasmoids
    monkeypatch.setattr(distro, 'current_distro', lambda: family)
    monkeypatch.setattr(distro, '_compatibility_parents', lambda: [])
    assert 'qt6-svg-icons' in plasmoids.deps()
    assert distro.package_for('qt6-svg-icons') == expected


def test_dock_mode_uses_desktop_mode_even_when_material_luminance_is_inverted():
    js = (PACKAGE / 'contents/ui/DockRoles.js').read_text().replace('.pragma library', '')
    result = evaluate(js + '\nJSON.stringify([darkMode("MacTahoeLiquidKde-Light", 0.1),'
                      'darkMode("MacTahoeLiquidKde-Dark", 0.9),'
                      'darkMode("MacTahoeLiquidKde-Light", 0.1),'
                      'darkMode("third-party", 0.1), darkMode("third-party", 0.9)]);')
    assert result == [False, True, False, True, False]
    task = (PACKAGE / 'contents/ui/Task.qml').read_text()
    assert 'tasksRoot.iconThemeWatcher.plasmaThemeName' in task


@pytest.mark.parametrize('revision', [0, 1, 2, 3])
@pytest.mark.parametrize('reset', [False, True])
def test_064_defaults_once_or_explicit_reset(monkeypatch, revision, reset):
    monkeypatch.setenv('MTTKDE_WIZARD_OPTIONS', json.dumps({'reset_layout': reset}))
    pins = ['applications:custom.desktop', 'preferred://browser']
    script = 'var installed = ["firefox.desktop", "org.kde.marknote.desktop"];\n' + HARNESS
    script += existing_dock(pins, revision=revision)
    script += 'task.writeConfig("macOSDockIcons", false);'
    script += layout._dock_migration_script()
    script += 'JSON.stringify({config:task.config, height:dock.height, hiding:dock.hiding});'
    observed = evaluate(script)
    result = observed['config']
    apply = revision < 3 or reset
    if apply:
        assert observed['height'] == 68 and observed['hiding'] == 'autohide'
    else:
        assert 'height' not in observed
    assert result['launchers'] == pins + (['applications:org.kde.marknote.desktop'] if apply else [])
    assert result['macOSDockIcons'] is apply
    assert result['dockPresetRevision'] == 3


def test_browser_keeps_real_app_artwork_and_label():
    js = (PACKAGE / 'contents/ui/DockRoles.js').read_text().replace('.pragma library', '')
    urls = ['applications:' + app for app in dock_apps.CANDIDATES['browser']] + ['preferred://browser']
    result = evaluate(js + '\nJSON.stringify(' + json.dumps(urls) + '.map(url => appearanceRoleFor(url, "")));')
    assert result == [''] * len(urls)
    task = (PACKAGE / 'contents/ui/Task.qml').read_text()
    assert 'DockRoles.appearanceRoleFor(' in task


@pytest.mark.parametrize('size', [32, 64, 128])
def test_dark_store_has_filled_strokes_in_qt_svg(size):
    """Qt resolves xlink:href by prefix; XML-equivalent ns1:href loses fills."""
    from PyQt6.QtCore import QByteArray, Qt
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer

    paths = [ROOT / 'src/offline/icons/overrides/app-store-dark.svg',
             PACKAGE / 'contents/icons/dark/store.svg']
    for path in paths:
        image = QImage(size, size, QImage.Format.Format_RGBA8888)
        image.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(QByteArray(path.read_bytes()))
        assert renderer.isValid()
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        # Interior of the right diagonal and crossbar, away from the thin rim.
        for x, y in [(10.0, 8.0), (8.0, 10.2)]:
            pixel = image.pixelColor(round(x / 16.933 * size), round(y / 16.933 * size))
            assert pixel.blue() > 170 and pixel.green() > 110, (path, size, x, y, pixel.getRgb())
            assert pixel.blue() - pixel.red() > 100
