"""Layout-step tests: pinned-launcher preservation across uninstall.

The old appletsrc-regex tests were removed (they asserted text we never
controlled directly — see git history). These cover the pure-parsing
logic that keeps the user's pinned taskbar apps alive when --resetLayout
rebuilds the panel from scratch.
"""

import steps.layout as layout


_APPLETSRC = """\
[Containments][19298][Applets][19302][General]
launchers=preferred://filemanager,applications:steam.desktop

[Containments][19319][Applets][19322][Configuration][General]
launchers=preferred://browser,applications:org.kde.mac.tahoe.liquid.globalmenu.desktop,applications:steam.desktop
"""


def _write_appletsrc(tmp_path, text):
    cfg = tmp_path / ".config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "plasma-org.kde.plasma.desktop-appletsrc").write_text(text)


def _write_colorizer(path, version):
    path.mkdir(parents=True)
    (path / "metadata.json").write_text(
        f'{{"KPlugin": {{"Version": "{version}"}}}}\n'
    )


def test_ensure_panel_colorizer_upgrades_stale_user_copy(monkeypatch, tmp_path):
    bundled = tmp_path / "bundled"
    user = tmp_path / "user"
    system = tmp_path / "system"
    _write_colorizer(bundled, "7.3.0")
    _write_colorizer(user, "7.0.1")
    calls = []

    monkeypatch.setattr(layout, "COLORIZER_SRC", bundled)
    monkeypatch.setattr(layout, "_colorizer_dirs", lambda: [user, system])
    monkeypatch.setattr(
        layout, "install_tree",
        lambda src, dest, label: calls.append((src, dest, label)) or True,
    )

    layout._ensure_panel_colorizer()

    assert calls == [(bundled, user, "Panel Colorizer")]


def test_ensure_panel_colorizer_preserves_newer_system_copy(monkeypatch, tmp_path):
    bundled = tmp_path / "bundled"
    user = tmp_path / "user"
    system = tmp_path / "system"
    _write_colorizer(bundled, "7.3.0")
    _write_colorizer(system, "7.4.0")
    calls = []

    monkeypatch.setattr(layout, "COLORIZER_SRC", bundled)
    monkeypatch.setattr(layout, "_colorizer_dirs", lambda: [user, system])
    monkeypatch.setattr(
        layout, "install_tree",
        lambda *args: calls.append(args) or True,
    )

    layout._ensure_panel_colorizer()

    assert calls == []


def test_capture_dedups_and_drops_mactahoe(monkeypatch, tmp_path):
    monkeypatch.setattr(layout, "HOME", tmp_path)
    _write_appletsrc(tmp_path, _APPLETSRC)

    pins = layout._capture_pinned_launchers()

    # Order preserved, steam.desktop deduped, the mac.tahoe plasmoid dropped.
    assert pins == [
        "preferred://filemanager",
        "applications:steam.desktop",
        "preferred://browser",
    ]


def test_capture_empty_when_no_appletsrc(monkeypatch, tmp_path):
    monkeypatch.setattr(layout, "HOME", tmp_path)
    assert layout._capture_pinned_launchers() == []


def test_reset_with_pins_writes_launchers_into_script(monkeypatch):
    captured = {}
    monkeypatch.setattr(layout, "_evaluate_layout_script",
                        lambda script: captured.update(script=script) or True)

    assert layout._reset_with_pins(
        ["preferred://browser", "applications:steam.desktop"]) is True
    script = captured["script"]
    # The default reset JS plus a restore block targeting icontasks.
    assert "org.kde.plasma.icontasks" in script
    assert ("writeConfig('launchers', "
            "'preferred://browser,applications:steam.desktop')") in script


def test_reset_with_pins_skips_restore_block_when_no_pins(monkeypatch):
    captured = {}
    monkeypatch.setattr(layout, "_evaluate_layout_script",
                        lambda script: captured.update(script=script) or True)

    layout._reset_with_pins([])
    # No pins → no writeConfig('launchers') injection, just the plain reset.
    assert "writeConfig('launchers'" not in captured["script"]


def test_mac_layout_adds_no_application_launchers_of_its_own():
    script = layout.LAYOUT_SCRIPT.read_text()

    assert 'tasks.writeConfig("launchers", "");' in script
    # Keep the full-width panel invisible and let Plasma draw its own
    # light/dark-aware floating-applet surfaces. Custom panel/widget layers
    # stack and recreate an opaque strip plus mismatched dark tiles.
    assert ('"background": { "enabled": false, "opacity": 0, '
            '"shadow": false }') in script
    assert '"panel": {' not in script
    assert '"widgets": {' not in script
    assert '"custom": "#1c1c1e"' not in script
    assert "preferred://filemanager" not in script
    assert "applications:steam.desktop" not in script


def test_panel_background_keeps_light_dark_surface_parity(offline):
    panel = "widgets/panel-background.svgz"
    dark = offline / "plasma-theme/MacTahoeLiquidKde-Dark" / panel
    light = offline / "plasma-theme/MacTahoeLiquidKde-Light" / panel

    # Both packages map the same neutral SVG through their active color
    # scheme. A separate hardcoded dark asset caused 55% square tiles on the
    # top bar and made the Dock inherit the same heavy tint in v0.48.0.
    assert dark.read_bytes() == light.read_bytes()


# ── Discover install check ──────────────────────────────────────────────

_LAUNCHERS_LINE = (
    'tasks.writeConfig("launchers", "preferred://filemanager,'
    "preferred://terminal,preferred://browser,"
    "applications:systemsettings.desktop,"
    "applications:org.kde.discover.desktop,"
    'applications:steam.desktop");'
)


def _capture_evaluated_script(monkeypatch):
    captured = {}
    monkeypatch.setattr(layout, "_evaluate_layout_script",
                        lambda script: captured.update(script=script) or True)
    return captured


class _FakeScript:
    def __init__(self, text):
        self._text = text

    def read_text(self):
        return self._text


def test_discover_installed_detected_in_xdg_data_home(monkeypatch, tmp_path):
    data_home = tmp_path / "xdg-data"
    monkeypatch.setattr(layout, "DATA_HOME", data_home)
    apps = data_home / "applications"
    apps.mkdir(parents=True)
    (apps / "org.kde.discover.desktop").write_text("[Desktop Entry]\n")

    assert layout._discover_is_installed() is True


def test_discover_absent_when_no_desktop_file(monkeypatch, tmp_path):
    # XDG_DATA_HOME has no Discover desktop file; force the system prefixes to
    # a bare tmp dir so a host installation cannot leak into this unit test.
    monkeypatch.setattr(layout, "DATA_HOME", tmp_path / "xdg-data")
    monkeypatch.setattr(layout, "Path", lambda p: tmp_path / "nonexistent")

    assert layout._discover_is_installed() is False


def test_discover_does_not_probe_legacy_home_when_xdg_data_home_is_custom(
        monkeypatch, tmp_path):
    # A custom XDG_DATA_HOME replaces ~/.local/share; silently probing both
    # would make the installer select launchers that Plasma cannot discover.
    legacy_apps = tmp_path / ".local/share/applications"
    legacy_apps.mkdir(parents=True)
    (legacy_apps / "org.kde.discover.desktop").write_text("[Desktop Entry]\n")

    monkeypatch.setattr(layout, "HOME", tmp_path)
    monkeypatch.setattr(layout, "DATA_HOME", tmp_path / "custom-data")
    monkeypatch.setattr(layout, "Path", lambda p: tmp_path / "nonexistent")

    assert layout._discover_is_installed() is False


def test_evaluate_layout_strips_discover_when_absent(monkeypatch):
    captured = _capture_evaluated_script(monkeypatch)
    monkeypatch.setattr(layout, "_discover_is_installed", lambda: False)

    layout._evaluate_layout(_FakeScript(_LAUNCHERS_LINE))
    script = captured["script"]

    assert "org.kde.discover.desktop" not in script
    # Neighbours survive intact, no dangling double comma.
    assert "applications:systemsettings.desktop,applications:steam.desktop" in script
    assert ",," not in script


def test_evaluate_layout_keeps_discover_when_installed(monkeypatch):
    captured = _capture_evaluated_script(monkeypatch)
    monkeypatch.setattr(layout, "_discover_is_installed", lambda: True)

    layout._evaluate_layout(_FakeScript(_LAUNCHERS_LINE))

    assert "applications:org.kde.discover.desktop" in captured["script"]


# ── plasmashellrc panel opacity ──────────────────────────────────────


def _write_plasmashellrc(tmp_path, text):
    cfg = tmp_path / ".config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "plasmashellrc").write_text(text)


def test_patch_plasmashellrc_forces_translucent_on_non_floating_top_bar(
        monkeypatch, tmp_path):
    # The top bar is floating=0 with applets-only floating. Leaving
    # panelOpacity unset falls back to Plasma's Adaptive default,
    # which goes opaque whenever a window touches the screen edge under it —
    # so the top bar must get the same forced Translucent (2) as the dock.
    monkeypatch.setattr(layout, "HOME", tmp_path)
    _write_plasmashellrc(
        tmp_path,
        "[PlasmaViews][Panel 238]\n"
        "floating=0\n"
        "shell=org.kde.plasma.desktop\n"
        "\n"
        "[PlasmaViews][Panel 259]\n"
        "floating=1\n"
        "shell=org.kde.plasma.desktop\n",
    )
    layout._patch_plasmashellrc()
    text = (tmp_path / ".config/plasmashellrc").read_text()
    top_section, dock_section = text.split("[PlasmaViews][Panel 259]")
    assert "panelOpacity=2" in top_section
    assert "floatingApplets=1" in top_section
    assert "panelOpacity=2" in dock_section


def test_patch_plasmashellrc_overwrites_stale_opacity_value(
        monkeypatch, tmp_path):
    monkeypatch.setattr(layout, "HOME", tmp_path)
    _write_plasmashellrc(
        tmp_path,
        "[PlasmaViews][Panel 238]\n"
        "floating=0\n"
        "panelOpacity=1\n"
        "shell=org.kde.plasma.desktop\n",
    )
    layout._patch_plasmashellrc()
    text = (tmp_path / ".config/plasmashellrc").read_text()
    assert "panelOpacity=2" in text
    assert "panelOpacity=1" not in text


# ── update-safe layout ownership ─────────────────────────────────────


def _quiet_layout_install(monkeypatch, tmp_path):
    monkeypatch.setattr(layout, "HOME", tmp_path)
    monkeypatch.setattr(layout, "_ensure_panel_colorizer", lambda: None)
    monkeypatch.setattr(layout, "_patch_plasmashellrc", lambda: None)
    monkeypatch.setattr(layout, "ok", lambda message: None)
    monkeypatch.setattr(layout, "warn", lambda message: None)
    monkeypatch.setattr(layout.time, "sleep", lambda seconds: None)


def test_install_always_rebuilds_layout_from_user_pins(monkeypatch, tmp_path):
    _quiet_layout_install(monkeypatch, tmp_path)
    _write_appletsrc(tmp_path, _APPLETSRC)
    marker = layout._layout_marker()
    marker.parent.mkdir(parents=True)
    marker.write_text("1\n")
    calls = []
    monkeypatch.setattr(
        layout, "_evaluate_layout_with_launchers",
        lambda script, pins, widget:
        calls.append((script, pins, widget)) or True,
    )
    monkeypatch.setattr(layout, "_wait_for_layout_install", lambda: True)

    layout.install()

    assert calls == [(
        layout.LAYOUT_SCRIPT,
        [
            "preferred://filemanager",
            "applications:steam.desktop",
            "preferred://browser",
        ],
        layout.MAC_TASKS_ID,
    )]
    assert marker.is_file()


def test_failed_install_clears_stale_marker_for_retry(monkeypatch, tmp_path):
    _quiet_layout_install(monkeypatch, tmp_path)
    marker = layout._layout_marker()
    marker.parent.mkdir(parents=True)
    marker.write_text("1\n")
    monkeypatch.setattr(
        layout, "_evaluate_layout_with_launchers",
        lambda script, pins, widget: False,
    )

    layout.install()

    assert not marker.exists()
    assert layout.is_installed() is False


def test_uninstall_always_rebuilds_bottom_panel_with_same_pins(
        monkeypatch, tmp_path):
    monkeypatch.setattr(layout, "HOME", tmp_path)
    _write_appletsrc(tmp_path, _APPLETSRC)
    calls = []
    monkeypatch.setattr(layout, "_layout_has_any_theme_widget", lambda: True)
    monkeypatch.setattr(
        layout, "_reset_with_pins",
        lambda pins: calls.append(pins) or True,
    )
    monkeypatch.setattr(layout, "ok", lambda message: None)

    layout.uninstall()

    assert calls == [[
        "preferred://filemanager",
        "applications:steam.desktop",
        "preferred://browser",
    ]]


def test_uninstall_leaves_unrelated_custom_layout_untouched(
        monkeypatch, tmp_path):
    monkeypatch.setattr(layout, "HOME", tmp_path)
    _write_appletsrc(tmp_path, "plugin=org.example.custom.panel\n")
    monkeypatch.setattr(
        layout, "_reset_with_pins",
        lambda pins: (_ for _ in ()).throw(
            AssertionError("unrelated layout was rebuilt"),
        ),
    )
    messages = []
    monkeypatch.setattr(layout, "ok", messages.append)

    layout.uninstall()

    assert messages == ["Layout already clean"]


def test_uninstall_scrubs_only_our_stale_panel_transparency(
        monkeypatch, tmp_path):
    monkeypatch.setattr(layout, "HOME", tmp_path)
    _write_appletsrc(tmp_path, "plugin=org.example.custom.panel\n")
    prc = tmp_path / ".config/plasmashellrc"
    prc.write_text(
        "[PlasmaViews][Panel 1]\n"
        "floating=1\n"
        "panelOpacity=2\n"
        "floatingApplets=1\n"
        "visibilityMode=0\n\n"
        "[PlasmaViews][Panel 2]\n"
        "floating=1\n"
        "panelOpacity=1\n"
        "floatingApplets=0\n"
    )
    messages = []
    monkeypatch.setattr(layout, "ok", messages.append)

    layout.uninstall()

    text = prc.read_text()
    assert "[PlasmaViews][Panel 1]\nfloating=1\nvisibilityMode=0" in text
    assert "[PlasmaViews][Panel 2]\nfloating=1\npanelOpacity=1" in text
    assert "floatingApplets=0" in text
    assert messages == ["Panel transparency reset", "Layout already clean"]


def test_uninstall_recognizes_legacy_mac_layout_ids(monkeypatch, tmp_path):
    monkeypatch.setattr(layout, "HOME", tmp_path)
    _write_appletsrc(
        tmp_path,
        "\n".join([
            "plugin=org.kde.mac-tahoe-liquid-kde.menu",
            "plugin=org.kde.mac.tahoe.globalmenu",
            "plugin=org.kde.mactahoe-liquid-kde.trash",
        ]),
    )
    calls = []
    monkeypatch.setattr(
        layout, "_reset_with_pins",
        lambda pins: calls.append(pins) or True,
    )
    monkeypatch.setattr(layout, "ok", lambda message: None)

    layout.uninstall()

    assert calls == [[]]


def test_layout_uninstall_removes_update_marker(monkeypatch, tmp_path):
    monkeypatch.setattr(layout, "HOME", tmp_path)
    monkeypatch.setattr(layout, "ok", lambda message: None)
    monkeypatch.setattr(layout, "_layout_has_any_theme_widget", lambda: True)
    monkeypatch.setattr(layout, "_reset_with_pins", lambda pins: True)
    marker = layout._layout_marker()
    marker.parent.mkdir(parents=True)
    marker.write_text("1\n")

    layout.uninstall()

    assert not marker.exists()
