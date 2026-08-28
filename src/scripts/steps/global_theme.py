import json

from steps._helpers import (
    DATA_HOME, install_tree, offline, ok, remove_tree,
)

DEST_DIR = DATA_HOME / "plasma/look-and-feel"


def install() -> None:
    src = offline("look-and-feel")
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    for theme in sorted(src.glob("MacTahoeLiquidKde-*")):
        if not theme.is_dir():
            continue
        try:
            meta = json.loads((theme / "metadata.json").read_text())
            theme_id = meta.get("KPlugin", {}).get("Id") or meta.get("Id")
        except (OSError, json.JSONDecodeError):
            theme_id = None
        if not theme_id:
            continue
        install_tree(theme, DEST_DIR / theme_id, theme.name)


def uninstall() -> None:
    for theme in DEST_DIR.glob("org.kde.mac-tahoe-liquid-kde.*"):
        remove_tree(theme)
