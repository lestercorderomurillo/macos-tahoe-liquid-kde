"""MacTahoe cursor themes: extracts the bundled
MacTahoeLiquidKde-Cursors.tar.zst into ~/.local/share/icons.
Fully offline — no download phase."""

import shutil
import subprocess

from steps._helpers import (
    DATA_HOME, fail, info, ok, offline,
)

OFFLINE_DIR = offline("cursors")
DEST_DIR = DATA_HOME / "icons"


def deps():
    return ["zstd"]


def install() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    tarball = OFFLINE_DIR / "MacTahoeLiquidKde-Cursors.tar.zst"
    if not tarball.is_file():
        fail(f"offline tarball missing: {tarball}")
        return

    # Wipe our own stale cursor dirs (crashed-run leftovers); dirs whose
    # name contains "Icons" belong to the icons step — never touch them.
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
