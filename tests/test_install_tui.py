"""Tests for the interactive curses wizard gate and selection logic.

The wizard's rendering needs a real terminal, so these tests exercise the
gate (``_interactive_wizard_enabled`` / ``_maybe_run_wizard``) and the pure
state machine (``_WizardState`` / ``_handle`` / ``_to_feat``) without ever
touching curses. The graphical installer (``./installer``) is intentionally
not covered here: it is a separate path.
"""

from __future__ import annotations

import sys

import pytest


@pytest.fixture
def cli_module():
    import cli
    return cli


@pytest.fixture
def tui_module():
    import install_tui
    return install_tui


def _gate_env(monkeypatch, *, confirm_unset=True, tty=True):
    monkeypatch.setattr(sys.stdout, "isatty", lambda: tty)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: tty)
    if confirm_unset:
        monkeypatch.delenv("MTTKDE_NO_CONFIRM", raising=False)
    else:
        monkeypatch.setenv("MTTKDE_NO_CONFIRM", "1")


# ── gate ───────────────────────────────────────────────────────────────


def test_gate_enabled_on_tty(cli_module, monkeypatch):
    _gate_env(monkeypatch)
    parsed = cli_module.parse_args([])
    assert cli_module._interactive_wizard_enabled(parsed, []) is True


def test_gate_disabled_headless(cli_module, monkeypatch):
    _gate_env(monkeypatch, confirm_unset=False)
    parsed = cli_module.parse_args([])
    assert cli_module._interactive_wizard_enabled(parsed, []) is False


def test_gate_disabled_with_flags(cli_module, monkeypatch):
    _gate_env(monkeypatch)
    parsed = cli_module.parse_args([])
    assert cli_module._interactive_wizard_enabled(parsed, ["--no-gtk"]) is False


def test_gate_disabled_preflight(cli_module, monkeypatch):
    _gate_env(monkeypatch)
    parsed = cli_module.parse_args(["--preflight"])
    assert cli_module._interactive_wizard_enabled(parsed, []) is False


def test_gate_disabled_check_update(cli_module, monkeypatch):
    _gate_env(monkeypatch)
    parsed = cli_module.parse_args(["--check-update"])
    assert cli_module._interactive_wizard_enabled(parsed, []) is False


def test_gate_disabled_without_tty(cli_module, monkeypatch):
    _gate_env(monkeypatch, tty=False)
    parsed = cli_module.parse_args([])
    assert cli_module._interactive_wizard_enabled(parsed, []) is False


# ── _maybe_run_wizard ───────────────────────────────────────────────────


def test_maybe_run_wizard_runs_when_enabled(cli_module, tui_module, monkeypatch):
    _gate_env(monkeypatch)
    seen = {}

    def fake(feat):
        seen["feat"] = feat
        return feat

    monkeypatch.setattr(tui_module, "run_wizard", fake)
    parsed = cli_module.parse_args([])
    feat = cli_module.load_features()
    result, interactive = cli_module._maybe_run_wizard(feat, parsed, [])
    assert interactive is True
    assert result is feat
    assert "feat" in seen


def test_maybe_run_wizard_fallback_on_error(cli_module, tui_module, monkeypatch):
    _gate_env(monkeypatch)

    def boom(feat):
        raise ImportError("no curses")

    monkeypatch.setattr(tui_module, "run_wizard", boom)
    parsed = cli_module.parse_args([])
    feat = cli_module.load_features()
    result, interactive = cli_module._maybe_run_wizard(feat, parsed, [])
    assert interactive is False
    assert result is feat


def test_maybe_run_wizard_skips_when_disabled(cli_module, tui_module, monkeypatch):
    _gate_env(monkeypatch, confirm_unset=False)
    called = {"n": 0}

    def fake(feat):
        called["n"] += 1
        return feat

    monkeypatch.setattr(tui_module, "run_wizard", fake)
    parsed = cli_module.parse_args([])
    feat = cli_module.load_features()
    result, interactive = cli_module._maybe_run_wizard(feat, parsed, [])
    assert interactive is False
    assert called["n"] == 0
    assert result is feat


# ── wizard state machine (no curses) ───────────────────────────────────


def _state(cli_module, tui_module):
    return tui_module._WizardState(cli_module.load_features())


def test_toggle_component_off(tui_module, cli_module):
    state = _state(cli_module, tui_module)
    idx = next(i for i, (kind, _, key) in enumerate(state.rows)
               if kind == "item" and key == "sddm")
    state.sel = idx
    tui_module._handle(state, ord(" "))
    assert state.on["sddm"] is False
    assert tui_module._to_feat(state)["sddm"] is False


def test_toggle_group(tui_module, cli_module):
    state = _state(cli_module, tui_module)
    # find the "Theme" group header row
    idx = next(i for i, (kind, gname, _) in enumerate(state.rows)
               if kind == "group" and gname == "Theme")
    state.sel = idx
    # default: everything on -> toggling the group turns it all off
    tui_module._handle(state, ord(" "))
    for key in ("wallpapers", "fonts", "layout"):
        assert state.on[key] is False


def test_theme_cycle(tui_module, cli_module):
    state = _state(cli_module, tui_module)
    state.screen = "theme"
    assert state.theme_mode == "auto"
    tui_module._handle(state, tui_module.KEY_RIGHT)
    assert state.theme_mode == "light"
    tui_module._handle(state, tui_module.KEY_RIGHT)
    assert state.theme_mode == "dark"
    tui_module._handle(state, tui_module.KEY_LEFT)
    assert state.theme_mode == "light"


def test_oled_toggle_and_adjust(tui_module, cli_module):
    state = _state(cli_module, tui_module)
    state.screen = "oled"
    tui_module._handle(state, ord(" "))
    assert state.oled is True
    assert state.on["oled_care"] is True
    tui_module._handle(state, ord("="))
    assert state.oled_interval == 6
    tui_module._handle(state, ord("]"))
    assert state.oled_max_shift == 9
    # clamps to bounds
    for _ in range(100):
        tui_module._handle(state, ord("-"))
    assert state.oled_interval == 1


def test_summary_confirm_returns_feat(tui_module, cli_module):
    state = _state(cli_module, tui_module)
    state.screen = "summary"
    state.on["sddm"] = False
    state.theme_mode = "dark"
    rc = tui_module._handle(state, 10)  # Enter
    assert rc == "confirm"
    out = tui_module._to_feat(state)
    assert out["sddm"] is False
    assert out["theme_mode"] == "dark"


def test_summary_save_toggle_does_not_write(tui_module, cli_module):
    state = _state(cli_module, tui_module)
    state.screen = "summary"
    tui_module._handle(state, ord("s"))
    assert state.save is True
    tui_module._handle(state, ord("s"))
    assert state.save is False


def test_all_features_present_in_checklist(tui_module, cli_module):
    state = _state(cli_module, tui_module)
    items = [key for kind, _, key in state.rows if kind == "item"]
    assert sorted(items) == sorted(cli_module.ALL_FEATURES)


def test_string_keys_navigate_like_terminal(tui_module, cli_module):
    # ``curses.get_wch`` returns ``str`` for printable keys; arrow keys arrive
    # as ``curses.KEY_*`` ints. Both must move the selection. (Regression test
    # for the arrow-key navigation bug from issue #44.)
    state = _state(cli_module, tui_module)
    start = state.sel
    tui_module._handle(state, "j")
    assert state.sel == (start + 1) % len(state.rows)
    tui_module._handle(state, "k")
    assert state.sel == start
    # space toggles a focused item when passed as a str
    idx = next(i for i, (kind, _, key) in enumerate(state.rows)
               if kind == "item" and key == "sddm")
    state.sel = idx
    tui_module._handle(state, " ")
    assert state.on["sddm"] is False


def test_read_progress_records_strips_done(tui_module, tmp_path):
    pf = tmp_path / "progress"
    pf.write_text("1\tVerification\n2\tDependencies\n__DONE__\t0\n")
    original = tui_module.PROGRESS_FILE
    tui_module.PROGRESS_FILE = str(pf)
    try:
        recs = tui_module._read_progress_records()
    finally:
        tui_module.PROGRESS_FILE = original
    assert recs == ["1\tVerification", "2\tDependencies"]


def test_estimate_total_steps_tracks_apply(cli_module):
    feat = cli_module.load_features()
    total = cli_module._estimate_total_steps(feat)
    assert total > 10
    off = dict(feat)
    off["apply_theme"] = False
    assert cli_module._estimate_total_steps(off) < total


def test_read_log_tail_returns_last_n(tui_module, tmp_path):
    logf = tmp_path / "install.log"
    logf.write_text("\n".join(f"line {i}" for i in range(10)) + "\n")
    tail = tui_module._read_log_tail(str(logf), 3)
    assert tail == ["line 7", "line 8", "line 9"]
    # missing file is safe
    assert tui_module._read_log_tail(str(tmp_path / "nope.log"), 3) == []


def test_strip_ansi_and_log_attr(tui_module):
    raw = "\x1b[0;32m✓\x1b[0m  zstd"
    assert tui_module._strip_ansi(raw) == "✓  zstd"
    assert tui_module._log_attr("✓  zstd") == tui_module._GREEN_ATTR
    assert tui_module._log_attr("✗  broken") == tui_module._RED_ATTR
    assert tui_module._log_attr("warning: x") == tui_module._RED_ATTR
    assert tui_module._log_attr("Building plasmoids") == 0


def test_theme_enter_skips_oled_when_off(tui_module, cli_module):
    state = _state(cli_module, tui_module)
    state.screen = "theme"
    assert state.oled is False
    tui_module._handle(state, 10)  # Enter
    assert state.screen == "summary"


def test_theme_enter_shows_oled_when_enabled(tui_module, cli_module):
    state = _state(cli_module, tui_module)
    state.screen = "theme"
    state.oled = True
    state.on["oled_care"] = True
    tui_module._handle(state, 10)  # Enter
    assert state.screen == "oled"

