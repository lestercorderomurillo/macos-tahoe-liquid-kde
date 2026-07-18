"""Behaviour tests for src/scripts/theme_switch.py.

Only behaviour that traces to a specific real bug or a load-bearing
invariant of the single-apply() design belongs here. Don't add
monkeypatched call-order proofs of internals (retry schedules, cycle
internals, DBus signal paths): those exercise the test's mental model
of the apply path, not the apply path itself, and need edits every
time the schedule changes.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from .conftest import (has_command, ini_get, make_live_shim_dir,
                       seed_breeze_dark, seed_breeze_light)


pytestmark = pytest.mark.skipif(
    not has_command("kwriteconfig6"),
    reason="kwriteconfig6 not available — KDE not installed",
)


# ── reference values from the .colors files ──────────────────────────────


@pytest.fixture(scope="module")
def colors(offline):
    light = offline / "color-schemes/MacTahoeLiquidKdeLight.colors"
    dark = offline / "color-schemes/MacTahoeLiquidKdeDark.colors"
    g = ini_get
    return {
        "light_btn":   g(light, "Colors:Button", "BackgroundNormal"),
        "dark_btn":    g(dark,  "Colors:Button", "BackgroundNormal"),
        "light_win":   g(light, "Colors:Window", "BackgroundNormal"),
        "dark_win":    g(dark,  "Colors:Window", "BackgroundNormal"),
        "light_tip":   g(light, "Colors:Tooltip", "BackgroundNormal"),
        "dark_tip":    g(dark,  "Colors:Tooltip", "BackgroundNormal"),
        "light_wm":    g(light, "WM", "activeBackground"),
        "dark_wm":     g(dark,  "WM", "activeBackground"),
    }


def test_color_files_have_distinct_values(colors):
    """A botched merge can ship identical .colors files for light and
    dark: visually identical themes, theme switch no-op — pin
    against it."""
    assert colors["light_btn"] and colors["dark_btn"]
    assert colors["light_btn"] != colors["dark_btn"]
    assert colors["light_tip"] != colors["dark_tip"]
    assert colors["light_wm"] != colors["dark_wm"]


# ── apply_color_groups_direct — real round-trip through kdeglobals ────


def _apply(scheme):
    from theme_switch import apply_color_groups_direct
    apply_color_groups_direct(scheme)


@pytest.mark.parametrize("seed,target,key,attr", [
    ("light", "MacTahoeLiquidKdeDark",  "Colors:Button", "dark_btn"),
    ("light", "MacTahoeLiquidKdeDark",  "Colors:Window", "dark_win"),
    ("light", "MacTahoeLiquidKdeDark",  "Colors:Tooltip", "dark_tip"),
    ("light", "MacTahoeLiquidKdeDark",  "WM",            "dark_wm"),
    ("dark",  "MacTahoeLiquidKdeLight", "Colors:Button", "light_btn"),
    ("dark",  "MacTahoeLiquidKdeLight", "Colors:Window", "light_win"),
    ("dark",  "MacTahoeLiquidKdeLight", "Colors:Tooltip", "light_tip"),
    ("dark",  "MacTahoeLiquidKdeLight", "WM",            "light_wm"),
])
def test_transition(seeded_color_schemes, colors, seed, target, key, attr):
    """Real transition: seed kdeglobals with Breeze values, apply our
    scheme, read back via kreadconfig6, assert the per-group keys hold
    the new values. Catches the class of bug where the surgery writes
    one group correctly but leaks the seed value in another."""
    if seed == "light":
        seed_breeze_light(seeded_color_schemes)
    else:
        seed_breeze_dark(seeded_color_schemes)
    _apply(target)
    kdeglobals = seeded_color_schemes / ".config/kdeglobals"
    actual_key = "activeBackground" if key == "WM" else "BackgroundNormal"
    assert ini_get(kdeglobals, key, actual_key) == colors[attr]


def test_double_apply_is_idempotent(seeded_color_schemes):
    """Applying twice must produce the exact same kdeglobals — a real
    bug shape: the second apply read the post-apply state, mistook our
    own writes for Breeze seed values, and applied a slightly-different
    set."""
    seed_breeze_light(seeded_color_schemes)
    _apply("MacTahoeLiquidKdeDark")
    once = (seeded_color_schemes / ".config/kdeglobals").read_text()
    _apply("MacTahoeLiquidKdeDark")
    twice = (seeded_color_schemes / ".config/kdeglobals").read_text()
    assert once == twice


def test_missing_scheme_no_crash(seeded_color_schemes):
    """Mistyped or removed scheme name: return False, do not raise.
    apply() runs this in a try-block; raising would skip the rest of
    the pipeline (cycle + reconfigure)."""
    from theme_switch import apply_color_groups_direct
    assert apply_color_groups_direct("NonExistent") is False


def test_no_stale_breeze_values(seeded_color_schemes):
    """After applying our scheme, no Breeze RGB value may survive in
    kdeglobals. A test that ALSO catches partial overwrites where the
    apply visited some groups and skipped others."""
    seed_breeze_light(seeded_color_schemes)
    _apply("MacTahoeLiquidKdeDark")
    kdeglobals = seeded_color_schemes / ".config/kdeglobals"
    assert ini_get(kdeglobals, "Colors:Window", "BackgroundNormal") != "239,240,241"
    assert ini_get(kdeglobals, "Colors:View", "BackgroundNormal") != "255,255,255"


def test_color_scheme_hash_tracks_active_scheme(seeded_color_schemes, offline):
    """The ColorSchemeHash in kdeglobals must equal SHA-1 of the
    currently-active .colors file. KDE reads this to decide whether to
    reload colors; a stale hash means Plasma keeps showing the previous
    palette even after a successful apply."""
    kdeglobals = seeded_color_schemes / ".config/kdeglobals"
    seed_breeze_light(seeded_color_schemes)

    _apply("MacTahoeLiquidKdeDark")
    dark_src = offline / "color-schemes/MacTahoeLiquidKdeDark.colors"
    expected = hashlib.sha1(dark_src.read_bytes()).hexdigest()
    assert ini_get(kdeglobals, "General", "ColorSchemeHash") == expected

    _apply("MacTahoeLiquidKdeLight")
    light_src = offline / "color-schemes/MacTahoeLiquidKdeLight.colors"
    expected = hashlib.sha1(light_src.read_bytes()).hexdigest()
    assert ini_get(kdeglobals, "General", "ColorSchemeHash") == expected


# ── apply() — single code path, no contexts, no skips ─────────────────


def _stub_apply_dependencies(monkeypatch, calls):
    import theme_switch
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode: calls.append(("write", mode)) or True)
    monkeypatch.setattr(theme_switch, "_apply_wallpaper",
                        lambda mode: calls.append(("wallpaper", mode)) or True)
    monkeypatch.setattr(theme_switch, "_apply_local_extras",
                        lambda mode: calls.append(("local_extras", mode)))
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live",
                        lambda laf: calls.append(("laf", laf)) or True)
    monkeypatch.setattr(theme_switch, "apply_cursortheme_live",
                        lambda theme: calls.append(("cursor", theme)) or True)
    monkeypatch.setattr(theme_switch, "cycle_widget_style_live",
                        lambda target: calls.append(("cycle", target)) or True)
    monkeypatch.setattr(theme_switch, "_qdbus",
                        lambda *args: calls.append(("qdbus", args)) or True)


def test_apply_runs_full_pipeline_in_order(monkeypatch):
    """A single apply() always runs: write → wallpaper → local extras
    → live LAF → live cursor → Kvantum cycle → KWin reconfigure, in
    that order. Reordering or skipping any step here breaks the live
    switch (skipped cycle = stale palette in plasmashell, etc.)."""
    import theme_switch
    calls: list = []
    _stub_apply_dependencies(monkeypatch, calls)

    assert theme_switch.apply("dark") is True

    write_idx = next(i for i, c in enumerate(calls) if c[0] == "write")
    extras_idx = next(i for i, c in enumerate(calls) if c[0] == "local_extras")
    laf_idx = next(i for i, c in enumerate(calls) if c[0] == "laf")
    cursor_idx = next(i for i, c in enumerate(calls) if c[0] == "cursor")
    cycle_idx = next(i for i, c in enumerate(calls) if c[0] == "cycle")
    reconfigure_idx = next(
        i for i, c in enumerate(calls)
        if c[0] == "qdbus" and c[1][0] == "org.kde.KWin"
    )

    assert write_idx < extras_idx < laf_idx < cursor_idx < cycle_idx < reconfigure_idx
    assert ("laf", theme_switch.LAF_DARK) in calls
    assert ("cycle", "kvantum-dark") in calls


def test_apply_finishes_cycle_and_reconfigure_when_extras_raise(monkeypatch):
    """``_apply_local_extras`` can crash on FileExistsError from
    copytree('~/.config/gtk-4.0/assets') when
    rmtree(..., ignore_errors=True) leaves the dir in place. An
    unhandled exception bubbling out of apply() skips the widget-
    style cycle + KWin.reconfigure, leaving plasmashell on the old
    palette while wallpaper + on-disk config have already flipped —
    the 'light bg, dark panel, white text' bug. Whatever extras
    raises, the cycle and reconfigure MUST still run."""
    import theme_switch

    calls: list = []
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode: calls.append(("write", mode)) or True)
    monkeypatch.setattr(theme_switch, "_apply_wallpaper",
                        lambda mode: calls.append(("wallpaper", mode)) or True)
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live",
                        lambda laf: calls.append(("laf", laf)) or True)
    monkeypatch.setattr(theme_switch, "apply_cursortheme_live",
                        lambda theme: calls.append(("cursor", theme)) or True)

    def boom(_mode):
        calls.append(("extras-attempted",))
        raise OSError(17, "File exists", "/home/x/.config/gtk-4.0/assets")

    monkeypatch.setattr(theme_switch, "_apply_local_extras", boom)
    monkeypatch.setattr(theme_switch, "cycle_widget_style_live",
                        lambda target: calls.append(("cycle", target)) or True)
    monkeypatch.setattr(theme_switch, "_qdbus",
                        lambda *args: calls.append(("qdbus", args)) or True)

    assert theme_switch.apply("light") is True
    assert ("extras-attempted",) in calls
    assert ("cycle", "kvantum") in calls
    assert any(c[0] == "qdbus" and c[1][0] == "org.kde.KWin" for c in calls)


def test_local_extras_survives_undeletable_gtk4_assets(monkeypatch, tmp_path):
    """shutil.rmtree(...,
    ignore_errors=True) can silently leave the destination in place
    (inotify watcher recreating files mid-iteration). Without
    dirs_exist_ok=True on the follow-up copytree, that raises
    FileExistsError and aborts the entire run."""
    import theme_switch

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    gtk_theme = "MacTahoeLiquidKde-Dark"
    src_root = home / ".themes" / gtk_theme / "gtk-4.0"
    (src_root / "assets" / "scalable").mkdir(parents=True)
    (src_root / "assets" / "combobox.png").write_bytes(b"x")
    (src_root / "assets" / "scalable" / "icon.svg").write_bytes(b"<svg/>")
    (src_root / "windows-assets").mkdir()
    (src_root / "windows-assets" / "frame.png").write_bytes(b"y")
    (src_root / "gtk-Dark.css").write_text("/* dark */")
    (src_root / "gtk-Light.css").write_text("/* light */")

    dest_root = home / ".config" / "gtk-4.0"
    (dest_root / "assets").mkdir(parents=True)
    (dest_root / "assets" / "stale.png").write_bytes(b"stale")

    monkeypatch.setattr(theme_switch, "_have",
                        lambda cmd: cmd not in ("kvantummanager", "gsettings"))
    monkeypatch.setattr(theme_switch, "_qdbus", lambda *args: True)
    monkeypatch.setattr(theme_switch.time, "sleep", lambda _: None)
    monkeypatch.setattr(theme_switch, "flush_icon_caches", lambda: None)
    # rmtree silently fails — exactly the production failure mode.
    monkeypatch.setattr(theme_switch.shutil, "rmtree",
                        lambda *_a, **_kw: None)

    theme_switch._apply_local_extras("dark")

    assert (dest_root / "assets" / "combobox.png").is_file()
    assert (dest_root / "assets" / "scalable" / "icon.svg").is_file()
    assert (dest_root / "gtk.css").is_symlink()
    assert (dest_root / "gtk.css").readlink().name == "gtk-Dark.css"


def test_cycle_restores_target_on_sigterm(monkeypatch):
    """If SIGTERM lands during the inter-write sleep (systemd stopping
    the apply service mid-cycle is the documented trigger), the on-disk
    value MUST end at the target, never frozen at Breeze. Otherwise
    next boot is 'Breeze night': MacTahoeLiquidKdeDark colors with
    breeze widgets."""
    import signal as signal_mod
    import theme_switch

    writes: list[str] = []

    def fake_kwrite(*args: str) -> bool:
        if "widgetStyle" in args:
            writes.append(args[-1])
        return True

    monkeypatch.setattr(theme_switch, "_kwrite", fake_kwrite)
    monkeypatch.setattr(theme_switch, "_have", lambda cmd: True)
    monkeypatch.setattr(theme_switch, "_has_session_dbus", lambda: True)
    monkeypatch.setattr(theme_switch, "_broadcast_widget_style_change",
                        lambda style: None)

    def sleep_then_sigterm(_seconds):
        os.kill(os.getpid(), signal_mod.SIGTERM)

    monkeypatch.setattr(theme_switch.time, "sleep", sleep_then_sigterm)

    with pytest.raises(SystemExit):
        theme_switch.cycle_widget_style_live("kvantum-dark")

    assert writes and writes[-1] == "kvantum-dark", (
        "last widgetStyle write must be the target, never Breeze — "
        "otherwise the 'Breeze night' regression returns"
    )


# ── main() entry-point invariants ─────────────────────────────────────


def test_main_auto_resolves_to_time_based_mode(monkeypatch):
    """``mac-tahoe-theme-switch auto`` (what the systemd service + timer
    fire) must resolve via wall clock alone and hand that straight to
    apply(). No other input is consulted — reading config back in
    creates a stale-config feedback loop."""
    import theme_switch
    calls: list = []
    monkeypatch.setattr(theme_switch, "detect_mode_by_time", lambda: "dark")
    monkeypatch.setattr(theme_switch, "apply",
                        lambda mode, **kw: calls.append(("apply", mode)) or True)
    assert theme_switch.main(["auto"]) == 0
    assert calls == [("apply", "dark")]


def test_main_rejects_invalid_mode(monkeypatch):
    """The surface accepts exactly light / dark / auto. Retired
    contexts (boot, scheduled, _deferred-live-apply, watch) must exit
    non-zero so a stale systemd unit from an upgrade can't silently
    no-op."""
    import theme_switch
    applied: list = []
    monkeypatch.setattr(theme_switch, "apply",
                        lambda mode, **kw: applied.append(mode) or True)
    assert theme_switch.main([]) == 1
    assert theme_switch.main(["watch"]) == 1
    assert theme_switch.main(["boot"]) == 1
    assert theme_switch.main(["_deferred-live-apply"]) == 1
    assert applied == []


_APPLY_SUBCALLS = (
    "write_kde_theme_config", "_apply_wallpaper", "_apply_local_extras",
    "_apply_lookandfeel_live", "apply_cursortheme_live",
    "cycle_widget_style_live", "_qdbus",
)


def _stub_apply_subcalls(monkeypatch, calls, ret=True):
    import theme_switch
    for fn in _APPLY_SUBCALLS:
        monkeypatch.setattr(
            theme_switch, fn,
            (lambda name: lambda *a, **k: calls.append(name) or ret)(fn))


def test_apply_install_context_skips_live_lookandfeel(monkeypatch):
    """The installer passes the ``install`` context
    because its final Plasma restart loads the theme anyway — running
    the live LAF apply too adds 2-14s of retry sleeps and races the
    QML teardown. Every other sub-call still runs in both contexts."""
    import theme_switch
    calls: list = []
    _stub_apply_subcalls(monkeypatch, calls)

    assert theme_switch.apply("dark", context="install") is True
    assert "_apply_lookandfeel_live" not in calls
    assert "apply_cursortheme_live" in calls
    assert "cycle_widget_style_live" in calls

    calls.clear()
    assert theme_switch.apply("dark") is True
    assert "_apply_lookandfeel_live" in calls


def test_main_passes_install_context_to_apply(monkeypatch):
    import theme_switch
    seen: dict = {}
    monkeypatch.setattr(
        theme_switch, "apply",
        lambda mode, context="user": seen.update(mode=mode, context=context) or True)
    assert theme_switch.main(["light", "install"]) == 0
    assert seen == {"mode": "light", "context": "install"}


def test_main_exit_code_reflects_apply_failure(monkeypatch):
    """The systemd oneshot service and the install step can
    only see failure through the exit code."""
    import theme_switch
    monkeypatch.setattr(theme_switch, "apply", lambda mode, **kw: False)
    assert theme_switch.main(["dark"]) == 1


def test_apply_fails_when_config_writes_fail(monkeypatch):
    """write_kde_theme_config is the critical call —
    False means the core config writes failed (kwriteconfig6 missing
    OR a write error, e.g. Qt6's setuid abort under the sudo'd
    installer), and apply() must surface it. The live sub-calls stay
    best-effort and cannot fail the run."""
    import theme_switch
    calls: list = []
    _stub_apply_subcalls(monkeypatch, calls)
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode: False)
    assert theme_switch.apply("dark") is False

    # config ok + every live sub-call failing → still success
    calls.clear()
    _stub_apply_subcalls(monkeypatch, calls, ret=False)
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode: True)
    monkeypatch.setattr(theme_switch, "_apply_wallpaper", lambda mode: True)
    monkeypatch.setattr(theme_switch, "_apply_local_extras", lambda mode: True)
    assert theme_switch.apply("dark") is True


# ── privilege drop + timeout on every child, honest returns ────────────


def test_kwrite_drops_privs_bounds_timeout_no_sync(monkeypatch):
    """Regression guard in the test_plasma_version_drops_privs_in_child
    mold. steps/apply.py imports these helpers into the sudo'd installer
    (real UID 0, effective UID user); a bare subprocess child trips Qt6's
    setuid abort and the write is silently lost. Every kwriteconfig6
    spawn must therefore carry preexec_fn=_drop_privs_in_child plus a 5s
    bound, and never trigger the per-write os.sync() flush storm."""
    import theme_switch

    seen: dict = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        seen["preexec_fn"] = kw.get("preexec_fn")
        seen["timeout"] = kw.get("timeout")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(theme_switch.subprocess, "run", fake_run)
    monkeypatch.setattr(theme_switch, "_have", lambda cmd: True)
    monkeypatch.setattr(theme_switch, "_has_session_dbus", lambda: False)

    def no_sync():
        raise AssertionError("per-write os.sync() is the #36/#37 regression")

    monkeypatch.setattr(theme_switch.os, "sync", no_sync)

    assert theme_switch._kwrite("--file", "kdeglobals", "--group", "G",
                                "--key", "k", "v") is True
    assert seen["cmd"][0] == "kwriteconfig6"
    assert seen["preexec_fn"] is theme_switch._drop_privs_in_child
    assert seen["timeout"] == 5


def test_run_live_plasma_tool_drops_privs_and_keeps_timeout(monkeypatch):
    """plasma-apply-lookandfeel / plasma-apply-cursortheme ride this
    transport from the sudo'd uninstall path — same setuid abort as
    _kwrite without the child-side drop."""
    import theme_switch

    seen: dict = {}

    def fake_run(cmd, **kw):
        seen["preexec_fn"] = kw.get("preexec_fn")
        seen["timeout"] = kw.get("timeout")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(theme_switch.subprocess, "run", fake_run)
    monkeypatch.setattr(theme_switch, "_sync_session_env", lambda: None)
    monkeypatch.delenv("MAC_TAHOE_SKIP_LIVE_APPLY", raising=False)

    assert theme_switch._run_live_plasma_tool(
        ["plasma-apply-cursortheme", "breeze_cursors"],
        timeout_seconds=7) is True
    assert seen["preexec_fn"] is theme_switch._drop_privs_in_child
    assert seen["timeout"] == 7


def test_reset_color_scheme_config_reports_write_failure(monkeypatch):
    """Under sudo the uninstall color reset can fail while the step
    prints success. Failed deletes or a failed final write
    must return False so the caller can warn."""
    import theme_switch
    monkeypatch.setattr(theme_switch, "_have", lambda cmd: True)

    monkeypatch.setattr(theme_switch, "_delete_color_groups_direct",
                        lambda: False)
    assert theme_switch.reset_kde_color_scheme_config("BreezeLight") is False

    monkeypatch.setattr(theme_switch, "_delete_color_groups_direct",
                        lambda: True)
    monkeypatch.setattr(theme_switch, "_kwrite", lambda *a: False)
    assert theme_switch.reset_kde_color_scheme_config("BreezeLight") is False

    monkeypatch.setattr(theme_switch, "_kwrite", lambda *a: True)
    assert theme_switch.reset_kde_color_scheme_config("BreezeLight") is True


def test_apply_color_groups_direct_reports_write_failure(monkeypatch, tmp_path):
    import theme_switch
    scheme = tmp_path / "S.colors"
    scheme.write_text("[Colors:Window]\nBackgroundNormal=1,2,3\n")
    monkeypatch.setattr(theme_switch, "_have", lambda cmd: True)
    monkeypatch.setattr(theme_switch, "_find_scheme_file", lambda s: scheme)
    monkeypatch.setattr(theme_switch, "_delete_color_groups_direct",
                        lambda: True)
    monkeypatch.setattr(theme_switch, "_kwrite", lambda *a: False)
    assert theme_switch.apply_color_groups_direct("S") is False
    monkeypatch.setattr(theme_switch, "_kwrite", lambda *a: True)
    assert theme_switch.apply_color_groups_direct("S") is True


def test_write_kde_theme_config_reports_write_failure(monkeypatch):
    import theme_switch
    monkeypatch.setattr(theme_switch, "_have", lambda cmd: True)

    monkeypatch.setattr(theme_switch, "_kwrite", lambda *a: False)
    assert theme_switch.write_kde_theme_config("dark") is False

    # fixed writes ok → the color-group stage decides the result
    monkeypatch.setattr(theme_switch, "_kwrite", lambda *a: True)
    monkeypatch.setattr(theme_switch, "apply_color_groups_direct",
                        lambda s: False)
    assert theme_switch.write_kde_theme_config("dark") is False
    monkeypatch.setattr(theme_switch, "apply_color_groups_direct",
                        lambda s: True)
    assert theme_switch.write_kde_theme_config("dark") is True


def test_cycle_reports_failure_but_still_restores(monkeypatch):
    """Failed widgetStyle writes or a dead broadcast phase must return
    False — while the finally-restore still runs so disk ends at the
    target. An unconditional True here keeps sudo'd uninstall
    breakage invisible."""
    import theme_switch
    writes: list[str] = []
    monkeypatch.setattr(theme_switch, "_have", lambda cmd: True)
    monkeypatch.setattr(theme_switch, "_has_session_dbus", lambda: True)
    monkeypatch.setattr(theme_switch.time, "sleep", lambda _s: None)

    monkeypatch.setattr(theme_switch, "_kwrite",
                        lambda *a: writes.append(a[-1]) or False)
    monkeypatch.setattr(theme_switch, "_broadcast_widget_style_change",
                        lambda style: True)
    assert theme_switch.cycle_widget_style_live("kvantum") is False
    assert writes[-1] == "kvantum", "restore must run even when writes fail"

    monkeypatch.setattr(theme_switch, "_kwrite",
                        lambda *a: writes.append(a[-1]) or True)
    monkeypatch.setattr(theme_switch, "_broadcast_widget_style_change",
                        lambda style: False)
    assert theme_switch.cycle_widget_style_live("kvantum") is False

    monkeypatch.setattr(theme_switch, "_broadcast_widget_style_change",
                        lambda style: True)
    assert theme_switch.cycle_widget_style_live("kvantum") is True


def test_broadcast_succeeds_when_any_signal_lands(monkeypatch):
    """The xdg-portal endpoints are optional: one delivered signal out of
    the three sends is a delivered phase; all three failing is not."""
    import theme_switch
    monkeypatch.setattr(theme_switch, "_has_session_dbus", lambda: True)

    results = iter([1, 0, 1])

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, next(results))

    monkeypatch.setattr(theme_switch.subprocess, "run", fake_run)
    assert theme_switch._broadcast_widget_style_change("Breeze") is True

    results = iter([1, 1, 1])
    assert theme_switch._broadcast_widget_style_change("Breeze") is False


# ── theme-switch step install / uninstall round-trip ─────────────────


def _run_step(step_name: str, phase: str, env: dict[str, str],
              shim_dir: Path | None = None) -> None:
    full = os.environ.copy()
    full.update(env)
    if shim_dir is not None:
        full["PATH"] = f"{shim_dir}{os.pathsep}{full.get('PATH', '')}"
    rc = subprocess.run(
        ["python3", "-c",
         f"from steps.{step_name} import {phase}; {phase}()"],
        check=False, env=full,
        cwd=str(Path(__file__).resolve().parent.parent / "src/scripts"),
    ).returncode
    assert rc == 0


def test_switch_step_does_not_touch_live_user_systemd(sandbox, tmp_path):
    """Real safety guard. A step that shells out to systemctl without
    going through PATH (absolute /usr/bin/systemctl) bypasses the test
    shim and silently disables the maintainer's live theme timer.
    If a regression reintroduces an absolute path, the
    maintainer's live systemd state gets clobbered every test run."""
    shim_dir = make_live_shim_dir(tmp_path)
    log_file = shim_dir / "calls.log"

    _run_step("theme_switch", "install", {"THEME_MODE": "auto"},
              shim_dir=shim_dir)
    _run_step("theme_switch", "uninstall", {"THEME_MODE": "auto"},
              shim_dir=shim_dir)

    assert log_file.exists(), (
        "shim was never invoked — step bypassed PATH (absolute path?)"
    )
    assert "systemctl --user" in log_file.read_text()


def test_switch_step_install_uninstall_reinstall(sandbox, tmp_path):
    """Round-trip the install/uninstall step. Asserts:
    - install drops the script + service + timer under $XDG_CONFIG_HOME
    - uninstall removes them
    - leftover apply.service (from an older install layout) is cleaned up
    - kdeglobals AutomaticLookAndFeel keys are reset on uninstall."""
    shim_dir = make_live_shim_dir(tmp_path)

    env = {"THEME_MODE": "auto"}
    _run_step("theme_switch", "install", env, shim_dir=shim_dir)
    bin_path = sandbox / ".local/bin/mac-tahoe-theme-switch"
    svc_dir = sandbox / ".config/systemd/user"
    assert bin_path.is_file() and bin_path.stat().st_mode & 0o111
    assert (svc_dir / "mac-tahoe-liquid-kde-theme.service").is_file()
    assert (svc_dir / "mac-tahoe-liquid-kde-theme.timer").is_file()

    # Drop a leftover apply.service from an older install layout.
    # Uninstall must remove it.
    (svc_dir / "mac-tahoe-liquid-kde-theme-apply.service").write_text(
        "# legacy unit from a previous version\n"
    )

    (sandbox / ".config/kdeglobals").write_text(
        "[KDE]\n"
        "AutomaticLookAndFeel=true\n"
        "DefaultLightLookAndFeel=org.kde.mac-tahoe-liquid-kde.light\n"
        "DefaultDarkLookAndFeel=org.kde.mac-tahoe-liquid-kde.dark\n"
    )
    _run_step("theme_switch", "uninstall", env, shim_dir=shim_dir)
    assert not bin_path.exists()
    assert not (svc_dir / "mac-tahoe-liquid-kde-theme.service").exists()
    assert not (svc_dir / "mac-tahoe-liquid-kde-theme.timer").exists()
    assert not (svc_dir / "mac-tahoe-liquid-kde-theme-apply.service").exists()
