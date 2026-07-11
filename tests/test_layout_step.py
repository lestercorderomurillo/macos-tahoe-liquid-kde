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


# ── Discover install check (issue #40) ──────────────────────────────────

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
