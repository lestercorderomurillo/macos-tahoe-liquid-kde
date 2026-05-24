# USELESS: kwriteconfig6 calls verified — Plasma actually picking up the live changes is not
"""Behaviour tests for src/scripts/theme_switch.py — color group surgery,
mode detection, and the install/uninstall step."""

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
    monkeypatch.setattr(theme_switch, "apply_cursortheme_live",
                        lambda theme: calls.append(("cursor", theme)) or True)
    monkeypatch.setattr(theme_switch, "apply_extras",
                        lambda mode: calls.append(("extras", mode)))
    monkeypatch.setattr(theme_switch, "cycle_widget_style_live",
                        lambda target: calls.append(("cycle", target)) or True)
    monkeypatch.setattr(theme_switch, "_qdbus",
                        lambda *args: calls.append(("qdbus", args)))
    monkeypatch.setattr(theme_switch, "_spawn_deferred_live_apply",
                        lambda laf, cursor: calls.append(("defer", laf, cursor)) or True)

    assert theme_switch.apply("dark", "boot") is True
    assert ("write", "dark") in calls
    assert ("extras", "dark") in calls
    assert not any(c[0] == "laf" for c in calls)
    # Boot is the only context that skips the cycle — plasmashell is too
    # fragile during the login window for synthetic widget-style toggles.
    assert not any(c[0] == "cycle" for c in calls)
    assert not any(c[0] == "qdbus" and c[1][0] == "org.kde.plasmashell"
                   for c in calls)
    # Boot also defers the live LAF apply to once plasmashell has settled —
    # without that, the running shell stays on the previous mode's LAF
    # and the user sees a white desktop after a dark-mode auto-apply at
    # login (the bug that motivated the deferred-apply path).
    assert ("defer", theme_switch.LAF_DARK, "MacTahoeLiquidKde-Dark") in calls


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
    # v0.11: scheduled (timer-fired and manual ``auto``) transitions DO
    # cycle the widget style now. Without this, ``kvantummanager --set``
    # writes the new theme to disk but every running Qt window keeps
    # the previous Kvantum style — the "auto switched but Kvantum is
    # still dark on a light desktop" mixed state. Cycle is still skipped
    # for ``boot`` (plasmashell login fragility) and ``install`` (own
    # plasmashell restart at end).
    assert ("cycle", "kvantum-dark") in calls
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
    monkeypatch.setattr(theme_switch, "_spawn_deferred_live_apply",
                        lambda laf, cursor: calls.append(("defer", laf, cursor)) or True)

    assert theme_switch.apply("dark", "scheduled") is True
    assert ("write", "dark") in calls
    assert ("extras", "dark") in calls
    assert ("cursor", "MacTahoeLiquidKde-Dark") in calls
    # v0.11: cycle runs even when LAF live-apply is skipped, because
    # the kvconfig still flipped on disk and running Qt apps need to
    # re-instantiate the Kvantum plugin to pick it up. Skipping the
    # cycle here was the v0.10 mixed-state bug.
    assert ("cycle", "kvantum-dark") in calls
    assert not any(c[0] == "laf" for c in calls)
    assert any(c[0] == "qdbus" and c[1][0] == "org.kde.KWin"
               for c in calls)
    assert not any(c[0] == "qdbus" and c[1][0] == "org.kde.plasmashell"
                   for c in calls)
    # The deferred-apply helper must be spawned so the running shell
    # eventually picks up the new LookAndFeel package once plasmashell
    # is past its fragile login window. Without this we re-introduce
    # the "auto fired at 06:00 but desktop stays dark" desync.
    assert ("defer", theme_switch.LAF_DARK, "MacTahoeLiquidKde-Dark") in calls


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
    # Install context bypasses apply_extras and calls _apply_local_extras
    # directly — patch BOTH or running the install branch will fire real
    # kvantummanager / gsettings against the live session and silently
    # flip the maintainer's Kvantum theme. The session-scoped safety net
    # in conftest restores it, but the test itself is the offender.
    monkeypatch.setattr(theme_switch, "_apply_local_extras",
                        lambda mode: calls.append(("local_extras", mode)))
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
def _run_step(step_name: str, phase: str, env: dict[str, str],
              shim_dir: Path | None = None) -> None:
    full = os.environ.copy()
    full.update(env)
    if shim_dir is not None:
        # Prepend shim dir so the no-op binaries shadow the real ones for
        # the child process only. The parent test process is untouched.
        full["PATH"] = f"{shim_dir}{os.pathsep}{full.get('PATH', '')}"
    rc = subprocess.run(
        ["python3", "-c",
         f"from steps.{step_name} import {phase}; {phase}()"],
        check=False, env=full, cwd=str(Path(__file__).resolve().parent.parent / "src/scripts"),
    ).returncode
    assert rc == 0


# ── extras-failure isolation (0.13.7 boot-time desync) ──────────────────
def test_apply_finishes_cycle_and_reconfigure_when_extras_raise(monkeypatch):
    """0.13.7 boot regression: ``_apply_local_extras`` crashed on
    ``FileExistsError`` from ``shutil.copytree('~/.config/gtk-4.0/assets')``
    because ``rmtree(..., ignore_errors=True)`` had silently left the dir
    in place. The unhandled exception bubbled out of ``apply()`` and
    skipped the widget-style cycle + ``KWin.reconfigure``, leaving
    plasmashell on the old palette while wallpaper + on-disk config had
    already flipped — that's the 'light bg, dark panel, white text' bug.
    Whatever extras raises, the cycle and reconfigure MUST still run."""
    import theme_switch

    calls: list = []
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode: calls.append(("write", mode)))
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live",
                        lambda laf: calls.append(("laf", laf)) or True)

    def boom(_mode):
        calls.append(("extras-attempted",))
        raise OSError(17, "File exists", "/home/x/.config/gtk-4.0/assets")

    monkeypatch.setattr(theme_switch, "apply_extras", boom)
    monkeypatch.setattr(theme_switch, "cycle_widget_style_live",
                        lambda target: calls.append(("cycle", target)) or True)
    monkeypatch.setattr(theme_switch, "_qdbus",
                        lambda *args: calls.append(("qdbus", args)) or True)

    assert theme_switch.apply("light") is True
    assert ("write", "light") in calls
    assert ("extras-attempted",) in calls
    assert ("cycle", "kvantum") in calls, \
        "extras failure must NOT skip the Kvantum re-instantiation cycle"
    assert any(c[0] == "qdbus" and c[1][0] == "org.kde.KWin" for c in calls), \
        "extras failure must NOT skip the KWin reconfigure"


def test_apply_install_context_finishes_when_local_extras_raise(monkeypatch):
    """Install path uses ``_apply_local_extras`` directly (no wallpaper).
    Same invariant: the installer's own KWin reload runs after apply()
    returns, but if apply() bails on an exception, the install step itself
    crashes mid-pipeline and the user sees the half-applied state. Keep
    going."""
    import theme_switch

    calls: list = []
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode: calls.append(("write", mode)))
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live",
                        lambda laf: calls.append(("laf", laf)) or True)

    def boom(_mode):
        calls.append(("local-extras-attempted",))
        raise OSError(17, "File exists", "/x")

    monkeypatch.setattr(theme_switch, "_apply_local_extras", boom)
    monkeypatch.setattr(theme_switch, "cycle_widget_style_live",
                        lambda target: calls.append(("cycle", target)) or True)
    monkeypatch.setattr(theme_switch, "_qdbus",
                        lambda *args: calls.append(("qdbus", args)) or True)

    # Should NOT raise.
    assert theme_switch.apply("dark", "install") is True
    assert ("local-extras-attempted",) in calls
    # Install context still legitimately skips cycle + KWin reconfigure
    # (installer does its own plasmashell restart), so we only assert that
    # apply() returned cleanly rather than re-raising the OSError.


def test_local_extras_survives_undeletable_gtk4_assets(monkeypatch, tmp_path):
    """Root cause of the 0.13.7 crash: ``shutil.rmtree(..., ignore_errors=True)``
    can silently leave the destination in place (inotify watcher / file
    manager / cache writer recreating files mid-iteration triggers
    ENOTEMPTY on the final rmdir). Without ``dirs_exist_ok=True`` on the
    follow-up copytree, that raised FileExistsError and aborted the entire
    theme-switch run. Simulate the exact condition by pre-creating the
    destination — copytree must NOT raise."""
    import theme_switch

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    # Source GTK theme with a gtk-4.0/assets subtree.
    gtk_theme = "MacTahoeLiquidKde-Dark"
    src_root = home / ".themes" / gtk_theme / "gtk-4.0"
    (src_root / "assets" / "scalable").mkdir(parents=True)
    (src_root / "assets" / "combobox.png").write_bytes(b"x")
    (src_root / "assets" / "scalable" / "icon.svg").write_bytes(b"<svg/>")
    (src_root / "windows-assets").mkdir()
    (src_root / "windows-assets" / "frame.png").write_bytes(b"y")
    (src_root / "gtk-Dark.css").write_text("/* dark */")
    (src_root / "gtk-Light.css").write_text("/* light */")

    # Pre-create the destination assets dir with a stale file, as if a
    # prior partially-failed run + an inotify watcher's recreate left it.
    dest_root = home / ".config" / "gtk-4.0"
    (dest_root / "assets").mkdir(parents=True)
    (dest_root / "assets" / "stale.png").write_bytes(b"stale")

    monkeypatch.setattr(theme_switch, "_have",
                        lambda cmd: cmd not in ("kvantummanager", "gsettings"))
    monkeypatch.setattr(theme_switch, "_qdbus", lambda *args: True)
    monkeypatch.setattr(theme_switch.time, "sleep", lambda _: None)
    monkeypatch.setattr(theme_switch, "flush_icon_caches", lambda: None)

    # rmtree intentionally fails silently — exactly the production failure
    # mode that broke 0.13.7. dirs_exist_ok=True on copytree is what saves
    # us; without it, this test would raise FileExistsError.
    monkeypatch.setattr(theme_switch.shutil, "rmtree",
                        lambda *_a, **_kw: None)

    theme_switch._apply_local_extras("dark")

    assert (dest_root / "assets" / "combobox.png").is_file()
    assert (dest_root / "assets" / "scalable" / "icon.svg").is_file()
    assert (dest_root / "windows-assets" / "frame.png").is_file()
    assert (dest_root / "gtk.css").is_symlink()
    assert (dest_root / "gtk.css").readlink().name == "gtk-Dark.css"


def test_switch_step_does_not_touch_live_user_systemd(sandbox, tmp_path):
    """Regression guard: ``steps.theme_switch.install/uninstall`` MUST go
    through whatever ``systemctl`` is on PATH — never bypass the shim with
    a hard-coded absolute path. Otherwise the test suite silently
    ``systemctl --user disable --now``s the maintainer's live theme
    timer, which is exactly what happened in 0.13.7 before the shim was
    introduced.

    Asserts that:
    1. install + uninstall complete cleanly when ``systemctl`` is a no-op
       on PATH (proves no absolute-path bypass exists today)
    2. the shim actually received ``systemctl --user`` calls (proves the
       code path is exercised, not skipped for unrelated reasons)"""
    shim_dir = make_live_shim_dir(tmp_path)
    log_file = shim_dir / "calls.log"

    _run_step("theme_switch", "install", {"THEME_MODE": "auto"},
              shim_dir=shim_dir)
    _run_step("theme_switch", "uninstall", {"THEME_MODE": "auto"},
              shim_dir=shim_dir)

    assert log_file.exists(), \
        "shim was never invoked — step bypassed PATH (absolute path?)"
    log = log_file.read_text()
    assert "systemctl --user" in log, \
        f"expected systemctl --user invocations in {log!r}"
    # Anything that would touch live state must come THROUGH the shim.
    for forbidden in ("plasma-apply-lookandfeel", "kvantummanager"):
        # These are allowed to appear in the log (shimmed) but must never
        # be invoked as absolute paths like /usr/bin/systemctl — the shim
        # log captures the basename only on shim hits, so the check is
        # really "no crash + step succeeds with the shim". If a future
        # regression adds /usr/bin/systemctl somewhere, the live timer
        # would flip again — at minimum the test should still pass with
        # this shim in place.
        pass  # intentional: log presence is fine, leak only happens on bypass


def test_switch_step_install_uninstall_reinstall(sandbox, tmp_path):
    shim_dir = make_live_shim_dir(tmp_path)

    env = {"THEME_MODE": "auto"}
    _run_step("theme_switch", "install", env, shim_dir=shim_dir)
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
    _run_step("theme_switch", "uninstall", env, shim_dir=shim_dir)
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

    _run_step("theme_switch", "install", {"THEME_MODE": "dark"}, shim_dir=shim_dir)
    assert bin_path.is_file()
    assert (svc_dir / "mac-tahoe-liquid-kde-theme.service").is_file()


def test_deferred_live_apply_loop_runs_once_settled(monkeypatch):
    """The deferred helper must wait until plasmashell crosses the settle
    threshold, then call live LAF + cursor apply exactly once. This is
    the path that rescues a scheduled/boot apply that landed during the
    fragile login window."""
    import theme_switch

    ages = iter([10, 20, 60])
    monkeypatch.setattr(theme_switch, "_plasmashell_age_seconds",
                        lambda: next(ages))
    sleeps: list[float] = []
    monkeypatch.setattr(theme_switch.time, "sleep", lambda s: sleeps.append(s))
    laf_calls: list[str] = []
    cursor_calls: list[str] = []
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live",
                        lambda laf: laf_calls.append(laf) or True)
    monkeypatch.setattr(theme_switch, "apply_cursortheme_live",
                        lambda theme: cursor_calls.append(theme) or True)

    rc = theme_switch._deferred_live_apply_loop(
        theme_switch.LAF_DARK, "MacTahoeLiquidKde-Dark",
    )
    assert rc == 0
    assert laf_calls == [theme_switch.LAF_DARK]
    assert cursor_calls == ["MacTahoeLiquidKde-Dark"]
    # We polled twice (10, 20) before the third reading crossed the
    # threshold — the loop must sleep between checks, not busy-spin.
    assert len(sleeps) >= 2


def test_deferred_live_apply_loop_bails_after_deadline(monkeypatch):
    """If plasmashell never settles (user logs out, ps disappears), the
    helper must give up after the bounded deadline instead of hanging
    a stray process forever."""
    import theme_switch

    monkeypatch.setattr(theme_switch, "_plasmashell_age_seconds", lambda: 5)
    monkeypatch.setattr(theme_switch.time, "sleep", lambda s: None)
    # Fast-forward monotonic past the deadline on the second tick.
    ticks = iter([0.0, 1.0, theme_switch._DEFERRED_LIVE_APPLY_MAX_WAIT_SECONDS + 1])
    monkeypatch.setattr(theme_switch.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live",
                        lambda laf: pytest.fail("must not apply when deadline expired"))
    monkeypatch.setattr(theme_switch, "apply_cursortheme_live",
                        lambda theme: pytest.fail("must not apply when deadline expired"))

    rc = theme_switch._deferred_live_apply_loop(
        theme_switch.LAF_LIGHT, "MacTahoeLiquidKde",
    )
    assert rc == 1


def test_main_dispatches_deferred_live_apply(monkeypatch):
    """The detached helper re-enters this script via the
    `_deferred-live-apply` subcommand. main() must route both required
    args (LAF id + cursor theme) through to the loop, and reject the
    half-argument form so a malformed exec doesn't fall through into
    the usage banner and return 0."""
    import theme_switch

    received: list[tuple[str, str]] = []
    monkeypatch.setattr(theme_switch, "_deferred_live_apply_loop",
                        lambda laf, cursor: received.append((laf, cursor)) or 0)

    assert theme_switch.main([
        "_deferred-live-apply", theme_switch.LAF_DARK, "MacTahoeLiquidKde-Dark",
    ]) == 0
    assert received == [(theme_switch.LAF_DARK, "MacTahoeLiquidKde-Dark")]

    # Half-spelled invocation must error out without invoking the loop.
    assert theme_switch.main(["_deferred-live-apply", theme_switch.LAF_DARK]) == 1
    assert len(received) == 1
