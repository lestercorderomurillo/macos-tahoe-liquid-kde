"""SF Pro / SF Mono fonts: copies src/offline/fonts/ into
~/.local/share/fonts and refreshes the fontconfig cache.
Fully offline — no download phase."""

from localization import tr

import filecmp
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
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


def _copy_font(source: Path, target: Path) -> bool:
    """Keep mapped fonts valid while desktop applications are using them."""
    if target.is_file() and filecmp.cmp(source, target, shallow=False):
        return False
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".mttkde-font-",
                                     suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def install() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    inst: dict[str, int] = defaultdict(int)
    re_: dict[str, int] = defaultdict(int)
    any_copied = False

    for f in (*OFFLINE_DIR.glob("*.otf"), *OFFLINE_DIR.glob("*.ttf")):
        target = DEST_DIR / f.name
        existed = target.is_file()
        try:
            any_copied = _copy_font(f, target) or any_copied
        except OSError:
            fail(tr('{value1} (copy failed)', value1=f.name))
            continue
        grp = _group(f.name)
        if existed:
            reinstall(f.name); re_[grp] += 1
        else:
            ok(tr('{value1} (installed)', value1=f.name)); inst[grp] += 1

    for grp in ("SF Pro", "SF Mono", "Other"):
        if inst[grp] or re_[grp]:
            info(tr('{grp} — {value2} installed, {value3} reinstalled', grp=tr(grp), value2=inst[grp], value3=re_[grp]))
    if any_copied:
        _refresh_font_cache()


def _refresh_font_cache() -> None:
    """Rebuild the fontconfig cache so new fonts show without a logout.
    fc-cache is optional on minimal installs — fonts then appear at next login."""
    if not have("fc-cache"):
        warn(tr('fc-cache not found (fontconfig package missing) — fonts copied but cache not refreshed; they will appear after the next login'))
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
    info(tr('{n} font files removed', n=n))
