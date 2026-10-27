"""Install and select the bundled MacTahoe sound theme.

The payload follows the freedesktop sound-theme specification and is kept
fully offline under ``src/offline/sounds``.  Plasma 6 stores the selected
theme in ``kdeglobals`` rather than in an app-specific notification file.
"""

from localization import tr

from pathlib import Path

from steps._helpers import (
    DATA_HOME, feat_enabled, info, install_tree, offline, ok, remove_tree, warn,
)
from utils import kw_read, kw_write


THEME_ID = "MacTahoeLiquidKde"
FALLBACK_THEME_ID = "ocean"
OFFLINE_DIR = offline("sounds", THEME_ID)
DEST_DIR = DATA_HOME / "sounds" / THEME_ID


def _sound_count(root: Path) -> int:
    return sum(
        path.is_file() and path.suffix.lower() in {".oga", ".ogg", ".wav"}
        for path in root.rglob("*")
    )


def _select_theme() -> bool:
    theme_ok = kw_write(
        "--file", "kdeglobals", "--group", "Sounds",
        "--key", "Theme", THEME_ID,
    )
    enabled_ok = kw_write(
        "--file", "kdeglobals", "--group", "Sounds",
        "--key", "Enable", "true",
    )
    if theme_ok and enabled_ok:
        ok(tr('Sound theme selected'))
        return True
    warn(tr('Sound theme copied but not selected (kwriteconfig6 failed)'))
    return False


def install() -> None:
    if not install_tree(OFFLINE_DIR, DEST_DIR, tr('MacTahoe sound theme')):
        info(tr('0 sound events installed/reinstalled'))
        return

    # ``--no-apply-theme`` stages assets without changing the desktop.
    if feat_enabled("APPLY_THEME"):
        _select_theme()

    info(tr('{value1} sound events installed/reinstalled', value1=_sound_count(DEST_DIR)))


def uninstall() -> None:
    # Do not undo a sound theme the user selected after installing ours.
    if kw_read("kdeglobals", "Sounds", "Theme") == THEME_ID:
        if kw_write(
            "--file", "kdeglobals", "--group", "Sounds",
            "--key", "Theme", FALLBACK_THEME_ID,
        ):
            ok(tr('Ocean sound theme restored'))
        else:
            warn(tr('Could not restore the Ocean sound theme'))

    removed = remove_tree(DEST_DIR, tr('MacTahoe sound theme'))
    info(tr('{value1} sound theme removed', value1=1 if removed else 0))
