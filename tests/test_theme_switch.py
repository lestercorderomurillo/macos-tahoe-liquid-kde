"""Behaviour tests for src/scripts/theme_switch.py — color group surgery,
mode detection, and the install/uninstall step."""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from .conftest import has_command, ini_get, seed_breeze_dark, seed_breeze_light


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
        "light_hdr_fg":  g(light, "Colors:Header][Inactive", "ForegroundNormal"),
        "dark_hdr_fg":   g(dark,  "Colors:Header][Inactive", "ForegroundNormal"),
        "light_hdr_focus": g(light, "Colors:Header][Inactive", "DecorationFocus"),
        "dark_hdr_focus":  g(dark,  "Colors:Header][Inactive", "DecorationFocus"),
    }


def test_color_files_have_distinct_values(colors):
    assert colors["light_btn"] and colors["dark_btn"]
    assert colors["light_btn"] != colors["dark_btn"]
    assert colors["light_tip"] and colors["dark_tip"]
    assert colors["light_tip"] != colors["dark_tip"]
    assert colors["light_wm"] and colors["dark_wm"]
    assert colors["light_hdr_fg"] and colors["dark_hdr_fg"]


# ── apply_color_groups_direct round-trips ────────────────────────────────
def _apply(scheme):
    from theme_switch import apply_color_groups_direct
    apply_color_groups_direct(scheme)


@pytest.mark.parametrize("seed,target,key,attr", [
    ("light", "MacTahoeLiquidKdeDark",  "Colors:Button", "dark_btn"),
    ("light", "MacTahoeLiquidKdeDark",  "Colors:Window", "dark_win"),
    ("light", "MacTahoeLiquidKdeDark",  "Colors:Tooltip", "dark_tip"),
    ("light", "MacTahoeLiquidKdeDark",  "WM",            "dark_wm"),
    ("light", "MacTahoeLiquidKdeDark",  "Colors:Header][Inactive", "dark_hdr_fg"),
    ("dark",  "MacTahoeLiquidKdeLight", "Colors:Button", "light_btn"),
    ("dark",  "MacTahoeLiquidKdeLight", "Colors:Window", "light_win"),
    ("dark",  "MacTahoeLiquidKdeLight", "Colors:Tooltip", "light_tip"),
    ("dark",  "MacTahoeLiquidKdeLight", "WM",            "light_wm"),
])
def test_transition(seeded_color_schemes, colors, seed, target, key, attr):
    if seed == "light":
        seed_breeze_light(seeded_color_schemes)
    else:
        seed_breeze_dark(seeded_color_schemes)
    _apply(target)
    kdeglobals = seeded_color_schemes / ".config/kdeglobals"
    actual_key = "ForegroundNormal" if "][" in key else (
        "activeBackground" if key == "WM" else "BackgroundNormal"
    )
    assert ini_get(kdeglobals, key, actual_key) == colors[attr]


def test_header_inactive_focus_matches(seeded_color_schemes, colors):
    seed_breeze_light(seeded_color_schemes)
    _apply("MacTahoeLiquidKdeDark")
    actual = ini_get(seeded_color_schemes / ".config/kdeglobals",
                     "Colors:Header][Inactive", "DecorationFocus")
    assert actual == colors["dark_hdr_focus"]


def test_double_apply_is_idempotent(seeded_color_schemes):
    seed_breeze_light(seeded_color_schemes)
    _apply("MacTahoeLiquidKdeDark")
    once = (seeded_color_schemes / ".config/kdeglobals").read_text()
    _apply("MacTahoeLiquidKdeDark")
    twice = (seeded_color_schemes / ".config/kdeglobals").read_text()
    assert once == twice


def test_missing_scheme_no_crash(seeded_color_schemes):
    from theme_switch import apply_color_groups_direct
    # Should return False, not raise.
    assert apply_color_groups_direct("NonExistent") is False


def test_no_stale_breeze_values(seeded_color_schemes):
    seed_breeze_light(seeded_color_schemes)
    _apply("MacTahoeLiquidKdeDark")
    kdeglobals = seeded_color_schemes / ".config/kdeglobals"
    assert ini_get(kdeglobals, "Colors:Window", "BackgroundNormal") != "239,240,241"
    assert ini_get(kdeglobals, "Colors:View", "BackgroundNormal") != "255,255,255"


def test_color_scheme_hash_tracks_active_scheme(seeded_color_schemes, offline):
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


def test_color_scheme_name_matches_palette(seeded_color_schemes, colors):
    seed_breeze_light(seeded_color_schemes)
    kdeglobals = seeded_color_schemes / ".config/kdeglobals"
    subprocess.run(
        ["kwriteconfig6", "--file", str(kdeglobals),
         "--group", "General", "--key", "ColorScheme", "MacTahoeLiquidKdeDark"],
        check=True,
    )
    _apply("MacTahoeLiquidKdeDark")
    assert ini_get(kdeglobals, "General", "ColorScheme") == "MacTahoeLiquidKdeDark"
    assert ini_get(kdeglobals, "Colors:Button", "BackgroundNormal") == colors["dark_btn"]


# ── auto-mode startup sync ───────────────────────────────────────────────
def test_auto_sync_reapplies_when_mode_changed(monkeypatch):
    import theme_switch

    calls = []
    monkeypatch.setattr(theme_switch, "detect_auto_target_mode", lambda: "light")
    monkeypatch.setattr(theme_switch, "current_theme_mode", lambda: "dark")
    monkeypatch.setattr(theme_switch, "apply",
                        lambda mode, ctx="": calls.append(("apply", mode, ctx)))
    monkeypatch.setattr(theme_switch, "apply_extras",
                        lambda mode: calls.append(("extras", mode)))

    theme_switch.sync_auto_mode_on_startup()
    assert ("apply", "light", "boot") in calls
    assert not any(c[0] == "extras" for c in calls)


def test_auto_sync_skips_full_apply_when_unchanged(monkeypatch):
    import theme_switch

    calls = []
    monkeypatch.setattr(theme_switch, "detect_auto_target_mode", lambda: "light")
    monkeypatch.setattr(theme_switch, "current_theme_mode", lambda: "light")
    monkeypatch.setattr(theme_switch, "apply",
                        lambda mode, ctx="": calls.append(("apply", mode, ctx)))
    monkeypatch.setattr(theme_switch, "apply_extras",
                        lambda mode: calls.append(("extras", mode)))

    theme_switch.sync_auto_mode_on_startup()
    assert ("extras", "light") in calls
    assert not any(c[0] == "apply" for c in calls)


def test_wallpaper_path_prefers_auto_package(monkeypatch, tmp_path):
    import theme_switch

    data = tmp_path / "data"
    wallpapers = data / "wallpapers"
    (wallpapers / "MacTahoe").mkdir(parents=True)
    (wallpapers / "MacTahoe-Light").mkdir()
    (wallpapers / "MacTahoe-Dark").mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(data))

    assert theme_switch._wallpaper_path("light") == wallpapers / "MacTahoe"
    assert theme_switch._wallpaper_path("dark") == wallpapers / "MacTahoe"


def test_apply_extras_syncs_wallpaper(monkeypatch, tmp_path):
    import theme_switch

    calls = []
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home/.cache").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(theme_switch, "_apply_wallpaper",
                        lambda mode: calls.append(("wallpaper", mode)) or True)
    monkeypatch.setattr(theme_switch, "_have", lambda cmd: False)

    theme_switch.apply_extras("dark")
    assert ("wallpaper", "dark") in calls


def test_settled_live_lookandfeel_requires_old_enough_plasmashell(monkeypatch):
    import theme_switch

    monkeypatch.setattr(theme_switch, "_plasmashell_age_seconds", lambda: 44)
    assert theme_switch._can_apply_settled_live_lookandfeel() is False

    monkeypatch.setattr(
        theme_switch,
        "_plasmashell_age_seconds",
        lambda: theme_switch._SETTLED_LIVE_APPLY_MIN_PLASMASHELL_AGE_SECONDS,
    )
    assert theme_switch._can_apply_settled_live_lookandfeel() is True


def test_apply_skips_live_lookandfeel_during_boot(monkeypatch):
    import theme_switch

    calls = []
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode: calls.append(("write", mode)))
    monkeypatch.setattr(theme_switch, "_can_apply_settled_live_lookandfeel",
                        lambda: False)
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live",
                        lambda laf: calls.append(("laf", laf)))
    monkeypatch.setattr(theme_switch, "apply_extras",
                        lambda mode: calls.append(("extras", mode)))
    monkeypatch.setattr(theme_switch, "cycle_widget_style_live",
                        lambda target: calls.append(("cycle", target)) or True)
    monkeypatch.setattr(theme_switch, "_qdbus",
                        lambda *args: calls.append(("qdbus", args)))

    assert theme_switch.apply("dark", "boot") is True
    assert ("write", "dark") in calls
    assert ("extras", "dark") in calls
    assert not any(c[0] == "laf" for c in calls)
    # Boot is the only context that skips the cycle — plasmashell is too
    # fragile during the login window for synthetic widget-style toggles.
    assert not any(c[0] == "cycle" for c in calls)
    assert not any(c[0] == "qdbus" and c[1][0] == "org.kde.plasmashell"
                   for c in calls)


def test_apply_uses_live_lookandfeel_after_boot(monkeypatch):
    import theme_switch

    calls = []
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode: calls.append(("write", mode)))
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live",
                        lambda laf: calls.append(("laf", laf)))
    monkeypatch.setattr(theme_switch, "apply_extras",
                        lambda mode: calls.append(("extras", mode)))
    monkeypatch.setattr(theme_switch, "cycle_widget_style_live",
                        lambda target: calls.append(("cycle", target)) or True)
    monkeypatch.setattr(theme_switch, "_qdbus",
                        lambda *args: calls.append(("qdbus", args)))

    assert theme_switch.apply("light") is True
    assert ("laf", theme_switch.LAF_LIGHT) in calls
    assert ("cycle", "kvantum") in calls
    assert any(c[0] == "qdbus" and c[1][0] == "org.kde.KWin"
               for c in calls)
    assert not any(c[0] == "qdbus" and c[1][0] == "org.kde.plasmashell"
                   for c in calls)


def test_apply_uses_live_lookandfeel_for_settled_scheduled_transition(monkeypatch):
    import theme_switch

    calls = []
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode: calls.append(("write", mode)))
    monkeypatch.setattr(theme_switch, "_can_apply_settled_live_lookandfeel",
                        lambda: True)
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live",
                        lambda laf: calls.append(("laf", laf)))
    monkeypatch.setattr(theme_switch, "apply_cursortheme_live",
                        lambda theme: calls.append(("cursor", theme)) or True)
    monkeypatch.setattr(theme_switch, "apply_extras",
                        lambda mode: calls.append(("extras", mode)))
    monkeypatch.setattr(theme_switch, "cycle_widget_style_live",
                        lambda target: calls.append(("cycle", target)) or True)
    monkeypatch.setattr(theme_switch, "_qdbus",
                        lambda *args: calls.append(("qdbus", args)))

    assert theme_switch.apply("dark", "scheduled") is True
    assert ("write", "dark") in calls
    assert ("extras", "dark") in calls
    assert ("laf", theme_switch.LAF_DARK) in calls
    # Scheduled (timer-fired) transitions must NOT cycle the widget style.
    # The cycle stresses plasmashell and the inter-write sleep is a
    # SIGTERM hazard (systemd KillSignal=TERM at unit stop = frozen
    # widgetStyle=Breeze + dark colors = "Breeze night" regression).
    assert not any(c[0] == "cycle" for c in calls)
    assert not any(c[0] == "cursor" for c in calls)
    assert any(c[0] == "qdbus" and c[1][0] == "org.kde.KWin"
               for c in calls)
    assert not any(c[0] == "qdbus" and c[1][0] == "org.kde.plasmashell"
                   for c in calls)


def test_apply_falls_back_to_cursor_for_unsettled_scheduled_transition(monkeypatch):
    import theme_switch

    calls = []
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode: calls.append(("write", mode)))
    monkeypatch.setattr(theme_switch, "_can_apply_settled_live_lookandfeel",
                        lambda: False)
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live",
                        lambda laf: calls.append(("laf", laf)))
    monkeypatch.setattr(theme_switch, "apply_cursortheme_live",
                        lambda theme: calls.append(("cursor", theme)) or True)
    monkeypatch.setattr(theme_switch, "apply_extras",
                        lambda mode: calls.append(("extras", mode)))
    monkeypatch.setattr(theme_switch, "cycle_widget_style_live",
                        lambda target: calls.append(("cycle", target)) or True)
    monkeypatch.setattr(theme_switch, "_qdbus",
                        lambda *args: calls.append(("qdbus", args)))

    assert theme_switch.apply("dark", "scheduled") is True
    assert ("write", "dark") in calls
    assert ("extras", "dark") in calls
    assert ("cursor", "MacTahoeLiquidKde-Dark") in calls
    # Scheduled context skips the cycle (see settled-transition test for why).
    assert not any(c[0] == "cycle" for c in calls)
    assert not any(c[0] == "laf" for c in calls)
    assert any(c[0] == "qdbus" and c[1][0] == "org.kde.KWin"
               for c in calls)
    assert not any(c[0] == "qdbus" and c[1][0] == "org.kde.plasmashell"
                   for c in calls)


def test_apply_never_refreshes_plasmashell_live(monkeypatch):
    import theme_switch

    calls = []
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode: calls.append(("write", mode)))
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live",
                        lambda laf: calls.append(("laf", laf)))
    monkeypatch.setattr(theme_switch, "apply_cursortheme_live",
                        lambda theme: calls.append(("cursor", theme)) or True)
    monkeypatch.setattr(theme_switch, "apply_extras",
                        lambda mode: calls.append(("extras", mode)))
    monkeypatch.setattr(theme_switch, "cycle_widget_style_live",
                        lambda target: calls.append(("cycle", target)) or True)
    monkeypatch.setattr(theme_switch, "_qdbus",
                        lambda *args: calls.append(("qdbus", args)))

    for mode, context in (("light", ""), ("dark", "boot"),
                          ("light", "install"), ("dark", "scheduled")):
        calls.clear()
        assert theme_switch.apply(mode, context) is True
        assert not any(c[0] == "qdbus" and c[1][0] == "org.kde.plasmashell"
                       for c in calls)


# ── widget-style cycle (Kvantum live re-instantiation) ───────────────────
def test_cycle_writes_breeze_then_target(monkeypatch):
    """Kvantum's style plugin only re-reads its kvconfig when Qt instantiates
    a new style instance, which requires writing a *different* widgetStyle
    name and then writing the target back. Verify both writes happen in that
    order."""
    import theme_switch

    writes: list[tuple[str, ...]] = []

    def fake_kwrite(*args: str) -> bool:
        writes.append(args)
        return True

    monkeypatch.setattr(theme_switch, "_kwrite", fake_kwrite)
    monkeypatch.setattr(theme_switch, "_have", lambda cmd: True)
    monkeypatch.setattr(theme_switch, "_has_session_dbus", lambda: True)
    monkeypatch.setattr(theme_switch, "_broadcast_widget_style_change",
                        lambda style: writes.append(("broadcast", style)))
    monkeypatch.setattr(theme_switch.time, "sleep", lambda _: None)

    assert theme_switch.cycle_widget_style_live("kvantum-dark") is True

    style_writes = [a for a in writes
                    if a and a[0] == "--file" and "widgetStyle" in a]
    assert len(style_writes) == 2
    assert style_writes[0][-1] == "Breeze"
    assert style_writes[1][-1] == "kvantum-dark"
    assert ("broadcast", "Breeze") in writes
    assert ("broadcast", "kvantum-dark") in writes
    # Breeze must come BEFORE the target, otherwise Qt sees the same style
    # name twice in a row and skips re-instantiation.
    assert writes.index(("broadcast", "Breeze")) < \
        writes.index(("broadcast", "kvantum-dark"))


def test_cycle_skips_without_kwriteconfig(monkeypatch):
    import theme_switch
    monkeypatch.setattr(theme_switch, "_have", lambda cmd: False)
    assert theme_switch.cycle_widget_style_live("kvantum") is False


def test_cycle_skips_without_session_bus(monkeypatch):
    import theme_switch
    monkeypatch.setattr(theme_switch, "_have", lambda cmd: True)
    monkeypatch.setattr(theme_switch, "_has_session_dbus", lambda: False)
    assert theme_switch.cycle_widget_style_live("kvantum") is False


def test_cycle_skips_with_empty_target(monkeypatch):
    import theme_switch
    monkeypatch.setattr(theme_switch, "_have", lambda cmd: True)
    monkeypatch.setattr(theme_switch, "_has_session_dbus", lambda: True)
    assert theme_switch.cycle_widget_style_live("") is False


def test_broadcast_sends_kglobalsettings_and_portal_signals(monkeypatch):
    """The cycle is only effective if BOTH the legacy KGlobalSettings signal
    *and* the xdg-portal SettingChanged signal go out — Plasma watches the
    first, but bare Qt apps (and some kded modules) only watch the second."""
    import theme_switch

    runs: list[list[str]] = []

    def fake_run(cmd, **_):
        runs.append(cmd)

        class R: returncode = 0
        return R()

    monkeypatch.setattr(theme_switch, "_has_session_dbus", lambda: True)
    monkeypatch.setattr(theme_switch.subprocess, "run", fake_run)

    theme_switch._broadcast_widget_style_change("kvantum")

    # dbus-send layout: [dbus-send, --session, --type=signal, path, member, ...]
    paths = [c[3] for c in runs]
    members = [c[4] for c in runs]
    assert "/KGlobalSettings" in paths
    assert "/org/freedesktop/portal/desktop" in paths
    assert "org.kde.KGlobalSettings.notifyChange" in members
    assert "org.freedesktop.portal.Settings.SettingChanged" in members
    assert "org.freedesktop.impl.portal.Settings.SettingChanged" in members
    # The variant payload has to carry the *target* widget style verbatim,
    # otherwise the portal listener can't tell what changed.
    assert any("variant:string:kvantum" in arg for c in runs for arg in c)


def test_cycle_restores_target_on_sigterm(monkeypatch):
    """If SIGTERM lands during the inter-write sleep (systemd stopping the
    apply service mid-cycle is the documented trigger), the on-disk value
    MUST end at the target, never frozen at Breeze. Otherwise the user
    next-boots into 'Breeze night': MacTahoeLiquidKdeDark colors with
    breeze widgets, which is what triggered this whole regression hunt."""
    import signal as signal_mod

    import theme_switch

    writes: list[str] = []

    def fake_kwrite(*args: str) -> bool:
        if "widgetStyle" in args:
            # Last positional arg is the value.
            writes.append(args[-1])
        return True

    monkeypatch.setattr(theme_switch, "_kwrite", fake_kwrite)
    monkeypatch.setattr(theme_switch, "_have", lambda cmd: True)
    monkeypatch.setattr(theme_switch, "_has_session_dbus", lambda: True)
    monkeypatch.setattr(theme_switch, "_broadcast_widget_style_change",
                        lambda style: None)

    def sleep_then_sigterm(_seconds):
        # Simulate systemd sending SIGTERM partway through the cycle.
        os.kill(os.getpid(), signal_mod.SIGTERM)

    monkeypatch.setattr(theme_switch.time, "sleep", sleep_then_sigterm)

    with pytest.raises(SystemExit):
        theme_switch.cycle_widget_style_live("kvantum-dark")

    # Most important assertion: the LAST widgetStyle written must be the
    # target, never Breeze. That's the invariant that prevents the
    # "Breeze night" regression.
    assert writes, "expected at least one widgetStyle write"
    assert writes[-1] == "kvantum-dark"


def test_apply_skips_cycle_on_install_context(monkeypatch):
    """Install ends with a full plasmashell restart (``apply.py
    restart_plasma``), so the cycle's QApplication::setStyle hot-swap is
    redundant during install and adds an extra plasmashell stress
    immediately before the kill — bad ordering. Skip it."""
    import theme_switch

    calls: list = []
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode: calls.append(("write", mode)))
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live",
                        lambda laf: calls.append(("laf", laf)))
    monkeypatch.setattr(theme_switch, "_apply_local_extras",
                        lambda mode: calls.append(("local_extras", mode)))
    monkeypatch.setattr(theme_switch, "apply_extras",
                        lambda mode: calls.append(("extras", mode)))
    monkeypatch.setattr(theme_switch, "cycle_widget_style_live",
                        lambda target: calls.append(("cycle", target)) or True)
    monkeypatch.setattr(theme_switch, "_qdbus",
                        lambda *args: calls.append(("qdbus", args)))

    assert theme_switch.apply("dark", "install") is True
    assert ("local_extras", "dark") in calls
    assert not any(c[0] == "extras" for c in calls)
    assert not any(c[0] == "cycle" for c in calls), \
        "install context must not cycle widget style"
    assert not any(c[0] == "qdbus" for c in calls), \
        "install context must not wait on a live KWin session"


def test_apply_cycles_kvantum_for_dark_manual_switch(monkeypatch):
    import theme_switch

    calls = []
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode: calls.append(("write", mode)))
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live",
                        lambda laf: calls.append(("laf", laf)))
    monkeypatch.setattr(theme_switch, "apply_extras",
                        lambda mode: calls.append(("extras", mode)))
    monkeypatch.setattr(theme_switch, "cycle_widget_style_live",
                        lambda target: calls.append(("cycle", target)) or True)
    monkeypatch.setattr(theme_switch, "_qdbus",
                        lambda *args: calls.append(("qdbus", args)))

    assert theme_switch.apply("dark") is True
    assert ("cycle", "kvantum-dark") in calls
    # Cycle must run AFTER apply_extras (which is what writes the new
    # kvantum.kvconfig) — otherwise Kvantum re-instantiates against the
    # *old* kvconfig and we end up exactly where we started.
    assert calls.index(("extras", "dark")) < calls.index(("cycle", "kvantum-dark"))


def test_auto_mode_uses_scheduled_context(monkeypatch):
    import theme_switch

    calls = []
    monkeypatch.setattr(theme_switch, "enable_auto_mode",
                        lambda: calls.append(("enable",)))
    monkeypatch.setattr(theme_switch, "detect_mode_by_time", lambda: "light")
    monkeypatch.setattr(theme_switch, "apply",
                        lambda mode, ctx="": calls.append(("apply", mode, ctx)))

    assert theme_switch.main(["auto"]) == 0
    assert ("enable",) in calls
    assert ("apply", "light", "scheduled") in calls


# ── theme-switch step install / uninstall cycle ──────────────────────────
def _run_step(step_name: str, phase: str, env: dict[str, str]) -> None:
    full = os.environ.copy()
    full.update(env)
    rc = subprocess.run(
        ["python3", "-c",
         f"from steps.{step_name} import {phase}; {phase}()"],
        check=False, env=full, cwd=str(Path(__file__).resolve().parent.parent / "src/scripts"),
    ).returncode
    assert rc == 0


def test_switch_step_install_uninstall_reinstall(sandbox):
    env = {"THEME_MODE": "auto"}
    _run_step("theme_switch", "install", env)
    bin_path = sandbox / ".local/bin/mac-tahoe-theme-switch"
    svc_dir = sandbox / ".config/systemd/user"
    assert bin_path.is_file() and bin_path.stat().st_mode & 0o111
    assert (svc_dir / "mac-tahoe-liquid-kde-theme.service").is_file()
    assert (svc_dir / "mac-tahoe-liquid-kde-theme.timer").is_file()
    assert (svc_dir / "mac-tahoe-liquid-kde-theme-apply.service").is_file()

    # Seed kdeglobals so uninstall has something to reset.
    (sandbox / ".config/kdeglobals").write_text(
        "[KDE]\n"
        "AutomaticLookAndFeel=true\n"
        "DefaultLightLookAndFeel=org.kde.mac-tahoe-liquid-kde.light\n"
        "DefaultDarkLookAndFeel=org.kde.mac-tahoe-liquid-kde.dark\n"
    )
    _run_step("theme_switch", "uninstall", env)
    assert not bin_path.exists()
    assert not (svc_dir / "mac-tahoe-liquid-kde-theme.service").exists()
    assert not (svc_dir / "mac-tahoe-liquid-kde-theme.timer").exists()
    assert not (svc_dir / "mac-tahoe-liquid-kde-theme-apply.service").exists()
    if not has_command("kwriteconfig6"):
        return
    val = ini_get(sandbox / ".config/kdeglobals", "KDE", "AutomaticLookAndFeel")
    assert val == "false"
    assert not ini_get(sandbox / ".config/kdeglobals", "KDE", "DefaultLightLookAndFeel")
    assert not ini_get(sandbox / ".config/kdeglobals", "KDE", "DefaultDarkLookAndFeel")

    _run_step("theme_switch", "install", {"THEME_MODE": "dark"})
    assert bin_path.is_file()
    assert (svc_dir / "mac-tahoe-liquid-kde-theme.service").is_file()
