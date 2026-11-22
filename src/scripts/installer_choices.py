"""Validated, per-run choices shared by the graphical wizard and its backend."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from pathlib import Path

from launcher_defaults import edition_name

COLORS = {
    "blue": "#007aff", "purple": "#af52de", "pink": "#ff2d55",
    "red": "#ff3b30", "orange": "#ff9500", "yellow": "#ffcc00",
    "green": "#28cd41", "gray": "#8e8e93",
}
GLASS_PRESETS = json.loads((Path(__file__).resolve().parents[1] /
    "offline/kwin-effects/acrylic-glass/src/presets.json").read_text())
ENUMS = {
    "appearance": ("auto", "light", "dark"),
    "dock_visibility": ("autohide", "none", "dodgewindows"),
    "dock_appearance": ("auto", "keep", "macos", "native"),
    "dock_apps_source": ("native", "flatpak"),
    "icons": ("regular", "dark", "clear", "glass", "keep"),
    # Light/dark variant of the icons, independent of the appearance (macOS).
    "icon_appearance": ("auto", "light", "dark"),
    "color": tuple(COLORS),
    "wallpaper": ("tahoe", "golden", "landscape", "sonoma", "prism", "macos", "keep", "custom"),
    "launcher": ("tahoe", "golden", "keep"),
    "files": ("nautilus", "dolphin", "keep"),
    "shadows": ("none", "soft", "medium", "hard"),
    "window_controls": ("flat", "glassy"),
    "button_position": ("left", "right", "keep"),
    "glass_style": tuple(preset["choice"] for preset in GLASS_PRESETS),
}
WALLPAPERS = {
    "prism": ("MacPrism", "MacPrism"),
    "macos": ("MacHeritage-Monterey", "MacHeritage-Monterey"),
    "tahoe": ("MacTahoe", "MacTahoe"),
    "golden": ("MacGoldenGate", "MacGoldenGate"),
    "landscape": ("MacTahoe-Landscape-Morning", "MacTahoe-Landscape-Night"),
    "sonoma": ("MacHeritage-Sonoma", "MacHeritage-Sonoma-Horizon"),
}


def launcher_preference() -> Path:
    state = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    return state / "mac-tahoe-liquid-kde/use-user-launcher"


def use_user_launcher() -> bool:
    choices = selected()
    return choices["launcher"] == "keep" if choices else launcher_preference().exists()


def dock_visibility_preference() -> Path:
    return launcher_preference().with_name("dock-visibility")


def dock_visibility() -> str:
    try:
        value = dock_visibility_preference().read_text().strip()
    except OSError:
        config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        try:
            applets = (config / "plasma-org.kde.plasma.desktop-appletsrc").read_text()
            panels = (config / "plasmashellrc").read_text()
        except OSError:
            return "autohide"
        for section, body in re.findall(r"^\[Containments\]\[(\d+)\]\[Applets\]\[\d+\]\n([^\[]*)", applets, re.M):
            if "plugin=org.kde.mac.tahoe.liquid.icontasks" in body.splitlines():
                group = re.search(r"^\[PlasmaViews\]\[Panel " + section + r"\]\n([^\[]*)", panels, re.M)
                if group:
                    for line in group[1].splitlines():
                        if line.startswith("panelVisibility="):
                            return {"1": "autohide", "2": "dodgewindows"}.get(line[16:], "none")
                return "none"  # Plasma omits its normal visibility setting on some existing panels.
        return "autohide"
    return value if value in ENUMS["dock_visibility"] else "autohide"


def defaults() -> dict:
    edition = "golden" if edition_name() == "MacGoldenGate" else "tahoe"
    return dict(
        appearance="auto", icons="regular", icon_appearance="auto", color="blue", wallpaper=edition,
        wallpaper_explicit=True, wallpaper_path="", launcher="keep" if launcher_preference().exists() else edition, panel=True, dock=True, reset_layout=True,
        acrylic_glass=True, rounded_corners=True, shadows="medium", fonts=True, firefox=True,
        window_controls="glassy" if edition == "golden" else "flat", button_position="left",
        files="nautilus", nautilus_bookmarks=True, plymouth=True, glass_style="official" if edition == "golden" else "classic",
        oled_care=False, oled_interval=5, oled_max_shift=8,
        dock_visibility=dock_visibility(), dock_appearance="auto", dock_apps=[], dock_apps_source="native", dock_add_flathub=False,
    )


def validate(value: object) -> dict:
    if isinstance(value, dict) and "clipboard" in value:
        value = {key: item for key, item in value.items() if key != "clipboard"}
    if not isinstance(value, dict) or set(value) - defaults().keys():
        raise ValueError("Invalid installer choices")
    result = defaults() | value
    for key, allowed in ENUMS.items():
        if result[key] not in allowed:
            raise ValueError(f"Invalid choice: {key}")
    for key, default in defaults().items():
        if isinstance(default, bool) and type(result[key]) is not bool:
            raise ValueError(f"Expected a boolean: {key}")
    for key, maximum in (("oled_interval", 59), ("oled_max_shift", 16)):
        if type(result[key]) is not int or not 1 <= result[key] <= maximum:
            raise ValueError(f"Invalid range: {key}")
    apps = result["dock_apps"]
    if (not isinstance(apps, list) or len(apps) > 6
            or any(not isinstance(app, str) or app not in
                   ("mail", "calendar", "notes", "photos", "music", "video") for app in apps)
            or len(set(apps)) != len(apps)):
        raise ValueError("Invalid Dock applications")
    path = result["wallpaper_path"]
    if not isinstance(path, str) or "\0" in path or len(path) > 4096:
        raise ValueError("Invalid wallpaper path")
    if result["wallpaper"] == "custom" and not os.path.isabs(path):
        raise ValueError("Choose a wallpaper file")
    return result


def selected() -> dict:
    raw = os.environ.get("MTTKDE_WIZARD_OPTIONS")
    return validate(json.loads(raw)) if raw else {}


def keep_panel_layout() -> bool:
    return selected().get("reset_layout") is False


def features(choices: dict, baseline: dict, *, existing_install: bool = False) -> dict:
    """Start from source defaults, never another edition's saved selections."""
    choices = validate(choices)
    result = dict(baseline)
    for key in ("acrylic_glass", "rounded_corners", "fonts", "firefox",
                "plymouth", "oled_care", "oled_interval", "oled_max_shift"):
        result[key] = choices[key]
    result.update(
        clipboard=choices["launcher"] != "keep",
        theme_mode=choices["appearance"], icons=choices["icons"] != "keep",
        wallpapers=choices["wallpaper"] != "keep",
        layout=(choices["panel"] or choices["dock"]) and
               choices["reset_layout"],
        nautilus=choices["files"] == "nautilus",
        nautilus_bookmarks=choices["files"] == "nautilus" and choices["nautilus_bookmarks"],
        apply_theme=True, sddm=False,
        apps=choices["dock"] and bool(choices["dock_apps"]),
        _reset_wallpapers=choices["wallpaper"] != "keep" and
                          (not existing_install or choices["wallpaper_explicit"]),
    )
    return result
