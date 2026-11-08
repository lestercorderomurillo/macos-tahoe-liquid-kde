"""Execute the bundled Plasma layouts without a live desktop or D-Bus."""
import json
import subprocess
import sys

import pytest

import steps.layout as layout

LAYOUTS = [
    'layouts/mac-tahoe.js',
    'look-and-feel/MacTahoeLiquidKde-Light/contents/layouts/org.kde.plasma.desktop-layout.js',
    'look-and-feel/MacTahoeLiquidKde-Dark/contents/layouts/org.kde.plasma.desktop-layout.js',
]
APPS = [
    'org.kde.dolphin.desktop', 'firefox.desktop', 'thunderbird.desktop',
    'org.kde.merkuro.calendar.desktop', 'org.kde.marknote.desktop',
    'org.kde.gwenview.desktop', 'org.kde.elisa.desktop', 'org.kde.haruna.desktop',
    'org.kde.discover.desktop', 'systemsettings.desktop',
]
HARNESS = '''
var created = [];
var screenCount = 2;
function panels() { return created; }
function applicationExists(id) { return installed.indexOf(id) !== -1; }
function Panel() {
    this.widgetIds = [];
    this.widgetsById = {};
    this.addWidget = function(type) {
        var widget = {type: type, config: {},
            writeConfig: function(key, value) { this.config[key] = value; }};
        var id = this.widgetIds.length;
        this.widgetIds.push(id);
        this.widgetsById[id] = widget;
        return widget;
    };
    this.widgetById = function(id) { return this.widgetsById[id]; };
    created.push(this);
}
'''
RUNNER = '''
import json, sys
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtQml import QJSEngine
app = QCoreApplication([])
engine = QJSEngine()
result = engine.evaluate(sys.stdin.read())
if result.isError():
    raise RuntimeError(result.toString())
print(result.toString())
'''


def execute(script, installed):
    pytest.importorskip('PyQt6.QtQml')
    source = 'var installed = ' + json.dumps(installed) + ';\n' + HARNESS + script
    source += '''
JSON.stringify(created.filter(p => p.location === "bottom").map(p =>
    p.widgetIds.map(id => p.widgetById(id)).map(w => ({type: w.type, pins: w.config.launchers}))));
'''
    result = subprocess.run([sys.executable, '-c', RUNNER], input=source,
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


@pytest.mark.parametrize('relative', LAYOUTS)
@pytest.mark.parametrize('installed, expected', [
    (APPS, APPS),
    ([], []),
    (['firefox-esr.desktop', 'thunderbird_thunderbird.desktop'],
     ['firefox-esr.desktop', 'thunderbird_thunderbird.desktop']),
    (['firefox_firefox.desktop'], ['firefox_firefox.desktop']),
    ([APPS[0], APPS[-1]], [APPS[0], APPS[-1]]),
    (APPS + ['org.mozilla.firefox.desktop', 'org.mozilla.Thunderbird.desktop'], APPS),
    ([app for app in APPS if app not in ('firefox.desktop', 'thunderbird.desktop')]
     + ['org.mozilla.firefox.desktop', 'org.mozilla.Thunderbird.desktop'],
     [APPS[0], 'org.mozilla.firefox.desktop', 'org.mozilla.Thunderbird.desktop'] + APPS[3:]),
])
def test_base_dock_order_and_missing_apps(offline, relative, installed, expected):
    docks = execute((offline / relative).read_text(), installed)
    assert docks
    for widgets in docks:
        tasks = [w for w in widgets if w['type'] == layout.MAC_TASKS_ID]
        assert tasks[0]['pins'] == ['applications:' + app for app in expected]
        assert widgets[-1]['type'] == 'org.kde.mac-tahoe-liquid-kde.trashcan'


def test_reinstall_preserves_pins_on_every_screen(monkeypatch):
    monkeypatch.setattr(layout, '_discover_is_installed', lambda: True)
    pins = ['applications:custom.desktop', 'preferred://browser']
    script = layout._layout_script_with_launchers(layout.LAYOUT_SCRIPT, pins, layout.MAC_TASKS_ID)
    docks = execute(script, APPS)
    assert len(docks) == 2
    for widgets in docks:
        assert next(w['pins'] for w in widgets if w['type'] == layout.MAC_TASKS_ID) == pins


def test_reinstall_preserves_intentionally_empty_dock(monkeypatch, tmp_path):
    monkeypatch.setattr(layout, 'HOME', tmp_path)
    monkeypatch.setattr(layout, '_discover_is_installed', lambda: True)
    config = tmp_path / '.config/plasma-org.kde.plasma.desktop-appletsrc'
    config.parent.mkdir()
    config.write_text('plugin=' + layout.MAC_TASKS_ID + '\nlaunchers=\n')
    script = layout._layout_script_with_launchers(layout.LAYOUT_SCRIPT, [], layout.MAC_TASKS_ID)
    for widgets in execute(script, APPS):
        assert next(w['pins'] for w in widgets if w['type'] == layout.MAC_TASKS_ID) == []


@pytest.mark.parametrize('style', ['regular', 'glass'])
def test_calendar_and_notes_keep_generated_appearance(tmp_path, style):
    from interface_icons import apply_interface_icons, APPLICATION_ALIASES
    from icon_toolset import BASE, installer_themes
    source = tmp_path / 'source'
    apps = source / BASE / 'apps/scalable'
    apps.mkdir(parents=True)
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect x="4" y="4" width="56" height="56" rx="12" fill="{}"/></svg>'
    (apps / 'calendar.svg').write_text(svg.format('#df3434'))
    (apps / 'notes.svg').write_text(svg.format('#f5cc43'))
    (apps / 'org.kde.haruna.svg').write_text(svg.format('#4080ff'))
    apply_interface_icons(source)
    apply_interface_icons(source)  # Reapplying must leave valid aliases intact.
    output = tmp_path / 'generated'
    names = installer_themes(source, output, style, '#4080ff')
    for alias, original in APPLICATION_ALIASES.items():
        assert (apps / alias).resolve() == (apps / original).resolve()
        for name in names:  # Both appearance modes must use the selected material.
            generated = output / name / 'apps/256'
            assert (generated / alias.replace('.svg', '.png')).read_bytes() == (generated / original.replace('.svg', '.png')).read_bytes()


def test_dock_aliases_preserve_dedicated_artwork(tmp_path):
    from interface_icons import apply_interface_icons
    apps = tmp_path / 'MacTahoeLiquidKde-Icons/apps/scalable'
    apps.mkdir(parents=True)
    (apps / 'notes.svg').write_text('base notes')
    dedicated = apps / 'org.kde.marknote.svg'
    dedicated.write_text('dedicated artwork')
    apply_interface_icons(tmp_path)
    assert dedicated.read_text() == 'dedicated artwork'
