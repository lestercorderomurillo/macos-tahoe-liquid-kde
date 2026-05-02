import json
import shutil
from pathlib import Path

from steps._helpers import (
    HOME, fail, info, legacy_steps_dir, offline, ok, reinstall, src_dir, steps_dir,
)
from utils import fetch, safe_copy

CACHE = steps_dir("wallpapers")
LEGACY_CACHE = legacy_steps_dir("wallpapers")
DEST_DIR = HOME / ".local/share/wallpapers"
MIRROR_FILE = src_dir("mirrors/wallpapers.json")
OFFLINE_DIR = offline("wallpapers")


def deps():
    return ["curl"]


def _cache_root() -> Path:
    for cache in (CACHE, LEGACY_CACHE):
        if any((cache / "MacTahoe/contents/images").glob("*")):
            return cache
    return CACHE


def _meta(dir_: Path, id_: str, name: str, desc: str, auto: bool = False) -> None:
    (dir_ / "contents/images").mkdir(parents=True, exist_ok=True)
    if auto:
        (dir_ / "contents/images_dark").mkdir(parents=True, exist_ok=True)
    payload = {
        "KPlugin": {
            "Id": id_,
            "Name": name,
            "Description": desc,
            "Authors": [{"Name": "MacTahoe Liquid KDE", "Email": ""}],
            "Category": "MacTahoe Liquid KDE",
            "License": "Apple Inc. wallpapers extracted from macOS",
            "Website": "https://github.com/lester-sudo/macos-tahoe-liquid-kde",
            "Version": "1.0",
        }
    }
    (dir_ / "metadata.json").write_text(
        json.dumps(payload, indent=4) + "\n", encoding="utf-8"
    )


def _wp_get(url: str, dest: Path, label: str, referer: str | None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not fetch(url, dest, referer):
        if dest.exists():
            try: dest.unlink()
            except OSError: pass
        fail(f"{label} (download failed)")


_BEACH = (
    ("MacTahoe-Beach-Dawn", "26-Tahoe-Beach-Dawn.png", "Tahoe Beach — Dawn"),
    ("MacTahoe-Beach-Day", "26-Tahoe-Beach-Day.png", "Tahoe Beach — Day"),
    ("MacTahoe-Beach-Dusk", "26-Tahoe-Beach-Dusk.png", "Tahoe Beach — Dusk"),
    ("MacTahoe-Beach-Night", "26-Tahoe-Beach-Night.png", "Tahoe Beach — Night"),
)

_PAIRS = (
    ("MacHeritage-Sequoia", "15-Sequoia-Light-6K.jpg", "15-Sequoia-Dark-6K.jpg",   "macOS Sequoia"),
    ("MacHeritage-Sonoma",  "14-Sonoma-Light.jpg",     "14-Sonoma-Dark.jpg",       "macOS Sonoma"),
    ("MacHeritage-Ventura", "13-Ventura-Light.jpg",    "13-Ventura-Dark.jpg",      "macOS Ventura"),
    ("MacHeritage-Monterey", "12-Light.jpg",           "12-Dark.jpg",              "macOS Monterey"),
    # Big Sur lives on the older mirror base.
)
_BIGSUR = ("MacHeritage-BigSur",
           "11-0-Color-Day.jpg", "11-0-Big-Sur-Color-Night.jpg",
           "macOS Big Sur")

_SINGLES = (
    ("MacHeritage-Sequoia-Sunrise", "15-Sequoia-Sunrise.png", "macOS Sequoia — Sunrise"),
    ("MacHeritage-Sonoma-Horizon",  "14-Sonoma-Horizon.png",  "macOS Sonoma — Horizon"),
)


def download() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)

    sources = json.loads(MIRROR_FILE.read_text())["sources"]
    src0 = sources[0]["mirrors"]
    base = src0[0]["url"]
    base_old = src0[-1]["url"]
    referer = src0[0].get("referer", "") or None

    # MacTahoe (auto light/dark)
    tahoe = CACHE / "MacTahoe"
    _meta(tahoe, "MacTahoe", "macOS Tahoe", "Auto light/dark wallpaper", auto=True)
    _wp_get(f"{base}/26-Tahoe-Light-6K.png",
            tahoe / "contents/images/3840x2160.png",
            "MacTahoe — Light", referer)
    _wp_get(f"{base}/26-Tahoe-Dark-6K.png",
            tahoe / "contents/images_dark/3840x2160.png",
            "MacTahoe — Dark", referer)

    for id_, fn, name in _BEACH:
        d = CACHE / id_
        _meta(d, id_, name, "Lake Tahoe landscape")
        ext = Path(fn).suffix
        _wp_get(f"{base}/{fn}", d / f"contents/images/3840x2160{ext}", id_, referer)

    # Bundled offline wallpapers (landscapes, iridescence, future packs).
    # Any ``Mac*/`` directory under src/offline/wallpapers/ ships as-is —
    # adding a new bundled wallpaper is just dropping a directory.
    for src in sorted(OFFLINE_DIR.glob("Mac*/")):
        if not src.is_dir():
            continue
        if not safe_copy(src, CACHE / src.name):
            fail(f"{src.name} (copy from offline failed)")

    for id_, ul, ud, name in _PAIRS:
        d = CACHE / id_
        _meta(d, id_, name, f"{name} — auto light/dark", auto=True)
        _wp_get(f"{base}/{ul}",
                d / f"contents/images/3840x2160{Path(ul).suffix}",
                f"{id_} — Light", referer)
        _wp_get(f"{base}/{ud}",
                d / f"contents/images_dark/3840x2160{Path(ud).suffix}",
                f"{id_} — Dark", referer)

    id_, ul, ud, name = _BIGSUR
    d = CACHE / id_
    _meta(d, id_, name, f"{name} — auto light/dark", auto=True)
    _wp_get(f"{base_old}/{ul}",
            d / f"contents/images/3840x2160{Path(ul).suffix}",
            f"{id_} — Light", referer)
    _wp_get(f"{base_old}/{ud}",
            d / f"contents/images_dark/3840x2160{Path(ud).suffix}",
            f"{id_} — Dark", referer)

    for id_, fn, name in _SINGLES:
        d = CACHE / id_
        _meta(d, id_, name, name)
        _wp_get(f"{base}/{fn}",
                d / f"contents/images/3840x2160{Path(fn).suffix}",
                id_, referer)


def install() -> None:
    pre = {p.name for p in DEST_DIR.glob("*/") if p.is_dir()}
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    cache = _cache_root()

    n_inst = n_re = 0
    for wp in sorted(cache.glob("Mac*/")):
        if not wp.is_dir():
            continue
        contents = wp / "contents"
        img_count = sum(1 for p in contents.rglob("*") if p.is_file()) if contents.is_dir() else 0
        if img_count == 0:
            fail(f"{wp.name} (download incomplete — re-run to retry)")
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
