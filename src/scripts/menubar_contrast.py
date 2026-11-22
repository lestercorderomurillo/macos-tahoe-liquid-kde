#!/usr/bin/env python3
"""Keep the menu bar readable on any wallpaper, as on macOS (#146).

On macOS the menu bar's text follows the wallpaper behind it, separately from
the system appearance. Plasma colours the menu bar, its tray icons and the
"Follow system" widgets from the colour scheme only, so in light mode on a dark
wallpaper they turn dark on dark.

Plasma applies a Plasma style's own ``colors`` file to plasmashell only. The
installer ships, next to each MacTahoe Plasma style, a ``-WallpaperBar``
variant: the other appearance's style and colours, under a name that keeps the
current appearance's word (``Light`` or ``Dark``) so the light/dark switcher
never reads it as an appearance change. This helper measures the top of every
screen's wallpaper and applies the plain style or its ``-WallpaperBar``
variant, leaving the colour scheme of the applications alone.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

LIGHT, DARK = "MacTahoeLiquidKde-Light", "MacTahoeLiquidKde-Dark"
SUFFIX = "-WallpaperBar"
# Share of the wallpaper's height behind the menu bar that is measured.
TOP_BAND = 0.06
# Hysteresis: stay put between the two thresholds so a mid-grey wallpaper
# does not flip the bar at every check.
DARK_BELOW, LIGHT_ABOVE = 0.42, 0.58


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def read_ini(path: Path) -> dict[str, dict[str, str]]:
    groups: dict[str, dict[str, str]] = {}
    current = None
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return groups
    for line in lines:
        if line.startswith("["):
            current = groups.setdefault(line.strip(), {})
        elif current is not None and "=" in line:
            key, value = line.split("=", 1)
            current[key.strip()] = value.strip()
    return groups


def wallpapers(appletsrc: Path) -> list[Path]:
    """Current image of each desktop: static wallpapers and slideshows."""
    groups = read_ini(appletsrc)
    found = []
    for name, values in groups.items():
        if not re.fullmatch(r"\[Containments\]\[\d+\]\[Wallpaper\]\[org\.kde\.(image|slideshow)\]\[General\]", name):
            continue
        path = resolve(values.get("Image", ""))
        if path is not None and path not in found:
            found.append(path)
    return found


# desktopForScreen() returns the desktop each screen shows; desktops() can
# also list desktops of an activity that are not on screen.
LIVE_SCRIPT = ("var images = []; for (var i = 0; i < screenCount; i++) {"
               " var d = desktopForScreen(i); if (!d) continue;"
               " d.currentConfigGroup = ['Wallpaper', d.wallpaperPlugin, 'General'];"
               " images.push(d.readConfig('Image')); } print(images.join('\\n'))")


def live_wallpapers() -> list[Path] | None:
    """Ask plasmashell for the wallpapers of the desktops it shows now.

    The configuration file also keeps desktops of screens and activities that
    are gone, and Plasma writes it with a delay, so prefer the live answer.
    """
    try:
        result = subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.kde.plasmashell", "--object-path", "/PlasmaShell",
             # gdbus parses each argument as a GVariant literal: quote it.
             "--method", "org.kde.PlasmaShell.evaluateScript",
             '"' + LIVE_SCRIPT.replace("\\", "\\\\").replace('"', '\\"') + '"'],
            capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    # gdbus prints ('line1\nline2',)
    text = result.stdout.strip()
    if text.startswith("('") and text.endswith("',)"):
        text = text[2:-3].encode().decode("unicode_escape")
    found = []
    for image in text.splitlines():
        path = resolve(image.strip())
        if path is not None and path not in found:
            found.append(path)
    return found


def resolve(image: str) -> Path | None:
    if not image:
        return None
    path = Path(unquote(urlparse(image).path)) if image.startswith("file:") else Path(image)
    if path.is_dir():
        # A wallpaper package: use its largest image.
        images = sorted((path / "contents/images").glob("*"), key=lambda p: p.stat().st_size)
        if not images:
            return None
        path = images[-1]
    return path if path.is_file() else None


def top_luminance(path: Path) -> float | None:
    """Mean relative luminance (0 dark … 1 light) of the wallpaper's top band."""
    try:
        from PyQt6.QtGui import QImage
        image = QImage(str(path))
        if image.isNull():
            raise ValueError
        image = image.scaled(64, max(1, round(64 * image.height() / image.width())))
        rows = max(1, round(image.height() * TOP_BAND))
        total = 0.0
        for y in range(rows):
            for x in range(image.width()):
                c = image.pixelColor(x, y)
                total += 0.2126 * c.redF() + 0.7152 * c.greenF() + 0.0722 * c.blueF()
        return total / (rows * image.width())
    except Exception:
        pass
    try:
        from PIL import Image
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((64, 64 * image.height // max(1, image.width)))
            rows = max(1, round(image.height * TOP_BAND))
            band = image.crop((0, 0, image.width, rows))
            pixels = list(band.getdata())
            return sum(0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in pixels) / (255 * len(pixels))
    except Exception:
        return None


def base_style(current: str) -> str | None:
    """The plain MacTahoe style behind the active Plasma style, or None."""
    name = current[:-len(SUFFIX)] if current.endswith(SUFFIX) else current
    return name if name in (LIGHT, DARK) else None


def wanted_style(current: str, luminances: list[float]) -> str:
    """Style to apply for the measured wallpapers, given the active style."""
    base = base_style(current)
    if base is None or not luminances:
        return current
    mean = sum(luminances) / len(luminances)
    bar_is_dark = current.endswith(SUFFIX) != (base == DARK)  # the bar's current colours
    if mean < DARK_BELOW:
        want_dark_bar = True
    elif mean > LIGHT_ABOVE:
        want_dark_bar = False
    else:
        want_dark_bar = bar_is_dark
    plain_is_dark = base == DARK
    return base if want_dark_bar == plain_is_dark else base + SUFFIX


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    current = read_ini(config_home() / "plasmarc").get("[Theme]", {}).get("name", "")
    if base_style(current) is None:
        return 0  # not a MacTahoe style: leave the user's choice alone
    paths = live_wallpapers()
    if not paths:
        paths = wallpapers(config_home() / "plasma-org.kde.plasma.desktop-appletsrc")
    values = [v for v in (top_luminance(p) for p in paths) if v is not None]
    style = wanted_style(current, values)
    if dry:
        print(style)
        return 0
    if style != current:
        subprocess.run(["plasma-apply-desktoptheme", style], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
