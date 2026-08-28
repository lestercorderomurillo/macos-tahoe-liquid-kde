"""SF Pro / SF Mono fonts: copies src/offline/fonts/ into
~/.local/share/fonts and refreshes the fontconfig cache.
Fully offline — no download phase."""

import shutil
import subprocess
from collections import defaultdict

from steps._helpers import (
    DATA_HOME, fail, have, info, ok, offline, reinstall, warn,
)
from utils import run_user

OFFLINE_DIR = offline("fonts")
DEST_DIR = DATA_HOME / "fonts"


def deps():
    return ["fc-cache:fontconfig"]


def _group(name: str) -> str:
    if name.startswith(("SF-Mono", "SFMono")):
        return "SF Mono"
    if name.startswith(("SF-Pro", "SFPro")):
        return "SF Pro"
    return "Other"


def install() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    inst: dict[str, int] = defaultdict(int)
    re_: dict[str, int] = defaultdict(int)
    any_copied = False

    for f in (*OFFLINE_DIR.glob("*.otf"), *OFFLINE_DIR.glob("*.ttf")):
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
            reinstall(f.name); re_[grp] += 1
        else:
            ok(f"{f.name} (installed)"); inst[grp] += 1

    for grp in ("SF Pro", "SF Mono", "Other"):
        if inst[grp] or re_[grp]:
            info(f"{grp} — {inst[grp]} installed, {re_[grp]} reinstalled")
    if any_copied:
        _refresh_font_cache()


def _refresh_font_cache() -> None:
    """Rebuild the fontconfig cache so new fonts show without a logout.
    fc-cache is optional on minimal installs — fonts then appear at next login."""
    if not have("fc-cache"):
        warn("fc-cache not found (fontconfig package missing) — fonts "
             "copied but cache not refreshed; they will appear after "
             "the next login")
        return
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
        _refresh_font_cache()
    info(f"{n} font files removed")
