import os
import shutil
import subprocess
import time

from steps._helpers import HOME, fail, have, kw_write, ok, offline, warn
from utils import run_user

NAUTILUS_DESKTOP = "org.gnome.Nautilus.desktop"
DOLPHIN_DESKTOP = "org.kde.dolphin.desktop"
MIME_FOLDER = "inode/directory"
MIME_SEARCH = "application/x-gnome-saved-search"
_NAUTILUS_TOOL_TIMEOUT_SECONDS = 5


def deps():
    return ["nautilus"]


def _set_default(desktop_id: str, mime: str) -> bool:
    """Write a default-handler binding the way xdg-mime would, but
    directly: kwriteconfig6 against ``~/.config/mimeapps.list``, group
    ``[Default Applications]``. Avoids the xdg-mime shell dispatcher
    (which can hang waiting for legacy Qt5 helpers in a Qt6-only
    install) while landing the same file format Plasma reads."""
    return kw_write(
        "--file", "mimeapps.list",
        "--group", "Default Applications",
        "--key", mime, desktop_id,
    )


def _is_kde() -> bool:
    return (
        "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "")
        or "plasma" in os.environ.get("XDG_SESSION_DESKTOP", "")
        or bool(os.environ.get("KDE_FULL_SESSION"))
        or bool(os.environ.get("KDE_SESSION_VERSION"))
    )


def _apply_overrides() -> None:
    src = offline("nautilus")
    if not src.is_dir():
        return
    copied = 0
    for item in src.iterdir():
        if item.name.startswith("README"):
            continue
        if item.name == "bookmarks":
            (HOME / ".config/gtk-3.0").mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(item, HOME / ".config/gtk-3.0/bookmarks")
                copied += 1
            except OSError:
                pass
        elif item.name == "gtk.css":
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
    try:
        rc = run_user(
            [
                "gdbus", "call", "--session",
                "--dest", "org.gnome.Nautilus",
                "--object-path", "/org/gnome/Nautilus",
                "--method", "org.freedesktop.Application.Quit",
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
        warn("Live Nautilus restart skipped")
        return False
    for _ in range(50):
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
    if not _is_kde():
        warn("Not running under KDE Plasma — skipping Nautilus setup")
        return

    if not have("nautilus"):
        fail("Nautilus not installed (expected deps to have provided it)")
        return

    # ``xdg-mime`` is a shell dispatcher that, under KDE, calls
    # ``kwriteconfig6 mimeapps.list`` and ``kbuildsycoca6`` — both of
    # which we already have. Going direct shaves the 5s timeout window
    # (xdg-mime's KDE backend can spend that just probing for legacy
    # Qt5 helpers) and removes a transient dependency.
    if _set_default(NAUTILUS_DESKTOP, MIME_FOLDER):
        ok("Nautilus set as default for folders")
    _set_default(NAUTILUS_DESKTOP, MIME_SEARCH)

    _apply_overrides()
    _apply_gsettings()
    if _nautilus_running():
        _restart_running_nautilus()
    ok("Nautilus configured")


def uninstall() -> None:
    if not _is_kde():
        return
    if have("dolphin"):
        if _set_default(DOLPHIN_DESKTOP, MIME_FOLDER):
            ok("Dolphin restored as default for folders")
        _set_default(DOLPHIN_DESKTOP, MIME_SEARCH)
    nautilus_css = HOME / ".config/nautilus/gtk.css"
    if nautilus_css.is_file():
        try: nautilus_css.unlink()
        except OSError: pass
