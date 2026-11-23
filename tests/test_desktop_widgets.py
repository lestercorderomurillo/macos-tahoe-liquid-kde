"""Opt-in Liquid Glass desktop widgets (#143)."""
import subprocess
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/scripts"))


def test_bundle_holds_the_widget_set_and_photos():
    archive = ROOT / "src/offline/desktop-widgets/liquidglass-kde-widgets.tar.zst"
    listing = subprocess.run(["tar", "--zstd", "-tf", str(archive)], capture_output=True, text=True, check=True).stdout
    ids = {line.split("/")[1] for line in listing.splitlines() if line.count("/") >= 2 and line.endswith("/metadata.json")}
    for name in ("calendar", "weather", "music", "timer", "clock-analog", "photos"):
        assert "com.jaxparrow07.macoswidgets." + name in ids
    assert not any(".test-" in i or i.endswith(".test-glass") for i in ids)
    assert (archive.parent / "LICENSE").read_text().startswith("                    GNU GENERAL PUBLIC LICENSE")


def test_panel_weather_route_preserves_existing_context_actions(tmp_path):
    from weather_panel_settings import MARKER, PLUGIN, stage_configuration_route

    archive = ROOT / "src/offline/desktop-widgets/liquidglass-kde-widgets.tar.zst"
    main = tmp_path / PLUGIN / "contents/ui/main.qml"
    subprocess.run(["tar", "--zstd", "-xf", str(archive), "-C", str(tmp_path),
                    f"./{PLUGIN}/contents/ui/main.qml"], check=True)
    stage_configuration_route(tmp_path / PLUGIN)
    updated = main.read_text()
    assert MARKER in updated
    assert "section: \"weather_panel\"" in updated
    assert "[refreshAction, settingsEntry].concat(commonActions.list)" in updated
    assert "settingsEntry.available ? Qt.NoButton : Qt.RightButton" in updated
    stage_configuration_route(tmp_path / PLUGIN)
    assert main.read_text() == updated


def test_migrated_desktop_widget_settings_cover_the_bundled_schema_and_clipboard(tmp_path):
    from xml.etree import ElementTree
    from desktop_widget_settings import (
        INACTIVE_FIELDS, MARKER, NAMES, PREFIX, STYLE_KEYS, read_schema, stage_configuration_route,
    )

    archive = ROOT / "src/offline/desktop-widgets/liquidglass-kde-widgets.tar.zst"
    subprocess.run(["tar", "--zstd", "-xf", str(archive), "-C", str(tmp_path),
                    *("./" + PREFIX + name for name in NAMES)], check=True)
    for variant in NAMES:
        package = tmp_path / (PREFIX + variant)
        xml = ElementTree.parse(package / "contents/config/main.xml")
        keys = {node.attrib["name"] for node in xml.findall(".//{*}entry")}
        assert read_schema(package).DEFAULTS.keys() == keys - INACTIVE_FIELDS.get(variant, set())
        stage_configuration_route(package)
        main = package / "contents/ui/main.qml"
        updated = main.read_text()
        assert MARKER in updated
        assert 'section: "desktop_widget"' in updated
        assert "commonActions.support] : commonActions.list" in updated
        stage_configuration_route(package)
        assert main.read_text() == updated
        codec = (package / "contents/ui/components/styleCodec.js").read_text()
        assert all(f'{key}: "{value}"' in codec for key, value in STYLE_KEYS.items())


def test_shared_widget_editors_preserve_values_and_save_only_the_selected_instance(tmp_path):
    from desktop_widget_settings import NAMES, PREFIX

    archive = ROOT / "src/offline/desktop-widgets/liquidglass-kde-widgets.tar.zst"
    subprocess.run(["tar", "--zstd", "-xf", str(archive), "-C", str(tmp_path),
                    *("./" + PREFIX + name for name in NAMES)], check=True)
    script = r'''
import sys
from pathlib import Path
sys.path[:0] = ['src/installer', 'src/scripts']
from PyQt6.QtWidgets import QApplication, QWidget
from desktop_widget_settings import NAMES, PREFIX, read_schema
import desktop_widget_editor as editor

app = QApplication([])
parent = QWidget()
parent.t = lambda label: label
editor.media_players = lambda: {'Firefox': 'Firefox'}
root = Path(sys.argv[1])
records = {}
for identifier, name in enumerate(NAMES, 1):
    plugin = PREFIX + name
    defaults = read_schema(root / plugin).DEFAULTS
    records[identifier] = (plugin, defaults, defaults.copy())
widget = editor.DesktopWidgetEditor(records, None, parent)
for index in range(widget.picker.count()):
    widget.picker.setCurrentIndex(index)
    expected = records[widget.picker.currentData()][1]
    assert widget.values() == expected, widget.plugin

def save(plugin, identifier, changes):
    saved.append((plugin, identifier, changes))
    return records[identifier][2] | changes

saved = []
editor.apply = save
identifier = next(key for key, record in records.items() if record[0] == PREFIX + 'calendar')
widget.picker.setCurrentIndex(widget.picker.findData(identifier))
widget.set_values({'enabledCalendarPlugins': ['astronomicalevents'], 'firstDayOfWeek': 1})
widget.save_settings()
assert saved == [(PREFIX + 'calendar', identifier,
                  {'enabledCalendarPlugins': ['astronomicalevents'], 'firstDayOfWeek': 1})]
'''
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], cwd=ROOT,
                            env=os.environ | {"QT_QPA_PLATFORM": "offscreen"},
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture
def widgets(tmp_path, monkeypatch):
    from steps import plasmoids
    archive_root = tmp_path / "src"
    for name in ("com.jaxparrow07.macoswidgets.one", "com.jaxparrow07.macoswidgets.two"):
        (archive_root / name).mkdir(parents=True)
        (archive_root / name / "metadata.json").write_text("{}")
    archive = tmp_path / "widgets.tar.zst"
    subprocess.run(["tar", "--zstd", "-cf", str(archive), "-C", str(archive_root), "."], check=True)
    dest = tmp_path / "plasmoids"
    monkeypatch.setattr(plasmoids, "WIDGETS_ARCHIVE", archive)
    monkeypatch.setattr(plasmoids, "DEST_DIR", dest)
    monkeypatch.setattr(plasmoids, "WIDGETS_STATE", tmp_path / "state/desktop-widgets.list")

    def copy(src, dst, label):
        import shutil
        shutil.copytree(src, dst, dirs_exist_ok=True)
        return True

    def remove(path, label=None):
        import shutil
        shutil.rmtree(path, ignore_errors=True)
        return True

    monkeypatch.setattr(plasmoids, "install_tree", copy)
    monkeypatch.setattr(plasmoids, "remove_tree", remove)
    return plasmoids, dest


def test_opting_in_installs_and_opting_out_removes_only_ours(widgets):
    plasmoids, dest = widgets
    (dest / "com.user.own").mkdir(parents=True)
    plasmoids.install_desktop_widgets(True)
    assert {p.name for p in dest.iterdir()} == {"com.jaxparrow07.macoswidgets.one", "com.jaxparrow07.macoswidgets.two", "com.user.own"}
    assert plasmoids._installed_widgets() == {"com.jaxparrow07.macoswidgets.one", "com.jaxparrow07.macoswidgets.two"}
    plasmoids.install_desktop_widgets(False)
    assert {p.name for p in dest.iterdir()} == {"com.user.own"}
    assert not plasmoids.WIDGETS_STATE.exists()


def test_existing_user_widget_survives_opt_in_and_out(widgets):
    plasmoids, dest = widgets
    user_widget = dest / "com.jaxparrow07.macoswidgets.one"
    user_widget.mkdir(parents=True)
    personal = user_widget / "metadata.json"
    personal.write_text('{"user": true}')
    plasmoids.install_desktop_widgets(False)
    plasmoids.install_desktop_widgets(True)
    assert "com.jaxparrow07.macoswidgets.one" not in plasmoids._installed_widgets()
    plasmoids.install_desktop_widgets(False)
    assert personal.read_text() == '{"user": true}'
    assert {p.name for p in dest.iterdir()} == {user_widget.name}


def test_state_entries_that_are_paths_are_ignored(widgets):
    plasmoids, dest = widgets
    unrelated = dest / "org.kde.other"
    unrelated.mkdir(parents=True)
    outside = dest.parent / "outside"
    outside.mkdir()
    plasmoids.WIDGETS_STATE.parent.mkdir(parents=True)
    plasmoids.WIDGETS_STATE.write_text("../outside\norg.kde.other\n")
    plasmoids._remove_desktop_widgets()
    assert outside.is_dir() and unrelated.is_dir()


def test_desktop_widgets_are_selected_by_default():
    from installer_choices import defaults
    assert defaults()["desktop_widgets"] is True
