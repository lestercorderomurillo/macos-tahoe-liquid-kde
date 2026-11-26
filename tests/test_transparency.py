"""Transparent themes remain selected when upgrading an old appearance file."""
import pytest
import theme_switch as switch


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("declarative", [False, True])
def test_old_reduced_preference_cannot_select_opaque_themes(monkeypatch, tmp_path, mode, declarative):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    path = tmp_path / "config/mac-tahoe-liquid-kde/appearance.json"
    path.parent.mkdir(parents=True)
    target = tmp_path / "appearance-source.json" if declarative else path
    original = '{"transparency":"reduced","otherSetting":42}'
    target.write_text(original)
    if declarative:
        path.symlink_to(target)
    name = "MacTahoeLiquidKde-" + mode.capitalize()
    (tmp_path / ".themes" / name).mkdir(parents=True)
    writes, gtk = [], []
    monkeypatch.setattr(switch, "_have", lambda command: command == "kwriteconfig6")
    monkeypatch.setattr(switch, "_kwrite", lambda *args: writes.append(args) or True)
    monkeypatch.setattr(switch, "apply_color_scheme", lambda *args: True)
    monkeypatch.setattr(switch, "_set_kvantum_theme", lambda mode: None)
    monkeypatch.setattr(switch, "_qdbus", lambda *args: gtk.append(args))
    monkeypatch.setattr(switch, "flush_icon_caches", lambda: None)
    assert switch.write_kde_theme_config(mode)
    switch._apply_local_extras(mode)
    assert ("--file", "plasmarc", "--group", "Theme", "--key", "name", name) in writes
    assert ("org.kde.GtkConfig", "/GtkConfig", "org.kde.GtkConfig.setGtkTheme", name) in gtk
    assert switch._kvantum_theme(mode) == (switch.KVANTUM_THEME_DARK if mode == "dark" else switch.KVANTUM_THEME_LIGHT)
    assert target.read_text() == original
    assert path.is_symlink() == declarative


def test_patch_dock_subcommand_is_idempotent_and_does_not_apply_theme(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(switch, "_sync_session_env", lambda: None)
    monkeypatch.setattr(switch, "apply", lambda *a, **k: pytest.fail("full apply called"))
    (tmp_path / "plasma-org.kde.plasma.desktop-appletsrc").write_text(
        "[Containments][1][Applets][4]\nplugin=org.kde.mac.tahoe.liquid.globalmenu\n")
    path = tmp_path / "plasmashellrc"
    path.write_text("[PlasmaViews][Panel 1]\nfloating=0\npanelOpacity=0\n")
    assert switch.main(["patch-dock"]) == 0
    result = path.read_text()
    assert "floatingApplets=1" in result
    assert "panelOpacity=2" in result
    assert switch.main(["patch-dock"]) == 0
    assert path.read_text() == result
