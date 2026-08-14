"""Regression coverage for Acrylic Glass live removal."""

from steps import acrylic_glass


def test_uninstall_disables_before_unload_and_reconfigures_after_removal(
        monkeypatch, tmp_path):
    home = tmp_path / "home"
    plugin_dir = tmp_path / "plugins"
    kwinrc = home / ".config/kwinrc"
    kwinrc.parent.mkdir(parents=True)
    kwinrc.write_text(
        "[Plugins]\nliquidglassEnabled=true\n\n"
        "[Effect-liquidglass]\nBlurStrength=5\n\n"
        "[Windows]\nPlacement=Smart\n"
    )

    calls = []
    removed = []
    monkeypatch.setattr(acrylic_glass.Path, "home", lambda: home)
    monkeypatch.setattr(acrylic_glass, "LEGACY_USER_PLUGIN_DIR",
                        home / ".local/lib/qt6/plugins")
    monkeypatch.setattr(acrylic_glass, "_plugin_dir", lambda: plugin_dir)
    monkeypatch.setattr(
        acrylic_glass, "kw_write",
        lambda *args: calls.append(("write", args)) or True,
    )
    monkeypatch.setattr(
        acrylic_glass, "qdbus_call",
        lambda *args: calls.append(("dbus", args)) or True,
    )
    monkeypatch.setattr(
        acrylic_glass, "sudo_remove",
        lambda path, label: removed.append(path) or True,
    )
    monkeypatch.setattr(acrylic_glass, "info", lambda message: None)

    acrylic_glass.uninstall()

    assert calls[0][0] == "write"
    assert "liquidglassEnabled" in calls[0][1]
    assert calls[1][1][-2:] == (
        "org.kde.kwin.Effects.unloadEffect", "liquidglass",
    )
    assert calls[2][1][-1] == "org.kde.KWin.reconfigure"
    assert calls[-1][1][-1] == "org.kde.KWin.reconfigure"
    assert len(removed) == 2
    text = kwinrc.read_text()
    assert "[Effect-liquidglass]" not in text
    assert "[Windows]\nPlacement=Smart" in text
