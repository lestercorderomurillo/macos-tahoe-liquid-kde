import shutil
import subprocess

from installer.steps._helpers import (
    HOME, fail, have, info, install_tree, offline, ok, qdbus_call, remove_tree,
)

DEST_DIR = HOME / ".themes"
VARIANTS = ("MacTahoeLiquidKde-Light", "MacTahoeLiquidKde-Dark")
GTK4_DEST = HOME / ".config/gtk-4.0"
GTK4_FILES_TO_REMOVE = (
    "gtk.css", "gtk-dark.css", "gtk-Dark.css", "gtk-Light.css",
    "colors.css", "window_decorations.css",
)
GTK4_DIRS_TO_REMOVE = ("assets", "windows-assets")


def install() -> None:
    src = offline("gtk")
    if not src.is_dir():
        fail(f"GTK theme source not found at {src}")
        return

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    for v in VARIANTS:
        if not (src / v).is_dir():
            continue
        if install_tree(src / v, DEST_DIR / v, v):
            n += 1
    if have("gsettings"):
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.wm.preferences",
             "button-layout", "close,minimize,maximize:"],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    info(f"{n} GTK themes installed/reinstalled")


def uninstall() -> None:
    n = 0
    for v in VARIANTS:
        if remove_tree(DEST_DIR / v, f"{v} removed"):
            n += 1

    # Wipe ~/.config/gtk-4.0/* — kde-gtk-config will regenerate its own
    # minimal gtk.css / colors.css / window_decorations.css on the next
    # theme change. Leaving our files mixed with KDE's output causes
    # split state.
    for sub in GTK4_DIRS_TO_REMOVE:
        shutil.rmtree(GTK4_DEST / sub, ignore_errors=True)
    for fn in GTK4_FILES_TO_REMOVE:
        try: (GTK4_DEST / fn).unlink()
        except FileNotFoundError: pass
        except OSError: pass

    qdbus_call("org.kde.GtkConfig", "/GtkConfig",
               "org.kde.GtkConfig.setGtkTheme", "Breeze")
    if have("gsettings"):
        for schema, key in (
            ("org.gnome.desktop.interface", "gtk-theme"),
            ("org.gnome.desktop.interface", "color-scheme"),
            ("org.gnome.desktop.wm.preferences", "button-layout"),
        ):
            subprocess.run(["gsettings", "reset", schema, key],
                           check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    info(f"{n} GTK themes removed")
