"""Apply a selected accent to owned, staged theme resources."""

import colorsys
import gzip
import re
from pathlib import Path

from installer_choices import COLORS, selected


def recolor(text: str, accent: str) -> str:
    target = tuple(int(accent[i:i+2], 16) / 255 for i in (1, 3, 5))
    hue, saturation, brightness = colorsys.rgb_to_hsv(*target)

    def convert(rgb):
        old_hue, old_saturation, value = colorsys.rgb_to_hsv(*(v / 255 for v in rgb))
        # The bundled selection/focus family is blue. Leave status colors,
        # neutral surfaces, foregrounds and alpha untouched.
        if not .52 <= old_hue <= .68 or old_saturation < .25:
            return rgb
        return tuple(round(v * 255) for v in colorsys.hsv_to_rgb(
            hue, saturation * min(1, old_saturation / .7), value * brightness))

    def hex_color(match):
        value = match[1]
        rgb = tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
        return "#" + "".join(f"{v:02x}" for v in convert(rgb))

    # Selection backgrounds and their text are a pair. Bright accents (notably
    # gray, yellow and green) cannot retain the bundled white-on-blue text.
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in target]
    luminance = sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))
    foreground = "#000000" if luminance > .179 else "#ffffff"

    def css_selection(match):
        body = match[0]
        accent_background = bool(re.search(r"background(?:-color)?\s*:\s*@accent_bg_color\s*;", body))
        literal = re.search(r"background(?:-color)?\s*:\s*#([0-9a-fA-F]{6})\s*;", body)
        if literal:
            original = tuple(int(literal[1][i:i+2],16)/255 for i in (0,2,4))
            old_hue, old_saturation, _ = colorsys.rgb_to_hsv(*original)
            accent_background |= .52 <= old_hue <= .68 and old_saturation >= .25
        if accent_background:
            body = re.sub(r"(?<![-\w])color\s*:\s*#ffffff\s*;", "color: " + foreground + ";", body)
        return body

    text = re.sub(r"\{[^{}]*\}", css_selection, text)
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
    text = re.sub(
        r"(?P<prefix>\brgba?\([ \t]*|^[ \t]*(?:Color|Background\w*|Foreground\w*|Decoration\w*)[ \t]*=[ \t]*)"
        r"(?P<r>\d{1,3})[ \t]*,[ \t]*(?P<g>\d{1,3})[ \t]*,[ \t]*(?P<b>\d{1,3})"
        r"(?=[ \t]*(?:[,)]|$))",
        rgb_color, text, flags=re.MULTILINE)

    # KDE and Qt delegates use palette roles rather than CSS inheritance.
    def selection_palette(match):
        section = match[0]
        selected_foreground = foreground
        background = re.search(r"(?m)^BackgroundNormal=(\d+),(\d+),(\d+)", section)
        highlight = re.search(r"(?m)^highlight\.color=#([0-9a-fA-F]{6})", section)
        values = ([int(v)/255 for v in background.groups()] if background else
                  [int(highlight[1][i:i+2],16)/255 for i in (0,2,4)] if highlight else None)
        if values:
            lum = sum((v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4)*w
                      for v,w in zip(values,(.2126,.7152,.0722)))
            selected_foreground = "#000000" if lum > .179 else "#ffffff"
        if section.startswith("[Colors:Selection]"):
            rgb = "0,0,0" if selected_foreground == "#000000" else "255,255,255"
            return re.sub(r"(?m)^(ForegroundNormal|ForegroundActive)=[^\n]+", lambda m: m[1] + "=" + rgb, section)
        return re.sub(r"(?m)^((?:inactive\.)?highlight\.text\.color)=[^\n]+", lambda m: m[1] + "=" + selected_foreground, section)

    text = re.sub(r"(?m)^\[(?:Colors:Selection|GeneralColors)\][^\[]*", selection_palette, text)
    text = re.sub(r"(@define-color (?:accent_fg_color|theme_selected_fg_color|selected_fg_color)) #[0-9a-fA-F]{6};",
                  lambda m: m[1] + " " + foreground + ";", text)
    return text


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
