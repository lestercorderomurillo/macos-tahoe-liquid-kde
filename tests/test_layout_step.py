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
    assert "preferred://filemanager" not in script
    assert "applications:steam.desktop" not in script


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


def test_discover_installed_detected_in_local_share(monkeypatch, tmp_path):
    monkeypatch.setattr(layout, "HOME", tmp_path)
    apps = tmp_path / ".local/share/applications"
    apps.mkdir(parents=True)
    (apps / "org.kde.discover.desktop").write_text("[Desktop Entry]\n")

    assert layout._discover_is_installed() is True


def test_discover_absent_when_no_desktop_file(monkeypatch, tmp_path):
    # HOME has no discover .desktop; force the system prefixes to a bare
    # tmp dir so a Discover actually installed on the test host can't leak in.
    monkeypatch.setattr(layout, "HOME", tmp_path)
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
