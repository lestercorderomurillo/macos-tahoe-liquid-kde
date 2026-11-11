"""Window button position: left (default), right, or keep the user's layout."""

import importlib.util
import json
import shutil
from importlib.machinery import SourceFileLoader

import pytest

import installer_choices as choices
import theme_switch
import window_controls as controls

LAYOUTS = {
    "left": ({"ButtonsOnLeft": "XIA", "ButtonsOnRight": ""}, "close,minimize,maximize:"),
    "right": ({"ButtonsOnLeft": "", "ButtonsOnRight": "IAX"}, ":minimize,maximize,close"),
    "keep": ({}, None),
}


def test_default_is_left_and_values_are_validated():
    assert choices.defaults()["button_position"] == "left"
    for value in ("left", "right", "keep"):
        assert choices.validate({"button_position": value})["button_position"] == value
    with pytest.raises(ValueError):
        choices.validate({"button_position": "center"})


@pytest.mark.parametrize("position", LAYOUTS)
def test_layouts_follow_the_choice(monkeypatch, position):
    monkeypatch.setenv("MTTKDE_WIZARD_OPTIONS", json.dumps({"button_position": position}))
    kwin, gtk = LAYOUTS[position]
    assert theme_switch.button_position() == position
    assert dict(zip(("ButtonsOnLeft", "ButtonsOnRight"), theme_switch.kwin_button_layout() or ())) == kwin
    assert theme_switch.gtk_button_layout() == gtk


def test_missing_or_unknown_choice_keeps_the_macos_layout(monkeypatch):
    monkeypatch.delenv("MTTKDE_WIZARD_OPTIONS", raising=False)
    assert theme_switch.button_position() == "left"
    monkeypatch.setenv("MTTKDE_WIZARD_OPTIONS", '{"button_position": "bogus"}')
    assert theme_switch.button_position() == "left"


@pytest.mark.parametrize("position", LAYOUTS)
def test_window_decoration_step_install_and_uninstall(tmp_path, monkeypatch, position):
    from steps import window_decorations as step
    state = tmp_path / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    monkeypatch.setenv("MTTKDE_WIZARD_OPTIONS", json.dumps({"button_position": position}))
    monkeypatch.setattr(step, "DEST_DIR", tmp_path / "aurorae")
    monkeypatch.setattr(step, "qdbus_call", lambda *args: True)
    monkeypatch.setattr(step, "theme_mode", lambda: "light")
    writes = []
    monkeypatch.setattr(step, "kw_write", lambda *args: writes.append(args[-2:]) or True)

    step.install()
    written = {key: value for key, value in writes if key.startswith("ButtonsOn")}
    assert written == LAYOUTS[position][0]
    assert controls.buttons_kept() == (position == "keep")

    writes.clear()
    step.uninstall()
    restored = {key: value for key, value in writes if key.startswith("ButtonsOn")}
    assert restored == ({} if position == "keep" else {"ButtonsOnLeft": "M", "ButtonsOnRight": "IAX"})


def test_reinstalling_with_a_layout_forgets_an_earlier_keep(tmp_path, monkeypatch):
    from steps import window_decorations as step
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(step, "DEST_DIR", tmp_path / "aurorae")
    monkeypatch.setattr(step, "qdbus_call", lambda *args: True)
    monkeypatch.setattr(step, "theme_mode", lambda: "dark")
    monkeypatch.setattr(step, "kw_write", lambda *args: True)
    for position, kept in (("keep", True), ("right", False)):
        monkeypatch.setenv("MTTKDE_WIZARD_OPTIONS", json.dumps({"button_position": position}))
        step.install()
        assert controls.buttons_kept() is kept


@pytest.mark.parametrize("position", LAYOUTS)
def test_global_theme_defaults_match_the_choice(repo, tmp_path, monkeypatch, position):
    monkeypatch.setenv("MTTKDE_WIZARD_OPTIONS", json.dumps({"button_position": position}))
    for mode in ("Light", "Dark"):
        theme = tmp_path / mode
        shutil.copytree(repo / f"src/offline/look-and-feel/MacTahoeLiquidKde-{mode}", theme)
        controls.apply_global_theme(theme)
        lines = (theme / "contents/defaults").read_text().splitlines()
        found = dict(line.split("=", 1) for line in lines if line.startswith("ButtonsOn"))
        assert found == LAYOUTS[position][0]
        assert "BorderSize=Tiny" in lines  # Neighbouring keys are untouched.


@pytest.mark.parametrize("position", LAYOUTS)
def test_installed_switcher_keeps_the_choice_across_mode_changes(repo, tmp_path, monkeypatch, position):
    script = tmp_path / "mac-tahoe-theme-switch"
    text = (repo / "src/scripts/theme_switch.py").read_text()
    script.write_text(text.replace("INSTALLER_OPTIONS = {}", f'INSTALLER_OPTIONS = {{"button_position": "{position}"}}'))
    loader = SourceFileLoader("button_switcher", str(script))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    writes = []
    monkeypatch.setattr(module, "_have", lambda cmd: cmd == "kwriteconfig6")
    monkeypatch.setattr(module, "_kwrite", lambda *args: writes.append(args[-2:]) or True)
    monkeypatch.setattr(module, "apply_color_scheme", lambda scheme: True)
    monkeypatch.setenv("MTTKDE_WIZARD_OPTIONS", '{"button_position":"left"}')  # Ignored by the installed command.
    for mode in ("light", "dark", "light"):
        writes.clear()
        assert module.write_kde_theme_config(mode)
        written = {key: value for key, value in writes if key.startswith("ButtonsOn")}
        assert written == LAYOUTS[position][0]
