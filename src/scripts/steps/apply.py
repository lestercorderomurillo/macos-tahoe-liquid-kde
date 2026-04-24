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
from theme_switch import reset_kde_color_scheme_config

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
        subprocess.run(["kbuildsycoca6", "--noincremental"],
                       check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
            subprocess.run(
                ["plasma-apply-wallpaperimage", str(wp)], check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            ok(f"Wallpaper applied ({wp.name})")

    _flush_caches()

    switch = HOME / ".local/bin/mac-tahoe-theme-switch"
    if switch.is_file() and (switch.stat().st_mode & 0o111):
        # "install" context skips plasma-apply-lookandfeel + refreshCurrentShell
        # which crash plasmashell (QML teardown race). The plasma restart at
        # the end of install loads the correct theme from config; Kvantum/GTK
        # are still applied immediately so already-open windows update.
        subprocess.run(
            [str(switch), theme_mode(), "install"], check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        ok(f"Theme applied ({theme_mode()})")

    if have("nautilus"):
        subprocess.run(["nautilus", "-q"], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ok("Nautilus restarted")

    print("  …  Restarting KWin", end="\r", flush=True)
    if feat_enabled("ACRYLIC_GLASS"):
        qdbus_call("org.kde.KWin", "/Effects",
                   "org.kde.kwin.Effects.loadEffect", "liquidglass")
        time.sleep(1)
    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    time.sleep(3)
    ok("KWin restarted ")


def restart_plasma() -> None:
    print("  …  Restarting Plasma", end="\r", flush=True)
    # let panels created by the layout script fully initialise
    time.sleep(6)

    # SIGKILL skips the QML engine teardown race (SIGABRT/SIGSEGV in
    # org.kde.panel.so → Applet::~Applet → deleteChildren cascade) that
    # kquitapp6/SIGTERM consistently trigger. Config is already on disk
    # (layout JS + plasmashellrc patching ran above).
    if subprocess.run(
        ["systemctl", "--user", "kill", "--signal=KILL", "plasma-plasmashell"],
        check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode != 0:
        for line in subprocess.run(
            ["pgrep", "-x", "plasmashell"],
            check=False, capture_output=True, text=True,
        ).stdout.splitlines():
            try:
                import os as _os
                _os.kill(int(line), signal.SIGKILL)
            except (OSError, ValueError):
                pass

    time.sleep(1)
    if subprocess.run(
        ["systemctl", "--user", "start", "plasma-plasmashell"],
        check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode != 0:
        subprocess.Popen(
            ["kstart", "plasmashell"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    for _ in range(15):
        if subprocess.run(["pgrep", "-x", "plasmashell"], check=False,
                          stdout=subprocess.DEVNULL).returncode == 0:
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
    # Reset look-and-feel to Breeze. plasma-apply-lookandfeel rewrites the
    # "defaults" layer from the applied LAF package; without it, kdedefaults/
    # keeps pointing at our theme and Plasma re-resolves those values on
    # next login, undoing individual step uninstalls.
    if have("plasma-apply-lookandfeel"):
        subprocess.run(
            ["plasma-apply-lookandfeel", "-a", "org.kde.breeze.desktop"],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        ok("Look-and-feel reset to Breeze")

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
            if have("plasma-apply-cursortheme"):
                subprocess.run(
                    ["plasma-apply-cursortheme", "breeze_cursors"], check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            ok("Cursor reset")
        if feat_enabled("ICONS"):
            kw_write("--file", "kdeglobals", "--group", "Icons",
                     "--key", "Theme", "breeze")
            subprocess.run(
                ["dbus-send", "--session", "--type=signal",
                 "/KIconLoader", "org.kde.KIconLoader.iconChanged", "int32:0"],
                check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            ok("Icons reset")
        if feat_enabled("WALLPAPERS"):
            for p in ("/usr/share/wallpapers/Next", "/usr/share/wallpapers/Breeze",
                      "/usr/share/wallpapers/Flow"):
                if Path(p).is_dir():
                    if have("plasma-apply-wallpaperimage"):
                        subprocess.run(
                            ["plasma-apply-wallpaperimage", p], check=False,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        )
                    ok("Wallpaper reset")
                    break
        reset_kde_color_scheme_config("BreezeLight")
        ok("Color scheme reset")

    _flush_caches()

    if have("qdbus6") or have("qdbus"):
        qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    time.sleep(2)
    ok("KWin reconfigured")
