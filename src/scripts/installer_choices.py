"""Validated, per-run choices shared by the graphical wizard and its backend."""

from __future__ import annotations

import json
import os

from launcher_defaults import edition_name

COLORS = {
    "blue": "#007aff", "purple": "#af52de", "pink": "#ff2d55",
    "red": "#ff3b30", "orange": "#ff9500", "yellow": "#ffcc00",
    "green": "#28cd41", "gray": "#8e8e93",
}
ENUMS = {
    "appearance": ("auto", "light", "dark"),
    "icons": ("regular", "glass", "keep"),
    "color": tuple(COLORS),
    "wallpaper": ("tahoe", "golden", "landscape", "sonoma", "keep", "custom"),
    "launcher": ("tahoe", "golden"),
    "files": ("nautilus", "dolphin", "keep"),
    "shadows": ("none", "soft", "medium", "hard"),
    "window_controls": ("flat", "glassy"),
}
WALLPAPERS = {
    "tahoe": ("MacTahoe", "MacTahoe"),
    "golden": ("MacGoldenGate", "MacGoldenGate"),
    "landscape": ("MacTahoe-Landscape-Morning", "MacTahoe-Landscape-Night"),
    "sonoma": ("MacHeritage-Sonoma", "MacHeritage-Sonoma-Horizon"),
}


def defaults() -> dict:
    edition = "golden" if edition_name() == "MacGoldenGate" else "tahoe"
    return dict(
        appearance="auto", icons="regular", color="blue", wallpaper=edition,
        wallpaper_path="", launcher=edition, panel=True, dock=True, reset_layout=True,
        acrylic_glass=True, rounded_corners=True, shadows="medium", fonts=True, firefox=True,
        window_controls="glassy" if edition == "golden" else "flat",
        files="nautilus", nautilus_bookmarks=True, plymouth=True,
        oled_care=False, oled_interval=5, oled_max_shift=8,
    )


def validate(value: object) -> dict:
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
    path = result["wallpaper_path"]
    if not isinstance(path, str) or "\0" in path or len(path) > 4096:
        raise ValueError("Invalid wallpaper path")
    if result["wallpaper"] == "custom" and not os.path.isabs(path):
        raise ValueError("Choose a wallpaper file")
    return result


def selected() -> dict:
    raw = os.environ.get("MTTKDE_WIZARD_OPTIONS")
    return validate(json.loads(raw)) if raw else {}


def features(choices: dict, baseline: dict, *, existing_install: bool = False) -> dict:
    """Start from source defaults, never another edition's saved selections."""
    choices = validate(choices)
    result = dict(baseline)
    for key in ("acrylic_glass", "rounded_corners", "fonts", "firefox",
                "plymouth", "oled_care", "oled_interval", "oled_max_shift"):
        result[key] = choices[key]
    result.update(
        theme_mode=choices["appearance"], icons=choices["icons"] != "keep",
        wallpapers=choices["wallpaper"] != "keep",
        layout=(choices["panel"] or choices["dock"]) and
               (not existing_install or choices["reset_layout"]),
        nautilus=choices["files"] == "nautilus",
        nautilus_bookmarks=choices["files"] == "nautilus" and choices["nautilus_bookmarks"],
        apply_theme=True, sddm=False,
        _reset_wallpapers=choices["wallpaper"] != "keep",
    )
    return result
