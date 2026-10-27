from localization import tr
import shutil

from glass_surfaces import apply_plasma_surface_defaults

from steps._helpers import (
    DATA_HOME, fail, info, install_tree, kw_write, offline, remove_tree, temp_dir, warn,
)

DEST_DIR = DATA_HOME / "plasma/desktoptheme"
LEGACY = ("MacTahoe-Dark", "MacTahoe-Light")
VARIANTS = ("MacTahoeLiquidKde-Dark", "MacTahoeLiquidKde-Light")

def install() -> None:
    src = offline("plasma-theme")
    if not src.is_dir():
        fail(tr('Plasma theme source not found at {src}', src=src))
        return
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    # Purge legacy names from pre-0.6.2 installs.
    for stale in LEGACY:
        shutil.rmtree(DEST_DIR / stale, ignore_errors=True)

    n = 0
    for v in VARIANTS:
        if not (src / v).is_dir():
            continue
        with temp_dir("plasma-surfaces-") as staging:
            source = staging / v
            shutil.copytree(src / v, source)
            apply_plasma_surface_defaults(source)
            from theme_accent import apply as apply_accent
            apply_accent(source)
            if install_tree(source, DEST_DIR / v, v):
                n += 1
    info(tr('{n} Plasma themes installed/reinstalled', n=n))


def uninstall() -> None:
    n = 0
    for v in VARIANTS:
        remove_tree(DEST_DIR / (v + "-ReducedTransparency"))
        if remove_tree(DEST_DIR / v, v):
            n += 1
    if not kw_write("--file", "plasmarc", "--group", "Theme",
                    "--key", "name", "default"):
        warn(tr("Active Plasma theme not reset to 'default' — kwriteconfig6 unavailable. Files are removed but Plasma will still try to load MacTahoeLiquidKde until you set plasmarc:Theme.name=default manually."))
    info(tr('{n} Plasma themes removed', n=n))
