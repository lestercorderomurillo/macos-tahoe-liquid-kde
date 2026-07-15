import datetime as _dt
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

from steps._helpers import (
    HOME, fail, feat_enabled, have, info, kw_write, ok, qdbus_call, theme_mode, warn,
)
from utils import qdbus_cmd, run_user
from theme_switch import (
    apply_cursortheme_live,
    cycle_widget_style_live,
    reset_kde_color_scheme_config,
    _apply_lookandfeel_live,
)

# Cache files / dirs flushed during install + uninstall before Plasma reloads.
_CACHES = (
    ".cache/icon-cache.kcache",
    ".cache/kiconthemes",
    ".cache/ksvg-elements",
    ".cache/gtk-3.0",
    ".cache/gtk-4.0",
)
_CACHE_GLOBS = (
    ".cache/plasma-svgelements-*",
    ".cache/plasma_theme_*",
    ".cache/plasmashell*",
    ".cache/ksycoca6*",
)

_FONTS_INSTALL = {
    "font":                 "SF Pro Text,10,-1,5,50,0,0,0,0,0",
    "menuFont":             "SF Pro Text,10,-1,5,50,0,0,0,0,0",
    "toolBarFont":          "SF Pro Text,10,-1,5,50,0,0,0,0,0",
    "taskbarFont":          "SF Pro Text,10,-1,5,50,0,0,0,0,0",
    "smallestReadableFont": "SF Pro Text,8,-1,5,50,0,0,0,0,0",
    "fixed":                "SF Mono,10,-1,5,50,0,0,0,0,0",
}
_FONTS_RESET = {
    "font":                 "Noto Sans,10,-1,5,50,0,0,0,0,0",
    "menuFont":             "Noto Sans,10,-1,5,50,0,0,0,0,0",
    "toolBarFont":          "Noto Sans,10,-1,5,50,0,0,0,0,0",
    "taskbarFont":          "Noto Sans,10,-1,5,50,0,0,0,0,0",
    "smallestReadableFont": "Noto Sans,8,-1,5,50,0,0,0,0,0",
    "fixed":                "Hack,10,-1,5,50,0,0,0,0,0",
}

# Timeout for the fire-and-forget live-apply calls; run_user has none.
_LIVE_APPLY_TIMEOUT = 15


def _run_live(cmd: list[str]) -> None:
    """Run a best-effort live-apply command, bounded by a timeout so a
    stuck KDE endpoint can't freeze the installer."""
    try:
        run_user(
            cmd, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=_LIVE_APPLY_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        pass


# The standalone switcher chains its own 15-20s bounded subcalls (wallpaper,
# cursor, kvantum); the shared 15s cap used to kill it mid-apply (#37).
_THEME_SWITCH_TIMEOUT = 90


def _run_theme_switch_install(switch: Path) -> int | None:
    """Exit code of the standalone switcher, or None on timeout."""
    try:
        return run_user(
            [str(switch), theme_mode(), "install"], check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=_THEME_SWITCH_TIMEOUT,
        ).returncode
    except subprocess.TimeoutExpired:
        return None


def _refresh_desktop_database() -> None:
    """Rebuild mimeinfo.cache: a stale cache leaves launcher/taskbar apps
    missing after a theme switch. User dir as user; the system dir needs root."""
    from steps._helpers import _as_root
    if not have("update-desktop-database"):
        return
    user_apps = HOME / ".local/share/applications"
    if user_apps.is_dir():
        _run_live(["update-desktop-database", str(user_apps)])
    sys_apps = Path("/usr/share/applications")
    if sys_apps.is_dir():
        try:
            with _as_root():
                subprocess.run(
                    ["update-desktop-database", str(sys_apps)],
                    check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=_LIVE_APPLY_TIMEOUT,
                )
        except (subprocess.TimeoutExpired, OSError, PermissionError):
            pass


def _flush_caches() -> None:
    for sub in _CACHES:
        p = HOME / sub
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file():
            try: p.unlink()
            except OSError: pass
    for pat in _CACHE_GLOBS:
        for p in HOME.glob(pat):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                try: p.unlink()
                except OSError: pass
    # Refresh mimeinfo.cache before sycoca so kbuildsycoca6 sees every app.
    _refresh_desktop_database()
    if have("kbuildsycoca6"):
        _run_live(["kbuildsycoca6", "--noincremental"])
    ok("Caches flushed")


def _wallpaper_path() -> Path | None:
    base = HOME / ".local/share/wallpapers"
    auto = base / "MacTahoe"
    if auto.is_dir():
        return auto
    mode = theme_mode()
    if mode == "light":
        legacy = base / "MacTahoe-Light"
    elif mode == "dark":
        legacy = base / "MacTahoe-Dark"
    else:
        h = _dt.datetime.now().hour
        legacy = base / ("MacTahoe-Light" if 6 <= h < 18 else "MacTahoe-Dark")
    return legacy if legacy.is_dir() else None


def _live_plasma_ready_quick() -> bool:
    """Probe whether live Plasma mutations are worth trying. Uninstall
    restarts plasmashell anyway, so a missing display/shell means skip the
    live niceties and let the restart pick up the on-disk config."""
    import os as _os
    if not (_os.environ.get("DISPLAY") or _os.environ.get("WAYLAND_DISPLAY")):
        return False
    try:
        return subprocess.run(
            ["pgrep", "-x", "plasmashell"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=3,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def install() -> None:
    if have("kwriteconfig6") and feat_enabled("FONTS"):
        for key, val in _FONTS_INSTALL.items():
            kw_write("--file", "kdeglobals", "--group", "General",
                     "--key", key, val)
        kw_write("--file", "kdeglobals", "--group", "WM",
                 "--key", "activeFont", "SF Pro Display,11,-1,5,63,0,0,0,0,0")
        ok("Fonts installed")

    if feat_enabled("WALLPAPERS"):
        wp = _wallpaper_path()
        if wp and have("plasma-apply-wallpaperimage"):
            _run_live(["plasma-apply-wallpaperimage", str(wp)])
            ok(f"Wallpaper applied ({wp.name})")

    _flush_caches()

    switch = HOME / ".local/bin/mac-tahoe-theme-switch"
    if switch.is_file() and (switch.stat().st_mode & 0o111):
        # "install" context skips live plasmashell mutation (first-session and
        # QML teardown races); the final Plasma restart loads theme from config.
        rc = _run_theme_switch_install(switch)
        if rc == 0:
            ok(f"Theme applied ({theme_mode()})")
        elif rc is None:
            warn("Theme switch timed out, config may be partial")
        else:
            warn(f"Theme switch failed (exit {rc})")

    print("  …  Restarting KWin", end="\r", flush=True)
    if feat_enabled("ACRYLIC_GLASS"):
        qdbus_call("org.kde.KWin", "/Effects",
                   "org.kde.kwin.Effects.loadEffect", "liquidglass")
        time.sleep(1)
    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    time.sleep(3)
    ok("KWin restarted ")


def restart_plasma() -> None:
    def _run_quick(cmd: list[str], *, capture_output: bool = False):
        try:
            kwargs = {
                "check": False,
                "timeout": 8,
            }
            if capture_output:
                kwargs["capture_output"] = True
                kwargs["text"] = True
            else:
                kwargs["stdout"] = subprocess.DEVNULL
                kwargs["stderr"] = subprocess.DEVNULL
            return run_user(cmd, **kwargs)
        except subprocess.TimeoutExpired:
            if capture_output:
                return subprocess.CompletedProcess(cmd, 124, stdout="", stderr="")
            return subprocess.CompletedProcess(cmd, 124)

    print("  …  Restarting Plasma", end="\r", flush=True)
    # let panels created by the layout script fully initialise
    time.sleep(6)

    # SIGKILL skips the QML teardown crash (Applet::~Applet cascade) that
    # kquitapp6/SIGTERM reliably trigger; config is already on disk.
    if _run_quick(
        ["systemctl", "--user", "kill", "--signal=KILL", "plasma-plasmashell"],
    ).returncode != 0:
        for line in _run_quick(
            ["pgrep", "-x", "plasmashell"],
            capture_output=True,
        ).stdout.splitlines():
            try:
                import os as _os
                _os.kill(int(line), signal.SIGKILL)
            except (OSError, ValueError):
                pass

    time.sleep(1)
    if _run_quick(
        ["systemctl", "--user", "start", "plasma-plasmashell"],
    ).returncode != 0:
        from utils import drop_privs_in_child as _drop
        subprocess.Popen(
            ["kstart", "plasmashell"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
            preexec_fn=_drop,
        )
    for _ in range(15):
        if _run_quick(["pgrep", "-x", "plasmashell"]).returncode == 0:
            break
        time.sleep(1)
    time.sleep(4)
    ok("Plasma restarted ")


def _scrub_kdedefaults() -> None:
    # The scrub lives in a bundled kconf_update helper (issue #56); run just
    # that one here — uninstall must not touch appletsrc or install anything.
    from steps.kconf_update import run_migration
    run_migration("mac-tahoe-scrub-kdedefaults.sh")
    ok("kdedefaults cleaned")


def uninstall() -> None:
    # Keep Breeze on disk as the source of truth, then best-effort the live
    # switch only when the full Plasma session is ready enough for it.
    if have("kwriteconfig6"):
        kw_write("--file", "kdeglobals", "--group", "KDE",
                 "--key", "LookAndFeelPackage", "org.kde.breeze.desktop")

    _scrub_kdedefaults()

    plasmarc = HOME / ".config/plasmarc"
    if plasmarc.is_file():
        text = plasmarc.read_text()
        # Strip [Theme-plasmathemeexplorer] when it caches our theme name.
        text = re.sub(
            r"\[Theme-plasmathemeexplorer\][^\[]*?(?=\n\[|\Z)",
            "", text,
        )
        plasmarc.write_text(text)

    if have("kwriteconfig6"):
        if feat_enabled("FONTS"):
            for key, val in _FONTS_RESET.items():
                kw_write("--file", "kdeglobals", "--group", "General",
                         "--key", key, val)
            kw_write("--file", "kdeglobals", "--group", "WM",
                     "--key", "activeFont", "Noto Sans,10,-1,5,50,0,0,0,0,0")
            ok("Fonts reset")
        if feat_enabled("CURSORS"):
            kw_write("--file", "kcminputrc", "--group", "Mouse",
                     "--key", "cursorTheme", "breeze_cursors")
            ok("Cursor reset")
        # Reset icons UNCONDITIONALLY (not gated on the ICONS feature): the
        # MacTahoe icon dirs are deleted later, so point config at breeze first.
        kw_write("--file", "kdeglobals", "--group", "Icons",
                 "--key", "Theme", "breeze")
        _run_live(
            ["dbus-send", "--session", "--type=signal",
             "/KIconLoader", "org.kde.KIconLoader.iconChanged", "int32:0"]
        )
        ok("Icons reset")
        if feat_enabled("WALLPAPERS"):
            for p in ("/usr/share/wallpapers/Next", "/usr/share/wallpapers/Breeze",
                      "/usr/share/wallpapers/Flow"):
                if Path(p).is_dir():
                    if have("plasma-apply-wallpaperimage"):
                        _run_live(["plasma-apply-wallpaperimage", p])
                    ok("Wallpaper reset")
                    break
        if reset_kde_color_scheme_config("BreezeLight"):
            ok("Color scheme reset")
        else:
            warn("Color scheme reset failed")

    _flush_caches()

    live_ready = _live_plasma_ready_quick()

    # Unresponsive session is fine by design — the final plasmashell restart
    # picks up the on-disk Breeze config (see _live_plasma_ready_quick).
    if live_ready:
        if _apply_lookandfeel_live("org.kde.breeze.desktop"):
            ok("Look-and-feel applied live")
        else:
            warn("Live Breeze look-and-feel apply skipped")

    # Qt apps started under Kvantum keep its style instance alive after the
    # LAF switch; cycling widgetStyle forces re-instantiation without restart.
    if live_ready:
        if not cycle_widget_style_live("Breeze"):
            warn("Widget style cycle failed")

    if feat_enabled("CURSORS") and live_ready:
        if apply_cursortheme_live("breeze_cursors"):
            ok("Cursor applied live")
        else:
            warn("Live cursor apply skipped")

    if live_ready and qdbus_cmd() is not None:
        qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
        time.sleep(2)
        ok("KWin reconfigured")
