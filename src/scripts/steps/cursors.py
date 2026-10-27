"""MacTahoe cursor themes: extracts the bundled
MacTahoeLiquidKde-Cursors.tar.zst into ~/.local/share/icons.
Fully offline — no download phase."""

from localization import tr

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
        fail(tr('offline tarball missing: {tarball}', tarball=tarball))
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
        fail(tr('tar --zstd failed ({value1}): {value2}', value1=res.returncode, value2=res.stderr.strip()))
        return

    n = 0
    for theme in sorted(DEST_DIR.glob("MacTahoeLiquidKde*")):
        if theme.is_dir() and "Icons" not in theme.name and \
                (theme / "cursors").is_dir():
            ok(tr('{value1} (installed)', value1=theme.name))
            n += 1
    info(tr('{n} cursor themes installed/reinstalled', n=n))


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
    info(tr('{n} cursor themes removed', n=n))
