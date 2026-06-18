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
    """Best-effort probe for whether live Plasma mutations are worth trying.

    Uninstall restarts plasmashell at the end anyway, so spending minutes
    waiting for DBus/display recovery after caches are flushed is pure UX
    pain. Look for a display and a live plasmashell; if either is missing,
    skip the live niceties and let the final Plasma restart pick up the
    on-disk Breeze config."""
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
        # "install" context skips live plasmashell mutation, which is where
        # the first-session and QML teardown races have shown up. The Plasma
        # restart at the end of install loads the correct theme from config;
        # Kvantum/GTK are still applied immediately so already-open windows
        # update.
        _run_live([str(switch), theme_mode(), "install"])
        ok(f"Theme applied ({theme_mode()})")

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

    # SIGKILL skips the QML engine teardown race (SIGABRT/SIGSEGV in
    # org.kde.panel.so → Applet::~Applet → deleteChildren cascade) that
    # kquitapp6/SIGTERM consistently trigger. Config is already on disk
    # (layout JS + plasmashellrc patching ran above).
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
    base = HOME / ".config/kdedefaults"
    if not base.is_dir():
        return
    pattern = re.compile(r"mac[-.]?tahoe|mactahoe|liquid", re.IGNORECASE)
    decl = re.compile(
        r"^(ColorScheme|Theme|name|cursorTheme|theme|library)\s*=.*"
        r"(mac[-.]?tahoe|mactahoe|MacTahoe|liquid).*$",
        re.MULTILINE,
    )
    for fn in ("package", "kdeglobals", "plasmarc", "kcminputrc",
               "kwinrc", "ksplashrc", "kscreenlockerrc"):
        f = base / fn
        if not f.is_file():
            continue
        try:
            text = f.read_text()
        except OSError:
            continue
        if not pattern.search(text):
            continue
        if fn == "package":
            f.write_text("org.kde.breeze.desktop\n")
            continue
        f.write_text(decl.sub("", text))
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
        if feat_enabled("ICONS"):
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
        reset_kde_color_scheme_config("BreezeLight")
        ok("Color scheme reset")

    _flush_caches()

    live_ready = _live_plasma_ready_quick()

    # If the session isn't responsive, the final plasmashell restart picks
    # up the on-disk Breeze config — no warning needed, that path is by
    # design (see ``_live_plasma_ready_quick``).
    if live_ready:
        if _apply_lookandfeel_live("org.kde.breeze.desktop"):
            ok("Look-and-feel applied live")
        else:
            warn("Live Breeze look-and-feel apply skipped")

    # Even after switching to the Breeze LAF, Qt apps that were started
    # under Kvantum keep its style plugin instance alive — the right-click
    # menus on plasmashell stay glass/translucent until something forces a
    # re-instantiation. Cycling widgetStyle does that without a restart.
    if live_ready:
        cycle_widget_style_live("Breeze")

    if feat_enabled("CURSORS") and live_ready:
        if apply_cursortheme_live("breeze_cursors"):
            ok("Cursor applied live")
        else:
            warn("Live cursor apply skipped")

    if live_ready and qdbus_cmd() is not None:
        qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
        time.sleep(2)
        ok("KWin reconfigured")
