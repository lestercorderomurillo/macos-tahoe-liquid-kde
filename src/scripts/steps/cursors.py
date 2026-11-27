"""MacTahoe cursor themes: extracts the bundled
MacTahoeLiquidKde-Cursors.tar.zst into ~/.local/share/icons.
Fully offline — no download phase."""

from localization import tr

import shutil
import subprocess

from steps._helpers import (
    DATA_HOME, fail, info, install_tree, ok, offline, temp_dir,
)

OFFLINE_DIR = offline("cursors")
DEST_DIR = DATA_HOME / "icons"
THEMES = ("MacTahoeLiquidKde", "MacTahoeLiquidKde-Dark")


def deps():
    return ["zstd"]


def install() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    tarball = OFFLINE_DIR / "MacTahoeLiquidKde-Cursors.tar.zst"
    if not tarball.is_file():
        fail(tr('offline tarball missing: {tarball}', tarball=tarball))
        return

    with temp_dir("mttkde-cursors-") as staging:
        res = subprocess.run(["tar", "--zstd", "-xf", str(tarball), "-C", str(staging)],
                             check=False, capture_output=True, text=True)
        if res.returncode:
            fail(tr('tar --zstd failed ({value1}): {value2}', value1=res.returncode, value2=res.stderr.strip()))
            return
        for name in THEMES:
            theme = staging / name
            if not (theme / "index.theme").is_file() or not (theme / "cursors/left_ptr").is_file():
                fail(tr('{label} (source missing: {src})', label=name, src=theme))
                return
        for name in THEMES:
            if not install_tree(staging / name, DEST_DIR / name, name):
                return
    info(tr('{n} cursor themes installed/reinstalled', n=len(THEMES)))


def uninstall() -> None:
    n = 0
    for name in THEMES:
        theme = DEST_DIR / name
        if not theme.is_dir() or theme.is_symlink():
            continue
        try:
            shutil.rmtree(theme)
            ok(theme.name)
            n += 1
        except OSError:
            fail(theme.name)
    info(tr('{n} cursor themes removed', n=n))
