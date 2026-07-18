"""macOS wallpapers: copies src/offline/wallpapers/<id>/ bundles (Plasma
layout: metadata.json + contents/images[_dark]/) into ~/.local/share/wallpapers.
Fully offline — no download phase."""

import shutil
from pathlib import Path

from steps._helpers import (
    HOME, fail, info, offline, ok, reinstall,
)
from utils import safe_copy

DEST_DIR = HOME / ".local/share/wallpapers"
OFFLINE_DIR = offline("wallpapers")


def install() -> None:
    pre = {p.name for p in DEST_DIR.glob("*/") if p.is_dir()}
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    n_inst = n_re = 0
    for wp in sorted(OFFLINE_DIR.glob("Mac*/")):
        if not wp.is_dir():
            continue
        # metadata.json is what Plasma lists the wallpaper by — skip the
        # bundle rather than ship a half-installed entry.
        if not (wp / "metadata.json").is_file():
            fail(f"{wp.name} (missing metadata.json in offline bundle)")
            continue
        if not safe_copy(wp, DEST_DIR / wp.name):
            fail(f"{wp.name} (copy failed)")
            continue
        if wp.name in pre:
            reinstall(wp.name); n_re += 1
        else:
            ok(f"{wp.name} (installed)"); n_inst += 1
    info(f"{n_inst + n_re} wallpapers — {n_inst} installed, {n_re} reinstalled")


_FIXED_NAMES = (
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
    info(f"{n} wallpapers removed")
