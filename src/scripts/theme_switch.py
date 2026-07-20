#!/usr/bin/env python3
"""Light/dark theme switcher: `mac-tahoe-theme-switch {light|dark|auto}
[install]`. Covers what Plasma's lookandfeelautoswitcher does NOT switch
(Kvantum, GTK 2/3/4, icon caches). Color schemes go through KDE's own
plasma-apply-colorscheme (correct [Colors:*] groups + ColorSchemeHash so
live Qt apps reload the palette); the manual [Colors:*] rewrite remains
only as a fallback for systems without the tool."""

import datetime as _dt
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path


LAF_LIGHT = "org.kde.mac-tahoe-liquid-kde.light"
LAF_DARK = "org.kde.mac-tahoe-liquid-kde.dark"
KVANTUM_THEME = "mac-tahoe-liquid-kde"
KVANTUM_STYLE = "kvantum"
_PROC_ROOT = Path("/proc")


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
    child trips Qt6's setuid abort and the call silently fails."""
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


def _sync_session_env_runtime_dir() -> None:
    """Recover the session bus/Wayland socket from the user runtime dir.

    Scheduled jobs can have a deliberately small environment on any init.
    The per-user runtime directory exposes stable socket names, so use it
    rather than guessing a display owned by another user.
    """
    uid = int(os.environ.get("SUDO_UID") or os.getuid())
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{uid}")
    if not runtime.is_dir():
        return
    os.environ.setdefault("XDG_RUNTIME_DIR", str(runtime))
    if "WAYLAND_DISPLAY" not in os.environ:
        for socket in sorted(runtime.glob("wayland-*")):
            if socket.is_socket() and not socket.name.endswith(".lock"):
                os.environ["WAYLAND_DISPLAY"] = socket.name
                break
    if "DBUS_SESSION_BUS_ADDRESS" not in os.environ:
        bus = runtime / "bus"
        if bus.is_socket():
            os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus}"


def _sync_session_env_from_plasmashell() -> None:
    """Fill X11 and remaining session values from a same-user shell.

    The switcher is installed as a standalone script, so it cannot import the
    installer's distro layer. ``/proc`` is init-agnostic and works for a
    systemd user service, OpenRC cron, and manually launched sessions alike.
    """
    try:
        uid = int(os.environ.get("SUDO_UID") or os.getuid())
    except ValueError:
        uid = os.getuid()
    wanted = {
        "DBUS_SESSION_BUS_ADDRESS", "DISPLAY", "WAYLAND_DISPLAY",
        "XAUTHORITY", "XDG_CURRENT_DESKTOP", "XDG_RUNTIME_DIR",
        "XDG_SESSION_TYPE",
    }
    try:
        processes = list(_PROC_ROOT.iterdir())
    except OSError:
        return
    for process in processes:
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != uid:
                continue
            if (process / "comm").read_text().strip() != "plasmashell":
                continue
            raw = (process / "environ").read_bytes()
        except OSError:
            continue
        for entry in raw.split(b"\0"):
            key_raw, sep, value_raw = entry.partition(b"=")
            key = key_raw.decode(errors="ignore")
            if not sep or key not in wanted or key in os.environ:
                continue
            value = value_raw.decode(errors="ignore")
            if value:
                os.environ[key] = value
        break


def _sync_session_env() -> None:
    global _HAS_DBUS
    old_bus = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    _sync_session_env_runtime_dir()
    _sync_session_env_from_plasmashell()
    if os.environ.get("DBUS_SESSION_BUS_ADDRESS") != old_bus:
        # A pre-sync probe may have cached a sparse cron env as bus-less.
        _HAS_DBUS = None


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
    return apply_color_scheme(scheme)


def apply_color_scheme(scheme: str) -> bool:
    """Apply a color scheme to kdeglobals.

    Prefer KDE's own ``plasma-apply-colorscheme`` (same package as
    kwriteconfig6): it rewrites the [Colors:*] groups and
    ColorSchemeHash exactly the way the Colors KCM does, so live Qt
    apps reload the palette instead of keeping the previous scheme.
    Fall back to the manual rewrite only when the binary is missing
    (minimal/CI systems)."""
    if _have("plasma-apply-colorscheme"):
        try:
            return _run_user(
                ["plasma-apply-colorscheme", scheme], timeout=15,
            ).returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False
    return apply_color_groups_direct(scheme)


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


def detect_mode_by_system() -> str | None:
    """The light/dark mode the DESKTOP currently wants, read from the live
    system rather than the clock. Used by the portal watcher so a manual flip
    in System Settings / quick-settings drives our full theme (GTK included).

    Source of truth order:
    1. The xdg-desktop-portal appearance ``color-scheme`` (1=dark, 2=light) —
       what the native quick-settings toggle actually sets, and what libadwaita
       reads. This is the value that changed when the user toggled.
    2. Fall back to KDE's active ColorScheme name (…Dark / …Light).
    None when neither can be read (caller then leaves the mode unchanged)."""
    scheme = _read_portal_color_scheme()
    if scheme == 1:
        return "dark"
    if scheme == 2:
        return "light"
    name = _kread("kdeglobals", "General", "ColorScheme")
    if name:
        low = name.lower()
        if "dark" in low:
            return "dark"
        if "light" in low:
            return "light"
    return None


_PRC_PANEL_RE = re.compile(
    r"(\[PlasmaViews\]\[Panel \d+\]\n(?:[^\[]*\n)*)", re.MULTILINE,
)


def patch_dock_transparency() -> bool:
    """Re-assert the dock's translucency in plasmashellrc so the Acrylic Glass
    shows through instead of an opaque (black) panel background painting over
    it. floating panels get panelOpacity=2 (adaptive), non-floating get
    floatingApplets=1. Applying a Global Theme from System Settings drops these,
    so we re-write them on every theme switch AND at install. Plasma's JS layout
    API can't set panelOpacity, hence the direct rc edit. Returns True if the
    file changed."""
    prc = _xdg_config() / "plasmashellrc"
    if not prc.is_file():
        return False
    try:
        text = prc.read_text()
    except OSError:
        return False

    def fix(m: "re.Match[str]") -> str:
        section = m.group(0)
        if "floating=1" in section:
            if "panelOpacity=" in section:
                section = re.sub(r"panelOpacity=\d+", "panelOpacity=2", section)
            else:
                section = section.rstrip() + "\npanelOpacity=2\n"
        if "floating=0" in section:
            if "floatingApplets=" in section:
                section = re.sub(r"floatingApplets=\d+", "floatingApplets=1",
                                 section)
            else:
                section = section.rstrip() + "\nfloatingApplets=1\n"
        return section

    new_text = _PRC_PANEL_RE.sub(fix, text)
    if new_text != text:
        try:
            prc.write_text(new_text)
        except OSError:
            return False
        return True
    return False


def _read_portal_color_scheme() -> int | None:
    """The freedesktop appearance ``color-scheme`` as an int (0 no-pref,
    1 prefer-dark, 2 prefer-light), or None if the portal can't be read."""
    if not _has_session_dbus():
        return None
    for tool in (
        ["gdbus", "call", "--session", "--dest",
         "org.freedesktop.portal.Desktop", "--object-path",
         "/org/freedesktop/portal/desktop", "--method",
         "org.freedesktop.portal.Settings.ReadOne",
         "org.freedesktop.appearance", "color-scheme"],
        ["gdbus", "call", "--session", "--dest",
         "org.freedesktop.portal.Desktop", "--object-path",
         "/org/freedesktop/portal/desktop", "--method",
         "org.freedesktop.portal.Settings.Read",
         "org.freedesktop.appearance", "color-scheme"],
    ):
        if not _have("gdbus"):
            return None
        try:
            res = _run_user(tool, timeout=5, capture=True)
        except subprocess.TimeoutExpired:
            return None
        if res.returncode != 0:
            continue
        m = re.search(r"uint32\s+(\d+)", res.stdout)
        if m:
            return int(m.group(1))
    return None


def _wallpaper_path(mode: str) -> Path | None:
    data_home = Path(os.environ.get("XDG_DATA_HOME") or
                     str(Path.home() / ".local/share"))
    base = data_home / "wallpapers"
    auto = base / "MacTahoe"
    if auto.is_dir():
        return auto
    legacy = base / ("MacTahoe-Dark" if mode == "dark" else "MacTahoe-Light")
    return legacy if legacy.is_dir() else None


_WALLPAPER_STATE_VERSION = 1


def _wallpaper_state_file() -> Path:
    state_home = Path(os.environ.get("XDG_STATE_HOME") or
                      str(Path.home() / ".local/state"))
    return state_home / "mac-tahoe-liquid-kde" / "wallpapers.json"


def _empty_wallpaper_state() -> dict:
    return {
        "version": _WALLPAPER_STATE_VERSION,
        "initialized": False,
        "enabled": True,
        "active_mode": None,
        "last_applied": [],
        "modes": {"light": [], "dark": []},
    }


def _normalize_wallpaper_snapshot(value: object) -> list[dict[str, object]]:
    """Validate and order a per-screen wallpaper snapshot.

    Plasma containment IDs can change when a panel layout is rebuilt, while
    screen numbers remain the stable identity users care about. Keep one
    non-empty image URL per screen and discard malformed state rather than
    ever feeding it back into evaluateScript.
    """
    if not isinstance(value, list):
        return []
    by_screen: dict[int, str] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        screen = item.get("screen")
        image = item.get("image")
        if isinstance(screen, bool) or not isinstance(screen, int) \
                or screen < 0 or not isinstance(image, str) or not image:
            continue
        by_screen[screen] = image
    return [
        {"screen": screen, "image": by_screen[screen]}
        for screen in sorted(by_screen)
    ]


def _load_wallpaper_state() -> dict:
    state = _empty_wallpaper_state()
    try:
        raw = json.loads(_wallpaper_state_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return state
    if not isinstance(raw, dict):
        return state
    state["initialized"] = raw.get("initialized") is True
    if isinstance(raw.get("enabled"), bool):
        state["enabled"] = raw["enabled"]
    if raw.get("active_mode") in ("light", "dark"):
        state["active_mode"] = raw["active_mode"]
    state["last_applied"] = _normalize_wallpaper_snapshot(
        raw.get("last_applied"))
    modes = raw.get("modes")
    if isinstance(modes, dict):
        for mode in ("light", "dark"):
            state["modes"][mode] = _normalize_wallpaper_snapshot(
                modes.get(mode))
    return state


def _save_wallpaper_state(state: dict) -> bool:
    path = _wallpaper_state_file()
    # The portal watcher and the scheduled switch may overlap briefly. Give
    # each writer its own temporary file so one process cannot rename away
    # another process's pending write.
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(
            json.dumps(state, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)
        return True
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        return False


def _evaluate_plasma_script(script: str) -> str | None:
    for q in ("qdbus6", "qdbus-qt6", "qdbus"):
        if not _have(q):
            continue
        try:
            res = _run_user(
                [q, "org.kde.plasmashell", "/PlasmaShell",
                 "org.kde.PlasmaShell.evaluateScript", script],
                timeout=15, capture=True,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return res.stdout if res.returncode == 0 else None
    return None


def _build_wallpaper_capture_script() -> str:
    return """
var out = [];
var all = desktops();
for (var i = 0; i < all.length; i++) {
    var d = all[i];
    d.currentConfigGroup = ['Wallpaper', 'org.kde.image', 'General'];
    out.push({screen: d.screen, image: d.readConfig('Image', '')});
}
print(JSON.stringify(out));
"""


def _parse_wallpaper_reply(output: str | None) -> list[dict[str, object]]:
    for line in reversed((output or "").strip().splitlines()):
        line = line.strip()
        if not line.startswith("["):
            continue
        try:
            return _normalize_wallpaper_snapshot(json.loads(line))
        except json.JSONDecodeError:
            return []
    return []


_DESKTOP_SECTION_RE = re.compile(r"^Containments\]\[([^]]+)$")
_WALLPAPER_SECTION_RE = re.compile(
    r"^Containments\]\[([^]]+)\]\[Wallpaper\]"
    r"\[org\.kde\.image\]\[General$",
)


def _wallpapers_from_config() -> list[dict[str, object]]:
    path = _xdg_config() / "plasma-org.kde.plasma.desktop-appletsrc"
    sections = _parse_ini(path)
    screens: dict[str, int] = {}
    for section, values in sections.items():
        match = _DESKTOP_SECTION_RE.fullmatch(section)
        if not match or values.get("plugin") != "org.kde.plasma.folder":
            continue
        try:
            screen = int(values.get("lastScreen", ""))
        except ValueError:
            continue
        if screen >= 0:
            screens[match.group(1)] = screen
    snapshot: list[dict[str, object]] = []
    for section, values in sections.items():
        match = _WALLPAPER_SECTION_RE.fullmatch(section)
        if not match or match.group(1) not in screens:
            continue
        image = values.get("Image", "")
        if image:
            snapshot.append({"screen": screens[match.group(1)],
                             "image": image})
    return _normalize_wallpaper_snapshot(snapshot)


def _current_wallpapers() -> list[dict[str, object]]:
    live = _parse_wallpaper_reply(
        _evaluate_plasma_script(_build_wallpaper_capture_script()))
    return live or _wallpapers_from_config()


def _build_wallpaper_apply_script(
        snapshot: list[dict[str, object]]) -> str:
    by_screen = {
        str(item["screen"]): item["image"]
        for item in _normalize_wallpaper_snapshot(snapshot)
    }
    fallback = next(iter(by_screen.values()), "")
    return f"""
var wanted = {json.dumps(by_screen)};
var fallback = {json.dumps(fallback)};
var all = desktops();
for (var i = 0; i < all.length; i++) {{
    var d = all[i];
    var image = wanted[String(d.screen)] || fallback;
    if (!image) continue;
    d.wallpaperPlugin = 'org.kde.image';
    d.currentConfigGroup = ['Wallpaper', 'org.kde.image', 'General'];
    d.writeConfig('Image', image);
}}
print('applied');
"""


def _write_wallpapers_to_config(
        snapshot: list[dict[str, object]]) -> bool:
    wanted = {
        int(item["screen"]): str(item["image"])
        for item in _normalize_wallpaper_snapshot(snapshot)
    }
    if not wanted:
        return False
    fallback = next(iter(wanted.values()))
    sections = _parse_ini(
        _xdg_config() / "plasma-org.kde.plasma.desktop-appletsrc")
    writes: list[bool] = []
    for section, values in sections.items():
        match = _DESKTOP_SECTION_RE.fullmatch(section)
        if not match or values.get("plugin") != "org.kde.plasma.folder":
            continue
        try:
            screen = int(values.get("lastScreen", ""))
        except ValueError:
            continue
        image = wanted.get(screen, fallback)
        writes.append(_kwrite(
            "--file", "plasma-org.kde.plasma.desktop-appletsrc",
            "--group", "Containments", "--group", match.group(1),
            "--group", "Wallpaper", "--group", "org.kde.image",
            "--group", "General", "--key", "Image", image,
        ))
    return bool(writes) and all(writes)


def _apply_wallpaper_snapshot(
        snapshot: list[dict[str, object]]) -> bool:
    snapshot = _normalize_wallpaper_snapshot(snapshot)
    if not snapshot:
        return False
    if _evaluate_plasma_script(
            _build_wallpaper_apply_script(snapshot)) is not None:
        return True
    return _write_wallpapers_to_config(snapshot)


def _theme_wallpaper_snapshot(
        current: list[dict[str, object]], wp: Path) \
        -> list[dict[str, object]]:
    screens = [int(item["screen"]) for item in current] or [0]
    image = f"file://{wp}"
    return [{"screen": screen, "image": image} for screen in sorted(screens)]


def _snapshot_is_theme_managed(
        snapshot: list[dict[str, object]]) -> bool:
    if not snapshot:
        return False
    managed = []
    base = Path(os.environ.get("XDG_DATA_HOME") or
                str(Path.home() / ".local/share")) / "wallpapers"
    for name in ("MacTahoe", "MacTahoe-Light", "MacTahoe-Dark"):
        managed.append(str(base / name).rstrip("/"))
    for item in snapshot:
        image = str(item["image"])
        if image.startswith("file://"):
            image = image[7:]
        image = image.rstrip("/")
        if not any(image == path or image.startswith(path + "/contents/")
                   for path in managed):
            return False
    return True


def _env_bool(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None
    return value.lower() == "true"


def _apply_theme_wallpaper(mode: str) -> tuple[bool, Path | None]:
    wp = _wallpaper_path(mode)
    if wp is None or not _have("plasma-apply-wallpaperimage"):
        return (False, wp)
    try:
        ok = _run_user(["plasma-apply-wallpaperimage", str(wp)],
                       timeout=20).returncode == 0
        return (ok, wp)
    except (OSError, subprocess.TimeoutExpired):
        return (False, wp)


def _apply_wallpaper(
        mode: str, context: str = "user",
        current_snapshot: list[dict[str, object]] | None = None) -> bool:
    """Preserve deliberate wallpapers and remember one set per mode.

    The last snapshot this switcher applied is the ownership boundary. If the
    live/config snapshot has changed since then, the user changed it, so save
    it for the outgoing light/dark mode. Reinstalls therefore never overwrite
    a custom wallpaper unless the one-shot reset action was explicitly chosen.
    """
    state = _load_wallpaper_state()
    was_initialized = bool(state["initialized"])
    was_enabled = bool(state["enabled"])
    feature = _env_bool("FEAT_WALLPAPERS")
    enabled = was_enabled if feature is None else feature
    reset = _env_bool("MTTKDE_RESET_WALLPAPERS") is True
    existing_env = _env_bool("MTTKDE_EXISTING_INSTALL")
    existing = (was_initialized or context != "install") \
        if existing_env is None else existing_env
    current = (_current_wallpapers() if current_snapshot is None
               else _normalize_wallpaper_snapshot(current_snapshot))
    outgoing = state.get("active_mode")
    last_applied = _normalize_wallpaper_snapshot(state.get("last_applied"))
    modes = state["modes"]

    state["initialized"] = True
    state["enabled"] = bool(enabled)

    if not enabled:
        state["active_mode"] = mode
        state["last_applied"] = current
        _save_wallpaper_state(state)
        return True

    if reset:
        modes["light"] = []
        modes["dark"] = []
        last_applied = []

    if current and not reset:
        if outgoing in ("light", "dark") and last_applied \
                and current != last_applied:
            modes[outgoing] = current
        elif (not was_initialized and existing
              and not _snapshot_is_theme_managed(current)):
            # Upgrade from a release that predates smart state: a non-theme
            # wallpaper is presumed deliberate and belongs to the current mode.
            modes[mode] = current
        elif not was_enabled and not _snapshot_is_theme_managed(current):
            # Wallpaper management was disabled and is being re-enabled.
            modes[mode] = current

    target = _normalize_wallpaper_snapshot(modes.get(mode))
    if target:
        success = current == target or _apply_wallpaper_snapshot(target)
        applied = target
    else:
        success, wp = _apply_theme_wallpaper(mode)
        applied = _theme_wallpaper_snapshot(current, wp) if wp else []
        if not success and applied:
            # The official helper is preferred, but a headless install or a
            # temporarily unavailable session bus must still leave correct
            # on-disk per-screen config for the final Plasma restart.
            success = _apply_wallpaper_snapshot(applied)

    if success:
        state["active_mode"] = mode
        state["last_applied"] = applied
    _save_wallpaper_state(state)
    return success


def flush_icon_caches() -> None:
    home = Path.home()
    for sub in (".cache/icon-cache.kcache", ".cache/kiconthemes"):
        shutil.rmtree(home / sub, ignore_errors=True)


def _apply_local_extras(mode: str) -> None:
    if _have("kvantummanager"):
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        try:
            # The base profile has respect_DE=true, so KDE's active palette is
            # the light/dark source of truth.  Selecting the separate Dark
            # profile pins Kvantum's own colors and leaves mixed surfaces when
            # Plasma's native appearance toggle changes the KDE palette.
            _run_user(
                ["kvantummanager", "--set", KVANTUM_THEME],
                timeout=15, env=env,
            )
        except subprocess.TimeoutExpired:
            pass

    home = Path.home()
    gtk_dest = home / ".themes"
    gtk_theme = "MacTahoeLiquidKde-Dark" if mode == "dark" else "MacTahoeLiquidKde-Light"

    # Releases 0.36.0-0.36.2 installed gtk.css as a per-user symlink. GTK
    # loads that file after the selected theme, so it permanently overrode
    # kde-gtk-config/gsettings and prevented Nautilus from following Plasma's
    # native appearance toggle. Remove only the symlink shape created by those
    # releases; never delete a user's own regular gtk.css.
    gtk4_css = home / ".config/gtk-4.0/gtk.css"
    try:
        if gtk4_css.is_symlink() and gtk4_css.readlink().name in {
            "gtk-Dark.css", "gtk-Light.css",
        }:
            gtk4_css.unlink()
    except OSError as exc:
        print(f"theme apply: legacy gtk4 override cleanup skipped: {exc}",
              file=sys.stderr)

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
        widget, aurorae = KVANTUM_STYLE, "__aurorae__svg__MacTahoeLiquidKde-Dark"
    else:
        laf, icon, cursor = LAF_LIGHT, "MacTahoeLiquidKde-Icons", "MacTahoeLiquidKde"
        scheme, plasma = "MacTahoeLiquidKdeLight", "MacTahoeLiquidKde-Light"
        widget, aurorae = KVANTUM_STYLE, "__aurorae__svg__MacTahoeLiquidKde-Light"

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

    return apply_color_scheme(scheme)


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

# Our own KWin effects: we manage these on purpose, so they're never treated
# as user effects to watch over. Everything else the user enabled in [Plugins]
# is a third-party effect we must not silently break.
_OWN_KWIN_EFFECT_KEYS = frozenset({
    "liquidglassEnabled", "glassEnabled", "blurEnabled",
})


def _kwinrc_path() -> Path:
    return _xdg_config() / "kwinrc"


def _effect_id_for_key(key: str) -> str:
    """kwinrc [Plugins] key -> KWin effect id. Third-party binary effects use
    the ``kwin4_effect_<name>`` id (e.g. shapecornersEnabled -> the effect KWin
    reports as ``kwin4_effect_shapecorners`` or, on some builds, ``shapecorners``
    -- we match either)."""
    return key[:-len("Enabled")] if key.endswith("Enabled") else key


def _snapshot_foreign_effects() -> list[str]:
    """The effect ids the user has ENABLED in kwinrc [Plugins] that aren't ours.
    A theme switch fires org.kde.KWin.reconfigure, which makes KWin re-scan and
    re-load effects; a third-party COMPILED effect whose .so is ABI-incompatible
    with the running KWin (common after a KWin update) fails to load and drops
    out of the live effect list. The user's config key stays true, so this is a
    runtime-load failure, not a config loss -- we can't fix their binary, but we
    must not let it happen SILENTLY (#46)."""
    plugins = _parse_ini(_kwinrc_path()).get("Plugins", {})
    return [
        _effect_id_for_key(key)
        for key, value in plugins.items()
        if key.endswith("Enabled") and key not in _OWN_KWIN_EFFECT_KEYS
        and value.strip().lower() == "true"
    ]


def _kwin_loaded_effects() -> set[str] | None:
    """KWin's currently-LOADED effect ids (not activeEffects -- an enabled but
    idle effect is loaded yet not active). None when the query can't run (no
    session bus / no qdbus / timeout), so callers degrade to silence rather
    than a false 'effect broke' warning on headless or first-login installs."""
    if not _has_session_dbus():
        return None
    for q in ("qdbus6", "qdbus-qt6", "qdbus"):
        if not _have(q):
            continue
        try:
            res = _run_user(
                [q, "org.kde.KWin", "/Effects",
                 "org.kde.kwin.Effects.loadedEffects"],
                timeout=10, capture=True)
        except subprocess.TimeoutExpired:
            return None
        if res.returncode != 0:
            return None
        return {e.strip() for e in res.stdout.replace("\n", ",").split(",")
                if e.strip()}
    return None


def _effect_is_loaded(effect: str, loaded: set[str]) -> bool:
    return (
        effect in loaded
        or f"kwin4_effect_{effect}" in loaded
        or any(effect in candidate for candidate in loaded)
    )


def _restore_or_warn_foreign_effects(enabled_before: list[str]) -> list[str]:
    """Restore third-party effects after KWin's global reconfigure.

    A reconfigure can leave a compiled effect such as ``shapecorners``
    unloaded.  First ask KWin to load every missing effect again; warn only if
    it is still missing after bounded retries.  The user's Enabled key is
    never changed, so an ABI-incompatible effect remains recoverable after it
    is rebuilt instead of being silently disabled.
    """
    if not enabled_before:
        return []
    loaded = _kwin_loaded_effects()
    if loaded is None:
        return []

    missing = [
        effect for effect in enabled_before
        if not _effect_is_loaded(effect, loaded)
    ]
    for effect in missing:
        _qdbus("org.kde.KWin", "/Effects",
               "org.kde.kwin.Effects.loadEffect", effect)

    # Effect loading is asynchronous. Give explicitly restored effects a
    # bounded window to appear before reporting a real failure.
    for attempt in range(3):
        if not missing:
            break
        if attempt:
            time.sleep(1)
        refreshed = _kwin_loaded_effects()
        if refreshed is None:
            return []
        missing = [
            effect for effect in missing
            if not _effect_is_loaded(effect, refreshed)
        ]

    for effect in missing:
        print(
            f"theme apply: your KWin effect '{effect}' is enabled but KWin "
            "could not load it after the theme switch. The switcher retried "
            "it and left your setting enabled; rebuild/reinstall the effect "
            "for the current KWin if it remains absent.",
            file=sys.stderr,
        )
    return missing


def reconfigure_kwin_preserving_foreign_effects() -> list[str]:
    """Reconfigure KWin, then restore every enabled third-party effect."""
    foreign_effects = _snapshot_foreign_effects()
    _qdbus("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    return _restore_or_warn_foreign_effects(foreign_effects)


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
    nothing — silent success here would mask a sudo'd-uninstall failure."""
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

    # signal.signal() only works on the main thread. The installer UI and the
    # portal watcher run steps off-thread, where registering a handler raises
    # ValueError; guard it so the cycle still runs (it just can't intercept a
    # mid-cycle SIGTERM there — the finally still restores the target on disk).
    handlers_installed = False
    old_term = old_int = None
    if threading.current_thread() is threading.main_thread():
        try:
            old_term = signal.signal(signal.SIGTERM, _on_signal)
            old_int = signal.signal(signal.SIGINT, _on_signal)
            handlers_installed = True
        except ValueError:
            handlers_installed = False
    try:
        phase_ok.append(_kwrite("--file", "kdeglobals", "--group", "KDE",
                                "--key", "widgetStyle", "Breeze"))
        phase_ok.append(bool(_broadcast_widget_style_change("Breeze")))
        time.sleep(0.4)
    finally:
        _restore_target()
        if handlers_installed:
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
    widget = KVANTUM_STYLE
    laf = LAF_DARK if mode == "dark" else LAF_LIGHT

    # Record which third-party KWin effects the user has enabled before we
    # trigger the reconfigure that makes KWin re-scan effects. If one fails to
    # reload (an ABI-incompatible third-party .so), we warn by name instead of
    # letting it break silently (#46). We never touch its config key.
    foreign_effects = _snapshot_foreign_effects()

    # Capture before the live look-and-feel apply.  Even if a third-party LAF
    # carries wallpaper defaults, it must not erase the outgoing custom choice
    # before our per-mode state has seen it.
    wallpaper_before = _current_wallpapers()
    config_ok = write_kde_theme_config(mode)
    if not config_ok:
        print("theme apply: core KDE config writes failed, theme not "
              "fully applied", file=sys.stderr)
    try:
        _apply_local_extras(mode)
    except Exception as exc:
        print(f"theme apply: extras step failed, continuing: {exc!r}",
              file=sys.stderr)
    if context != "install":
        if not _apply_lookandfeel_live(laf):
            print("theme apply: live look-and-feel apply skipped",
                  file=sys.stderr)
    try:
        _apply_wallpaper(mode, context=context,
                         current_snapshot=wallpaper_before)
    except Exception as exc:
        print(f"theme apply: wallpaper step failed, continuing: {exc!r}",
              file=sys.stderr)
    if not apply_cursortheme_live(cursor):
        print("theme apply: live cursor apply skipped", file=sys.stderr)
    if not cycle_widget_style_live(widget):
        print("theme apply: widget-style cycle skipped", file=sys.stderr)
    # Keep the dock translucent so the glass shows through (a theme apply can
    # drop panelOpacity, painting an opaque black panel over the effect).
    patch_dock_transparency()
    _qdbus("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    # After KWin re-scans effects, restore a user's third-party effects and
    # warn if one still cannot load (best-effort when KWin is unavailable).
    _restore_or_warn_foreign_effects(foreign_effects)
    return config_ok


def follow_system(light: bool = False) -> int:
    """Apply whichever mode the desktop currently wants (System Settings /
    quick-settings choice), so a NATIVE light/dark toggle drives our full
    theme. No-op success when the current mode can't be read (don't guess and
    fight the user's real state).

    light=True is the portal-watcher path. A native toggle flips ONLY the KDE
    color scheme, leaving our other per-mode pieces on the previous variant:
    the GTK theme, the Kvantum theme, the icon theme, the cursor, the LAF
    package AND the Aurorae window-decoration theme all lag behind. So we sync
    EVERY piece — write_kde_theme_config covers LAF/icons/scheme/widgetStyle/
    cursor/aurorae, the live GTK/icon/Kvantum/cursor niceties bring running
    apps up to date, and a KWin reconfigure + Plasma-shell refresh repaint the
    window decorations (X/maximise buttons) and the global menu / panels, which
    do NOT follow a bare color-scheme change on their own. We only SKIP the full
    LAF-apply retries (the native toggle already applied the look-and-feel), so
    this stays fast and doesn't fight the session."""
    mode = detect_mode_by_system()
    if mode is None:
        return 0
    if not light:
        return 0 if apply(mode, context="user") else 1

    cursor = "MacTahoeLiquidKde-Dark" if mode == "dark" else "MacTahoeLiquidKde"
    widget = KVANTUM_STYLE
    ok = write_kde_theme_config(mode)
    try:
        _apply_wallpaper(mode, context="user")
        _apply_local_extras(mode)   # GTK swap + icon-cache flush + Kvantum set
    except Exception as exc:
        print(f"theme follow: extras failed: {exc!r}", file=sys.stderr)
        ok = False
    # Live niceties so running apps catch up without a logout. Best-effort:
    # a missing tool must not fail the sync.
    apply_cursortheme_live(cursor)
    cycle_widget_style_live(widget)
    # A manual theme change from System Settings drops the dock's panelOpacity,
    # so re-assert it here too — this is the path the portal watcher runs.
    patch_dock_transparency()
    # Repaint the window decorations: Aurorae reads its theme from kwinrc and
    # only restyles on a reconfigure. This is the SAFE reload path — it does
    # NOT restart KWin (verified against KWin's D-Bus docs). We deliberately do
    # NOT touch plasmashell here: refreshCurrentShell() is an internal API that
    # reloads the whole shell and drops the panel, so the global menu is left
    # to follow the color scheme on its own.
    reconfigure_kwin_preserving_foreign_effects()
    return 0 if ok else 1


def watch_portal() -> int:
    """Block on the freedesktop appearance ``color-scheme`` change signal and
    apply the matching theme each time the user toggles light/dark natively.
    Event-driven (a blocking D-Bus signal read), never a poll loop — this is
    the init-agnostic bridge (systemd AND OpenRC) that makes GTK apps like
    Nautilus follow the native toggle, which on its own only flips Qt colors
    and leaves the GTK theme on the wrong variant (#46)."""
    if not _have("gdbus") or not _has_session_dbus():
        print("theme watch: no session bus / gdbus — portal watch unavailable",
              file=sys.stderr)
        return 1
    runtime_value = os.environ.get("XDG_RUNTIME_DIR")
    runtime = Path(runtime_value) if runtime_value else None
    lock_dir = runtime if runtime is not None and runtime.is_dir() else (
        Path(os.environ.get("XDG_STATE_HOME") or
             str(Path.home() / ".local/state")) / "mac-tahoe-liquid-kde"
    )
    try:
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock = (lock_dir / "mac-tahoe-liquid-kde-gtk-sync.lock").open(
            "w", encoding="utf-8",
        )
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock.write(f"{os.getpid()}\n")
        lock.flush()
    except (OSError, BlockingIOError):
        # XDG autostart and an install-time launch can overlap. The process
        # already holding the lock owns the portal subscription.
        return 0
    # Converge once up front (a toggle may have happened before we started, e.g.
    # autostart lag): make GTK match the current mode.
    follow_system(light=True)
    proc = subprocess.Popen(
        ["gdbus", "monitor", "--session",
         "--dest", "org.freedesktop.portal.Desktop"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        bufsize=1,  # line-buffered: react per line, don't wait for a full block
        preexec_fn=_drop_privs_in_child,
    )
    stop_requested = False

    def _stop_monitor(_signum=None, _frame=None):
        nonlocal stop_requested
        stop_requested = True
        try:
            proc.terminate()
        except OSError:
            pass

    old_term = signal.signal(signal.SIGTERM, _stop_monitor)
    old_int = signal.signal(signal.SIGINT, _stop_monitor)
    last = 0.0
    try:
        for line in proc.stdout:
            # Only react to the appearance color-scheme change, nothing else
            # the portal emits.
            if "SettingChanged" in line and "color-scheme" in line \
                    and "appearance" in line:
                # Debounce: a single toggle can emit the signal more than once;
                # coalesce bursts so we don't stack GTK swaps.
                now = time.monotonic()
                if now - last < 1.0:
                    continue
                last = now
                follow_system(light=True)
    except KeyboardInterrupt:
        stop_requested = True
    finally:
        if proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGINT, old_int)
    # A requested stop is clean. If gdbus died independently, report failure
    # so a future supervisor can restart the watcher.
    return 0 if stop_requested else 1


USAGE = ("Usage: mac-tahoe-theme-switch "
         "{light|dark|auto|follow-system|watch-portal} [install]")


def main(argv: list[str]) -> int:
    if not argv:
        print(USAGE, file=sys.stderr)
        return 1

    _sync_session_env()
    mode = argv[0]
    if mode == "watch-portal":
        return watch_portal()
    if mode == "follow-system":
        return follow_system()
    if mode == "auto":
        mode = detect_mode_by_time()
    if mode not in ("light", "dark"):
        print(USAGE, file=sys.stderr)
        return 1

    context = argv[1] if len(argv) > 1 else "user"
    return 0 if apply(mode, context=context) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
