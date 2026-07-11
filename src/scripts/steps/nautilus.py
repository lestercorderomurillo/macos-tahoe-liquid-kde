import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

from steps._helpers import HOME, fail, feat_enabled, have, kw_write, ok, offline, warn
from utils import is_plasma_session, run_user

NAUTILUS_DESKTOP = "org.gnome.Nautilus.desktop"
DOLPHIN_DESKTOP = "org.kde.dolphin.desktop"
MIME_FOLDER = "inode/directory"
MIME_SEARCH = "application/x-gnome-saved-search"
_NAUTILUS_TOOL_TIMEOUT_SECONDS = 5

# XDG directories to include in the Nautilus sidebar, in display order.
# Keys correspond to XDG_xxx_DIR variables in ~/.config/user-dirs.dirs.
_XDG_SIDEBAR_ORDER = ("DESKTOP", "DOCUMENTS", "DOWNLOAD", "PICTURES", "VIDEOS", "MUSIC")


def deps():
    return ["nautilus"]


def _set_default(desktop_id: str, mime: str) -> bool:
    """Write the default-handler key straight to mimeapps.list — the
    xdg-mime dispatcher can hang probing legacy Qt5 helpers on Qt6-only
    installs, and this lands the same format Plasma reads."""
    return kw_write(
        "--file", "mimeapps.list",
        "--group", "Default Applications",
        "--key", mime, desktop_id,
    )


def _generate_bookmarks() -> None:
    """Write ~/.config/gtk-3.0/bookmarks from the user's XDG dirs (labels
    follow the on-disk folder names, i.e. the system language). The
    pre-existing file is backed up once and restored on uninstall."""
    if not feat_enabled("nautilus_bookmarks"):
        return
    src = HOME / ".config/user-dirs.dirs"
    if not src.is_file():
        warn("~/.config/user-dirs.dirs not found — skipping Nautilus bookmarks")
        return

    dirs: dict[str, Path] = {}
    for line in src.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r'^XDG_(\w+)_DIR="(.+)"$', line)
        if m:
            key = m.group(1)
            path_str = m.group(2).replace("$HOME", str(HOME))
            dirs[key] = Path(path_str)

    lines: list[str] = []
    for key in _XDG_SIDEBAR_ORDER:
        path = dirs.get(key)
        if path is None or not path.is_dir():
            continue
        # xdg-user-dirs disables a dir by pointing it at $HOME itself —
        # never bookmark the whole home directory.
        if path == HOME:
            continue
        uri = "file://" + quote(str(path), safe="/")
        lines.append(f"{uri} {path.name}")

    if not lines:
        warn("No XDG directories found — skipping Nautilus bookmarks")
        return

    dest = HOME / ".config/gtk-3.0"
    dest.mkdir(parents=True, exist_ok=True)
    bookmarks = dest / "bookmarks"
    backup = dest / "bookmarks.mac-tahoe-backup"
    # Back up the user's own bookmarks once; reinstalls must not clobber
    # the true original with our generated file.
    if bookmarks.is_file() and not backup.is_file():
        try:
            shutil.copy2(bookmarks, backup)
        except OSError:
            pass
    bookmarks.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok(f"Bookmarks written ({len(lines)} entries)")


def _apply_overrides() -> None:
    src = offline("nautilus")
    if not src.is_dir():
        return
    copied = 0
    for item in src.iterdir():
        if item.name.startswith("README"):
            continue
        if item.name == "gtk.css":
            (HOME / ".config/nautilus").mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(item, HOME / ".config/nautilus/gtk.css")
                copied += 1
            except OSError:
                pass
    if copied:
        ok(f"Applied {copied} Nautilus override(s)")


_FINDER_GSETTINGS = (
    ("org.gnome.nautilus.preferences", "default-folder-viewer", "icon-view"),
    ("org.gnome.nautilus.preferences", "show-hidden-files", "false"),
    ("org.gnome.nautilus.preferences", "default-sort-order", "name"),
    ("org.gnome.nautilus.preferences", "show-create-link", "true"),
    ("org.gnome.nautilus.preferences", "click-policy", "double"),
    ("org.gnome.nautilus.icon-view", "default-zoom-level", "small"),
)


def _nautilus_running() -> bool:
    return run_user(
        ["pgrep", "-x", "nautilus"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def _restart_running_nautilus() -> bool:
    if not _nautilus_running():
        return False
    if not have("gdbus"):
        warn("gdbus not found — skipping live Nautilus restart")
        return False
    # Nautilus 50+ quits via org.gtk.Actions Activate("quit"), not the legacy
    # Application.Quit; the ack is immediate but exit takes ~5-10s.
    try:
        rc = run_user(
            [
                "gdbus", "call", "--session",
                "--dest", "org.gnome.Nautilus",
                "--object-path", "/org/gnome/Nautilus",
                "--method", "org.gtk.Actions.Activate",
                "quit", "[]", "{}",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).returncode
    except subprocess.TimeoutExpired:
        warn("Timed out waiting for Nautilus to quit")
        return False
    if rc != 0:
        warn(f"Live Nautilus restart skipped (gdbus rc={rc})")
        return False
    # 15s exit window — Nautilus 50.1 with multiple windows takes ~10s to
    # drain; the 100ms poll lets the relaunch start promptly.
    for _ in range(150):
        if not _nautilus_running():
            break
        time.sleep(0.1)
    else:
        warn("Nautilus did not exit cleanly — leaving it alone")
        return False

    if have("gapplication"):
        from utils import drop_privs_in_child as _drop
        subprocess.Popen(
            ["gapplication", "launch", "org.gnome.Nautilus"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            preexec_fn=_drop,
        )
        ok("Nautilus restarted")
        return True

    warn("gapplication not found — skipping Nautilus relaunch")
    return False


def _apply_gsettings() -> None:
    if not have("gsettings"):
        return
    for schema, key, value in _FINDER_GSETTINGS:
        try:
            run_user(
                ["gsettings", "set", schema, key, value],
                check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=_NAUTILUS_TOOL_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            warn(f"gsettings timed out for {schema}:{key} — skipping")


def install() -> None:
    if not is_plasma_session():
        warn("Not running under KDE Plasma — skipping Nautilus setup")
        return

    if not have("nautilus"):
        fail("Nautilus not installed (expected deps to have provided it)")
        return

    if _set_default(NAUTILUS_DESKTOP, MIME_FOLDER):
        ok("Nautilus set as default for folders")
    _set_default(NAUTILUS_DESKTOP, MIME_SEARCH)

    _generate_bookmarks()
    _apply_overrides()
    _apply_gsettings()
    if _nautilus_running():
        _restart_running_nautilus()
    ok("Nautilus configured")


def uninstall() -> None:
    if not is_plasma_session():
        return
    if have("dolphin"):
        if _set_default(DOLPHIN_DESKTOP, MIME_FOLDER):
            ok("Dolphin restored as default for folders")
        _set_default(DOLPHIN_DESKTOP, MIME_SEARCH)
    nautilus_css = HOME / ".config/nautilus/gtk.css"
    if nautilus_css.is_file():
        try: nautilus_css.unlink()
        except OSError: pass
    _restore_bookmarks()


def _restore_bookmarks() -> None:
    """Undo _generate_bookmarks(): put back the backed-up bookmarks, or
    remove the generated file when the user had none before install."""
    dest = HOME / ".config/gtk-3.0"
    bookmarks = dest / "bookmarks"
    backup = dest / "bookmarks.mac-tahoe-backup"
    try:
        if backup.is_file():
            shutil.move(str(backup), str(bookmarks))
            ok("Nautilus bookmarks restored")
        elif bookmarks.is_file():
            bookmarks.unlink()
    except OSError:
        pass
