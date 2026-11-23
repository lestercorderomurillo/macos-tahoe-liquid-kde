import json

import pytest

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
