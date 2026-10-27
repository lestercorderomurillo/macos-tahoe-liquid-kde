"""Assemble store assets without invoking installer or changing user config."""
import json
import shutil
import sys
from pathlib import Path

from window_controls import EDITIONS, assemble_aurorae, apply_gtk_controls, apply_global_theme
from launcher_defaults import LAUNCHER_ID, apply_launcher_default
from glass_surfaces import apply_kvantum_surface_defaults, apply_plasma_surface_defaults

source, out = map(Path, sys.argv[1:])
share = out / "share"

def copy(src, dst):
    shutil.copytree(src, dst, dirs_exist_ok=True)

for folder, destination in (("color-schemes", "color-schemes"),
                            ("plasma-theme", "plasma/desktoptheme"),
                            ("gtk", "themes")):
    copy(source / folder, share / destination)
for theme in sorted((source / "look-and-feel").glob("MacTahoeLiquidKde-*")):
    name = json.loads((theme / "metadata.json").read_text())["KPlugin"]["Id"]
    copy(theme, share / "plasma/look-and-feel" / name)
    apply_global_theme(share / "plasma/look-and-feel" / name)
for mode in ("Light", "Dark"):
    name = f"MacTahoeLiquidKde-{mode}"
    apply_plasma_surface_defaults(share / "plasma/desktoptheme" / name)
    apply_gtk_controls(share / "themes" / name)
    for edition in EDITIONS:
        dest = share / "aurorae/themes" / f"{edition}LiquidKde-{mode}"
        assemble_aurorae(source / "aurorae", dest, mode, edition)
for name in ("mac-tahoe-liquid-kde", "mac-tahoe-liquid-kdeDark"):
    dest = share / "Kvantum" / name
    dest.mkdir(parents=True)
    for ext in (".svg", ".kvconfig"):
        shutil.copy2(source / "kvantum/mac-tahoe-liquid-kde" / (name + ext), dest)
    apply_kvantum_surface_defaults(dest / (name + ".svg"))
for theme in (source / "plasmoids").iterdir():
    if (theme / "metadata.json").is_file() and not (theme / "CMakeLists.txt").exists():
        copy(theme, share / "plasma/plasmoids" / theme.name)
        if theme.name == LAUNCHER_ID:
            apply_launcher_default(share / "plasma/plasmoids" / theme.name)
# The icons-only wrapper resolves this runtime package via X-Plasma-RootPath.
task = source / "plasmoids/org.kde.mac.tahoe.liquid.taskmanager"
dest = share / "plasma/plasmoids" / task.name
copy(task / "contents", dest / "contents")
shutil.copy2(task / "metadata.json", dest)
