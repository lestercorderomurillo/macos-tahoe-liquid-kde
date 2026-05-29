"""SF Pro fonts — fully bundled offline since v0.18.0.

Earlier releases downloaded San Francisco Pro from
github.com/sahibjotsaggu/San-Francisco-Pro-Fonts on first install
and cached the result under ``~/.cache/mac-tahoe-liquid-kde/steps/
fonts/``. Two problems:

* Every fresh install hit the network for ~73 MB of OTFs before any
  font appeared, slowing down installs and breaking on air-gapped
  hosts.
* If GitHub returned an HTML error page or the upstream renamed
  files, the install partially succeeded with a font subset and
  Plasma fell back to Noto Sans without telling the user.

v0.18 ships the full 47-file SF Pro family in-repo under
``src/offline/fonts/`` (~109 MB). No ``download()`` phase, no
mirror JSON, no network dependency.
"""

import shutil
import subprocess
from collections import defaultdict

from steps._helpers import (
    HOME, fail, have, info, ok, offline, reinstall, warn,
)
from utils import run_user

OFFLINE_DIR = offline("fonts")
DEST_DIR = HOME / ".local/share/fonts"


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
    """Rebuild fontconfig's cache so newly-installed .otf/.ttf files
    are visible to Qt / GTK apps without a logout. Guarded by
    ``have('fc-cache')`` because fontconfig is technically optional on
    minimal Plasma installs — fonts still copy to ~/.local/share/fonts,
    they just don't show up until the next login (Qt re-scans the
    font dir at session start)."""
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
