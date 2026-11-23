import json
from pathlib import Path
import re
from xml.etree import ElementTree

import pytest

from dock_preferences import APPEARANCE, BEHAVIOR, DEFAULTS, DOCK_ICONS, DOCK_TASKS
import launcher_preferences
import plasmoid_settings
import system_menu_preferences


def test_installed_settings_records_its_golden_gate_source(tmp_path, monkeypatch):
    import settings_launcher

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    source = tmp_path / "snapshot"
    source.mkdir()
    (source / "installer").write_text("")
    (source / ".golden-gate-ready").write_text("local-development\n")
    settings_launcher.install(source)
    record = tmp_path / "state/mac-tahoe-liquid-kde/settings-source"
    assert record.read_text().strip() == str(source)
    settings_launcher.uninstall()
    assert not record.exists()


def test_system_menu_preferences_use_the_applet_appearance_group(monkeypatch):
    plugin = system_menu_preferences.PLUGIN
    qml = Path(__file__).resolve().parents[1] / "src/offline/plasmoids" / plugin / "qml"
    legacy_fields = {field for name in ("configSystemMenu.qml", "configGeneral.qml")
                     for field in re.findall(r"\bcfg_(\w+)", (qml / name).read_text())}
    defaults = system_menu_preferences.DEFAULTS
    assert defaults.keys() == legacy_fields | {"cmdAppStore", "menuIconPreset"}
    assert defaults.keys() == {key for form in system_menu_preferences.FORMS.values() for key in form}
    expected = {
        key: (not default if isinstance(default, bool) else f"test-{key}")
        for key, default in defaults.items()
    }
    expected["cmdAppStore"] = '/usr/bin/example "one argument"'
    expected["menuIconPreset"] = "pear"
    expected["activationShortcut"] = "Ctrl+Alt+M"
    scripts = []

    def evaluate(script):
        scripts.append(script)
        request = json.loads(script.split("const request = ", 1)[1].split(";\n", 1)[0])
        assert request["plugins"] == [plugin]
        assert request["group"] == "Appearance"
        assert request["instance"] == 19
        assert request["hasShortcut"] is True
        assert request["changes"] == expected
        assert request["defaults"] == defaults
        return json.dumps({19: expected | {"useSystemFont": "true"}})

    monkeypatch.setattr(plasmoid_settings, "_evaluate_plasma_script", evaluate)
    assert plasmoid_settings.apply("system_menu", 19, expected) == expected

    with pytest.raises(ValueError, match="Invalid widget preferences"):
        plasmoid_settings.apply("system_menu", 19, {"macOSDockIcons": True})
    with pytest.raises(ValueError, match="Invalid widget preference value"):
        plasmoid_settings.apply("system_menu", 19, {"menuIconPreset": "../pear"})
    assert len(scripts) == 1


@pytest.mark.parametrize(("detected", "icon"), [("neon", "neon"), ("opensuse", "opensuse-tumbleweed"), ("other", "penguin")])
def test_system_menu_automatic_icon_and_offline_presets(monkeypatch, detected, icon):
    import distro

    monkeypatch.setattr(distro, "current_distro", lambda: detected)
    assert system_menu_preferences.detected_distro_icon() == icon
    presets = set(system_menu_preferences.CHOICES["menuIconPreset"]) - {"distro", "custom"}
    assert presets == {path.stem for path in system_menu_preferences.ICON_DIR.glob("*.svg")}


def test_missing_instance_does_not_report_saved(monkeypatch):
    monkeypatch.setattr(plasmoid_settings, "_evaluate_plasma_script", lambda script: "{}")
    with pytest.raises(RuntimeError, match="Could not save"):
        plasmoid_settings.apply("system_menu", 19, {"iconAppStore": "folder-download"})


def test_shared_dock_form_covers_each_legacy_config_field():
    ui = Path(__file__).resolve().parents[1] / "src/offline/plasmoids" / DOCK_TASKS / "contents/ui"
    for filename, form in (("ConfigAppearance.qml", APPEARANCE), ("ConfigBehavior.qml", BEHAVIOR)):
        legacy_fields = set(re.findall(r"\bproperty\s+\w+\s+cfg_(\w+)", (ui / filename).read_text()))
        assert legacy_fields == form.keys()
    assert DEFAULTS.keys() == APPEARANCE.keys() | BEHAVIOR.keys()


def test_dock_normalizes_values_and_preserves_existing_sort_modes(monkeypatch):
    called = []
    def evaluate(script):
        request = json.loads(script.split("const request = ", 1)[1].split(";\n", 1)[0])
        assert request["plugins"] == sorted((DOCK_ICONS, DOCK_TASKS))
        assert request["group"] == "General"
        called.append(request)
        return json.dumps({21: {"_plugin": DOCK_ICONS, "_vertical": False, "dockMagnification": "120",
                                "sortingStrategy": "5", "showToolTips": "false"}})

    monkeypatch.setattr(plasmoid_settings, "_evaluate_plasma_script", evaluate)
    values = plasmoid_settings.apply("dock", 21, {"dockMagnification": 120})
    assert values["dockMagnification"] == 120
    assert values["sortingStrategy"] == 5
    assert values["showToolTips"] is False
    assert values["_plugin"] == DOCK_ICONS
    assert values["_vertical"] is False
    assert called[0]["changes"] == {"dockMagnification": 120}
    with pytest.raises(ValueError, match="Invalid Dock preference value"):
        plasmoid_settings.apply("dock", 21, {"dockMagnification": 200})
    with pytest.raises(ValueError, match="Invalid widget preferences"):
        plasmoid_settings.apply("dock", 21, {"dockMagnification": True})
    assert len(called) == 1


def test_apps_form_covers_the_config_and_preserves_editions_and_file_urls(monkeypatch):
    prefs = launcher_preferences
    ui = Path(__file__).resolve().parents[1] / "src/offline/plasmoids" / prefs.LAUNCHER_ID / "contents/ui"
    legacy = set(re.findall(r"\bproperty\s+\w+\s+cfg_(\w+)", (ui / "ConfigGeneral.qml").read_text()))
    assert legacy == {key for page in prefs.FORMS.values() for key in page} == prefs.DEFAULTS.keys()
    image = "file:///home/tester/my%20icon.svg"
    changes = {"launcherPreset": 0, "customButtonImage": image, "goldenGateColumns": 8,
               "activationShortcut": "Meta+Shift+F11"}

    def evaluate(script):
        request = json.loads(script.split("const request = ", 1)[1].split(";\n", 1)[0])
        assert request["plugins"] == [prefs.LAUNCHER_ID]
        assert request["hasShortcut"]
        assert "activationShortcut" not in request["defaults"]
        assert request["changes"] == changes
        return json.dumps({18: changes | {"numberColumns": "5", "floating": "false"}})

    monkeypatch.setattr(plasmoid_settings, "_evaluate_plasma_script", evaluate)
    values = plasmoid_settings.apply("launcher", 18, changes)
    assert values["launcherPreset"] == 0
    assert values["customButtonImage"] == image
    assert values["goldenGateColumns"] == 8 and values["numberColumns"] == 5
    assert values["floating"] is False
    assert values["activationShortcut"] == "Meta+Shift+F11"


def test_control_center_retains_every_tile_and_its_existing_default():
    plugin = plasmoid_settings.WIDGET_PREFIX + "controlcenter"
    package = Path(__file__).resolve().parents[1] / "src/offline/plasmoids" / plugin / "contents"
    edit = (package / "ui/EditControls.qml").read_text()
    assert set(re.findall(r'key:"(\w+)"', edit)) == plasmoid_settings.CONTROL_CENTER_FIELDS.keys()
    schema = ElementTree.parse(package / "config/main.xml")
    defaults = {node.attrib["name"]: node.findtext("{*}default") == "true"
                for node in schema.findall(".//{*}entry")}
    assert plasmoid_settings.SETTINGS["control_center"][2] == defaults


def test_bar_widgets_use_plasma_activation_shortcut_and_keep_plugin_identity(monkeypatch):
    plugin = plasmoid_settings.WIDGET_PREFIX + "downloads"

    def evaluate(script):
        request = json.loads(script.split("const request = ", 1)[1].split(";\n", 1)[0])
        assert request["plugins"] == sorted(plasmoid_settings.BAR_WIDGET_LABELS)
        assert request["identifyPlugin"] and request["hasShortcut"]
        assert request["defaults"] == {}
        assert request["changes"] == {"activationShortcut": "Meta+Shift+F11"}
        return json.dumps({25: {"activationShortcut": "Meta+Shift+F11", "_plugin": plugin}})

    monkeypatch.setattr(plasmoid_settings, "_evaluate_plasma_script", evaluate)
    assert plasmoid_settings.apply("bar_shortcuts", 25, {"activationShortcut": "Meta+Shift+F11"}) == {
        "activationShortcut": "Meta+Shift+F11", "_plugin": plugin,
    }


def test_panel_weather_coordinates_and_temperature_unit(monkeypatch):
    desired = {"location": "Quito", "latitude": -0.18065, "longitude": -78.46783, "temperatureUnit": 1}

    def evaluate(script):
        request = json.loads(script.split("const request = ", 1)[1].split(";\n", 1)[0])
        assert request["plugins"] == ["com.jaxparrow07.macoswidgets.weatherpanel"]
        assert request["changes"] == desired
        return json.dumps({77: desired | {"latitude": "-0.18065", "temperatureUnit": "1", "activationShortcut": ""}})

    monkeypatch.setattr(plasmoid_settings, "_evaluate_plasma_script", evaluate)
    assert plasmoid_settings.apply("weather_panel", 77, desired) == desired | {"activationShortcut": ""}
    with pytest.raises(ValueError, match="Invalid weather preference value"):
        plasmoid_settings.apply("weather_panel", 77, {"latitude": 95.0})
