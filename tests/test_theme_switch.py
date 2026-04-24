"""Behaviour tests for installer/theme_switch.py — color group surgery,
mode detection, and the install/uninstall step."""

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
    from installer.theme_switch import apply_color_groups_direct
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
    from installer.theme_switch import apply_color_groups_direct
    # Should return False, not raise.
    assert apply_color_groups_direct("NonExistent") is False


def test_no_stale_breeze_values(seeded_color_schemes):
    seed_breeze_light(seeded_color_schemes)
    _apply("MacTahoeLiquidKdeDark")
    kdeglobals = seeded_color_schemes / ".config/kdeglobals"
    assert ini_get(kdeglobals, "Colors:Window", "BackgroundNormal") != "239,240,241"
    assert ini_get(kdeglobals, "Colors:View", "BackgroundNormal") != "255,255,255"


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
    from installer import theme_switch

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
    from installer import theme_switch

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
    from installer import theme_switch

    data = tmp_path / "data"
    wallpapers = data / "wallpapers"
    (wallpapers / "MacTahoe").mkdir(parents=True)
    (wallpapers / "MacTahoe-Light").mkdir()
    (wallpapers / "MacTahoe-Dark").mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(data))

    assert theme_switch._wallpaper_path("light") == wallpapers / "MacTahoe"
    assert theme_switch._wallpaper_path("dark") == wallpapers / "MacTahoe"


def test_apply_extras_syncs_wallpaper(monkeypatch, tmp_path):
    from installer import theme_switch

    calls = []
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home/.cache").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(theme_switch, "_apply_wallpaper",
                        lambda mode: calls.append(("wallpaper", mode)) or True)
    monkeypatch.setattr(theme_switch, "_have", lambda cmd: False)

    theme_switch.apply_extras("dark")
    assert ("wallpaper", "dark") in calls


def test_apply_skips_live_lookandfeel_during_boot(monkeypatch):
    from installer import theme_switch

    calls = []
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode: calls.append(("write", mode)))
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live",
                        lambda laf: calls.append(("laf", laf)))
    monkeypatch.setattr(theme_switch, "apply_extras",
                        lambda mode: calls.append(("extras", mode)))
    monkeypatch.setattr(theme_switch, "_qdbus",
                        lambda *args: calls.append(("qdbus", args)))

    assert theme_switch.apply("dark", "boot") is True
    assert ("write", "dark") in calls
    assert ("extras", "dark") in calls
    assert not any(c[0] == "laf" for c in calls)
    assert not any(c[0] == "qdbus" and c[1][0] == "org.kde.plasmashell"
                   for c in calls)


def test_apply_uses_live_lookandfeel_after_boot(monkeypatch):
    from installer import theme_switch

    calls = []
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode: calls.append(("write", mode)))
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live",
                        lambda laf: calls.append(("laf", laf)))
    monkeypatch.setattr(theme_switch, "apply_extras",
                        lambda mode: calls.append(("extras", mode)))
    monkeypatch.setattr(theme_switch, "_qdbus",
                        lambda *args: calls.append(("qdbus", args)))

    assert theme_switch.apply("light") is True
    assert ("laf", theme_switch.LAF_LIGHT) in calls
    assert any(c[0] == "qdbus" and c[1][0] == "org.kde.plasmashell"
               for c in calls)


def test_apply_skips_live_lookandfeel_for_scheduled_transition(monkeypatch):
    from installer import theme_switch

    calls = []
    monkeypatch.setattr(theme_switch, "write_kde_theme_config",
                        lambda mode: calls.append(("write", mode)))
    monkeypatch.setattr(theme_switch, "_apply_lookandfeel_live",
                        lambda laf: calls.append(("laf", laf)))
    monkeypatch.setattr(theme_switch, "apply_extras",
                        lambda mode: calls.append(("extras", mode)))
    monkeypatch.setattr(theme_switch, "_qdbus",
                        lambda *args: calls.append(("qdbus", args)))

    assert theme_switch.apply("dark", "scheduled") is True
    assert ("write", "dark") in calls
    assert ("extras", "dark") in calls
    assert not any(c[0] == "laf" for c in calls)
    assert any(c[0] == "qdbus" and c[1][0] == "org.kde.plasmashell"
               for c in calls)


def test_auto_mode_uses_scheduled_context(monkeypatch):
    from installer import theme_switch

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
         f"from installer.steps.{step_name} import {phase}; {phase}()"],
        check=False, env=full, cwd=str(Path(__file__).resolve().parent.parent),
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
