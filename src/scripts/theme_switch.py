#!/usr/bin/env python3
"""Light/dark theme switcher: `mac-tahoe-theme-switch {light|dark|auto}
[install]`. Covers what Plasma's lookandfeelautoswitcher does NOT switch
(Kvantum, GTK 2/3/4, icon caches) and rewrites the [Colors:*] groups
directly — plasma-apply-colorscheme alone can leave stale palette values."""

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


def _drop_privs_in_child() -> None:
    """Duplicate of utils.drop_privs_in_child (the canonical copy) — this
    file ships standalone to ~/.local/bin and cannot import utils.
    No-op without SUDO_UID/SUDO_GID, i.e. in plain user runs."""
    sudo_uid = os.environ.get("SUDO_UID")
    sudo_gid = os.environ.get("SUDO_GID")
    if not sudo_uid or not sudo_gid:
        return
    # GID first: changing UID can drop the right to call setresgid.
    os.setresgid(int(sudo_gid), int(sudo_gid), int(sudo_gid))
    os.setresuid(int(sudo_uid), int(sudo_uid), int(sudo_uid))


def _run_user(cmd: list[str], *, timeout: int,
              env: dict[str, str] | None = None,
              capture: bool = False) -> subprocess.CompletedProcess:
    """Every child spawn goes through here. steps/apply.py imports these
    helpers into the sudo'd installer (ruid=0, euid=user), where a bare
    child trips Qt6's setuid abort and the call silently fails (#37)."""
    kwargs: dict = {"check": False, "timeout": timeout, "env": env,
                    "preexec_fn": _drop_privs_in_child}
    if capture:
        kwargs.update(capture_output=True, text=True)
    else:
        kwargs.update(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return subprocess.run(cmd, **kwargs)


def _xdg_config() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or
                str(Path.home() / ".config"))


def _kdeglobals_path() -> Path:
    return _xdg_config() / "kdeglobals"


def _qdbus(*args: str) -> bool:
    # Fedora ships the Qt6 client as qdbus-qt6, not qdbus6 (see utils.qdbus_cmd).
    for q in ("qdbus6", "qdbus-qt6", "qdbus"):
        if _have(q):
            try:
                return _run_user([q, *args], timeout=10).returncode == 0
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
        _HAS_DBUS = _run_user(
            ["dbus-send", "--session", "--print-reply",
             "--dest=org.freedesktop.DBus", "/org/freedesktop/DBus",
             "org.freedesktop.DBus.ListNames"],
            timeout=5,
        ).returncode == 0
    except subprocess.TimeoutExpired:
        _HAS_DBUS = False
    return _HAS_DBUS


def _sync_session_env() -> None:
    try:
        res = _run_user(["systemctl", "--user", "show-environment"],
                        timeout=5, capture=True)
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
        return _run_user(cmd, timeout=5).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def _kread(file: str, group: str, key: str) -> str:
    if not _have("kreadconfig6"):
        return ""
    try:
        return _run_user(
            ["kreadconfig6", "--file", file, "--group", group, "--key", key],
            timeout=5, capture=True,
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


def _delete_color_groups_direct() -> bool:
    if not _have("kwriteconfig6"):
        return False
    path = _kdeglobals_path()
    if not path.is_file():
        return True
    _scrub_malformed_color_groups()
    sections = _parse_ini(path)
    keys: set[tuple[str, str]] = set()
    for section, items in sections.items():
        if _is_color_group(section):
            for key in items:
                keys.add((section, key))
    for section, key in sorted(keys):
        if not _kwrite("--file", "kdeglobals",
                       *_build_group_args(section),
                       "--key", key, "--delete"):
            return False
    return True


def reset_kde_color_scheme_config(scheme: str) -> bool:
    if not _have("kwriteconfig6"):
        return False
    if not _delete_color_groups_direct():
        return False
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
    if not _delete_color_groups_direct():
        return False
    for section, items in sections.items():
        if not _is_color_group(section):
            continue
        group_args = _build_group_args(section)
        for key, value in items.items():
            if not _kwrite("--file", "kdeglobals", *group_args,
                           "--key", key, value):
                return False
    # Qt apps key cached palettes on ColorSchemeHash — without rewriting
    # it they keep serving the previous scheme's colors.
    digest = hashlib.sha1(scheme_file.read_bytes()).hexdigest()
    return _kwrite("--file", "kdeglobals", "--group", "General",
                   "--key", "ColorSchemeHash", digest)


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
        return _run_user(["plasma-apply-wallpaperimage", str(wp)],
                         timeout=20).returncode == 0
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
            _run_user(["kvantummanager", "--set", kv], timeout=15, env=env)
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
                    _run_user(["gsettings", *args], timeout=5)
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
                # rmtree(ignore_errors=True) can leave the dir behind (an
                # inotify watcher recreating files mid-walk → ENOTEMPTY);
                # dirs_exist_ok=True merges into whatever survived.
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

    # AutomaticLookAndFeel=false: Plasma's sunrise/sunset scheduler must
    # not fight our 06:00 / 18:00 timer (idempotent).
    fixed = (
        ("kdeglobals", "KDE", "LookAndFeelPackage", laf),
        ("kdeglobals", "KDE", "AutomaticLookAndFeel", "false"),
        ("kdeglobals", "Icons", "Theme", icon),
        ("kdeglobals", "General", "ColorScheme", scheme),
        ("kdeglobals", "KDE", "widgetStyle", widget),
        ("kcminputrc", "Mouse", "cursorTheme", cursor),
        ("plasmarc", "Theme", "name", plasma),
    )
    for file, group, key, value in fixed:
        if not _kwrite("--file", file, "--group", group,
                       "--key", key, value):
            return False
    for key, value in (
        ("library", "org.kde.kwin.aurorae"),
        ("theme", aurorae),
        ("BorderSize", "Tiny"),
        ("ButtonsOnLeft", "XIA"),
        ("ButtonsOnRight", ""),
    ):
        if not _kwrite("--file", "kwinrc", "--group", "org.kde.kdecoration2",
                       "--key", key, value):
            return False

    return apply_color_groups_direct(scheme)


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
        return _run_user(cmd, timeout=timeout_seconds,
                         env=_live_tool_env()).returncode == 0
    except subprocess.TimeoutExpired:
        return False


_LAF_APPLY_ATTEMPTS = 3
_LAF_APPLY_FIRST_WAIT_SECONDS = 2
_LAF_APPLY_RETRY_SLEEP_SECONDS = 6


def _apply_lookandfeel_live(laf: str) -> bool:
    """Up to three attempts: 2s lead-in, then 6s between retries. On a
    fresh login plasma-apply-lookandfeel exits 0 against a not-yet-ready
    bus WITHOUT re-rendering — don't shorten the lead-in."""
    if not _have("plasma-apply-lookandfeel"):
        return False
    for attempt in range(_LAF_APPLY_ATTEMPTS):
        if attempt == 0:
            time.sleep(_LAF_APPLY_FIRST_WAIT_SECONDS)
        else:
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


def _broadcast_widget_style_change(style: str) -> bool:
    """True when at least one signal lands — the portal endpoints are
    optional and must not turn a delivered change into a failure."""
    if not _has_session_dbus():
        return False
    sent = False
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
            sent = _run_user(cmd, timeout=5).returncode == 0 or sent
        except subprocess.TimeoutExpired:
            pass
    return sent


def cycle_widget_style_live(target: str) -> bool:
    """Kvantum can't hot-reload kvconfig; only QApplication::setStyle()
    re-instantiates the plugin — so write Breeze, broadcast, write the
    target back (https://github.com/tsujan/Kvantum/discussions/975).
    SIGTERM/SIGINT mid-cycle would strand widgetStyle=Breeze on disk;
    the finally + signal handler guarantee disk ends at the target.
    False when a widgetStyle write fails or a broadcast phase lands
    nothing — silent-success here masked the sudo'd-uninstall bug (#37)."""
    if not _have("kwriteconfig6") or not _has_session_dbus():
        return False
    if not target:
        return False

    phase_ok: list[bool] = []

    def _restore_target() -> None:
        phase_ok.append(_kwrite("--file", "kdeglobals", "--group", "KDE",
                                "--key", "widgetStyle", target))
        phase_ok.append(bool(_broadcast_widget_style_change(target)))

    interrupted: list[int] = []

    def _on_signal(signum, _frame):
        interrupted.append(signum)

    old_term = signal.signal(signal.SIGTERM, _on_signal)
    old_int = signal.signal(signal.SIGINT, _on_signal)
    try:
        phase_ok.append(_kwrite("--file", "kdeglobals", "--group", "KDE",
                                "--key", "widgetStyle", "Breeze"))
        phase_ok.append(bool(_broadcast_widget_style_change("Breeze")))
        time.sleep(0.4)
    finally:
        _restore_target()
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGINT, old_int)
    if interrupted:
        raise SystemExit(128 + interrupted[0])
    return all(phase_ok)


def apply(mode: str, context: str = "user") -> bool:
    """Config writes + best-effort live niceties. Returns False when the
    core config writes fail (kwriteconfig6 missing or a write error).
    Live LAF is skipped during install — Plasma restarts anyway and
    running both races plasmashell's QML teardown."""
    cursor = "MacTahoeLiquidKde-Dark" if mode == "dark" else "MacTahoeLiquidKde"
    widget = "kvantum-dark" if mode == "dark" else "kvantum"
    laf = LAF_DARK if mode == "dark" else LAF_LIGHT

    config_ok = write_kde_theme_config(mode)
    if not config_ok:
        print("theme apply: core KDE config writes failed, theme not "
              "fully applied", file=sys.stderr)
    try:
        _apply_wallpaper(mode)
        _apply_local_extras(mode)
    except Exception as exc:
        print(f"theme apply: extras step failed, continuing: {exc!r}",
              file=sys.stderr)
    if context != "install":
        if not _apply_lookandfeel_live(laf):
            print("theme apply: live look-and-feel apply skipped",
                  file=sys.stderr)
    if not apply_cursortheme_live(cursor):
        print("theme apply: live cursor apply skipped", file=sys.stderr)
    if not cycle_widget_style_live(widget):
        print("theme apply: widget-style cycle skipped", file=sys.stderr)
    _qdbus("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    return config_ok


USAGE = "Usage: mac-tahoe-theme-switch {light|dark|auto} [install]"


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

    context = argv[1] if len(argv) > 1 else "user"
    return 0 if apply(mode, context=context) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
