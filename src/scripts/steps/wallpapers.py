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

DEST_DIR = DATA_HOME / "wallpapers"
OFFLINE_DIR = offline("wallpapers")


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
        shutil.copyfile(source, custom / "wallpaper")
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
        if not safe_copy(wp, DEST_DIR / wp.name):
            fail(tr('{value1} (copy failed)', value1=wp.name))
            continue
        if wp.name in pre:
            reinstall(wp.name); n_re += 1
        else:
            ok(tr('{value1} (installed)', value1=wp.name)); n_inst += 1
    info(tr('{value1} wallpapers — {n_inst} installed, {n_re} reinstalled', value1=n_inst + n_re, n_inst=n_inst, n_re=n_re))


_FIXED_NAMES = (
    "MacTahoe-Custom", "MacGoldenGate",
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
    n = 0
    for name in _FIXED_NAMES:
        d = DEST_DIR / name
        if d.is_dir():
            try:
                shutil.rmtree(d)
                ok(name); n += 1
            except OSError:
                fail(name)
    # Legacy index-numbered landscapes from earlier releases.
    for d in DEST_DIR.glob("MacTahoe-Landscape-[0-9][0-9]/"):
        try:
            shutil.rmtree(d)
            ok(d.name); n += 1
        except OSError:
            fail(d.name)
    info(tr('{n} wallpapers removed', n=n))
