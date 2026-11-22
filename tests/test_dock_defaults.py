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
    'org.kde.gwenview.desktop', 'org.kde.merkuro.calendar.desktop',
    'org.kde.marknote.desktop', 'org.kde.haruna.desktop', 'org.kde.elisa.desktop',
    'org.kde.discover.desktop', 'systemsettings.desktop',
]
HARNESS = '''
var created = [];
var screenCount = 2;
function userDataPath(type) { return "/home/tester/Downloads"; }
function panels() { return created.slice(); }
function applicationExists(id) { return installed.indexOf(id) !== -1; }
function Panel() {
    this.widgetIds = [];
    this.widgetsById = {};
    this.remove = function() { created.splice(created.indexOf(this), 1); };
    this.addWidget = function(type) {
        var widget = {type: type, config: {},
            readConfig: function(key, fallback) { return key in this.config ? this.config[key] : fallback; },
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
    (APPS + ["org.kde.mac-tahoe-liquid-kde.apps.desktop"],
     [APPS[0], "org.kde.mac-tahoe-liquid-kde.apps.desktop", *APPS[1:]]),
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
        assert [w["type"] for w in widgets[-3:]] == [
            "org.kde.mac-tahoe-liquid-kde.dockseparator", "org.kde.plasma.folder",
            "org.kde.mac-tahoe-liquid-kde.trashcan",
        ]


def test_upgrade_adds_defaults_after_user_pins_on_every_screen(monkeypatch):
    monkeypatch.setattr(layout, '_discover_is_installed', lambda: True)
    pins = ['applications:custom.desktop', 'preferred://browser']
    script = layout._layout_script_with_launchers(layout.LAYOUT_SCRIPT, pins, layout.MAC_TASKS_ID)
    docks = execute(script, APPS)
    assert len(docks) == 1
    for widgets in docks:
        assert next(w['pins'] for w in widgets if w['type'] == layout.MAC_TASKS_ID) == pins + ['applications:' + app for app in APPS if app != 'firefox.desktop']


def test_upgrade_populates_empty_legacy_dock(monkeypatch, tmp_path):
    monkeypatch.setattr(layout, 'HOME', tmp_path)
    monkeypatch.setattr(layout, '_discover_is_installed', lambda: True)
    config = tmp_path / '.config/plasma-org.kde.plasma.desktop-appletsrc'
    config.parent.mkdir()
    config.write_text('plugin=' + layout.MAC_TASKS_ID + '\nlaunchers=\n')
    script = layout._layout_script_with_launchers(layout.LAYOUT_SCRIPT, [], layout.MAC_TASKS_ID)
    for widgets in execute(script, APPS):
        assert next(w['pins'] for w in widgets if w['type'] == layout.MAC_TASKS_ID) == ['applications:' + app for app in APPS]


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


def existing_dock(pins, revision=0, screen=0):
    return (
        'var dock = new Panel(); dock.location = "bottom"; dock.screen = ' + str(screen) + ';'
        'var task = dock.addWidget(' + json.dumps(layout.MAC_TASKS_ID) + ');'
        'task.writeConfig("launchers", ' + json.dumps(pins) + ');'
        'task.writeConfig("dockPresetRevision", ' + str(revision) + ');'
    )


def test_apps_pin_retains_its_new_position_after_edition_rebuild(monkeypatch):
    apps = "applications:org.kde.mac-tahoe-liquid-kde.apps.desktop"
    pins = ["applications:org.kde.dolphin.desktop", "applications:firefox.desktop", apps]
    monkeypatch.setattr(layout, "_layout_has_any_theme_widget", lambda: True)
    script = existing_dock(pins, revision=3)
    script += layout._layout_script_with_launchers(layout.LAYOUT_SCRIPT, pins, layout.MAC_TASKS_ID)
    dock, = execute(script, [pin.removeprefix("applications:") for pin in pins])
    assert next(widget["pins"] for widget in dock if widget["type"] == layout.MAC_TASKS_ID) == pins


def test_earlier_factory_pins_adopt_new_order_without_reinstalling_apps():
    apps = "org.kde.mac-tahoe-liquid-kde.apps.desktop"
    old = [APPS[i] for i in (0, 1, 2, 4, 5, 3, 7, 6, 8, 9)]
    script = existing_dock(["applications:" + desktop for desktop in old], revision=3)
    script += 'dock.addWidget("org.kde.mac-tahoe-liquid-kde.launcher");'
    dock, = execute(script + layout.DOCK_MIGRATION.read_text(), [apps, *APPS])
    assert dock[0]["pins"] == ["applications:" + desktop for desktop in [APPS[0], apps, *APPS[1:]]]


def test_migration_does_not_reintroduce_removed_pins():
    migration = layout.DOCK_MIGRATION.read_text()
    script = existing_dock(['applications:custom.desktop']) + migration
    script += 'task.writeConfig("launchers", ["applications:custom.desktop"]);'
    script += migration
    assert execute(script, APPS)[0][0]['pins'] == ['applications:custom.desktop']


def test_migration_keeps_aliases_and_only_adds_installed_apps():
    pins = ['preferred://browser', 'file:///usr/share/applications/org.mozilla.Thunderbird.desktop']
    script = existing_dock(pins) + layout.DOCK_MIGRATION.read_text()
    assert execute(script, ['firefox.desktop', 'thunderbird.desktop', 'org.kde.marknote.desktop'])[0][0]['pins'] == pins + ['applications:org.kde.marknote.desktop']


@pytest.mark.parametrize('pins', [[], ['applications:custom.desktop']])
def test_rebuild_retains_completed_migration(monkeypatch, pins):
    monkeypatch.setattr(layout, '_layout_has_any_theme_widget', lambda: True)
    script = existing_dock(pins, revision=3)
    script += layout._layout_script_with_launchers(layout.LAYOUT_SCRIPT, pins, layout.MAC_TASKS_ID)
    docks = execute(script, APPS)
    assert next(w['pins'] for w in docks[0] if w['type'] == layout.MAC_TASKS_ID) == pins


def test_migration_and_base_have_identical_candidates(offline):
    import re
    pattern = r'var dockApplications = (\[.*?\n\s*\]);'
    candidates = json.loads(re.search(pattern, layout.DOCK_MIGRATION.read_text(), re.S)[1])
    for relative in LAYOUTS:
        assert json.loads(re.search(pattern, (offline / relative).read_text(), re.S)[1]) == candidates


def test_migration_honors_disabled_dock(monkeypatch):
    import installer_choices
    monkeypatch.setattr(installer_choices, 'selected', lambda: {'dock': False})
    calls = []
    monkeypatch.setattr(layout, '_evaluate_layout_script', lambda script: calls.append(script))
    layout.migrate_dock_preset()
    assert calls == []


def test_fresh_install_preserves_existing_user_pins(monkeypatch):
    monkeypatch.setattr(layout, '_layout_marker', lambda: type('Marker', (), {'is_file': lambda self: False})())
    monkeypatch.setattr(layout, '_layout_has_any_theme_widget', lambda: False)
    monkeypatch.setattr(layout, '_clear_layout_marker', lambda: None)
    monkeypatch.setattr(layout, 'remember_installed_edition', lambda *args: None)
    monkeypatch.setattr(layout, '_ensure_panel_colorizer', lambda: None)
    monkeypatch.setattr(layout, '_capture_pinned_launchers', lambda: ['applications:stock.desktop'])
    calls = []
    monkeypatch.setattr(layout, '_evaluate_layout_with_launchers', lambda path, pins, widget: calls.append(pins) or False)
    layout.install()
    assert calls == [['applications:stock.desktop']]


@pytest.mark.parametrize('relative', LAYOUTS)
def test_base_uses_installed_equivalents(offline, relative):
    installed = ['org.gnome.Nautilus.desktop', 'chromium.desktop',
                 'org.kde.kmail2.desktop', 'org.gnome.Loupe.desktop',
                 'org.gnome.Calendar.desktop', 'org.gnome.Gnote.desktop',
                 'org.gnome.Showtime.desktop', 'org.gnome.Rhythmbox3.desktop',
                 'org.kde.discover.desktop', 'systemsettings.desktop']
    for widgets in execute((offline / relative).read_text(), installed):
        assert next(w['pins'] for w in widgets if w['type'] == layout.MAC_TASKS_ID) == [
            'applications:' + app for app in installed]


def test_revision_one_recovers_photos_and_video_from_host_equivalents():
    pins = ['preferred://filemanager', 'preferred://browser',
            'applications:systemsettings.desktop',
            'applications:org.kde.discover.desktop', 'applications:steam.desktop']
    installed = ['org.gnome.Loupe.desktop', 'org.gnome.Showtime.desktop',
                 'systemsettings.desktop', 'org.kde.discover.desktop']
    script = existing_dock(pins, revision=1) + layout.DOCK_MIGRATION.read_text()
    assert execute(script, installed)[0][0]['pins'] == pins + [
        'applications:org.gnome.Loupe.desktop', 'applications:org.gnome.Showtime.desktop']


def test_completed_migration_does_not_add_apps_on_later_reinstall():
    migration = layout.DOCK_MIGRATION.read_text()
    script = existing_dock([]) + migration
    script += 'task.writeConfig("launchers", []); installed.push("org.gnome.Showtime.desktop");'
    script += migration
    assert execute(script, ['org.gnome.Loupe.desktop'])[0][0]['pins'] == []


def test_existing_equivalent_prevents_a_second_app_for_same_role():
    pins = ['applications:vlc.desktop', 'applications:org.gnome.Loupe.desktop']
    script = existing_dock(pins) + layout.DOCK_MIGRATION.read_text()
    installed = ['vlc.desktop', 'org.gnome.Showtime.desktop', 'org.kde.haruna.desktop',
                 'org.gnome.Loupe.desktop', 'org.kde.gwenview.desktop']
    assert execute(script, installed)[0][0]['pins'] == pins


def test_first_064_rebuild_fills_previously_resolved_categories(monkeypatch):
    monkeypatch.setattr(layout, '_layout_has_any_theme_widget', lambda: True)
    script = existing_dock([], revision=2)
    script += 'task.writeConfig("dockPresetCategories", "photos");'
    script += layout._layout_script_with_launchers(layout.LAYOUT_SCRIPT, [], layout.MAC_TASKS_ID)
    docks = execute(script, ['org.gnome.Loupe.desktop', 'org.gnome.Showtime.desktop'])
    assert next(w['pins'] for w in docks[0] if w['type'] == layout.MAC_TASKS_ID) == [
        'applications:org.gnome.Loupe.desktop', 'applications:org.gnome.Showtime.desktop']


def test_csv_pins_and_category_state_are_supported():
    script = existing_dock(['applications:custom.desktop'], revision=2)
    script += 'task.writeConfig("launchers", "applications:custom.desktop");'
    script += 'task.writeConfig("dockPresetCategories", "photos,music");'
    script += layout.DOCK_MIGRATION.read_text()
    assert execute(script, ['org.gnome.Loupe.desktop', 'org.gnome.Showtime.desktop'])[0][0]['pins'] == [
        'applications:custom.desktop', 'applications:org.gnome.Loupe.desktop', 'applications:org.gnome.Showtime.desktop']


def test_requested_install_fills_legacy_revision_one_dock(monkeypatch):
    monkeypatch.setenv('MTTKDE_WIZARD_OPTIONS', json.dumps({'dock_apps':['mail']}))
    script = existing_dock(['applications:custom.desktop'], revision=1)
    script += layout._dock_migration_script()
    assert execute(script, ['thunderbird.desktop'])[0][0]['pins'] == [
        'applications:custom.desktop', 'applications:thunderbird.desktop']


def test_status_control_migration_preserves_apps_and_unrelated_panels(offline):
    script = (offline / 'layouts/migrate-status-controls.js').read_text()
    source = HARNESS + '''
Panel.prototype.widgets = function() { return this.widgetIds.map(id => this.widgetById(id)); };
function fixture(themed) {
    var bar = new Panel();
    if (themed) {
        bar.addWidget('org.kde.mac-tahoe-liquid-kde.controlcenter');
        bar.addWidget('org.kde.mac-tahoe-liquid-kde.notifications');
    }
    var tray = bar.addWidget('org.kde.plasma.systemtray');
    tray.config = {
        shownItems: ['slack', 'org.kde.plasma.bluetooth', 'org.kde.plasma.volume', 'org.kde.plasma.notifications'],
        hiddenItems: 'discord,org.kde.plasma.brightness',
        knownItems: ['org.kde.plasma.networkmanagement'],
        extraItems: ['org.kde.plasma.notifications', 'org.kde.plasma.bluetooth', 'org.kde.plasma.brightness', 'org.kde.plasma.volume', 'org.kde.plasma.networkmanagement']
    };
    return tray;
}
var themed = fixture(true), unrelated = fixture(false);
var before = JSON.stringify(unrelated.config);
''' + script + '''
var once = JSON.stringify(themed.config);
''' + script + '''
JSON.stringify({themed:themed.config, unrelated:before === JSON.stringify(unrelated.config),
    stable:once === JSON.stringify(themed.config), panels:created.length,
    widgets:created[0].widgetIds.length});
'''
    result = subprocess.run([sys.executable, '-c', RUNNER], input=source,
                            capture_output=True, text=True, check=True)
    actual = json.loads(result.stdout)
    assert actual['stable'] and actual['unrelated']
    assert actual['panels'] == 2 and actual['widgets'] == 3
    tray = actual['themed']
    assert tray['shownItems'] == ['slack']
    assert set(tray['hiddenItems']) == {'discord', 'org.kde.plasma.brightness',
                                      'org.kde.plasma.bluetooth', 'org.kde.plasma.volume'}
    assert tray['extraItems'] == ['org.kde.plasma.networkmanagement']
    assert set(tray['knownItems']) == {'org.kde.plasma.networkmanagement', 'org.kde.plasma.notifications',
                                      'org.kde.plasma.bluetooth', 'org.kde.plasma.brightness', 'org.kde.plasma.volume'}


def test_reset_on_reinstall_does_not_repin_apps_the_user_unpinned():
    # The wizard resets the Dock by default on every reinstall. Apps the
    # Dock already offered once and the user unpinned must stay unpinned.
    migration = layout.DOCK_MIGRATION.read_text()
    installed = ['org.gnome.Loupe.desktop', 'org.gnome.Showtime.desktop']
    script = existing_dock(['applications:custom.desktop']) + migration
    script += 'task.writeConfig("launchers", ["applications:custom.desktop"]);'
    script += 'var mttkdeResetDock = true;' + migration
    assert execute(script, installed)[0][0]['pins'] == ['applications:custom.desktop']


def test_reset_still_offers_a_default_app_installed_since_the_last_install():
    migration = layout.DOCK_MIGRATION.read_text()
    script = existing_dock([]) + migration
    script += 'task.writeConfig("launchers", []); installed.push("org.gnome.Showtime.desktop");'
    script += 'var mttkdeResetDock = true;' + migration
    assert execute(script, ['org.gnome.Loupe.desktop'])[0][0]['pins'] == [
        'applications:org.gnome.Showtime.desktop']


def test_explicitly_requested_app_is_pinned_even_if_offered_before():
    migration = layout.DOCK_MIGRATION.read_text()
    script = existing_dock([]) + migration
    script += 'task.writeConfig("launchers", []);'
    script += 'var mttkdeRequestedDockApps = ["photos"];' + migration
    assert execute(script, ['org.gnome.Loupe.desktop'])[0][0]['pins'] == [
        'applications:org.gnome.Loupe.desktop']


def test_rebuild_with_reset_keeps_unpinned_apps_off_every_dock(monkeypatch):
    # Full reinstall path: layout rebuilt, user pins restored, reset migration.
    monkeypatch.setattr(layout, '_layout_has_any_theme_widget', lambda: True)
    monkeypatch.setenv('MTTKDE_WIZARD_OPTIONS', json.dumps({'reset_layout': True}))
    script = existing_dock(['applications:custom.desktop'], revision=3)
    script += 'task.writeConfig("dockPresetCategories", "photos,video");'
    script += layout._layout_script_with_launchers(
        layout.LAYOUT_SCRIPT, ['applications:custom.desktop'], layout.MAC_TASKS_ID)
    docks = execute(script, ['org.gnome.Loupe.desktop', 'org.gnome.Showtime.desktop'])
    for dock in docks:
        assert next(w['pins'] for w in dock if w['type'] == layout.MAC_TASKS_ID) == [
            'applications:custom.desktop']


def test_clock_upgrade_preserves_custom_date_and_hour_preferences(offline):
    migration = (offline / 'layouts/migrate-status-controls.js').read_text()
    source = HARNESS + '''
Panel.prototype.widgets = function() { return this.widgetIds.map(id => this.widgetById(id)); };
function clockWith(format, hourMode) {
    var panel = new Panel();
    panel.addWidget('org.kde.mac-tahoe-liquid-kde.controlcenter').writeConfig('statusOrderRevision', 2);
    panel.addWidget('org.kde.mac-tahoe-liquid-kde.wifi');
    var clock = panel.addWidget('org.kde.plasma.digitalclock');
    clock.config = {dateFormat: 'custom', customDateFormat: format, use24hFormat: hourMode};
    return clock;
}
var oldFormat = "ddd d ' | '";
var original = clockWith(oldFormat, 1), custom = clockWith('yyyy-MM-dd', 1), military = clockWith(oldFormat, 2);
''' + migration + '''
var updated = [original, custom, military].map(w => [w.config.customDateFormat, w.config.use24hFormat]);
original.writeConfig('customDateFormat', oldFormat);
''' + migration + '''
JSON.stringify([updated, original.config.customDateFormat]);
'''
    result = subprocess.run([sys.executable, '-c', RUNNER], input=source,
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == [
        [['ddd MMM d', 0], ['yyyy-MM-dd', 1], ['ddd MMM d', 2]], "ddd d ' | '"]
