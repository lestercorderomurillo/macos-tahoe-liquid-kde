#!/usr/bin/env python3
"""Light/dark theme switcher for MacTahoe Liquid KDE.

Plasma 6's lookandfeelautoswitcher KDED module switches the colour scheme,
plasma theme, icons, cursors, aurorae and wallpaper on its own. This script
covers what Plasma does NOT switch automatically (Kvantum, GTK 2/3/4, icon
caches) and rewrites the [Colors:*]/[ColorEffects:*]/[WM] groups in
kdeglobals directly — ``plasma-apply-colorscheme`` is unreliable and can
silently leave stale palette values from a previous scheme.

Usage:
    mac-tahoe-theme-switch {light|dark|auto|watch|reset} [boot|install]
"""

import datetime as _dt
import hashlib
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


LAF_LIGHT = "org.kde.mac-tahoe-liquid-kde.light"
LAF_DARK = "org.kde.mac-tahoe-liquid-kde.dark"
_SETTLED_LIVE_APPLY_MIN_PLASMASHELL_AGE_SECONDS = 45


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _xdg_config() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or
                str(Path.home() / ".config"))


def _kdeglobals_path() -> Path:
    return _xdg_config() / "kdeglobals"


def _qdbus(*args: str) -> bool:
    """Fire-and-forget qdbus call bounded by 10s so a stuck KWin / plasma
    DBus endpoint can't freeze the switcher (which would in turn freeze
    the installer that's waiting on the switcher's exit)."""
    for q in ("qdbus6", "qdbus"):
        if _have(q):
            try:
                return subprocess.run(
                    [q, *args], check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=10,
                ).returncode == 0
            except subprocess.TimeoutExpired:
                return False
    return False


_HAS_DBUS: bool | None = None


def _has_session_dbus() -> bool:
    global _HAS_DBUS
    if _HAS_DBUS is not None:
        return _HAS_DBUS
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS") or not _have("dbus-send"):
        _HAS_DBUS = False
        return _HAS_DBUS
    try:
        _HAS_DBUS = subprocess.run(
            ["dbus-send", "--session", "--print-reply",
             "--dest=org.freedesktop.DBus", "/org/freedesktop/DBus",
             "org.freedesktop.DBus.ListNames"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=5,
        ).returncode == 0
    except subprocess.TimeoutExpired:
        _HAS_DBUS = False
    return _HAS_DBUS


def _sync_session_env() -> None:
    """Refresh session env vars from the user systemd manager."""
    try:
        res = subprocess.run(
            ["systemctl", "--user", "show-environment"],
            check=False, capture_output=True, text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return
    if res.returncode != 0:
        return
    wanted = {
        "DBUS_SESSION_BUS_ADDRESS",
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "XAUTHORITY",
        "XDG_CURRENT_DESKTOP",
        "XDG_RUNTIME_DIR",
        "XDG_SESSION_TYPE",
    }
    for line in res.stdout.splitlines():
        key, _, value = line.partition("=")
        if key in wanted and value:
            os.environ[key] = value


def _session_bus_has_name(name: str) -> bool:
    if not _has_session_dbus():
        return False
    try:
        res = subprocess.run(
            ["dbus-send", "--session", "--print-reply",
             "--dest=org.freedesktop.DBus", "/org/freedesktop/DBus",
             "org.freedesktop.DBus.NameHasOwner", f"string:{name}"],
            check=False, capture_output=True, text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return False
    return res.returncode == 0 and "boolean true" in res.stdout


def _kwrite(*args: str) -> bool:
    """Write a kdeglobals key. ``--notify`` serialises rapid back-to-back
    writes against the same file so kwriteconfig6's atomic .tmp→rename
    can't race; it requires a live session bus, so we probe once.

    Hard 5s timeout: ``--notify`` blocks on the session bus, and a
    degraded plasmashell can leave the bus partially unresponsive,
    which would hang the whole installer indefinitely. 5s is generous
    for any legitimate kwriteconfig invocation; if it's not done by
    then the bus is broken anyway and silently dropping the notify is
    the right call (the on-disk file write succeeded before the notify
    step)."""
    if not _have("kwriteconfig6"):
        return False
    cmd = ["kwriteconfig6"]
    if _has_session_dbus():
        cmd.append("--notify")
    cmd.extend(args)
    try:
        rc = subprocess.run(
            cmd, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=5,
        ).returncode
    except subprocess.TimeoutExpired:
        rc = 1
    os.sync()
    return rc == 0


def _kread(file: str, group: str, key: str) -> str:
    if not _have("kreadconfig6"):
        return ""
    try:
        return subprocess.run(
            ["kreadconfig6", "--file", file, "--group", group, "--key", key],
            check=False, capture_output=True, text=True,
            timeout=5,
        ).stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


def _build_group_args(section: str) -> list[str]:
    """``Colors:Header][Inactive`` → ``[--group, Colors:Header, --group, Inactive]``."""
    args: list[str] = []
    rest = section
    while True:
        idx = rest.find("][")
        if idx < 0:
            break
        args.extend(["--group", rest[:idx]])
        rest = rest[idx + 2:]
    args.extend(["--group", rest])
    return args


def _parse_ini(path: Path) -> dict[str, dict[str, str]]:
    """Read a kdeglobals/.colors-style INI. Section names retain ``][`` syntax."""
    sections: dict[str, dict[str, str]] = {}
    section: str | None = None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return sections
    for raw in text.splitlines():
        line = raw.rstrip("\r").strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            sections.setdefault(section, {})
            continue
        if "=" in line and section is not None:
            key, value = line.split("=", 1)
            sections[section][key.strip()] = value
    return sections


def _is_color_group(name: str) -> bool:
    return name.startswith(("Colors:", "ColorEffects:")) or name == "WM"


def _scrub_malformed_color_groups() -> None:
    """Older versions wrote nested sections like ``[Colors:Header][Inactive]``
    as ``[Colors:Header\\x5d\\x5bInactive]``. Strip those ghost sections
    before applying a new palette so stale values can't survive."""
    path = _kdeglobals_path()
    if not path.is_file():
        return
    bad = re.compile(r"^\[(Colors:|ColorEffects:).*(\\x5d\\x5b).*\]$")
    text = path.read_text(encoding="utf-8", errors="replace")
    out: list[str] = []
    skip = False
    for line in text.splitlines():
        if bad.match(line):
            skip = True
            continue
        if skip and line.startswith("["):
            skip = False
        if not skip:
            out.append(line)
    path.write_text("\n".join(out) + ("\n" if text.endswith("\n") else ""),
                    encoding="utf-8")


def _delete_color_groups_direct() -> None:
    if not _have("kwriteconfig6"):
        return
    path = _kdeglobals_path()
    if not path.is_file():
        return
    _scrub_malformed_color_groups()
    sections = _parse_ini(path)
    keys: set[tuple[str, str]] = set()
    for section, items in sections.items():
        if _is_color_group(section):
            for key in items:
                keys.add((section, key))
    for section, key in sorted(keys):
        _kwrite("--file", "kdeglobals",
                *_build_group_args(section),
                "--key", key, "--delete")


def reset_kde_color_scheme_config(scheme: str) -> bool:
    if not _have("kwriteconfig6"):
        return False
    _delete_color_groups_direct()
    return _kwrite("--file", "kdeglobals", "--group", "General",
                   "--key", "ColorScheme", scheme)


def _find_scheme_file(scheme: str) -> Path | None:
    candidates = [
        Path.home() / ".local/share/color-schemes" / f"{scheme}.colors",
        Path("/usr/share/color-schemes") / f"{scheme}.colors",
    ]
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        candidates.insert(0, Path(xdg) / "color-schemes" / f"{scheme}.colors")
    for p in candidates:
        if p.is_file():
            return p
    return None


def apply_color_groups_direct(scheme: str) -> bool:
    """Force-write every [Colors:*]/[ColorEffects:*]/[WM] group from ``scheme``
    so the active ColorScheme name and the on-disk palette can never disagree."""
    if not _have("kwriteconfig6"):
        return False
    scheme_file = _find_scheme_file(scheme)
    if scheme_file is None:
        return False

    sections = _parse_ini(scheme_file)
    _delete_color_groups_direct()

    for section, items in sections.items():
        if not _is_color_group(section):
            continue
        group_args = _build_group_args(section)
        for key, value in items.items():
            _kwrite("--file", "kdeglobals", *group_args, "--key", key, value)

    # KColorSchemeManager and several Qt apps key cached palettes on
    # ColorSchemeHash. plasma-apply-colorscheme is the only tool that
    # rewrites it, and we deliberately bypass that tool — so without this,
    # the hash desyncs on every dark↔light flip and apps serve cached
    # colors from the previous scheme.
    digest = hashlib.sha1(scheme_file.read_bytes()).hexdigest()
    _kwrite("--file", "kdeglobals", "--group", "General",
            "--key", "ColorSchemeHash", digest)
    return True


def detect_mode_by_time() -> str:
    h = _dt.datetime.now().hour
    return "light" if 6 <= h < 18 else "dark"


def _wallpaper_path(mode: str) -> Path | None:
    data_home = Path(os.environ.get("XDG_DATA_HOME") or
                     str(Path.home() / ".local/share"))
    base = data_home / "wallpapers"
    auto = base / "MacTahoe"
    if auto.is_dir():
        return auto
    legacy = base / ("MacTahoe-Dark" if mode == "dark" else "MacTahoe-Light")
    return legacy if legacy.is_dir() else None


def _apply_wallpaper(mode: str) -> bool:
    wp = _wallpaper_path(mode)
    if wp is None or not _have("plasma-apply-wallpaperimage"):
        return False
    if not wait_for_plasma(settle_seconds=1):
        return False
    try:
        return subprocess.run(
            ["plasma-apply-wallpaperimage", str(wp)],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=20,
        ).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def get_system_preference() -> str:
    res = subprocess.run(
        ["dbus-send", "--session", "--print-reply",
         "--dest=org.freedesktop.portal.Desktop",
         "/org/freedesktop/portal/desktop",
         "org.freedesktop.portal.Settings.Read",
         "string:org.freedesktop.appearance",
         "string:color-scheme"],
        check=False, capture_output=True, text=True,
    )
    if res.returncode != 0:
        return "none"
    if "uint32 1" in res.stdout:
        return "dark"
    if "uint32 2" in res.stdout:
        return "light"
    return "none"


def current_theme_mode() -> str | None:
    if not _have("kreadconfig6"):
        return None
    scheme = _kread("kdeglobals", "General", "ColorScheme")
    if scheme.endswith(("Dark", "dark")):
        return "dark"
    if scheme.endswith(("Light", "light")):
        return "light"
    return None


def detect_mode() -> str:
    m = current_theme_mode()
    if m:
        return m
    pref = get_system_preference()
    return pref if pref != "none" else detect_mode_by_time()


def detect_auto_target_mode() -> str:
    """Auto = strictly time-based. Portal and kdeglobals can be stale or
    contradict us after a crash or external tool, so ignore them — that's
    how the 11-AM dark-mode trap used to happen."""
    return detect_mode_by_time()


_AUTO_TIMER_UNIT = "mac-tahoe-liquid-kde-theme.timer"


def _systemctl_user(*args: str) -> bool:
    """Best-effort ``systemctl --user`` wrapper. Returns False on no
    systemctl, no user manager, or non-zero rc — never raises, since
    a missing user systemd shouldn't break a manual theme switch."""
    if not _have("systemctl"):
        return False
    try:
        return subprocess.run(
            ["systemctl", "--user", *args],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=10,
        ).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def enable_auto_mode() -> bool:
    if not _have("kwriteconfig6"):
        return False
    # Disable Plasma's AutomaticLookAndFeel so the portal / KDE night-color
    # scheduler can't override our 6–18 rule. The systemd timer is the only
    # source of truth for auto.
    _kwrite("--file", "kdeglobals", "--group", "KDE",
            "--key", "AutomaticLookAndFeel", "false")
    _kwrite("--file", "kdeglobals", "--group", "KDE",
            "--key", "DefaultLightLookAndFeel", LAF_LIGHT)
    _kwrite("--file", "kdeglobals", "--group", "KDE",
            "--key", "DefaultDarkLookAndFeel", LAF_DARK)
    # Re-enable the timer so the 06:00 / 18:00 transitions fire. Calling
    # ``mac-tahoe-theme-switch auto`` after a previous ``light`` / ``dark``
    # invocation must restore the scheduled flip; without this the kdeglobals
    # keys flip back to "auto" but the timer is still dead from the
    # disable_auto_mode() call that ``light`` / ``dark`` made.
    _systemctl_user("enable", "--now", _AUTO_TIMER_UNIT)
    return True


def disable_auto_mode() -> bool:
    if not _have("kwriteconfig6"):
        return False
    # Stop the scheduler too — README documents that ``light`` / ``dark``
    # disable the auto timer, and the user expects the theme to stay put
    # until they explicitly re-enable auto.
    _systemctl_user("disable", "--now", _AUTO_TIMER_UNIT)
    return _kwrite("--file", "kdeglobals", "--group", "KDE",
                   "--key", "AutomaticLookAndFeel", "false")


def flush_icon_caches() -> None:
    home = Path.home()
    for sub in (".cache/icon-cache.kcache", ".cache/kiconthemes"):
        shutil.rmtree(home / sub, ignore_errors=True)


def _apply_local_extras(mode: str) -> None:
    if _have("kvantummanager"):
        kv = "mac-tahoe-liquid-kdeDark" if mode == "dark" else "mac-tahoe-liquid-kde"
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        try:
            subprocess.run(
                ["kvantummanager", "--set", kv], check=False, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            pass

    home = Path.home()
    gtk_dest = home / ".themes"
    gtk_theme = "MacTahoeLiquidKde-Dark" if mode == "dark" else "MacTahoeLiquidKde-Light"
    if (gtk_dest / gtk_theme).is_dir():
        _qdbus("org.kde.GtkConfig", "/GtkConfig",
               "org.kde.GtkConfig.setGtkTheme", gtk_theme)
        if _have("gsettings"):
            for args in (
                ["set", "org.gnome.desktop.interface", "gtk-theme", gtk_theme],
                ["set", "org.gnome.desktop.wm.preferences",
                 "button-layout", "close,minimize,maximize:"],
                ["set", "org.gnome.desktop.interface", "color-scheme",
                 "prefer-dark" if mode == "dark" else "prefer-light"],
            ):
                try:
                    subprocess.run(
                        ["gsettings", *args], check=False,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=5,
                    )
                except subprocess.TimeoutExpired:
                    pass

        gtk4_dest = home / ".config/gtk-4.0"
        gtk4_src = gtk_dest / gtk_theme / "gtk-4.0"
        if gtk4_src.is_dir():
            time.sleep(3)
            gtk4_dest.mkdir(parents=True, exist_ok=True)
            for sub in ("assets", "windows-assets"):
                src = gtk4_src / sub
                if src.is_dir():
                    dst = gtk4_dest / sub
                    shutil.rmtree(dst, ignore_errors=True)
                    shutil.copytree(src, dst)
            for fn in ("gtk-Dark.css", "gtk-Light.css"):
                src = gtk4_src / fn
                if src.is_file():
                    shutil.copy2(src, gtk4_dest / fn)
            for link_name, target in (
                ("gtk.css", f"gtk-{mode.capitalize()}.css"),
                ("gtk-dark.css", "gtk-Dark.css"),
            ):
                link = gtk4_dest / link_name
                if link.is_symlink() or link.exists():
                    link.unlink()
                link.symlink_to(target)

    flush_icon_caches()
    cache = home / ".cache"
    for f in cache.glob("ksvg-elements"):
        try: f.unlink()
        except OSError: pass
    for f in cache.glob("plasma_theme_*"):
        try: f.unlink()
        except OSError: pass


def apply_extras(mode: str) -> None:
    _apply_wallpaper(mode)
    _apply_local_extras(mode)


def write_kde_theme_config(mode: str) -> bool:
    if not _have("kwriteconfig6"):
        return False

    if mode == "dark":
        laf, icon, cursor = LAF_DARK, "MacTahoeLiquidKde-Icons-dark", "MacTahoeLiquidKde-Dark"
        scheme, plasma = "MacTahoeLiquidKdeDark", "MacTahoeLiquidKde-Dark"
        widget, aurorae = "kvantum-dark", "__aurorae__svg__MacTahoeLiquidKde-Dark"
    else:
        laf, icon, cursor = LAF_LIGHT, "MacTahoeLiquidKde-Icons", "MacTahoeLiquidKde"
        scheme, plasma = "MacTahoeLiquidKdeLight", "MacTahoeLiquidKde-Light"
        widget, aurorae = "kvantum", "__aurorae__svg__MacTahoeLiquidKde-Light"

    _kwrite("--file", "kdeglobals", "--group", "KDE",
            "--key", "LookAndFeelPackage", laf)
    _kwrite("--file", "kdeglobals", "--group", "Icons", "--key", "Theme", icon)
    _kwrite("--file", "kdeglobals", "--group", "General",
            "--key", "ColorScheme", scheme)
    _kwrite("--file", "kdeglobals", "--group", "KDE",
            "--key", "widgetStyle", widget)
    _kwrite("--file", "kcminputrc", "--group", "Mouse",
            "--key", "cursorTheme", cursor)
    _kwrite("--file", "plasmarc", "--group", "Theme", "--key", "name", plasma)
    for key, value in (
        ("library", "org.kde.kwin.aurorae"),
        ("theme", aurorae),
        ("BorderSize", "Tiny"),
        ("ButtonsOnLeft", "XIA"),
        ("ButtonsOnRight", ""),
    ):
        _kwrite("--file", "kwinrc", "--group", "org.kde.kdecoration2",
                "--key", key, value)

    apply_color_groups_direct(scheme)
    return True


def apply(mode: str, context: str = "") -> bool:
    laf = LAF_DARK if mode == "dark" else LAF_LIGHT
    cursor = "MacTahoeLiquidKde-Dark" if mode == "dark" else "MacTahoeLiquidKde"
    widget = "kvantum-dark" if mode == "dark" else "kvantum"
    write_kde_theme_config(mode)

    # Skip plasma-apply-lookandfeel during install — it triggers a QML
    # engine teardown race (SIGABRT in org.kde.panel.so). The Plasma
    # restart at the end of install loads the on-disk theme + colour
    # config we just wrote.
    #
    # Boot-time sync and replayed 06:00/18:00 timer firings are trickier:
    # they can still happen during the fragile login window where a full
    # live apply has black-screened Plasma in the past. Once the current
    # plasmashell is clearly past that window, though, use the same live
    # LAF apply as a manual switch so the running shell reloads the new
    # palette instead of staying in a split light/dark state.
    if context not in ("boot", "install", "scheduled"):
        _apply_lookandfeel_live(laf)
    elif context in ("boot", "scheduled") and _can_apply_settled_live_lookandfeel():
        _apply_lookandfeel_live(laf)
    elif context == "scheduled":
        # Cursor is the one extra that does NOT pick up from kwriteconfig
        # --notify alone — Xcursor for running apps stays on the old theme
        # until something pokes plasma-apply-cursortheme. Safe individually
        # (no plasmashell rebuild, unlike the full LAF apply).
        apply_cursortheme_live(cursor)

    # The installer already applies wallpaper up front and does its own KWin
    # reload after the helper exits. Keep install-mode work local so a half-up
    # Plasma session can't pin Step 19 inside wait_for_plasma().
    if context == "install":
        _apply_local_extras(mode)
    else:
        apply_extras(mode)
    # Widget-style cycle: forces Qt apps to re-instantiate the Kvantum
    # plugin against the new kvconfig. Without this, ``kvantummanager
    # --set`` writes the new theme to disk but every running Qt window
    # keeps the previous style — the "auto switched but Kvantum is
    # still dark on a light desktop" mixed state.
    #
    # Skip on ``boot`` (plasmashell during the login window has black-
    # screened on the cycle before — see CLAUDE.md) and ``install``
    # (the explicit plasmashell restart at the end of install loads the
    # on-disk theme cleanly without needing a live cycle). Everything
    # else — interactive ``light`` / ``dark`` / ``auto``, timer-fired
    # ``auto scheduled`` — gets the cycle so running apps propagate.
    if context not in ("boot", "install"):
        cycle_widget_style_live(widget)
    if context != "install":
        _qdbus("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    return True


def wait_for_plasma(
    require_display: bool = False,
    settle_seconds: int = 3,
    max_wait_seconds: int = 90,
    kded_wait_seconds: int = 30,
) -> bool:
    for _ in range(max(1, max_wait_seconds)):
        _sync_session_env()
        have_display = bool(
            os.environ.get("DISPLAY") if require_display
            else (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        )
        have_shell = subprocess.run(
            ["pgrep", "-x", "plasmashell"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0
        if have_display and have_shell and _has_session_dbus() \
                and _session_bus_has_name("org.kde.plasmashell") \
                and _session_bus_has_name("org.kde.KWin"):
            break
        time.sleep(1)
    else:
        return False

    for _ in range(max(0, kded_wait_seconds)):
        if subprocess.run(
            ["pgrep", "-x", "kded6"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0:
            break
        time.sleep(1)

    time.sleep(settle_seconds)
    return True


def _live_tool_env() -> dict[str, str]:
    _sync_session_env()
    env = os.environ.copy()
    if env.get("WAYLAND_DISPLAY") and not env.get("QT_QPA_PLATFORM"):
        env["QT_QPA_PLATFORM"] = "wayland"
    return env


def _run_live_plasma_tool(
    cmd: list[str],
    *,
    require_display: bool = True,
    settle_seconds: int = 5,
    timeout_seconds: int = 20,
) -> bool:
    if os.environ.get("MAC_TAHOE_SKIP_LIVE_APPLY", "").lower() == "true":
        return False
    if not wait_for_plasma(require_display=require_display,
                           settle_seconds=settle_seconds):
        return False
    try:
        return subprocess.run(
            cmd,
            check=False,
            env=_live_tool_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_seconds,
        ).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def _apply_lookandfeel_live(laf: str) -> bool:
    if not _have("plasma-apply-lookandfeel"):
        return False
    # On Wayland login, WAYLAND_DISPLAY often appears a few seconds before the
    # X11 DISPLAY/XWayland bridge. plasma-apply-lookandfeel still aborts in
    # QGuiApplication startup if that DISPLAY is missing or not ready yet.
    ok = _run_live_plasma_tool(
        ["plasma-apply-lookandfeel", "-a", laf, "--keep-auto"],
        require_display=True,
        settle_seconds=5,
    )
    if not ok:
        print("Skipping plasma-apply-lookandfeel: DISPLAY/session not ready",
              file=sys.stderr)
    return ok


def _plasmashell_age_seconds() -> int | None:
    try:
        res = subprocess.run(
            ["ps", "-C", "plasmashell", "-o", "etimes="],
            check=False, capture_output=True, text=True,
        )
    except OSError:
        return None
    if res.returncode != 0:
        return None
    ages: list[int] = []
    for raw in res.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            ages.append(int(raw))
        except ValueError:
            continue
    return min(ages) if ages else None


def _can_apply_settled_live_lookandfeel() -> bool:
    """Only do delayed live LAF applies once plasmashell is well past the
    fragile login/startup window."""
    age = _plasmashell_age_seconds()
    return age is not None and age >= _SETTLED_LIVE_APPLY_MIN_PLASMASHELL_AGE_SECONDS


def apply_cursortheme_live(theme: str) -> bool:
    if not _have("plasma-apply-cursortheme"):
        return False
    return _run_live_plasma_tool(
        ["plasma-apply-cursortheme", theme],
        require_display=True,
        settle_seconds=5,
    )


def _broadcast_widget_style_change(style: str) -> None:
    if not _has_session_dbus():
        return
    for cmd in (
        ["dbus-send", "--session", "--type=signal",
         "/KGlobalSettings", "org.kde.KGlobalSettings.notifyChange",
         "int32:2", "int32:0"],
        ["dbus-send", "--session", "--type=signal",
         "/org/freedesktop/portal/desktop",
         "org.freedesktop.impl.portal.Settings.SettingChanged",
         "string:org.kde.kdeglobals.KDE", "string:widgetStyle",
         f"variant:string:{style}"],
        ["dbus-send", "--session", "--type=signal",
         "/org/freedesktop/portal/desktop",
         "org.freedesktop.portal.Settings.SettingChanged",
         "string:org.kde.kdeglobals.KDE", "string:widgetStyle",
         f"variant:string:{style}"],
    ):
        try:
            subprocess.run(
                cmd, check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except subprocess.TimeoutExpired:
            pass


def cycle_widget_style_live(target: str) -> bool:
    """Force-reload Kvantum (or whatever style is in widgetStyle) in running
    Qt apps without restarting plasmashell. Kvantum is a style plugin and
    can't apply theme changes on the fly — only QApplication::setStyle()
    re-instantiates the plugin and re-reads kvconfig. We trick Qt into doing
    that by writing a different widgetStyle (Breeze), broadcasting the
    KGlobalSettings + xdg-portal signals, then writing the target back. See
    https://github.com/tsujan/Kvantum/discussions/975 — the maintainer
    confirms only platform-theme plugins can hot-reload, so cycling is the
    only way to keep right-click QMenus / popups consistent across a
    light/dark switch.

    SIGTERM / SIGINT delivered during the inter-write sleep would leave
    ``widgetStyle=Breeze`` frozen on disk and the user effectively in
    Breeze night the next time plasmashell reads the config — so install a
    handler that flushes the target value before exiting. Safe even on a
    crash: ``finally`` runs on any exception, the handler runs on signals,
    so the on-disk state always ends at the target style."""
    if not _have("kwriteconfig6") or not _has_session_dbus():
        return False
    if not target:
        return False

    def _restore_target() -> None:
        _kwrite("--file", "kdeglobals", "--group", "KDE",
                "--key", "widgetStyle", target)
        _broadcast_widget_style_change(target)

    import signal
    interrupted: list[int] = []

    def _on_signal(signum, _frame):
        interrupted.append(signum)

    old_term = signal.signal(signal.SIGTERM, _on_signal)
    old_int = signal.signal(signal.SIGINT, _on_signal)
    try:
        _kwrite("--file", "kdeglobals", "--group", "KDE",
                "--key", "widgetStyle", "Breeze")
        _broadcast_widget_style_change("Breeze")
        time.sleep(0.4)
    finally:
        # Restore target FIRST (the load-bearing invariant — disk state
        # must end at target, never frozen at Breeze), THEN restore signal
        # handlers, then propagate the signal-as-SystemExit so the caller
        # actually exits if systemd sent SIGTERM.
        _restore_target()
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGINT, old_int)
    if interrupted:
        raise SystemExit(128 + interrupted[0])
    return True


def sync_auto_mode_on_startup() -> str:
    target = detect_auto_target_mode()
    current = current_theme_mode()
    if current and current == target:
        apply_extras(target)
    else:
        apply(target, "boot")
    return target


def _spawn_dbus_monitor() -> subprocess.Popen | None:
    """Start the portal Settings dbus-monitor or return None.

    Separated out so watch_loop() can degrade gracefully when dbus-monitor
    is missing (Popen would raise FileNotFoundError) or can't connect — the
    bare ``subprocess.Popen(["dbus-monitor", ...])`` used to leak that
    exception, the service exited rc=1, and systemd's Restart=on-failure
    spun the unit every RestartSec=15s. Now the failure path is local: the
    helper returns None, watch_loop blocks on signal, and the systemd timer
    still owns 06:00/18:00 transitions.
    """
    if not _have("dbus-monitor"):
        return None
    try:
        return subprocess.Popen(
            ["dbus-monitor", "--session",
             "type='signal',interface='org.freedesktop.portal.Settings',"
             "member='SettingChanged'"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
    except OSError:
        return None


def _block_until_signal() -> None:
    """Park the watcher forever; only SIGTERM/SIGINT wakes it.

    Used by watch_loop when there is no portal listener to read (dbus-monitor
    unavailable) or when the listener exited unexpectedly. Returning from
    watch_loop in either of those cases would either restart-storm (with
    Restart=on-failure) or leave the unit silently dead — neither is what
    we want. The timer + apply.service still drive 06:00/18:00, so blocking
    here keeps the unit honestly long-running until the session ends.
    """
    signal.pause()


def _watch_consume(stdout, initial_mode: str) -> str:
    """Iterate the dbus-monitor stdout and apply on color-scheme changes.

    Pulled out of watch_loop so the test suite can drive it with a fake
    iterable. ``last_mode`` tracks the most recent applied mode so a
    burst of repeated SettingChanged signals (Plasma re-emits the same
    setting several times during a single toggle) only causes one apply
    per real transition.
    """
    last_mode = initial_mode
    for line in stdout:
        if "color-scheme" not in line:
            continue
        # Brief settle: portal often emits the signal a hair before the
        # new color-scheme value is queryable from kdeglobals / portal.
        time.sleep(0.5)
        new = detect_mode()
        if new != last_mode:
            apply_extras(new)
            last_mode = new
    return last_mode


def watch_loop() -> int:
    """Long-running portal/Plasma watcher for the auto theme mode.

    Return codes are deliberately always 0. Routinely-failing modes
    (Plasma not up, dbus-monitor missing, dbus-monitor died) used to
    return non-zero and trip the unit's Restart=on-failure into a
    Started→Stopped storm every RestartSec. The unit is now Restart=no
    and this function owns its own degraded-mode behaviour: when the
    portal listener isn't available, it parks on signal.pause() instead
    of bailing.
    """
    if not wait_for_plasma():
        print("Plasma not ready after 60s — staying alive for timer fallback",
              file=sys.stderr)
        _block_until_signal()
        return 0

    last_mode = sync_auto_mode_on_startup()

    proc = _spawn_dbus_monitor()
    if proc is None or proc.stdout is None:
        print("dbus-monitor unavailable — staying alive for timer fallback",
              file=sys.stderr)
        _block_until_signal()
        return 0

    try:
        _watch_consume(proc.stdout, last_mode)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    # dbus-monitor exited (bus restarted, OOM, etc.). Returning would let
    # systemd notice the unit died and — if anyone re-adds Restart= in
    # the future — fire the next iteration. Park here instead so the
    # only way out is a real SIGTERM from `systemctl stop`.
    print("dbus-monitor exited; staying alive for timer fallback",
          file=sys.stderr)
    _block_until_signal()
    return 0


USAGE = (
    "Usage: mac-tahoe-theme-switch {light|dark|auto|watch|reset} [boot|install]\n"
    "       mac-tahoe-theme-switch reset <scheme-name>"
)


def main(argv: list[str]) -> int:
    if not argv:
        print(USAGE, file=sys.stderr)
        return 1

    mode, rest = argv[0], argv[1:]
    context = rest[0] if rest else ""

    if mode == "light":
        disable_auto_mode()
        apply("light", context)
        return 0
    if mode == "dark":
        disable_auto_mode()
        apply("dark", context)
        return 0
    if mode == "auto":
        enable_auto_mode()
        apply(detect_mode_by_time(), context or "scheduled")
        return 0
    if mode == "watch":
        return watch_loop()
    if mode == "reset":
        return 0 if reset_kde_color_scheme_config(rest[0] if rest else "BreezeLight") else 1

    print(USAGE, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
