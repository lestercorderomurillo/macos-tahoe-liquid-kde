import os
import shutil
import subprocess

from installer.steps._helpers import HOME, fail, have, ok, offline, warn

NAUTILUS_DESKTOP = "org.gnome.Nautilus.desktop"
DOLPHIN_DESKTOP = "org.kde.dolphin.desktop"
MIME_FOLDER = "inode/directory"
MIME_SEARCH = "application/x-gnome-saved-search"


def deps():
    return ["nautilus"]


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


def _apply_gsettings() -> None:
    if not have("gsettings"):
        return
    for schema, key, value in _FINDER_GSETTINGS:
        subprocess.run(
            ["gsettings", "set", schema, key, value],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )


def install() -> None:
    if not _is_kde():
        warn("Not running under KDE Plasma — skipping Nautilus setup")
        return

    if not have("nautilus"):
        fail("Nautilus not installed (expected deps to have provided it)")
        return

    if have("xdg-mime"):
        # xdg-mime spits out a `qtpaths: command not found` warning on
        # Qt6-only systems (it greps for the legacy Qt5 helper). The
        # default-handler write still succeeds, so we just hush stderr.
        if subprocess.run(
            ["xdg-mime", "default", NAUTILUS_DESKTOP, MIME_FOLDER],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0:
            ok("Nautilus set as default for folders")
        subprocess.run(
            ["xdg-mime", "default", NAUTILUS_DESKTOP, MIME_SEARCH],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        warn("xdg-mime not found — default file manager not changed")

    _apply_overrides()
    _apply_gsettings()
    subprocess.run(["nautilus", "-q"], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok("Nautilus configured")


def uninstall() -> None:
    if not _is_kde():
        return
    if have("dolphin") and have("xdg-mime"):
        if subprocess.run(
            ["xdg-mime", "default", DOLPHIN_DESKTOP, MIME_FOLDER],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0:
            ok("Dolphin restored as default for folders")
        subprocess.run(
            ["xdg-mime", "default", DOLPHIN_DESKTOP, MIME_SEARCH],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    nautilus_css = HOME / ".config/nautilus/gtk.css"
    if nautilus_css.is_file():
        try: nautilus_css.unlink()
        except OSError: pass
