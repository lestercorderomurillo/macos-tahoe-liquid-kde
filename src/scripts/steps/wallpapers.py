"""Wallpapers — fully bundled offline since v0.17.0.

Earlier releases downloaded the macOS heritage wallpapers from
512pixels.net on first install and cached them under
``~/.cache/mac-tahoe-liquid-kde/steps/wallpapers/``. That broke twice:

* 512pixels reorganised their CDN (``512pixels.net/downloads/...`` →
  ``media.512pixels.net/downloads/...``) and renamed Monterey + Big
  Sur, killing the install on v0.16.x.
* Every fresh install hit the network for ~270 MB of source PNGs
  before any wallpaper appeared.

v0.17 ships the full set in-repo as ~5MB JPEG q90 (re-encoded from
the 6K originals — visually indistinguishable on 4K monitors but
46 MB total instead of 273 MB). No ``download()`` phase, no mirror
JSON, no network dependency. The user always has the wallpapers
even on an air-gapped machine.

Each bundle directory follows the Plasma desktoptheme layout:

  src/offline/wallpapers/<id>/
    ├── metadata.json
    └── contents/
        ├── images/3840x2160.jpg          # light variant (or single)
        └── images_dark/3840x2160.jpg     # dark variant (auto packs only)
"""

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
        # Guard against an accidentally-empty bundle dir — the metadata
        # is the only thing Plasma reads to list the wallpaper, so if
        # it's missing we skip rather than ship a half-installed entry.
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
