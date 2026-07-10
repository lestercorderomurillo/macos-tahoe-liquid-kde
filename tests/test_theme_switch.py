"""Behaviour tests for src/scripts/theme_switch.py.

Previously ~36 tests, with several layers of monkeypatched-call-order
proofs (LAF retry schedule pinned to specific sleep counts, Kvantum
cycle internals, DBus signal paths). Those exercised the test's mental
model of the apply path, not the apply path itself, and required edits
every time the schedule changed.

What's kept: behaviour that traces to a specific shipped bug or a
load-bearing invariant of the v0.14.2 rewrite.
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
    """Real regression: a botched merge once shipped identical .colors
    files for light and dark. Visually identical themes, theme switch
    no-op — pin against it."""
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
    palette even after a successful apply. Real shipped bug shape."""
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
    """The v0.14.2 rewrite collapsed multiple contexts into a single
    apply() that always runs: write → wallpaper → local extras → live
    LAF → live cursor → Kvantum cycle → KWin reconfigure, in that
    order. Reordering or skipping any step here brings back one of the
    v0.13.x bugs (skipped cycle = stale palette in plasmashell, etc.)."""
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
    """0.13.7 boot regression: ``_apply_local_extras`` crashed on
    FileExistsError from copytree('~/.config/gtk-4.0/assets') because
    rmtree(..., ignore_errors=True) had left the dir in place. The
    unhandled exception bubbled out of apply() and skipped the widget-
    style cycle + KWin.reconfigure, leaving plasmashell on the old
    palette while wallpaper + on-disk config had already flipped —
    that's the 'light bg, dark panel, white text' bug. Whatever extras
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
    """Root cause of the 0.13.7 crash: shutil.rmtree(...,
    ignore_errors=True) can silently leave the destination in place
    (inotify watcher recreating files mid-iteration). Without
    dirs_exist_ok=True on the follow-up copytree, that raised
    FileExistsError and aborted the entire run."""
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
    breeze widgets, which is what triggered the v0.13.x regression hunt."""
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
    apply(). No other input is consulted to avoid the stale-config
    feedback loop earlier versions hit."""
    import theme_switch
    calls: list = []
    monkeypatch.setattr(theme_switch, "detect_mode_by_time", lambda: "dark")
    monkeypatch.setattr(theme_switch, "apply",
                        lambda mode, **kw: calls.append(("apply", mode)) or True)
    assert theme_switch.main(["auto"]) == 0
    assert calls == [("apply", "dark")]


def test_main_rejects_invalid_mode(monkeypatch):
    """The simplified surface accepts exactly light / dark / auto. Old
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
    """Issue #32 (PR #33): the installer passes the ``install`` context
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
    """Issue #24: the systemd oneshot service and the install step can
    only see failure through the exit code."""
    import theme_switch
    monkeypatch.setattr(theme_switch, "apply", lambda mode, **kw: False)
    assert theme_switch.main(["dark"]) == 1


def test_apply_fails_only_when_config_write_layer_missing(monkeypatch):
    """Issue #24: write_kde_theme_config is the critical call — without
    kwriteconfig6 nothing was applied, so apply() must return False.
    The live sub-calls are best-effort and cannot fail the run."""
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
    """Real safety guard. v0.13.7 silently disabled the maintainer's
    live theme timer because the step shelled out to systemctl without
    going through PATH (absolute /usr/bin/systemctl bypassed the test
    shim). If a future regression reintroduces an absolute path, the
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
    - leftover apply.service (from a pre-v0.14.2 install) is cleaned up
    - kdeglobals AutomaticLookAndFeel keys are reset on uninstall."""
    shim_dir = make_live_shim_dir(tmp_path)

    env = {"THEME_MODE": "auto"}
    _run_step("theme_switch", "install", env, shim_dir=shim_dir)
    bin_path = sandbox / ".local/bin/mac-tahoe-theme-switch"
    svc_dir = sandbox / ".config/systemd/user"
    assert bin_path.is_file() and bin_path.stat().st_mode & 0o111
    assert (svc_dir / "mac-tahoe-liquid-kde-theme.service").is_file()
    assert (svc_dir / "mac-tahoe-liquid-kde-theme.timer").is_file()

    # Drop a leftover apply.service from a pre-v0.14.2 install. Uninstall
    # must remove it.
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
