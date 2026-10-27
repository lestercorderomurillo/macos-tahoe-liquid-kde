"""Apply a selected accent to owned, staged theme resources."""

import colorsys
import gzip
import re
from pathlib import Path

from installer_choices import COLORS, selected


def recolor(text: str, accent: str) -> str:
    target = tuple(int(accent[i:i+2], 16) / 255 for i in (1, 3, 5))
    hue, saturation, _ = colorsys.rgb_to_hsv(*target)

    def convert(rgb):
        old_hue, old_saturation, value = colorsys.rgb_to_hsv(*(v / 255 for v in rgb))
        # The bundled selection/focus family is blue. Leave status colors,
        # neutral surfaces, foregrounds and alpha untouched.
        if not .52 <= old_hue <= .68 or old_saturation < .25:
            return rgb
        return tuple(round(v * 255) for v in colorsys.hsv_to_rgb(
            hue, saturation * min(1, old_saturation / .7), value))

    def hex_color(match):
        value = match[1]
        rgb = tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
        return "#" + "".join(f"{v:02x}" for v in convert(rgb))

    text = re.sub(r"#([0-9a-fA-F]{6})(?![0-9a-fA-F])", hex_color, text)

    def rgb_color(match):
        rgb = tuple(int(match[key]) for key in ("r", "g", "b"))
        if any(v > 255 for v in rgb):
            return match[0]
        updated = convert(rgb)
        if updated == rgb:
            return match[0]
        return match["prefix"] + ",".join(str(v) for v in updated)

    # Bare triples also occur in SVG paths and transform matrices. Only RGB
    # functions and KDE color-setting assignments contain colors here.
    return re.sub(
        r"(?P<prefix>\brgba?\([ \t]*|^[ \t]*(?:Color|Background\w*|Foreground\w*|Decoration\w*)[ \t]*=[ \t]*)"
        r"(?P<r>\d{1,3})[ \t]*,[ \t]*(?P<g>\d{1,3})[ \t]*,[ \t]*(?P<b>\d{1,3})"
        r"(?=[ \t]*(?:[,)]|$))",
        rgb_color, text, flags=re.MULTILINE)


def apply(path: Path) -> None:
    options = selected()
    if not options:
        return
    color = COLORS[options["color"]]
    files = path.rglob("*") if path.is_dir() else (path,)
    for file in files:
        if file.is_symlink() or not file.is_file():
            continue
        if file.suffix not in (".svg", ".svgz", ".css", ".colors", ".kvconfig"):
            continue
        original = file.read_bytes()
        data = gzip.decompress(original) if file.suffix == ".svgz" else original
        updated = recolor(data.decode("utf-8"), color).encode("utf-8")
        if data != updated:
            file.write_bytes(gzip.compress(updated, mtime=0) if file.suffix == ".svgz" else updated)
