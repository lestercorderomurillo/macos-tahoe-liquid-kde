"""Keep shared interface names symbolic instead of selecting application tiles.

SPDX-License-Identifier: GPL-3.0-or-later
Copyright (C) 2026 Lester Cordero Murillo
"""
from pathlib import Path
import os

from status_icon_palette import apply_status_palette

# These names are also requested at large sizes by Plasma control surfaces.
# Keep canonical application IDs and their original artwork untouched.
INTERFACE_ICONS = {
    "battery": "status/22/battery-full.svg",
    "camera": "status/22/camera-on.svg",
    "camera-web": "devices/22/camera-web.svg",
    "preferences-desktop-display-nightcolor": "status/symbolic/night-light-symbolic.svg",
    "kdeconnect": "status/22/kdeconnect-tray.svg",
    "kdeconnect-tray": "status/22/kdeconnect-tray.svg",
    "bluetooth": "status/22/bluetooth-active.svg",
    "bluetooth-active": "status/22/bluetooth-active.svg",
    "bluetooth-disabled": "status/22/bluetooth-disabled.svg",
    "network-bluetooth": "status/22/network-bluetooth.svg",
    "audio-volume-high": "status/22/audio-volume-high.svg",
    "network-wireless-signal-excellent": "status/22/network-wireless-signal-excellent.svg",
    "brightness-high": "status/22/brightness-high.svg",
    "redshift-status-on": "status/22/redshift-status-on.svg",
}


def apply_interface_icons(directory: Path) -> None:
    """Adapt extracted themes only; retain canonical sources and notices."""
    directory = directory.resolve()
    apply_status_palette(directory)
    for theme_name in ("MacTahoeLiquidKde-Icons", "MacTahoeLiquidKde-Icons-dark"):
        theme = directory / theme_name
        if not theme.is_dir():
            continue
        # Read all originals before replacing aliases to those same originals.
        artwork = {}
        for name, relative in INTERFACE_ICONS.items():
            source = theme / relative
            if source.is_file():
                if not source.resolve().is_relative_to(directory):
                    raise ValueError(f"Interface icon escapes staging: {source}")
                artwork[name] = source.read_text()
        for name, svg in artwork.items():
            canonical = theme / "status/symbolic" / ("interface-" + name + ".svg")
            canonical.parent.mkdir(parents=True, exist_ok=True)
            if not canonical.resolve().is_relative_to(directory):
                raise ValueError(f"Interface icon escapes staging: {canonical}")
            canonical.write_text(svg)
            # Replace the requested alias, never its target (which can be an app).
            candidates = list(theme.glob("*/*/" + name + ".svg"))
            candidates.append(theme / "status/symbolic" / (name + ".svg"))
            for path in candidates:
                if not path.parent.resolve().is_relative_to(directory):
                    raise ValueError(f"Interface icon escapes staging: {path}")
                if path.is_symlink() or path.exists():
                    path.unlink()
                path.symlink_to(os.path.relpath(canonical, path.parent))


if __name__ == "__main__":
    import sys
    apply_interface_icons(Path(sys.argv[1]))
