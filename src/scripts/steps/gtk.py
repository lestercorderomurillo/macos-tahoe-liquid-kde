from localization import tr
import os
import subprocess
import tempfile
from pathlib import Path

from steps._helpers import (
    HOME, fail, have, info, install_tree, offline, ok, qdbus_call, remove_tree,
)
from utils import run_user

DEST_DIR = HOME / ".themes"
VARIANTS = ("MacTahoeLiquidKde-Light", "MacTahoeLiquidKde-Dark")
GTK4_DEST = HOME / ".config/gtk-4.0"
GTK4_FILES_TO_REMOVE = (
    "gtk.css", "gtk-dark.css", "gtk-Dark.css", "gtk-Light.css",
    "gtk-Adaptive.css", "gtk-AdaptiveLegacy.css",
    "colors.css", "window_decorations.css",
)
GTK4_DIRS_TO_REMOVE = ("assets", "windows-assets")


def deps() -> list[str]:
    return ["kde-gtk-config:kde-gtk-config"]


def _retain_gtk4_css_ownership(source_root: Path) -> None:
    """Recognize our old copied sheet before replacing its comparison sources."""
    from theme_switch import _gtk4_css_is_replaceable
    css = GTK4_DEST / "gtk.css"
    if css.is_symlink() or not css.is_file():
        return
    if not (_gtk4_css_is_replaceable(css, DEST_DIR)
            or _gtk4_css_is_replaceable(css, source_root)):
        return
    original = css.read_bytes()
    adaptive = GTK4_DEST / "gtk-AdaptiveLegacy.css"
    # Preserve the currently displayed sheet until the final theme activation
    # regenerates it from the newly installed CSS and selected accent.
    with tempfile.NamedTemporaryFile(dir=GTK4_DEST, prefix=".mttkde-gtk-",
                                     delete=False) as stream:
        staged = Path(stream.name)
        stream.write(original)
    try:
        if css.read_bytes() != original:
            return
        staged.replace(adaptive)
        staged.symlink_to(adaptive.name)
        staged.replace(css)
    finally:
        staged.unlink(missing_ok=True)


def install() -> None:
    src = offline("gtk")
    if not src.is_dir():
        fail(tr('GTK theme source not found at {src}', src=src))
        return

    _retain_gtk4_css_ownership(src)
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    for v in VARIANTS:
        if not (src / v).is_dir():
            continue
        if install_tree(src / v, DEST_DIR / v, v):
            from window_controls import apply_gtk_controls
            apply_gtk_controls(DEST_DIR / v)
            from theme_accent import apply as apply_accent
            apply_accent(DEST_DIR / v)
            from window_shadows import apply_gtk
            apply_gtk(DEST_DIR / v)
            from theme_switch import gtk4_compatible_css
            for css in (DEST_DIR / v / "gtk-4.0").glob("*.css"):
                source = css.read_text(encoding="utf-8")
                compatible = gtk4_compatible_css(source)
                if compatible != source:
                    css.write_text(compatible, encoding="utf-8")
            n += 1
    # A minimal Plasma session may have started before deps installed this
    # module. Load it now so the final theme switch also reaches GTK settings.
    qdbus_call("org.kde.kded6", "/kded", "org.kde.kded6.loadModule", "gtkconfig")
    from theme_switch import gtk_button_layout
    if have("gsettings") and gtk_button_layout():
        run_user(
            ["gsettings", "set", "org.gnome.desktop.wm.preferences",
             "button-layout", gtk_button_layout()],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    info(tr('{n} GTK themes installed/reinstalled', n=n))


def uninstall() -> None:
    # Compare overrides before removing their installed reference sources.
    _remove_owned_gtk4_overrides()
    n = 0
    for v in VARIANTS:
        remove_tree(DEST_DIR / (v + "-ReducedTransparency"))
        if remove_tree(DEST_DIR / v, tr('{v} removed', v=v)):
            n += 1

    qdbus_call("org.kde.GtkConfig", "/GtkConfig",
               "org.kde.GtkConfig.setGtkTheme", "Breeze")
    from window_controls import buttons_kept
    keep_buttons = buttons_kept()
    if have("gsettings"):
        for schema, key in (
            ("org.gnome.desktop.interface", "gtk-theme"),
            ("org.gnome.desktop.interface", "color-scheme"),
            *(() if keep_buttons else (("org.gnome.desktop.wm.preferences", "button-layout"),)),
        ):
            run_user(["gsettings", "reset", schema, key],
                     check=False,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    info(tr('{n} GTK themes removed', n=n))


def _remove_owned_gtk4_overrides() -> None:
    """Remove unchanged project copies, preserving KDE/user CSS and assets."""
    from theme_switch import GTK4_ADAPTIVE_CSS, gtk4_legacy_adaptive_css

    if GTK4_DEST.is_symlink() or not GTK4_DEST.is_dir():
        return
    sources = [DEST_DIR / (variant + suffix) / "gtk-4.0"
               for variant in VARIANTS for suffix in ("", "-ReducedTransparency")]

    def contents(path):
        if path.is_symlink() or not path.is_file():
            return None
        return path.read_bytes()

    def reference(source, relative):
        path = source / relative
        # copytree dereferences bundled aliases. Compare those copies too,
        # but never use an external symlink target as ownership evidence.
        if path.resolve().is_relative_to(source.resolve()) and path.is_file():
            return path.read_bytes()
        return None

    sheets = {GTK4_ADAPTIVE_CSS.strip().encode()}
    for source in sources:
        for path in source.glob("*.css"):
            data = contents(path)
            if data is not None:
                sheets.add(data.strip())
                if path.name == "gtk-Light.css":
                    for mode in ("light", "dark"):
                        sheets.add(gtk4_legacy_adaptive_css(data.decode("utf-8"), mode).strip().encode())

    owned = set()
    for name in GTK4_FILES_TO_REMOVE:
        path = GTK4_DEST / name
        data = contents(path)
        if data is not None:
            text = data.strip()
            if name == "gtk.css":
                text = text.removesuffix(b"@import 'colors.css';").rstrip()
            if text in sheets:
                owned.add(path)
    # A familiar basename alone does not prove ownership of an external link.
    targets = owned | {p.relative_to(GTK4_DEST) for p in owned}
    for name in GTK4_FILES_TO_REMOVE:
        path = GTK4_DEST / name
        if path.is_symlink() and path.readlink() in targets:
            path.unlink()
    for path in owned:
        path.unlink()

    for sub in GTK4_DIRS_TO_REMOVE:
        directory = GTK4_DEST / sub
        if directory.is_symlink() or not directory.is_dir():
            continue
        for root, _, files in os.walk(directory, topdown=False, followlinks=False):
            for name in files:
                path = Path(root) / name
                data = contents(path)
                if data is not None and any(reference(source, path.relative_to(GTK4_DEST)) == data
                                            for source in sources):
                    path.unlink()
            # Remove empty project directories only; never traverse symlinks.
            if not any(Path(root).iterdir()):
                Path(root).rmdir()
