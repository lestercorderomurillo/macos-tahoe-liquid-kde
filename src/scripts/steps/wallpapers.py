"""macOS wallpapers: copies src/offline/wallpapers/<id>/ bundles (Plasma
layout: metadata.json + contents/images[_dark]/) into ~/.local/share/wallpapers.
Fully offline — no download phase."""

from localization import tr

import shutil
from pathlib import Path

from steps._helpers import (
    DATA_HOME, fail, info, offline, ok, reinstall,
)
from utils import safe_copy
from owned_assets import install as install_owned, remove_owned

DEST_DIR = DATA_HOME / "wallpapers"
OFFLINE_DIR = offline("wallpapers")


def _update_package(source: Path, target: Path) -> bool:
    # Plasma's slideshow watcher interprets removing the package directory
    # as an uninstall and can recursively delete its replacement (#157).
    if target.is_symlink() or not target.is_dir():
        return safe_copy(source, target)

    from steps.fonts import _copy_font
    for entry in source.iterdir():
        destination = target / entry.name
        if entry.is_symlink():
            if destination.is_symlink() and destination.readlink() == entry.readlink():
                continue
            if destination.is_dir() and not destination.is_symlink():
                shutil.rmtree(destination)
            else:
                destination.unlink(missing_ok=True)
            destination.symlink_to(entry.readlink())
        elif entry.is_dir():
            if not _update_package(entry, destination):
                return False
        else:
            if destination.is_symlink():
                destination.unlink()
            elif destination.is_dir():
                shutil.rmtree(destination)
            _copy_font(entry, destination)

    for obsolete in target.iterdir():
        if not (source / obsolete.name).exists() and not (source / obsolete.name).is_symlink():
            if obsolete.is_symlink() or not obsolete.is_dir():
                obsolete.unlink()
            else:
                shutil.rmtree(obsolete)
    return True


def install() -> None:
    from installer_choices import selected
    options = selected()
    if options.get("wallpaper") == "custom":
        source = Path(options["wallpaper_path"])
        from PyQt6.QtGui import QImageReader
        if not source.is_file() or not QImageReader(str(source)).canRead():
            fail("The selected wallpaper is not a readable image")
            return
        custom = DEST_DIR / "MacTahoe-Custom"
        custom.mkdir(parents=True, exist_ok=True)
        from steps.fonts import _copy_font
        def copy(src, dst):
            _copy_font(src, dst)
            return True
        install_owned("wallpapers", source, custom / "wallpaper", copy)
    pre = {p.name for p in DEST_DIR.glob("*/") if p.is_dir()}
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    n_inst = n_re = 0
    for wp in sorted(OFFLINE_DIR.glob("Mac*/")):
        if not wp.is_dir():
            continue
        # metadata.json is what Plasma lists the wallpaper by — skip the
        # bundle rather than ship a half-installed entry.
        if not (wp / "metadata.json").is_file():
            fail(tr('{value1} (missing metadata.json in offline bundle)', value1=wp.name))
            continue
        if not install_owned("wallpapers", wp, DEST_DIR / wp.name, _update_package):
            fail(tr('{value1} (copy failed)', value1=wp.name))
            continue
        if wp.name in pre:
            reinstall(wp.name); n_re += 1
        else:
            ok(tr('{value1} (installed)', value1=wp.name)); n_inst += 1
    info(tr('{value1} wallpapers — {n_inst} installed, {n_re} reinstalled', value1=n_inst + n_re, n_inst=n_inst, n_re=n_re))


_FIXED_NAMES = (
    "MacPrism", "MacTahoe-Custom", "MacGoldenGate",
    "MacTahoe", "MacTahoe-Beach-Dawn", "MacTahoe-Beach-Day",
    "MacTahoe-Beach-Dusk", "MacTahoe-Beach-Night",
    "MacTahoe-Iridescence",
    "MacTahoe-Landscape-Morning", "MacTahoe-Landscape-Evening",
    "MacTahoe-Landscape-Night",
    "MacHeritage-Sequoia", "MacHeritage-Sequoia-Sunrise",
    "MacHeritage-Sonoma", "MacHeritage-Sonoma-Horizon",
    "MacHeritage-Ventura", "MacHeritage-Monterey", "MacHeritage-BigSur",
)


def uninstall() -> None:
    n = remove_owned("wallpapers", DEST_DIR)
    info(tr('{n} wallpapers removed', n=n))
