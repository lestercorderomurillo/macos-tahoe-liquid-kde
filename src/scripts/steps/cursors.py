"""MacTahoe cursor themes — fully bundled offline since v0.18.0.

Earlier releases downloaded the cursor themes from
github.com/vinceliuice/MacTahoe-icon-theme alongside the icon
themes (same upstream repo, different subdir). Same shape of bug:
network on every install, half-failed downloads silently shipped
fewer cursor variants than intended.

v0.18 ships the pre-renamed cursor themes as
``src/offline/cursors/MacTahoeLiquidKde-Cursors.tar.zst``
(~927 KB compressed from 16 MB raw). install() extracts the
tarball directly into ~/.local/share/icons.
"""

import shutil
import subprocess

from steps._helpers import (
    HOME, fail, info, ok, offline,
)

OFFLINE_DIR = offline("cursors")
DEST_DIR = HOME / ".local/share/icons"


def deps():
    return ["zstd"]


def install() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    tarball = OFFLINE_DIR / "MacTahoeLiquidKde-Cursors.tar.zst"
    if not tarball.is_file():
        fail(f"offline tarball missing: {tarball}")
        return

    # Wipe pre-existing installs of OUR cursor themes so a half-
    # installed state from a crashed previous run doesn't leak.
    # We do NOT touch theme dirs whose name contains "Icons" — those
    # belong to the icons step.
    for old in DEST_DIR.glob("MacTahoeLiquidKde*"):
        if old.is_dir() and "Icons" not in old.name:
            shutil.rmtree(old, ignore_errors=True)

    res = subprocess.run(
        ["tar", "--zstd", "-xf", str(tarball), "-C", str(DEST_DIR)],
        check=False, capture_output=True, text=True,
    )
    if res.returncode != 0:
        fail(f"tar --zstd failed ({res.returncode}): {res.stderr.strip()}")
        return

    n = 0
    for theme in sorted(DEST_DIR.glob("MacTahoeLiquidKde*")):
        if theme.is_dir() and "Icons" not in theme.name and \
                (theme / "cursors").is_dir():
            ok(f"{theme.name} (installed)")
            n += 1
    info(f"{n} cursor themes installed/reinstalled")


def uninstall() -> None:
    n = 0
    for theme in DEST_DIR.glob("MacTahoeLiquidKde*"):
        if not theme.is_dir() or "Icons" in theme.name:
            continue
        try:
            shutil.rmtree(theme)
            ok(theme.name)
            n += 1
        except OSError:
            fail(theme.name)
    info(f"{n} cursor themes removed")
