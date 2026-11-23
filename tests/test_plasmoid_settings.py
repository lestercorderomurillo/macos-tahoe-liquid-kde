import json
from pathlib import Path
import re

import pytest

from dock_preferences import APPEARANCE, BEHAVIOR, DEFAULTS, DOCK_ICONS, DOCK_TASKS
import plasmoid_settings


def test_system_menu_preferences_use_the_applet_appearance_group(monkeypatch):
    expected = {"iconAppStore": "folder-download",
                "cmdAppStore": '/usr/bin/example "one argument"',
                "cmdLogOut": "example-logout"}
    scripts = []

    def evaluate(script):
        scripts.append(script)
        request = json.loads(script.split("const request = ", 1)[1].split(";\n", 1)[0])
        assert request["plugins"] == ["org.kde.mac.tahoe.liquid.globalmenu"]
        assert request["group"] == "Appearance"
        assert request["instance"] == 19
        assert request["changes"] == expected
        return json.dumps({19: expected})

    monkeypatch.setattr(plasmoid_settings, "_evaluate_plasma_script", evaluate)
    assert plasmoid_settings.apply("system_menu", 19, expected) == expected

    with pytest.raises(ValueError, match="Invalid widget preferences"):
        plasmoid_settings.apply("system_menu", 19, {"macOSDockIcons": True})
    assert len(scripts) == 1


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
