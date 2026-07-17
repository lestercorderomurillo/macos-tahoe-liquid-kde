"""Guards for the interactive install wizard (issue #44).

Two surfaces: the gate in ``cli.py`` (the wizard must NEVER run for the
GUI, CI, the VM harness, flag invocations, or the legacy-* entries) and
the curses-free ``Wizard`` model in ``install_tui.py``. The actual
screen loop is exercised by the maintainer in a real terminal; here we
only pin that ``run_wizard`` delegates through ``curses.wrapper`` so a
patched wrapper (or a broken curses) behaves as documented.
"""

from __future__ import annotations

import sys
import types

import pytest

import cli
import install_tui


class _Stream:
    def __init__(self, tty: bool):
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def _fake_tty(monkeypatch, tty: bool) -> None:
    """Patch INSIDE the test body — pytest's capture manager re-installs
    its own sys.stdout/sys.stdin at phase boundaries, so a fixture-time
    setattr would be clobbered before the test runs."""
    monkeypatch.delenv("MTTKDE_NO_CONFIRM", raising=False)
    monkeypatch.setattr(sys, "stdin", _Stream(tty))
    monkeypatch.setattr(sys, "stdout", _Stream(tty))


# ── the gate ──────────────────────────────────────────────────────────


def test_gate_active_on_tty(monkeypatch):
    _fake_tty(monkeypatch, True)
    assert cli._tui_active([], tui=True)


def test_gate_inactive_headless(monkeypatch):
    """The GUI installer and the VM harness both export
    MTTKDE_NO_CONFIRM=1 — the wizard must never appear there."""
    _fake_tty(monkeypatch, True)
    monkeypatch.setenv("MTTKDE_NO_CONFIRM", "1")
    assert not cli._tui_active([], tui=True)


def test_gate_inactive_without_tty(monkeypatch):
    _fake_tty(monkeypatch, False)
    assert not cli._tui_active([], tui=True)


def test_gate_inactive_with_flags(monkeypatch):
    """Any CLI flag means the user already made their picks — scripted
    ``./install --no-gtk`` runs must behave exactly as before."""
    _fake_tty(monkeypatch, True)
    assert not cli._tui_active(["--no-gtk"], tui=True)
    assert not cli._tui_active(["--preflight"], tui=True)


def test_gate_inactive_for_legacy_entries(monkeypatch):
    """legacy-install / legacy-uninstall call run_install with tui=False
    (the default) and must never see the wizard."""
    _fake_tty(monkeypatch, True)
    assert not cli._tui_active([], tui=False)


# ── cli-side wizard runner ────────────────────────────────────────────


def test_tui_wizard_falls_back_when_curses_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "install_tui", None)
    assert cli._tui_wizard({}, "install") is cli._TUI_UNAVAILABLE


def test_tui_wizard_falls_back_when_wizard_raises(monkeypatch):
    fake = types.SimpleNamespace(
        run_wizard=lambda feat, mode: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setitem(sys.modules, "install_tui", fake)
    assert cli._tui_wizard({}, "install") is cli._TUI_UNAVAILABLE


def test_tui_wizard_propagates_cancel_and_result(monkeypatch):
    fake = types.SimpleNamespace(run_wizard=lambda feat, mode: None)
    monkeypatch.setitem(sys.modules, "install_tui", fake)
    assert cli._tui_wizard({}, "install") is None

    sentinel = {"gtk": False, "_save": True}
    fake = types.SimpleNamespace(run_wizard=lambda feat, mode: sentinel)
    monkeypatch.setitem(sys.modules, "install_tui", fake)
    assert cli._tui_wizard({}, "install") is sentinel


def test_run_wizard_returns_wrapper_result(monkeypatch):
    """run_wizard is a thin shell over curses.wrapper — patching the
    wrapper simulates a full screen session without a terminal."""
    sentinel = {"sddm": False, "_save": False}
    monkeypatch.setattr(install_tui.curses, "wrapper", lambda fn: sentinel)
    assert install_tui.run_wizard(dict(cli.DEFAULT_FEATURES)) is sentinel


# ── the Wizard model (curses-free) ────────────────────────────────────


def _wizard(mode: str = "install") -> install_tui.Wizard:
    return install_tui.Wizard(dict(cli.DEFAULT_FEATURES), mode)


def _goto(wiz: install_tui.Wizard, row: tuple[str, str]) -> None:
    wiz.cursor = wiz.rows.index(row)


def test_install_rows_cover_every_feature():
    """A feature missing from GROUPS would silently become
    untoggleable in the wizard — pin full coverage of ALL_FEATURES."""
    toggles = {key for kind, key in _wizard().rows if kind == "toggle"}
    assert toggles == set(cli.ALL_FEATURES)


def test_uninstall_mode_has_no_settings_rows():
    kinds = {kind for kind, _ in _wizard("uninstall").rows}
    assert kinds == {"header", "toggle"}


def test_toggle_flips_value():
    wiz = _wizard()
    _goto(wiz, ("toggle", "gtk"))
    wiz.activate()
    assert wiz.feat["gtk"] is False
    wiz.activate()
    assert wiz.feat["gtk"] is True


def test_radio_cycles_theme_mode():
    wiz = _wizard()
    _goto(wiz, ("radio", "theme_mode"))
    wiz.adjust(1)
    assert wiz.feat["theme_mode"] == "light"
    wiz.adjust(1)
    assert wiz.feat["theme_mode"] == "dark"
    wiz.adjust(1)
    assert wiz.feat["theme_mode"] == "auto"


def test_int_adjust_clamps_to_bounds():
    wiz = _wizard()
    _goto(wiz, ("int", "oled_interval"))
    for _ in range(100):
        wiz.adjust(1)
    assert wiz.feat["oled_interval"] == 59
    for _ in range(100):
        wiz.adjust(-1)
    assert wiz.feat["oled_interval"] == 1


def test_reset_restores_defaults():
    wiz = _wizard()
    wiz.set_all(False)
    wiz.reset()
    assert wiz.feat["gtk"] is True
    assert wiz.feat["oled_care"] is False  # opt-in stays opt-in


def test_set_all_none_preserves_apply_theme():
    """'n' deselects components, not the activation switch — a user
    unchecking everything shouldn't also stage a --no-apply-theme."""
    wiz = _wizard()
    wiz.set_all(False)
    assert wiz.feat["apply_theme"] is True
    assert wiz.feat["gtk"] is False


def test_result_filters_to_known_keys_and_carries_save():
    wiz = _wizard()
    wiz.feat["_bogus"] = 1
    wiz.save = True
    res = wiz.result()
    assert res["_save"] is True
    assert "_bogus" not in res
    assert set(res) - {"_save"} == set(cli.DEFAULT_FEATURES)


def test_cursor_moves_skip_headers():
    wiz = _wizard()
    assert wiz.rows[wiz.cursor][0] == "toggle"
    for _ in range(len(wiz.rows) * 2):
        wiz.move(1)
    assert wiz.rows[wiz.cursor][0] != "header"
