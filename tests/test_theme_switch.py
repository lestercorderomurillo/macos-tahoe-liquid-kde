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
import threading
import time
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
    monkeypatch.setattr(theme_switch, "_current_wallpapers", lambda: [])
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode, **kw:
                        calls.append(("write", mode, kw)) or True)
    monkeypatch.setattr(theme_switch, "_apply_wallpaper",
                        lambda mode, **kw:
                        calls.append(("wallpaper", mode)) or True)
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
    """Capture first, then live LAF → write → local extras → wallpaper
    → live cursor → Kvantum cycle → KWin reconfigure. Applying LAF
    before stamping its target into kdeglobals makes Plasma observe a real
    transition; wallpaper capture still precedes it so custom state survives."""
    import theme_switch
    calls: list = []
    _stub_apply_dependencies(monkeypatch, calls)

    assert theme_switch.apply("dark") is True

    write_idx = next(i for i, c in enumerate(calls) if c[0] == "write")
    extras_idx = next(i for i, c in enumerate(calls) if c[0] == "local_extras")
    laf_idx = next(i for i, c in enumerate(calls) if c[0] == "laf")
    wallpaper_idx = next(i for i, c in enumerate(calls)
                         if c[0] == "wallpaper")
    cursor_idx = next(i for i, c in enumerate(calls) if c[0] == "cursor")
    cycle_idx = next(i for i, c in enumerate(calls) if c[0] == "cycle")
    reconfigure_idx = next(
        i for i, c in enumerate(calls)
        if c[0] == "qdbus" and c[1][0] == "org.kde.KWin"
    )

    assert (laf_idx < write_idx < extras_idx < wallpaper_idx < cursor_idx
            < cycle_idx < reconfigure_idx)
    assert ("laf", theme_switch.LAF_DARK) in calls
    assert ("cycle", "kvantum") in calls


def test_apply_serializes_overlapping_theme_transitions(monkeypatch, tmp_path):
    """A login service, timer and manual apply can overlap. The second
    pipeline must wait rather than interleave panel config and cache changes."""
    import theme_switch

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    entered: list[str] = []
    first_inside = threading.Event()
    release_first = threading.Event()

    def fake_apply(mode, context="user"):
        entered.append(mode)
        if mode == "dark":
            first_inside.set()
            assert release_first.wait(timeout=2)
        return True

    monkeypatch.setattr(theme_switch, "_apply_unlocked", fake_apply)
    first = threading.Thread(target=theme_switch.apply, args=("dark",))
    second = threading.Thread(target=theme_switch.apply, args=("light",))
    first.start()
    assert first_inside.wait(timeout=2)
    second.start()
    time.sleep(0.05)
    assert entered == ["dark"]
    release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)
    assert not first.is_alive() and not second.is_alive()
    assert entered == ["dark", "light"]


def _prep_effect_warn_case(monkeypatch, tmp_path, kwinrc_body):
    """Shared setup for the #46 effect-warning tests: an isolated kwinrc, all
    live sub-calls stubbed to no-op, and stderr captured. Returns (theme_switch
    module, kwinrc path)."""
    import theme_switch
    home = tmp_path / "home"
    (home / ".config").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    kwinrc = home / ".config/kwinrc"
    kwinrc.write_text(kwinrc_body)
    for fn in ("write_kde_theme_config", "_apply_wallpaper",
               "apply_cursortheme_live", "cycle_widget_style_live"):
        monkeypatch.setattr(theme_switch, fn, lambda *a, **k: True)
    monkeypatch.setattr(theme_switch, "_apply_local_extras", lambda m: None)
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live", lambda laf: True)
    monkeypatch.setattr(theme_switch, "_qdbus", lambda *a: True)
    monkeypatch.setattr(theme_switch.time, "sleep", lambda _s: None)
    return theme_switch, kwinrc


def test_apply_warns_when_third_party_effect_fails_to_load(
        monkeypatch, tmp_path, capsys):
    """Regression for #46: after a theme switch, KWin re-scans effects; a
    third-party COMPILED effect (KDE-Rounded-Corners' shapecornersEnabled=true)
    whose .so is ABI-incompatible fails to load. We proved on a live session
    that its config key survives, so this is a runtime-load failure, not config
    loss. The installer must WARN by name rather than let it break silently —
    and must NOT touch the on-disk key (so it returns once rebuilt)."""
    ts, kwinrc = _prep_effect_warn_case(
        monkeypatch, tmp_path,
        "[Plugins]\nshapecornersEnabled=true\nliquidglassEnabled=true\n")
    # KWin reloaded everything EXCEPT the third-party effect.
    monkeypatch.setattr(ts, "_kwin_loaded_effects",
                        lambda: {"liquidglass", "blur", "kwin4_effect_slide"})

    assert ts.apply("dark") is True
    err = capsys.readouterr().err
    assert "shapecorners" in err and "could not load it" in err
    # The user's config key is left exactly as it was — never disabled.
    assert ts._parse_ini(kwinrc)["Plugins"]["shapecornersEnabled"] == "true"


def test_apply_no_warn_when_effect_loads_fine(monkeypatch, tmp_path, capsys):
    """The warning must never cry wolf: a healthy third-party effect that KWin
    loads back produces no warning. Verified live — a compatible effect stays
    in loadedEffects across reconfigure."""
    ts, _ = _prep_effect_warn_case(
        monkeypatch, tmp_path, "[Plugins]\nshapecornersEnabled=true\n")
    monkeypatch.setattr(ts, "_kwin_loaded_effects",
                        lambda: {"kwin4_effect_shapecorners", "liquidglass"})
    assert ts.apply("dark") is True
    assert "could not load" not in capsys.readouterr().err


def test_apply_reloads_third_party_effect_before_warning(
        monkeypatch, tmp_path, capsys):
    """A temporarily unloaded compatible effect is actively restored. The
    warning is reserved for effects that remain absent after that retry."""
    ts, _ = _prep_effect_warn_case(
        monkeypatch, tmp_path, "[Plugins]\nshapecornersEnabled=true\n")
    loaded = iter([
        {"liquidglass"},
        {"liquidglass", "kwin4_effect_shapecorners"},
    ])
    monkeypatch.setattr(ts, "_kwin_loaded_effects", lambda: next(loaded))
    calls = []
    monkeypatch.setattr(ts, "_qdbus",
                        lambda *args: calls.append(args) or True)

    assert ts.apply("dark") is True
    assert any(
        call[-2:] == ("org.kde.kwin.Effects.loadEffect", "shapecorners")
        for call in calls
    )
    assert "shapecorners" not in capsys.readouterr().err


def test_apply_no_warn_for_user_disabled_effect(monkeypatch, tmp_path, capsys):
    """An effect the user themselves DISABLED (Enabled=false) is not one we
    watch — its absence from the loaded set is expected, not a failure. No
    warning, and obviously no re-enabling."""
    ts, kwinrc = _prep_effect_warn_case(
        monkeypatch, tmp_path, "[Plugins]\nshapecornersEnabled=false\n")
    monkeypatch.setattr(ts, "_kwin_loaded_effects", lambda: {"liquidglass"})
    assert ts.apply("dark") is True
    assert "shapecorners" not in capsys.readouterr().err
    assert ts._parse_ini(kwinrc)["Plugins"]["shapecornersEnabled"] == "false"


def test_apply_no_warn_when_loaded_set_unreadable(monkeypatch, tmp_path, capsys):
    """No session bus / qdbus / a timeout means the loaded set is unknown. We
    degrade to SILENCE — never a false 'your effect broke' on headless CI or a
    first-login install where KWin isn't answering yet."""
    ts, _ = _prep_effect_warn_case(
        monkeypatch, tmp_path, "[Plugins]\nshapecornersEnabled=true\n")
    monkeypatch.setattr(ts, "_kwin_loaded_effects", lambda: None)
    assert ts.apply("dark") is True
    assert "could not load" not in capsys.readouterr().err


def test_apply_finishes_cycle_and_reconfigure_when_extras_raise(monkeypatch):
    """An unexpected local-extras failure must not skip the widget-style
    cycle or KWin reconfigure after the on-disk theme has already changed."""
    import theme_switch

    calls: list = []
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode, **kw:
                        calls.append(("write", mode, kw)) or True)
    monkeypatch.setattr(theme_switch, "_apply_wallpaper",
                        lambda mode, **kw:
                        calls.append(("wallpaper", mode)) or True)
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


def test_local_extras_switches_libadwaita_gtk4_override(monkeypatch, tmp_path):
    """Modern Nautilus needs GTK's user stylesheet in addition to the GTK
    theme setting, so the project-managed link must track both modes."""
    import theme_switch

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    for variant in ("Dark", "Light"):
        src = (home / ".themes" / f"MacTahoeLiquidKde-{variant}"
               / "gtk-4.0")
        (src / "assets").mkdir(parents=True)
        (src / "windows-assets").mkdir()
        (src / "assets" / "button.png").write_bytes(variant.encode())
        (src / "windows-assets" / "frame.png").write_bytes(
            variant.encode())
        (src / "gtk-Dark.css").write_text("/* dark */")
        (src / "gtk-Light.css").write_text("/* light */")

    dest_root = home / ".config" / "gtk-4.0"
    dest_root.mkdir(parents=True)
    # This is the regular stub kde-gtk-config writes on the live desktop.
    (dest_root / "gtk.css").write_text("@import 'colors.css';")

    monkeypatch.setattr(theme_switch, "_have",
                        lambda cmd: cmd not in ("kvantummanager", "gsettings"))
    monkeypatch.setattr(theme_switch, "_qdbus", lambda *args: True)
    monkeypatch.setattr(theme_switch, "flush_icon_caches", lambda: None)

    theme_switch._apply_local_extras("dark")

    assert (dest_root / "gtk.css").is_symlink()
    assert (dest_root / "gtk.css").readlink().name == "gtk-Dark.css"
    assert (dest_root / "gtk-Dark.css").read_text() == "/* dark */"
    assert (dest_root / "assets/button.png").read_bytes() == b"Dark"

    theme_switch._apply_local_extras("light")

    assert (dest_root / "gtk.css").is_symlink()
    assert (dest_root / "gtk.css").readlink().name == "gtk-Light.css"
    assert (dest_root / "gtk-Light.css").read_text() == "/* light */"
    assert (dest_root / "assets/button.png").read_bytes() == b"Light"


def test_local_extras_preserves_user_owned_gtk4_css(monkeypatch, tmp_path):
    import theme_switch

    home = tmp_path / "home"
    (home / ".themes/MacTahoeLiquidKde-Light").mkdir(parents=True)
    gtk4 = home / ".config/gtk-4.0"
    gtk4.mkdir(parents=True)
    custom = gtk4 / "gtk.css"
    custom.write_text("/* my custom overrides */\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(theme_switch, "_have", lambda _cmd: False)
    monkeypatch.setattr(theme_switch, "_qdbus", lambda *args: True)
    monkeypatch.setattr(theme_switch, "flush_icon_caches", lambda: None)

    theme_switch._apply_local_extras("light")

    assert custom.read_text() == "/* my custom overrides */\n"


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_local_extras_uses_palette_following_kvantum_theme(
        monkeypatch, tmp_path, mode):
    import theme_switch

    home = tmp_path / "home"
    gtk_theme = f"MacTahoeLiquidKde-{mode.capitalize()}"
    (home / ".themes" / gtk_theme).mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        theme_switch, "_have",
        lambda cmd: cmd == "kvantummanager",
    )
    calls = []
    monkeypatch.setattr(
        theme_switch, "_run_user",
        lambda cmd, **kwargs:
        calls.append(cmd) or subprocess.CompletedProcess(cmd, 0),
    )
    monkeypatch.setattr(theme_switch, "_qdbus", lambda *args: True)
    monkeypatch.setattr(theme_switch, "flush_icon_caches", lambda: None)

    theme_switch._apply_local_extras(mode)

    assert ["kvantummanager", "--set", "mac-tahoe-liquid-kde"] in calls


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


def test_cycle_widget_style_works_off_main_thread(monkeypatch):
    """Real regression: cycle_widget_style_live registers SIGTERM/SIGINT
    handlers, but signal.signal() only works on the MAIN thread. The
    installer UI runs steps off-thread, where the bare signal.signal() raised
    'ValueError: signal only works in main thread of the main interpreter' and
    crashed uninstall. It must run to completion on a worker thread (skipping
    only the mid-cycle SIGTERM interception).

    NOTE: this test does NOT monkeypatch cycle_widget_style_live — it runs the
    REAL function on a real worker thread, because the crash lived in exactly
    the code the other tests stub away."""
    import threading as _threading
    import theme_switch

    monkeypatch.setattr(theme_switch, "_have", lambda cmd: True)
    monkeypatch.setattr(theme_switch, "_has_session_dbus", lambda: True)
    monkeypatch.setattr(theme_switch, "_kwrite", lambda *a: True)
    monkeypatch.setattr(theme_switch, "_broadcast_widget_style_change",
                        lambda style: True)
    monkeypatch.setattr(theme_switch.time, "sleep", lambda _s: None)

    result: dict = {}

    def run():
        try:
            result["ok"] = theme_switch.cycle_widget_style_live("kvantum")
        except BaseException as exc:  # ValueError would fail the test
            result["err"] = repr(exc)

    t = _threading.Thread(target=run)
    t.start()
    t.join(timeout=10)

    assert "err" not in result, (
        f"cycle_widget_style_live crashed off-thread: {result.get('err')}"
    )
    assert result.get("ok") is True


def test_patch_dock_transparency_reasserts_panel_opacity(monkeypatch, tmp_path):
    """The dock goes black when panelOpacity is dropped (a Global Theme apply
    from System Settings drops it), because the opaque panel background paints
    over the Acrylic Glass. patch_dock_transparency must re-assert
    panelOpacity=2 on floating panels and floatingApplets=1 on non-floating —
    on install, on switch, and on the manual System Settings path. Real run
    against a real plasmashellrc, no mocking of the patch itself."""
    import theme_switch
    cfg = tmp_path / ".config"
    cfg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
    prc = cfg / "plasmashellrc"
    prc.write_text(
        "[PlasmaViews][Panel 1]\n"
        "floating=0\n"
        "shell=org.kde.plasma.desktop\n"
        "\n"
        "[PlasmaViews][Panel 2]\n"
        "alignment=132\n"
        "floating=1\n"
        "shell=org.kde.plasma.desktop\n"
        "\n"
        "[PlasmaViews][Panel 2][Defaults]\n"
        "thickness=68\n"
    )

    assert theme_switch.patch_dock_transparency() is True
    text = prc.read_text()
    # Floating dock got the translucency that lets the glass show through.
    assert "panelOpacity=2" in text
    # Non-floating panel got floatingApplets.
    assert "floatingApplets=1" in text
    # The [Defaults] subsection is untouched (regex must not swallow it).
    assert "[PlasmaViews][Panel 2][Defaults]\nthickness=68" in text

    # Idempotent: a second run makes no further change.
    assert theme_switch.patch_dock_transparency() is False


def test_patch_dock_transparency_no_file_is_safe(monkeypatch, tmp_path):
    """No plasmashellrc yet (fresh account / CI) → no crash, returns False."""
    import theme_switch
    cfg = tmp_path / ".config"
    cfg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
    assert theme_switch.patch_dock_transparency() is False


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


# ── explicit native light/dark follow (one-shot; no watcher) ──────────


def test_detect_mode_by_system_prefers_portal(monkeypatch):
    """The portal color-scheme (what the native quick-settings toggle sets:
    1=dark, 2=light) wins over KDE's ColorScheme name. This is the value that
    actually changed when the user toggled, so Nautilus/GTK follows it."""
    import theme_switch
    monkeypatch.setattr(theme_switch, "_read_portal_color_scheme", lambda: 2)
    assert theme_switch.detect_mode_by_system() == "light"
    monkeypatch.setattr(theme_switch, "_read_portal_color_scheme", lambda: 1)
    assert theme_switch.detect_mode_by_system() == "dark"


def test_detect_mode_by_system_falls_back_to_colorscheme_name(monkeypatch):
    """No portal (0/no-preference or unreadable) → fall back to KDE's active
    ColorScheme name. None only when NEITHER can be read, so the caller
    leaves the mode untouched rather than guessing."""
    import theme_switch
    monkeypatch.setattr(theme_switch, "_read_portal_color_scheme", lambda: None)
    monkeypatch.setattr(theme_switch, "_kread",
                        lambda f, g, k: "MacTahoeLiquidKdeDark")
    assert theme_switch.detect_mode_by_system() == "dark"
    monkeypatch.setattr(theme_switch, "_kread",
                        lambda f, g, k: "MacTahoeLiquidKdeLight")
    assert theme_switch.detect_mode_by_system() == "light"
    monkeypatch.setattr(theme_switch, "_kread", lambda f, g, k: "")
    assert theme_switch.detect_mode_by_system() is None


def test_follow_system_applies_detected_mode(monkeypatch):
    """follow-system applies whatever mode the desktop currently wants, so a
    native toggle drives our full theme (GTK included)."""
    import theme_switch
    seen: list = []
    monkeypatch.setattr(theme_switch, "detect_mode_by_system", lambda: "light")
    monkeypatch.setattr(theme_switch, "_apply_unlocked",
                        lambda mode, **kw: seen.append((mode, kw)) or True)
    assert theme_switch.follow_system() == 0
    assert seen == [("light", {"context": "user"})]


def test_follow_system_noop_when_mode_unknown(monkeypatch):
    """When the current mode can't be read, follow-system does NOT guess and
    apply a mode — that would fight the user's real state. Success, no apply."""
    import theme_switch
    called: list = []
    monkeypatch.setattr(theme_switch, "detect_mode_by_system", lambda: None)
    monkeypatch.setattr(theme_switch, "apply",
                        lambda *a, **k: called.append(1) or True)
    assert theme_switch.follow_system() == 0
    assert called == []


def test_main_routes_follow_system_and_rejects_retired_watcher(monkeypatch):
    """follow-system remains an explicit one-shot command; the background
    watch-portal entry point is retired and must not be startable."""
    import theme_switch
    monkeypatch.setattr(theme_switch, "follow_system", lambda: 0)
    assert theme_switch.main(["follow-system"]) == 0
    assert theme_switch.main(["watch-portal"]) == 1


def test_session_env_uses_runtime_fallback_without_systemd(monkeypatch):
    """OpenRC cron has no user systemd manager.  A missing systemctl binary
    must fall back cleanly and invalidate an earlier bus-less cache."""
    import theme_switch
    called = []
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.setattr(
        theme_switch, "_run_user",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("no systemctl")),
    )

    def recover():
        called.append(True)
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=/run/user/1000/bus"

    monkeypatch.setattr(theme_switch, "_sync_session_env_runtime_dir", recover)
    theme_switch._HAS_DBUS = False

    theme_switch._sync_session_env()

    assert called == [True]
    assert theme_switch._HAS_DBUS is None


_APPLY_SUBCALLS = (
    "write_kde_theme_config", "_apply_wallpaper", "_apply_local_extras",
    "_apply_lookandfeel_live", "apply_cursortheme_live",
    "cycle_widget_style_live", "_qdbus",
)


def _stub_apply_subcalls(monkeypatch, calls, ret=True):
    import theme_switch
    monkeypatch.setattr(theme_switch, "_current_wallpapers", lambda: [])
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
    write_kwargs: list[dict] = []
    _stub_apply_subcalls(monkeypatch, calls)
    monkeypatch.setattr(
        theme_switch, "write_kde_theme_config",
        lambda mode, **kw: write_kwargs.append(kw) or True,
    )

    assert theme_switch.apply("dark", context="install") is True
    assert "_apply_lookandfeel_live" not in calls
    assert "apply_cursortheme_live" in calls
    assert "cycle_widget_style_live" in calls
    assert write_kwargs == [{"force_color_reload": True}]

    calls.clear()
    write_kwargs.clear()
    assert theme_switch.apply("dark") is True
    assert "_apply_lookandfeel_live" in calls
    assert write_kwargs == [{"force_color_reload": False}]


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


# ── smart per-mode wallpaper ownership ───────────────────────────────


def _smart_wallpaper_env(monkeypatch, tmp_path):
    import theme_switch

    home = tmp_path / "home"
    data = home / ".local/share"
    state = home / ".local/state"
    config = home / ".config"
    for path in (data / "wallpapers/MacTahoe", state, config):
        path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.delenv("FEAT_WALLPAPERS", raising=False)
    monkeypatch.delenv("MTTKDE_RESET_WALLPAPERS", raising=False)
    monkeypatch.delenv("MTTKDE_EXISTING_INSTALL", raising=False)
    return theme_switch, data / "wallpapers/MacTahoe"


def _wp(image, screen=0):
    return [{"screen": screen, "image": image}]


def test_first_install_applies_theme_wallpaper(monkeypatch, tmp_path):
    ts, theme = _smart_wallpaper_env(monkeypatch, tmp_path)
    custom = _wp("file:///pictures/first-install-custom.jpg")
    calls = []
    monkeypatch.setenv("FEAT_WALLPAPERS", "true")
    monkeypatch.setenv("MTTKDE_EXISTING_INSTALL", "false")
    monkeypatch.setattr(ts, "_current_wallpapers", lambda: custom)
    monkeypatch.setattr(
        ts, "_apply_theme_wallpaper",
        lambda mode: calls.append(mode) or (True, theme),
    )
    monkeypatch.setattr(
        ts, "_apply_wallpaper_snapshot",
        lambda snapshot: (_ for _ in ()).throw(
            AssertionError("first install must use the theme wallpaper")),
    )

    assert ts._apply_wallpaper("light", context="install") is True
    state = ts._load_wallpaper_state()
    assert calls == ["light"]
    assert state["modes"]["light"] == []
    assert state["last_applied"] == _wp(f"file://{theme}")


def test_theme_wallpaper_helper_failure_uses_config_fallback(
        monkeypatch, tmp_path):
    ts, theme = _smart_wallpaper_env(monkeypatch, tmp_path)
    current = _wp("file:///pictures/before-install.jpg")
    expected = _wp(f"file://{theme}")
    restored = []
    monkeypatch.setenv("FEAT_WALLPAPERS", "true")
    monkeypatch.setenv("MTTKDE_EXISTING_INSTALL", "false")
    monkeypatch.setattr(ts, "_current_wallpapers", lambda: current)
    monkeypatch.setattr(ts, "_apply_theme_wallpaper",
                        lambda mode: (False, theme))
    monkeypatch.setattr(
        ts, "_apply_wallpaper_snapshot",
        lambda snapshot: restored.append(snapshot) or True,
    )

    assert ts._apply_wallpaper("light", context="install") is True
    assert restored == [expected]
    assert ts._load_wallpaper_state()["last_applied"] == expected


def test_failed_wallpaper_switch_does_not_advance_active_mode(
        monkeypatch, tmp_path):
    ts, theme = _smart_wallpaper_env(monkeypatch, tmp_path)
    light = _wp(f"file://{theme}")
    ts._save_wallpaper_state({
        "version": 1,
        "initialized": True,
        "enabled": True,
        "active_mode": "light",
        "last_applied": light,
        "modes": {"light": [], "dark": []},
    })
    monkeypatch.setattr(ts, "_current_wallpapers", lambda: light)
    monkeypatch.setattr(ts, "_apply_theme_wallpaper",
                        lambda mode: (False, theme))
    monkeypatch.setattr(ts, "_apply_wallpaper_snapshot", lambda snapshot: False)

    assert ts._apply_wallpaper("dark") is False
    state = ts._load_wallpaper_state()
    assert state["active_mode"] == "light"
    assert state["last_applied"] == light


def test_reinstall_without_state_preserves_custom_wallpaper(
        monkeypatch, tmp_path):
    ts, _theme = _smart_wallpaper_env(monkeypatch, tmp_path)
    custom = _wp("file:///pictures/my-light-wallpaper.jpg")
    monkeypatch.setenv("FEAT_WALLPAPERS", "true")
    monkeypatch.setenv("MTTKDE_EXISTING_INSTALL", "true")
    monkeypatch.setattr(ts, "_current_wallpapers", lambda: custom)
    monkeypatch.setattr(
        ts, "_apply_theme_wallpaper",
        lambda mode: (_ for _ in ()).throw(
            AssertionError("reinstall overwrote a custom wallpaper")),
    )

    assert ts._apply_wallpaper("light", context="install") is True
    state = ts._load_wallpaper_state()
    assert state["modes"]["light"] == custom
    assert state["last_applied"] == custom


def test_switcher_remembers_different_custom_wallpapers_per_mode(
        monkeypatch, tmp_path):
    ts, theme = _smart_wallpaper_env(monkeypatch, tmp_path)
    theme_snapshot = _wp(f"file://{theme}")
    light_custom = _wp("file:///pictures/custom-light.jpg")
    dark_custom = _wp("file:///pictures/custom-dark.jpg")
    ts._save_wallpaper_state({
        "version": 1,
        "initialized": True,
        "enabled": True,
        "active_mode": "light",
        "last_applied": theme_snapshot,
        "modes": {"light": [], "dark": []},
    })
    current = {"value": light_custom}
    restored = []
    monkeypatch.setattr(ts, "_current_wallpapers",
                        lambda: current["value"])
    monkeypatch.setattr(ts, "_apply_theme_wallpaper",
                        lambda mode: (True, theme))
    monkeypatch.setattr(
        ts, "_apply_wallpaper_snapshot",
        lambda snapshot: restored.append(snapshot) or True,
    )

    # Leaving light captures the manual light choice; dark has no saved
    # choice yet, so it receives the bundled default.
    assert ts._apply_wallpaper("dark") is True
    assert ts._load_wallpaper_state()["modes"]["light"] == light_custom

    # The user chooses a different dark wallpaper. Returning to light saves
    # it, then restores the independent light choice.
    current["value"] = dark_custom
    assert ts._apply_wallpaper("light") is True
    state = ts._load_wallpaper_state()
    assert state["modes"]["dark"] == dark_custom
    assert restored == [light_custom]
    assert state["last_applied"] == light_custom


def test_explicit_wallpaper_reset_clears_both_custom_modes(
        monkeypatch, tmp_path):
    ts, theme = _smart_wallpaper_env(monkeypatch, tmp_path)
    light_custom = _wp("file:///pictures/custom-light.jpg")
    dark_custom = _wp("file:///pictures/custom-dark.jpg")
    ts._save_wallpaper_state({
        "version": 1,
        "initialized": True,
        "enabled": True,
        "active_mode": "light",
        "last_applied": light_custom,
        "modes": {"light": light_custom, "dark": dark_custom},
    })
    monkeypatch.setenv("FEAT_WALLPAPERS", "true")
    monkeypatch.setenv("MTTKDE_EXISTING_INSTALL", "true")
    monkeypatch.setenv("MTTKDE_RESET_WALLPAPERS", "true")
    monkeypatch.setattr(ts, "_current_wallpapers", lambda: light_custom)
    calls = []
    monkeypatch.setattr(
        ts, "_apply_theme_wallpaper",
        lambda mode: calls.append(mode) or (True, theme),
    )

    assert ts._apply_wallpaper("light", context="install") is True
    state = ts._load_wallpaper_state()
    assert calls == ["light"]
    assert state["modes"] == {"light": [], "dark": []}
    assert state["last_applied"] == _wp(f"file://{theme}")


def test_disabled_wallpaper_feature_never_changes_background(
        monkeypatch, tmp_path):
    ts, _theme = _smart_wallpaper_env(monkeypatch, tmp_path)
    custom = _wp("file:///pictures/leave-me-alone.jpg")
    monkeypatch.setenv("FEAT_WALLPAPERS", "false")
    monkeypatch.setattr(ts, "_current_wallpapers", lambda: custom)
    monkeypatch.setattr(
        ts, "_apply_theme_wallpaper",
        lambda mode: (_ for _ in ()).throw(AssertionError("wallpaper touched")),
    )
    monkeypatch.setattr(
        ts, "_apply_wallpaper_snapshot",
        lambda snapshot: (_ for _ in ()).throw(AssertionError("wallpaper touched")),
    )

    assert ts._apply_wallpaper("dark", context="install") is True
    state = ts._load_wallpaper_state()
    assert state["enabled"] is False
    assert state["last_applied"] == custom


def test_wallpaper_config_fallback_captures_each_desktop_screen(
        monkeypatch, tmp_path):
    ts, _theme = _smart_wallpaper_env(monkeypatch, tmp_path)
    appletsrc = (Path(os.environ["XDG_CONFIG_HOME"])
                 / "plasma-org.kde.plasma.desktop-appletsrc")
    appletsrc.write_text(
        "[Containments][10]\nplugin=org.kde.plasma.folder\nlastScreen=1\n"
        "[Containments][10][Wallpaper][org.kde.image][General]\n"
        "Image=file:///pictures/right.jpg\n"
        "[Containments][11]\nplugin=org.kde.plasma.folder\nlastScreen=0\n"
        "[Containments][11][Wallpaper][org.kde.image][General]\n"
        "Image=file:///pictures/left.jpg\n"
        "[Containments][12]\nplugin=org.kde.panel\nlastScreen=0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ts, "_evaluate_plasma_script", lambda script: None)

    assert ts._current_wallpapers() == [
        {"screen": 0, "image": "file:///pictures/left.jpg"},
        {"screen": 1, "image": "file:///pictures/right.jpg"},
    ]


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
                        lambda mode, **kw: False)
    assert theme_switch.apply("dark") is False

    # config ok + every live sub-call failing → still success
    calls.clear()
    _stub_apply_subcalls(monkeypatch, calls, ret=False)
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode, **kw: True)
    monkeypatch.setattr(theme_switch, "_apply_wallpaper",
                        lambda mode, **kwargs: True)
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


def test_reset_color_scheme_config_reports_write_failure(monkeypatch,
                                                         tmp_path):
    """Under sudo the uninstall color reset can fail while the step
    prints success. Failed deletes or a failed final write
    must return False so the caller can warn."""
    import theme_switch
    # Force the offline fallback: plasma-apply-colorscheme is "missing"
    # so reset_kde_color_scheme_config exercises apply_color_groups_direct.
    monkeypatch.setattr(theme_switch, "_have",
                        lambda cmd: cmd == "kwriteconfig6")
    # Supply a scheme file so the fallback does not early-out on a
    # missing BreezeLight.colors (CI containers don't ship it).
    scheme = tmp_path / "BreezeLight.colors"
    scheme.write_text("[Colors:Window]\nBackgroundNormal=239,240,241\n")
    monkeypatch.setattr(theme_switch, "_find_scheme_file", lambda s: scheme)

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


class _FakeResult:
    def __init__(self, returncode: int):
        self.returncode = returncode


def test_apply_color_scheme_prefers_plasma_apply_tool(monkeypatch):
    """The official plasma-apply-colorscheme rewrites the [Colors:*]
    groups and ColorSchemeHash exactly like the Colors KCM, so live Qt
    apps reload the palette. When the binary is present we must call it
    and not the manual rewrite."""
    import theme_switch
    seen: dict = {}
    monkeypatch.setattr(theme_switch, "_have",
                        lambda cmd: cmd == "plasma-apply-colorscheme")
    monkeypatch.setattr(theme_switch, "_run_user",
                        lambda cmd, **kw: seen.update(cmd=cmd) or
                        _FakeResult(0))
    assert theme_switch.apply_color_scheme("MacTahoeLiquidKdeDark") is True
    assert seen["cmd"] == ["plasma-apply-colorscheme",
                           "MacTahoeLiquidKdeDark"]


def test_apply_color_scheme_reports_tool_failure(monkeypatch):
    """A non-zero plasma-apply-colorscheme exit must propagate as False
    rather than falling through to a silent manual apply."""
    import theme_switch
    monkeypatch.setattr(theme_switch, "_have",
                        lambda cmd: cmd == "plasma-apply-colorscheme")
    monkeypatch.setattr(theme_switch, "_run_user",
                        lambda cmd, **kw: _FakeResult(1))
    assert theme_switch.apply_color_scheme("MacTahoeLiquidKdeDark") is False


def test_apply_color_scheme_survives_timeout(monkeypatch):
    """A hung plasma-apply-colorscheme must report failure, not raise
    through write_kde_theme_config into the apply step."""
    import subprocess
    import theme_switch

    def _hang(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 0))

    monkeypatch.setattr(theme_switch, "_have",
                        lambda cmd: cmd == "plasma-apply-colorscheme")
    monkeypatch.setattr(theme_switch, "_run_user", _hang)
    assert theme_switch.apply_color_scheme("MacTahoeLiquidKdeDark") is False


def test_apply_color_scheme_falls_back_to_manual(monkeypatch):
    """Offline / minimal systems without plasma-apply-colorscheme keep
    the working manual rewrite. The fallback must be used and mirror
    the scheme name straight through."""
    import theme_switch
    seen: dict = {}
    monkeypatch.setattr(theme_switch, "_have", lambda cmd: False)
    monkeypatch.setattr(theme_switch, "apply_color_groups_direct",
                        lambda scheme: seen.update(scheme=scheme) or True)
    assert theme_switch.apply_color_scheme("MacTahoeLiquidKdeLight") is True
    assert seen["scheme"] == "MacTahoeLiquidKdeLight"


def test_write_kde_theme_config_reports_write_failure(monkeypatch):
    import theme_switch
    # Force the offline fallback so the final color stage goes through
    # apply_color_groups_direct, not plasma-apply-colorscheme.
    monkeypatch.setattr(theme_switch, "_have",
                        lambda cmd: cmd == "kwriteconfig6")

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


def test_color_scheme_is_applied_before_target_name_is_stamped(monkeypatch):
    """KDE must see the outgoing scheme name when its color tool applies the
    target; stamping first left Plasma menus on the old live palette."""
    import theme_switch
    events: list[tuple[str, str]] = []
    monkeypatch.setattr(theme_switch, "_have",
                        lambda cmd: cmd == "kwriteconfig6")
    monkeypatch.setattr(
        theme_switch, "apply_color_scheme",
        lambda scheme: events.append(("apply", scheme)) or True,
    )

    def write(*args):
        if args[1:7] == ("kdeglobals", "--group", "General", "--key",
                         "ColorScheme", "MacTahoeLiquidKdeDark"):
            events.append(("stamp", "MacTahoeLiquidKdeDark"))
        return True

    monkeypatch.setattr(theme_switch, "_kwrite", write)
    assert theme_switch.write_kde_theme_config("dark") is True
    assert events == [
        ("apply", "MacTahoeLiquidKdeDark"),
        ("stamp", "MacTahoeLiquidKdeDark"),
    ]


def test_install_forces_real_color_transition_when_target_is_already_named(
        monkeypatch):
    """A reinstall heals an on-disk-dark/runtime-light split by making KDE
    observe a real light-to-dark transition."""
    import theme_switch
    events: list[tuple[str, str]] = []
    monkeypatch.setattr(theme_switch, "_have",
                        lambda cmd: cmd == "kwriteconfig6")
    monkeypatch.setattr(theme_switch, "_kread",
                        lambda file, group, key: "MacTahoeLiquidKdeDark")
    monkeypatch.setattr(
        theme_switch, "apply_color_scheme",
        lambda scheme: events.append(("apply", scheme)) or True,
    )

    def write(*args):
        if args[1:7] == ("kdeglobals", "--group", "General", "--key",
                         "ColorScheme", "MacTahoeLiquidKdeDark"):
            events.append(("stamp", "MacTahoeLiquidKdeDark"))
        return True

    monkeypatch.setattr(theme_switch, "_kwrite", write)
    assert theme_switch.write_kde_theme_config(
        "dark", force_color_reload=True,
    ) is True
    assert events == [
        ("apply", "MacTahoeLiquidKdeLight"),
        ("apply", "MacTahoeLiquidKdeDark"),
        ("stamp", "MacTahoeLiquidKdeDark"),
    ]


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

    # This guard specifically verifies the systemd command path. Pin the
    # backend because container runners have no booted init and correctly
    # resolve to the separately-tested OpenRC/crontab path.
    env = {"THEME_MODE": "auto", "MTTKDE_INIT": "systemd"}
    _run_step("theme_switch", "install", env, shim_dir=shim_dir)
    _run_step("theme_switch", "uninstall", env, shim_dir=shim_dir)

    assert log_file.exists(), (
        "shim was never invoked — step bypassed PATH (absolute path?)"
    )
    assert "systemctl --user" in log_file.read_text()


def test_switch_step_removes_old_watcher_before_replacing_binary(
        monkeypatch, tmp_path):
    """An upgrade must stop the old process and remove its autostart before
    copying the new switcher."""
    import steps.theme_switch as step

    source = tmp_path / "theme_switch.py"
    source.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    destination = tmp_path / "bin/mac-tahoe-theme-switch"
    events: list[str] = []
    original_copy = shutil.copy2

    monkeypatch.setattr(step, "PY_SRC", source)
    monkeypatch.setattr(step, "BIN_DEST", destination)
    monkeypatch.setattr(step, "SVC_DIR", tmp_path / "systemd")
    monkeypatch.setattr(step, "stop_gtk_sync_watcher",
                        lambda: events.append("stop"))
    monkeypatch.setattr(step, "_watcher_pids", lambda: [])
    monkeypatch.setattr(step, "_teardown_gtk_sync_autostart",
                        lambda: events.append("teardown"))
    monkeypatch.setattr(step.shutil, "copy2",
                        lambda src, dst:
                        events.append("copy") or original_copy(src, dst))
    monkeypatch.setattr(step, "theme_mode", lambda: "dark")
    monkeypatch.setattr(step, "_teardown_units", lambda: None)
    monkeypatch.setattr(step, "remove_periodic", lambda tag: None)
    monkeypatch.setattr(step, "ok", lambda message: None)
    monkeypatch.setattr(step, "warn", lambda message: None)

    step.install()

    assert events[:3] == ["stop", "teardown", "copy"]


def test_switch_step_install_uninstall_reinstall(sandbox, tmp_path):
    """Round-trip the install/uninstall step. Asserts:
    - install drops the script + service + timer under $XDG_CONFIG_HOME
    - uninstall removes them
    - leftover apply.service (from an older install layout) is cleaned up
    - kdeglobals AutomaticLookAndFeel keys are reset on uninstall."""
    shim_dir = make_live_shim_dir(tmp_path)

    # Pin systemd so this exercises the timer path regardless of the CI host
    # (which resolves to OpenRC). The OpenRC crontab path has its own tests.
    env = {"THEME_MODE": "auto", "MTTKDE_INIT": "systemd"}
    bin_path = sandbox / ".local/bin/mac-tahoe-theme-switch"
    svc_dir = sandbox / ".config/systemd/user"
    autostart = (sandbox / ".config/autostart"
                 / "mac-tahoe-liquid-kde-gtk-sync.desktop")
    # Seed the file left by 0.36.x-0.38.x; install must remove it.
    autostart.parent.mkdir(parents=True, exist_ok=True)
    autostart.write_text("Exec=watch-portal\n")
    _run_step("theme_switch", "install", env, shim_dir=shim_dir)
    assert bin_path.is_file() and bin_path.stat().st_mode & 0o111
    assert (svc_dir / "mac-tahoe-liquid-kde-theme.service").is_file()
    assert (svc_dir / "mac-tahoe-liquid-kde-theme.timer").is_file()
    assert not autostart.exists()

    state_dir = sandbox / ".local/state/mac-tahoe-liquid-kde"
    state_dir.mkdir(parents=True)
    wallpaper_state = state_dir / "wallpapers.json"
    layout_marker = state_dir / "layout-installed"
    wallpaper_state.write_text("{}\n")
    layout_marker.write_text("1\n")

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
    assert not autostart.exists()
    assert not wallpaper_state.exists()
    assert not layout_marker.exists()


def test_switch_step_openrc_schedules_via_crontab_not_systemd(sandbox, tmp_path):
    """On OpenRC (forced) the auto theme flip installs a crontab line at
    06:00/18:00 and never installs a systemd timer. The shimmed crontab
    logs the stdin write so we can confirm both times were scheduled."""
    shim_dir = make_live_shim_dir(tmp_path)
    log_file = shim_dir / "calls.log"

    _run_step("theme_switch", "install",
              {"THEME_MODE": "auto", "MTTKDE_INIT": "openrc"},
              shim_dir=shim_dir)

    calls = log_file.read_text()
    assert "crontab -" in calls          # stdin write happened
    # No systemd timer file on disk under OpenRC.
    svc_dir = sandbox / ".config/systemd/user"
    assert not (svc_dir / "mac-tahoe-liquid-kde-theme.timer").exists()
    # enable/start of the user timer must not have been attempted.
    assert "systemctl --user enable" not in calls
    assert not (sandbox / ".config/autostart"
                / "mac-tahoe-liquid-kde-gtk-sync.desktop").exists()
    assert "systemctl --user start" not in calls


def test_switch_step_openrc_uninstall_strips_crontab(sandbox, tmp_path):
    shim_dir = make_live_shim_dir(tmp_path)
    log_file = shim_dir / "calls.log"
    _run_step("theme_switch", "uninstall",
              {"THEME_MODE": "auto", "MTTKDE_INIT": "openrc"},
              shim_dir=shim_dir)
    # uninstall reads the crontab (to filter our tag) on the OpenRC path.
    assert "crontab -l" in log_file.read_text()
