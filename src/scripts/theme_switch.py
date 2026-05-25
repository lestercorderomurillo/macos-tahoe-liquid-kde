#!/usr/bin/env python3
"""Light/dark theme switcher for MacTahoe Liquid KDE.

Single entry point: `mac-tahoe-theme-switch {light|dark|auto}`. Same binary
runs from the install step, from the systemd service that fires after the
desktop is up, from the 06:00 / 18:00 timer, and from the user when they
flip the switch by hand. There are no contexts, no deferred re-applies,
no watch loops — install only schedules this for `--auto`; `--light` and
`--dark` apply once and stay put.

Plasma 6's lookandfeelautoswitcher KDED module touches color scheme,
plasma theme, icons, cursors, aurorae, and wallpaper on its own when
plasma-apply-lookandfeel runs. This script covers what Plasma does NOT
switch automatically (Kvantum, GTK 2/3/4, icon caches) and rewrites the
[Colors:*]/[ColorEffects:*]/[WM] groups in kdeglobals directly — relying
on `plasma-apply-colorscheme` alone can leave stale palette values from
the previous scheme.
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


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _xdg_config() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or
                str(Path.home() / ".config"))


def _kdeglobals_path() -> Path:
    return _xdg_config() / "kdeglobals"


def _qdbus(*args: str) -> bool:
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


def _kwrite(*args: str) -> bool:
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
    # ColorSchemeHash. Without rewriting it, apps serve cached colors
    # from the previous scheme after a flip.
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
    try:
        return subprocess.run(
            ["plasma-apply-wallpaperimage", str(wp)],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=20,
        ).returncode == 0
    except subprocess.TimeoutExpired:
        return False


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
            gtk4_dest.mkdir(parents=True, exist_ok=True)
            for sub in ("assets", "windows-assets"):
                src = gtk4_src / sub
                if not src.is_dir():
                    continue
                dst = gtk4_dest / sub
                # rmtree(ignore_errors=True) can silently leave the dir in
                # place — an inotify watcher (file manager, GTK client,
                # cache writer) recreating files during the iteration is
                # enough to make rmdir fail with ENOTEMPTY. dirs_exist_ok=True
                # merges into whatever survived rmtree.
                try:
                    shutil.rmtree(dst, ignore_errors=True)
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                except OSError as exc:
                    print(f"theme apply: gtk4 {sub} copy skipped: {exc}",
                          file=sys.stderr)
            for fn in ("gtk-Dark.css", "gtk-Light.css"):
                src = gtk4_src / fn
                if src.is_file():
                    try:
                        shutil.copy2(src, gtk4_dest / fn)
                    except OSError as exc:
                        print(f"theme apply: gtk4 {fn} copy skipped: {exc}",
                              file=sys.stderr)
            for link_name, target in (
                ("gtk.css", f"gtk-{mode.capitalize()}.css"),
                ("gtk-dark.css", "gtk-Dark.css"),
            ):
                link = gtk4_dest / link_name
                try:
                    if link.is_symlink() or link.exists():
                        link.unlink()
                    link.symlink_to(target)
                except OSError as exc:
                    print(f"theme apply: gtk4 {link_name} link skipped: {exc}",
                          file=sys.stderr)

    flush_icon_caches()
    cache = home / ".cache"
    for f in cache.glob("ksvg-elements"):
        try: f.unlink()
        except OSError: pass
    for f in cache.glob("plasma_theme_*"):
        try: f.unlink()
        except OSError: pass


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
    # Disable Plasma's built-in AutomaticLookAndFeel so the KDE sunrise/sunset
    # scheduler can't fight our 06:00 / 18:00 timer. Idempotent — set on every
    # apply rather than guarded by a separate enable/disable function.
    _kwrite("--file", "kdeglobals", "--group", "KDE",
            "--key", "AutomaticLookAndFeel", "false")
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


def _live_tool_env() -> dict[str, str]:
    _sync_session_env()
    env = os.environ.copy()
    if env.get("WAYLAND_DISPLAY") and not env.get("QT_QPA_PLATFORM"):
        env["QT_QPA_PLATFORM"] = "wayland"
    return env


def _run_live_plasma_tool(cmd: list[str], *, timeout_seconds: int = 20) -> bool:
    if os.environ.get("MAC_TAHOE_SKIP_LIVE_APPLY", "").lower() == "true":
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


_LAF_APPLY_ATTEMPTS = 3
_LAF_APPLY_RETRY_SLEEP_SECONDS = 10


def _apply_lookandfeel_live(laf: str) -> bool:
    """Run plasma-apply-lookandfeel against the running shell. Up to three
    attempts spaced 10s apart, stopping at the first success. The wait is
    deliberate: on a fresh login the systemd unit can race plasmashell's
    DBus registration, and plasma-apply-lookandfeel exits 0 against a not-
    yet-ready bus without actually re-rendering the desktop. Sleeping
    first lets plasmashell finish settling; retrying covers the occasional
    slow boot (HDD, encrypted home, heavy login program list)."""
    if not _have("plasma-apply-lookandfeel"):
        return False
    for _ in range(_LAF_APPLY_ATTEMPTS):
        time.sleep(_LAF_APPLY_RETRY_SLEEP_SECONDS)
        if _run_live_plasma_tool(
            ["plasma-apply-lookandfeel", "-a", laf, "--keep-auto"],
        ):
            return True
    return False


def apply_cursortheme_live(theme: str) -> bool:
    if not _have("plasma-apply-cursortheme"):
        return False
    return _run_live_plasma_tool(["plasma-apply-cursortheme", theme])


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
    """Force-reload Kvantum in running Qt apps without restarting plasmashell.
    Kvantum is a style plugin and can't apply theme changes on the fly — only
    QApplication::setStyle() re-instantiates the plugin and re-reads kvconfig.
    Trick Qt by writing Breeze, broadcasting the signals, then writing the
    target back. https://github.com/tsujan/Kvantum/discussions/975 — upstream
    confirms only platform-theme plugins can hot-reload.

    SIGTERM / SIGINT during the inter-write sleep would leave widgetStyle=Breeze
    on disk and freeze the user in Breeze the next time plasmashell reads the
    config. The finally + signal handler guarantee disk state always ends at
    the target style."""
    if not _have("kwriteconfig6") or not _has_session_dbus():
        return False
    if not target:
        return False

    def _restore_target() -> None:
        _kwrite("--file", "kdeglobals", "--group", "KDE",
                "--key", "widgetStyle", target)
        _broadcast_widget_style_change(target)

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
        _restore_target()
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGINT, old_int)
    if interrupted:
        raise SystemExit(128 + interrupted[0])
    return True


def apply(mode: str) -> bool:
    """One code path. Same behaviour whether install, service, timer, or
    a manual `light` / `dark` / `auto` invocation runs this. Writes config
    + extras (Kvantum, GTK, caches) + live LAF + live cursor + Kvantum
    cycle + KWin reconfigure."""
    cursor = "MacTahoeLiquidKde-Dark" if mode == "dark" else "MacTahoeLiquidKde"
    widget = "kvantum-dark" if mode == "dark" else "kvantum"
    laf = LAF_DARK if mode == "dark" else LAF_LIGHT

    write_kde_theme_config(mode)
    try:
        _apply_wallpaper(mode)
        _apply_local_extras(mode)
    except Exception as exc:
        print(f"theme apply: extras step failed, continuing: {exc!r}",
              file=sys.stderr)
    _apply_lookandfeel_live(laf)
    apply_cursortheme_live(cursor)
    cycle_widget_style_live(widget)
    _qdbus("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    return True


USAGE = "Usage: mac-tahoe-theme-switch {light|dark|auto}"


def main(argv: list[str]) -> int:
    if not argv:
        print(USAGE, file=sys.stderr)
        return 1

    mode = argv[0]
    if mode == "auto":
        mode = detect_mode_by_time()
    if mode not in ("light", "dark"):
        print(USAGE, file=sys.stderr)
        return 1

    apply(mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
