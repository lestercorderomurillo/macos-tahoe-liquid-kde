import shutil
import subprocess
from collections import defaultdict

from steps._helpers import (
    HOME, fail, info, legacy_steps_dir, ok, reinstall, src_dir, steps_dir, temp_dir,
)
from utils import run_mirrors, run_user

CACHE = steps_dir("fonts")
LEGACY_CACHE = legacy_steps_dir("fonts")
DEST_DIR = HOME / ".local/share/fonts"


def deps():
    return ["curl", "unzip", "fc-cache:fontconfig"]


def _cache_root():
    for cache in (CACHE, LEGACY_CACHE):
        if any((*cache.glob("*.otf"), *cache.glob("*.ttf"))):
            return cache
    return CACHE


def download() -> None:
    mirror = src_dir("mirrors/fonts.json")
    CACHE.mkdir(parents=True, exist_ok=True)
    for f in (*CACHE.glob("*.otf"), *CACHE.glob("*.ttf")):
        f.unlink()

    with temp_dir("tahoe-fonts") as tmp:
        def handle(xdir, _prefix, *_referer):
            installed = False
            font_files = sorted(
                p for p in xdir.rglob("*")
                if p.is_file() and p.suffix.lower() in (".otf", ".ttf")
            )
            for f in font_files:
                try:
                    shutil.copy2(f, CACHE / f.name)
                    installed = True
                except OSError:
                    fail(f"{f.name} (copy failed)")
            return installed

        if not run_mirrors(mirror, 0, tmp, handle):
            fail("no fonts installed — all mirrors failed")


def _group(name: str) -> str:
    if name.startswith(("SF-Mono", "SFMono")):
        return "SF Mono"
    if name.startswith(("SF-Pro", "SFPro")):
        return "SF Pro"
    return "Other"


def install() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    inst: dict[str, int] = defaultdict(int)
    re: dict[str, int] = defaultdict(int)
    any_copied = False
    cache = _cache_root()

    for f in (*cache.glob("*.otf"), *cache.glob("*.ttf")):
        target = DEST_DIR / f.name
        existed = target.is_file()
        try:
            shutil.copy2(f, target)
            any_copied = True
        except OSError:
            fail(f"{f.name} (copy failed)")
            continue
        grp = _group(f.name)
        if existed:
            reinstall(f.name); re[grp] += 1
        else:
            ok(f"{f.name} (installed)"); inst[grp] += 1

    for grp in ("SF Pro", "SF Mono", "Other"):
        if inst[grp] or re[grp]:
            info(f"{grp} — {inst[grp]} installed, {re[grp]} reinstalled")
    if any_copied:
        run_user(["fc-cache", "-f", str(DEST_DIR)],
                 check=False,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def uninstall() -> None:
    n = 0
    for pat in ("SF-Pro*", "SF-Mono*", "SFPro*", "SFMono*"):
        for f in DEST_DIR.glob(pat):
            try:
                f.unlink()
                n += 1
            except OSError:
                pass
    if n > 0:
        run_user(["fc-cache", "-f", str(DEST_DIR)],
                 check=False,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    info(f"{n} font files removed")
