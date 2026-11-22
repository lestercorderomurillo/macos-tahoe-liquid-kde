"""The always-visible Dock keeps floating, as on macOS."""
from steps import layout


def test_always_visible_dock_uses_windows_go_below():
    # Plasma de-floats an always-visible panel touched by a window, which
    # squares the Dock's corners; "windows go below" never de-floats.
    assert layout.plasma_dock_hiding("none") == "windowsgobelow"
    assert layout.plasma_dock_hiding("autohide") == "autohide"
    assert layout.plasma_dock_hiding("dodgewindows") == "dodgewindows"


def _record(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(layout, "DATA_HOME", tmp_path)
    monkeypatch.setattr(layout, "kw_write", lambda *a: calls.append(("write",) + a) or True)
    monkeypatch.setattr(layout, "qdbus_call", lambda *a: calls.append(("dbus",) + a) or True)
    def install(src, dest, label):
        dest.mkdir(parents=True)
        calls.append(("install", dest.name))
        return True
    monkeypatch.setattr(layout, "install_tree", install)
    monkeypatch.setattr(layout, "remove_tree", lambda dest, label: calls.append(("remove", dest.name)))
    return calls


def test_always_visible_installs_the_flush_effect_and_window_fitting(monkeypatch, tmp_path):
    calls = _record(monkeypatch, tmp_path)
    layout._configure_dock_flush("none")
    assert ("install", layout.DOCK_FLUSH_ID) in calls
    assert any(c[0] == "write" and "FitAboveDock" in c and c[-1] == "true" for c in calls)
    assert not any(c[0] == "dbus" and c[-2:] == ("org.kde.kwin.Effects.unloadEffect", layout.DOCK_FLUSH_ID) for c in calls)


def test_auto_hide_keeps_the_slide_but_not_the_flush(monkeypatch, tmp_path):
    calls = _record(monkeypatch, tmp_path)
    layout._configure_dock_flush("autohide")
    assert ("install", layout.DOCK_FLUSH_ID) in calls
    fits = [c for c in calls if c[0] == "write" and "FitAboveDock" in c]
    assert len(fits) == 2 and all(c[-1] == "false" for c in fits)


def test_motion_effect_declares_the_setting_it_reads():
    # Scripted effects only read keys declared in contents/config/main.xml;
    # without it effect.readConfig("FitAboveDock") always returns the default.
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "src/offline/kwin-effects/dock-flush/contents"
    assert 'effect.readConfig("FitAboveDock"' in (root / "code/main.js").read_text()
    assert '<entry name="FitAboveDock" type="Bool">' in (root / "config/main.xml").read_text()
