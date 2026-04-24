import shutil

from steps._helpers import (
    HOME, fail, info, install_tree, kw_write, offline, remove_tree,
)

DEST_DIR = HOME / ".local/share/plasma/desktoptheme"
LEGACY = ("MacTahoe-Dark", "MacTahoe-Light")
VARIANTS = ("MacTahoeLiquidKde-Dark", "MacTahoeLiquidKde-Light")


def install() -> None:
    src = offline("plasma-theme")
    if not src.is_dir():
        fail(f"Plasma theme source not found at {src}")
        return
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    # Purge legacy names from pre-0.6.2 installs.
    for stale in LEGACY:
        shutil.rmtree(DEST_DIR / stale, ignore_errors=True)

    n = 0
    for v in VARIANTS:
        if not (src / v).is_dir():
            continue
        if install_tree(src / v, DEST_DIR / v, v):
            n += 1
    info(f"{n} Plasma themes installed/reinstalled")


def uninstall() -> None:
    n = 0
    for v in VARIANTS:
        if remove_tree(DEST_DIR / v, v):
            n += 1
    kw_write("--file", "plasmarc", "--group", "Theme", "--key", "name", "default")
    info(f"{n} Plasma themes removed")
