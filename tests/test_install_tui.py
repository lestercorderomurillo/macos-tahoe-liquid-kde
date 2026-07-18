"""Guards for the interactive install wizard.

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
    """run_wizard is a thin shell over curses.wrapper. Fake the whole
    module, not just the wrapper attribute — install_tui.curses is None
    on distros without python3-curses (openSUSE CI) and the test must
    run there too."""
    sentinel = {"sddm": False, "_save": False}
    fake = types.SimpleNamespace(wrapper=lambda fn: sentinel)
    monkeypatch.setattr(install_tui, "curses", fake)
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
    assert kinds == {"toggle"}


def test_rows_are_one_flat_list():
    """No group headers or spacers — every row is an interactive
    control (toggle / radio / int)."""
    kinds = {kind for kind, _ in _wizard().rows}
    assert kinds == {"toggle", "radio", "int"}


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


def test_result_filters_to_known_keys_and_always_saves_on_install():
    """Install selections always persist to features.json — the save
    checkbox is gone by design; uninstall never writes the file."""
    wiz = _wizard()
    wiz.feat["_bogus"] = 1
    res = wiz.result()
    assert res["_save"] is True
    assert "_bogus" not in res
    assert set(res) - {"_save"} == set(cli.DEFAULT_FEATURES)
    assert _wizard("uninstall").result()["_save"] is False


def test_cursor_stays_in_bounds():
    wiz = _wizard()
    for _ in range(len(wiz.rows) * 2):
        wiz.move(1)
    assert wiz.cursor == len(wiz.rows) - 1
    for _ in range(len(wiz.rows) * 2):
        wiz.move(-1)
    assert wiz.cursor == 0


# ── live progress screen ──────────────────────────────────────────────


def test_strip_ansi_removes_log_escapes():
    line = "  \x1b[0;32m✓\x1b[0m  Fonts installed"
    assert install_tui._strip_ansi(line) == "  ✓  Fonts installed"


def test_read_progress_records_drops_done_marker(monkeypatch, tmp_path):
    pf = tmp_path / "progress"
    pf.write_text("1\tVerification\n2\tDependencies\n__DONE__\t0\n")
    monkeypatch.setattr(install_tui, "PROGRESS_FILE", str(pf))
    assert install_tui._read_progress_records() == [
        "1\tVerification", "2\tDependencies"]


def test_read_progress_records_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(install_tui, "PROGRESS_FILE",
                        str(tmp_path / "nope"))
    assert install_tui._read_progress_records() == []


def test_read_log_tail_preserves_ansi_and_limits(tmp_path):
    """The tail keeps log.py's SGR escapes — _ansi_segments renders them
    as native curses colours instead of stripping to monochrome."""
    log = tmp_path / "log"
    log.write_text("\n".join(
        f"\x1b[0;32m✓\x1b[0m line {i}" for i in range(10)) + "\n")
    tail = install_tui._read_log_tail(str(log), 3)
    assert tail == [f"\x1b[0;32m✓\x1b[0m line {i}" for i in (7, 8, 9)]


def test_read_log_tail_keeps_interior_blank_lines(tmp_path):
    """The classic CLI output separates steps with blank lines — the
    live log must show the same spacing, trimming only trailing blanks."""
    log = tmp_path / "log"
    log.write_text("Step 1: Fonts\n\n  ✓  installed\n\n")
    assert install_tui._read_log_tail(str(log), 10) == [
        "Step 1: Fonts", "", "  ✓  installed"]


@pytest.mark.skipif(install_tui.curses is None,
                    reason="python3-curses not installed (openSUSE split)")
def test_ansi_segments_split_and_bold(monkeypatch):
    """Colour pairs need a live screen, but the segment split and the
    bold/dim/reset state machine are pure logic."""
    monkeypatch.setattr(install_tui, "_HAVE_COLOR", False)
    segs = install_tui._ansi_segments("\x1b[1mStep 1\x1b[0m: done")
    assert segs == [("Step 1", install_tui.curses.A_BOLD), (": done", 0)]


def test_ansi_segments_plain_line_passthrough(monkeypatch):
    monkeypatch.setattr(install_tui, "_HAVE_COLOR", False)
    assert install_tui._ansi_segments("plain text") == [("plain text", 0)]


# ── the three-phase rail ──────────────────────────────────────────────


def _recs(*titles):
    return [f"{i}\t{t}" for i, t in enumerate(titles, 1)]


def test_phase_index_install_progression():
    assert install_tui._phase_index("install", []) == 0
    assert install_tui._phase_index(
        "install", _recs("Preflight", "Verification", "Dependencies")) == 0
    assert install_tui._phase_index(
        "install", _recs("Preflight", "Building Compiled Components")) == 1
    assert install_tui._phase_index(
        "install", _recs("Building Compiled Components",
                         "Installing fonts")) == 2


def test_phase_index_never_regresses_on_late_verification():
    """The config re-check near the end is also titled 'Verification' —
    the rail must stay on INSTALLING, not bounce back to phase 0."""
    recs = _recs("Preflight", "Building Compiled Components",
                 "Installing fonts", "Applying Changes", "Verification",
                 "Restarting Plasma")
    assert install_tui._phase_index("install", recs) == 2


def test_phase_index_uninstall_progression():
    assert install_tui._phase_index(
        "uninstall", _recs("Preflight", "Verification")) == 0
    assert install_tui._phase_index(
        "uninstall", _recs("Removing Theme Switcher",
                           "Applying Changes")) == 1
    assert install_tui._phase_index(
        "uninstall", _recs("Applying Changes", "Removing fonts")) == 2


def test_run_progress_without_curses_runs_body_once(monkeypatch):
    """No curses → the body runs directly, exactly once, undecorated."""
    monkeypatch.setattr(install_tui, "curses", None)
    calls = []

    def body():
        calls.append(1)
        return 0

    assert install_tui.run_progress(body, 10) == 0
    assert calls == [1]


def test_run_wizard_without_curses_raises(monkeypatch):
    """cli._tui_wizard catches this and falls back to classic confirm."""
    monkeypatch.setattr(install_tui, "curses", None)
    with pytest.raises(RuntimeError):
        install_tui.run_wizard(dict(cli.DEFAULT_FEATURES))


# ── step estimates for the progress bar ───────────────────────────────


def test_install_estimate_shrinks_with_features_disabled():
    full = cli._estimate_install_steps(dict(cli.DEFAULT_FEATURES))
    trimmed = dict(cli.DEFAULT_FEATURES)
    trimmed["gtk"] = False
    trimmed["icons"] = False
    assert cli._estimate_install_steps(trimmed) == full - 2


def test_install_estimate_counts_skipped_activation():
    staged = dict(cli.DEFAULT_FEATURES)
    staged["apply_theme"] = False
    full = cli._estimate_install_steps(dict(cli.DEFAULT_FEATURES))
    # -3 apply/verify/restart, -1 layout step, +1 Skipping Activation
    assert cli._estimate_install_steps(staged) < full


def test_uninstall_estimate_positive_and_tracks_features():
    full = cli._estimate_uninstall_steps(dict(cli.DEFAULT_FEATURES))
    assert full > 5
    trimmed = dict(cli.DEFAULT_FEATURES)
    trimmed["gtk"] = False
    assert cli._estimate_uninstall_steps(trimmed) == full - 1


def test_run_body_with_progress_falls_back_without_module(monkeypatch):
    monkeypatch.setitem(sys.modules, "install_tui", None)
    calls = []

    def body(feat):
        calls.append(feat)
        return 0

    assert cli._run_body_with_progress(body, {"x": 1}, "install", 5) == 0
    assert calls == [{"x": 1}]
