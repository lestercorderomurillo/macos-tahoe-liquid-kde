"""Render project artwork into consistent tiles and tonal glass appearances.

SPDX-License-Identifier: GPL-3.0-or-later
Copyright (C) 2026 Lester Cordero Murillo
"""
from __future__ import annotations

import hashlib
import io
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass, asdict
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps


VARIANTS = ("light", "dark", "black", "white", "clear-light", "clear-dark",
            "tinted-light", "tinted-dark")


@dataclass(frozen=True)
class GlassMaterial:
    """Versioned by generator source hash; defaults preserve the reviewed material."""
    shadow_tint: float = .08
    relief_tint: float = .8
    sparse_fraction: float = .08
    sparse_gamma: float = 2.2
    ink_blackpoint: int = 64

    def __post_init__(self):
        for name, value in asdict(self).items():
            maximum = 8 if name == "sparse_gamma" else 163 if name == "ink_blackpoint" else 1
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= maximum:
                raise ValueError(f"Invalid glass material parameter: {name}")
        if not isinstance(self.ink_blackpoint, int) or self.sparse_gamma == 0:
            raise ValueError("Invalid glass ink curve")


DEFAULT_GLASS = GlassMaterial()


def minimum_filter(image: Image.Image, width: int) -> Image.Image:
    """Exact square erosion via small kernels; identical edge extension to Pillow.

    Repeating a 3x3 minimum n times equals a (2n+1)x(2n+1) minimum,
    without Pillow's expensive large-window rank selection.
    """
    for _ in range(width // 2):
        image = image.filter(ImageFilter.MinFilter(3))
    return image


def svg_input(data: bytes) -> tuple[bytes, int]:
    """Discard unavailable external image layers, recording each removal for review."""
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)", data, re.I):
        raise ValueError("SVG document types and entities are not supported")
    root = ET.fromstring(data)
    removed = 0
    for parent in root.iter():
        for child in list(parent):
            if child.tag.rsplit("}", 1)[-1] != "image":
                continue
            hrefs = [v for k, v in child.attrib.items() if k.rsplit("}", 1)[-1] == "href"]
            if any(not v.startswith(("#", "data:image/png;base64,", "data:image/jpeg;base64,")) for v in hrefs):
                parent.remove(child)
                removed += 1
    cleaned = ET.tostring(root) if removed else data
    validate_svg(cleaned)
    return cleaned, removed


def validate_svg(data: bytes) -> None:
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)", data, re.I):
        raise ValueError("SVG document types and entities are not supported")
    root = ET.fromstring(data)
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in {"script", "foreignObject"}:
            raise ValueError(f"Unsupported SVG element: {tag}")
        for key, value in element.attrib.items():
            if key.rsplit("}", 1)[-1] == "href":
                if not (value.startswith("#") or value.startswith("data:image/png;base64,")
                        or value.startswith("data:image/jpeg;base64,")):
                    raise ValueError("SVG external resources are not supported")
        text = " ".join(element.attrib.values()) + (element.text or "")
        if "@import" in text.lower() or "\\" in text:
            raise ValueError("SVG CSS imports and escaped resource references are unsupported")
        for url in re.findall(r"url\s*\((.*?)\)", text, re.I | re.S):
            if not url.strip(" \t\r\n\"'").startswith("#"):
                raise ValueError("SVG external paint resources are not supported")


def raster(source: Path, size: int) -> Image.Image:
    if source.suffix.lower() == ".svg":
        data, _ = svg_input(source.read_bytes())
        image = raster_svg(data, size)
    else:
        with Image.open(source) as original:
            image = original.convert("RGBA")
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size))
    canvas.alpha_composite(image, ((size - image.width) // 2, (size - image.height) // 2))
    return canvas


def raster_svg(data: bytes, size: int) -> Image.Image:
    rendered = subprocess.run(
        ["rsvg-convert", "--width", str(size), "--height", str(size),
         "--keep-aspect-ratio"], input=data, capture_output=True, timeout=30,
    )
    if rendered.returncode:
        raise ValueError("SVG render failed: " + rendered.stderr.decode(errors="replace")[:300])
    with Image.open(io.BytesIO(rendered.stdout)) as image:
        image = image.convert("RGBA")
    canvas = Image.new("RGBA", (size, size))
    canvas.alpha_composite(image, ((size-image.width)//2, (size-image.height)//2))
    return canvas


def prepare_source(source: Path, size: int, glyph: bool = False, *, clean_rim: bool = False) -> tuple:
    image = raster(source, size)
    # Resolve links so the same paint settings apply to every artwork alias.
    image.info["artwork_name"] = source.resolve().stem
    if glyph or source.suffix.lower() != ".svg":
        removed = svg_input(source.read_bytes())[1] if source.suffix.lower() == ".svg" else 0
        return (*prepare(image, glyph), None, removed)
    data, removed_images = svg_input(source.read_bytes())
    layered = {
        "1dd88e9ee27a257855d8712de3870cf7ca7c87f3e591f45de7444c2456bfa007": "finder",
        "2961c8cd92c6270b7b2acefa1e275692466f5d5c69b948c25f51efd72c53c13e": "apps",
        "a3905306bcefa3809c64a5da38b1d336abdbf320deafa54b2a31804fd8ed70af": "store",
        "8ff99c6c70c0a33282aa351e3de4f0fc29bb4437d3cfe6c6ae6cfda4a7b97632": "settings",
        "5f8eb7594ee00628afaae671e44536306b41944d97129722364eade5ed106168": "photos",
    }.get(hashlib.sha256(data).hexdigest())
    if layered:
        image.info["material_svg"] = (layered, data)
    root = ET.fromstring(data)
    drawables = []

    def collect(element):
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in {"defs", "clipPath", "mask", "pattern", "metadata"}:
            return
        if tag in {"path", "rect", "circle", "ellipse", "polygon", "polyline", "image", "text", "use"}:
            drawables.append(element)
        else:
            for child in element:
                collect(child)

    collect(root)
    if not drawables:
        return (*prepare(image), None, removed_images)
    originals = [dict(node.attrib) for node in drawables]
    removed = []
    plate_index = None
    plate_probe = None
    found_artwork = False
    for i, node in enumerate(drawables[:24]):
        for other in drawables:
            other.set("style", other.get("style", "") + ";display:none")
        node.attrib.clear()
        node.attrib.update(originals[i])
        isolated = raster_svg(ET.tostring(root), 64)
        for other, original in zip(drawables, originals):
            other.attrib.clear()
            other.attrib.update(original)
        alpha = isolated.getchannel("A")
        center = alpha.crop((12, 12, 52, 52))
        solid = sum(center.histogram()[231:]) / 1600
        area = sum(alpha.histogram()[231:]) / 4096
        if not found_artwork and solid > .94 and area > .60:
            plate_index, plate_probe = i, isolated
            removed = list(range(i+1))
        elif plate_index is not None:
            # Existing rim/shadow layers surround the tile but leave its centre empty.
            central = alpha.crop((18, 18, 46, 46)).getextrema()[1]
            bounds = alpha.getbbox()
            wide = bounds and bounds[0] < 9 and bounds[1] < 9 and bounds[2] > 55 and bounds[3] > 55
            rim_layer = False
            if clean_rim and central < 8:
                plate_alpha = plate_probe.getchannel("A")
                edge_band = ImageChops.subtract(plate_alpha.filter(ImageFilter.MaxFilter(3)),
                                               minimum_filter(plate_alpha, 7))
                edge_alpha = ImageChops.multiply(alpha, edge_band)
                weight = sum(value * count for value, count in enumerate(alpha.histogram()))
                edge_weight = sum(value * count for value, count in enumerate(edge_alpha.histogram()))
                rim_layer = weight > 0 and edge_weight / weight > .9
            if central < 8 and (wide or rim_layer):
                removed.append(i)
            else:
                found_artwork = True
    if plate_index is None:
        return (*prepare(image), None, removed_images)
    for i in removed:
        drawables[i].set("style", drawables[i].get("style", "") + ";display:none")
    artwork = raster_svg(ET.tostring(root), size)
    # Retain the actual background, including its existing rim and shadows.
    # Color variants may recolor these layers, never replace their geometry.
    for i, node in enumerate(drawables):
        node.attrib.clear()
        node.attrib.update(originals[i])
        if i not in removed:
            node.set("style", node.get("style", "") + ";display:none")
    image.info["icon_background"] = raster_svg(ET.tostring(root), size)
    if artwork.getchannel("A").getbbox() is None:
        return (*prepare(image), None, removed_images)
    for i, node in enumerate(drawables):
        node.attrib.clear()
        node.attrib.update(originals[i])
        if i != plate_index:
            node.set("style", node.get("style", "") + ";display:none")
    shape = raster_svg(ET.tostring(root), size).getchannel("A")
    plate_pixels = [p for p in plate_probe.getdata() if p[3] > 230]
    colored = sum(max(p[:3]) - min(p[:3]) >= 20 for p in plate_pixels)
    brightness = sum(sum(p[:3]) / 3 for p in plate_pixels) / len(plate_pixels)
    # Split-color tiles can express a white logo through the base layer itself.
    # Their colored edge panels are part of the background, not removable rims.
    plate_alpha = plate_probe.getchannel("A")
    inset_alpha = minimum_filter(plate_alpha, 13)
    edge_pixels = [p for p, outer, inner in zip(
        image.resize((64, 64), Image.Resampling.LANCZOS).getdata(),
        plate_alpha.getdata(), inset_alpha.getdata()) if outer > 230 and inner < 128]
    colored_edge = sum(max(p[:3]) - min(p[:3]) >= 20 and p[3] > 230 for p in edge_pixels)
    classification = "vector-colored" if (colored / len(plate_pixels) > .01
        or colored_edge > len(edge_pixels) * .25) else (
        "vector-light" if brightness > 145 else "vector-dark")
    return image, shape, classification, artwork, removed_images


def neutral_plate(image: Image.Image) -> tuple[Image.Image | None, str]:
    """Find only an edge-connected neutral tile, leaving internal white glyphs alone.

    Classify at 64 px so decisions are stable across output sizes. Unknown or
    multicolored plates remain intact and are reported for optional overrides.
    """
    probe = image.resize((64, 64), Image.Resampling.LANCZOS)
    pixels = probe.load()
    seeds = [(x, y) for x in range(20, 44) for y in (7, 56)]
    seeds += [(x, y) for y in range(20, 44) for x in (7, 56)]
    opaque = [pixels[x, y] for x, y in seeds if pixels[x, y][3] > 220]
    if len(opaque) < len(seeds) * .85:
        return None, "unclassified"
    neutral = [p for p in opaque if max(p[:3]) - min(p[:3]) < 20]
    if len(neutral) < len(opaque) * .95:
        return None, "colored-plate"
    values = sorted(sum(p[:3]) / 3 for p in neutral)
    if values[-1] - values[0] > 90:
        return None, "complex-plate"
    center = values[len(values) // 2]
    lower, upper = max(0, values[0] - 15), min(255, values[-1] + 15)
    mask = Image.new("L", (64, 64))
    mask_pixels = mask.load()
    queue = deque(seeds)
    seen = set()
    while queue:
        x, y = queue.popleft()
        if (x, y) in seen or not (3 <= x <= 60 and 3 <= y <= 60):
            continue
        seen.add((x, y))
        p = pixels[x, y]
        value = sum(p[:3]) / 3
        if p[3] < 180 or max(p[:3]) - min(p[:3]) >= 22 or not lower <= value <= upper:
            continue
        mask_pixels[x, y] = 255
        queue.extend(((x-1, y), (x+1, y), (x, y-1), (x, y+1)))
    count = sum(mask.histogram()[1:])
    if count < 650 or count > 3050:
        return None, "complex-plate"
    return mask.resize(image.size, Image.Resampling.BILINEAR), "light-plate" if center > 145 else "dark-plate"


def gradient(size: int, top: tuple, bottom: tuple) -> Image.Image:
    ramp = Image.new("RGBA", (1, size))
    ramp.putdata([tuple(round(a + (b-a) * y / max(1, size-1)) for a, b in zip(top, bottom))
                  for y in range(size)])
    return ramp.resize((size, size))


def tile(size: int, variant: str, tint: tuple[int, int, int]) -> Image.Image:
    dark = variant in {"dark", "black", "clear-dark", "tinted-dark"}
    glass = variant.startswith(("clear-", "tinted-"))
    if glass:
        if variant.startswith("tinted-"):
            top = (*tuple(round(c * .6 + 255 * .4) for c in tint), 150 if dark else 125)
            bottom = (*tuple(round(c * .65) for c in tint), 80 if dark else 55)
        else:
            top, bottom = ((220, 228, 240, 100), (70, 80, 100, 55)) if dark else (
                (255, 255, 255, 155), (220, 228, 240, 55))
    else:
        top, bottom = ((51, 53, 58, 255), (20, 21, 25, 255)) if dark else (
            (253, 252, 251, 255), (237, 236, 234, 255))
    return gradient(size, top, bottom)


def prepare(image: Image.Image, glyph: bool = False) -> tuple:
    size = image.width
    if glyph:
        bounds = image.getchannel("A").getbbox()
        if bounds is None:
            raise ValueError("Empty glyph artwork")
        art = image.crop(bounds)
        art.thumbnail((round(size*.65), round(size*.65)), Image.Resampling.LANCZOS)
        image = Image.new("RGBA", (size, size))
        image.alpha_composite(art, ((size-art.width)//2, (size-art.height)//2))
        return image, None, "glyph"
    mask, classification = neutral_plate(image)
    return image, mask, classification


def render(prepared: tuple, variant: str, tint: tuple[int, int, int]) -> Image.Image:
    if variant not in VARIANTS:
        raise ValueError("Unknown icon variant")
    if variant in {"light", "dark"}:
        return render_installer(prepared, "regular", variant, tint)
    mode = "dark" if variant in {"dark", "black", "clear-dark", "tinted-dark"} else "light"
    style = "clear" if variant.startswith("clear-") else "glass"
    return render_installer(prepared, style, mode,
                            (142, 142, 147) if variant in {"black", "white"} else tint)


def dark_foreground(artwork: Image.Image) -> Image.Image:
    """Lift exposed neutral black glyphs, retaining colored and enclosed details."""
    probe = artwork.resize((128, 128), Image.Resampling.LANCZOS)
    pixels = probe.load()
    transparent = probe.getchannel("A").point(lambda a: 255 if a < 64 else 0)
    near_clear = transparent.filter(ImageFilter.MaxFilter(5)).load()
    remaining = {(x, y) for y in range(128) for x in range(128)
                 if pixels[x, y][3] > 96}
    mask = Image.new("L", probe.size)
    selected = mask.load()
    while remaining:
        queue = deque([remaining.pop()])
        component = []
        exposed = False
        colored = bright = 0
        while queue:
            x, y = queue.popleft()
            component.append((x, y))
            r, g, b, _ = pixels[x, y]
            colored += max(r, g, b) - min(r, g, b) >= 18
            bright += max(r, g, b) > 160
            exposed |= bool(near_clear[x, y] and max(r, g, b) < 85)
            for point in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                if point in remaining:
                    remaining.remove(point)
                    queue.append(point)
        # Recolor isolated neutral glyphs as a whole. Dark outlines attached
        # to colored illustrations and shaded objects retain their original ink.
        if exposed and colored / len(component) < .01 and bright / len(component) < .12:
            for point in component:
                selected[point] = 255
    if mask.getbbox() is None:
        return artwork
    mask = mask.resize(artwork.size, Image.Resampling.NEAREST).filter(ImageFilter.MaxFilter(3))
    r, g, b = artwork.convert("RGB").split()
    high = ImageChops.lighter(ImageChops.lighter(r, g), b)
    low = ImageChops.darker(ImageChops.darker(r, g), b)
    neutral = ImageChops.subtract(high, low).point(lambda v: 255 if v < 18 else 0)
    mask = ImageChops.multiply(mask, neutral)
    # A continuous curve avoids seams through gradients and antialiased edges.
    lifted = artwork.point([round(174 + v * .24) for v in range(256)] * 3 + list(range(256)))
    return Image.composite(lifted, artwork, mask)


def _recolor_layer(layer: Image.Image, low: tuple, high: tuple,
                   *, opacity: float = 1.0, invert: bool = False, gamma: float = 1.0) -> Image.Image:
    """Change paint only: retain the layer's coverage, holes and tonal detail."""
    luminance = ImageOps.grayscale(layer)
    if gamma != 1:
        luminance = luminance.point(lambda v: round(255 * (v / 255) ** gamma))
    if invert:
        luminance = ImageOps.invert(luminance)
    result = ImageOps.colorize(luminance, low, high).convert("RGBA")
    alpha = layer.getchannel("A")
    result.putalpha(alpha if opacity == 1 else alpha.point(lambda a: round(a * opacity)))
    return result


def _render_dock_layers(image, style, mode, tint):
    """Paint the existing face, smile, petals and overlaps before compositing."""
    kind, data = image.info["material_svg"]
    root = ET.fromstring(data)
    clear = style == "clear"
    dark = mode == "dark"
    white, black = (255, 255, 255), (0, 0, 0)

    def blend(a, b, fraction):
        return tuple(round(x + (y - x) * fraction) for x, y in zip(a, b))

    def color(rgb):
        return "#%02x%02x%02x" % rgb

    if clear:
        plate = black if dark else white
        opacity = .63 if dark else .17
        ink = white
    elif dark:
        plate = blend(black, tint, .095)
        opacity = .83
        ink = blend(tint, white, .26)
    else:
        # Recover the hue even from a pastel swatch. Ease into neutral paint
        # for low chroma so near-gray RGB choices remain stable.
        floor, peak = min(tint), max(tint)
        chroma = peak - floor
        hue = tuple(round(255 * (v - floor) / max(chroma, 1)) for v in tint)
        strength = min(1, chroma / 40)
        saturated = blend(tint, hue, strength)
        density = .57 - .11 * saturated[1] / 255 + .09 * min(saturated) / 255
        plate = blend(black, saturated, density)
        # Warm and pale accents need more pigment to resist a cool backdrop.
        warm = max(0, tint[0] - max(tint[1:])) / 128
        pastel = max(0, floor - 112) / 40
        pigment = min(1, max(warm, pastel))
        if kind == "settings":
            pigment = 1
            green = max(0, tint[1] - max(tint[0], tint[2])) / 255
            plate = blend(plate, blend(black, tint, .33), green)
        plate = blend(blend(black, tint, .42), plate, pigment)
        opacity = .52 + .39 * pigment
        if kind == "finder":
            # Keep the pale eye legible over light wallpaper.
            opacity = max(opacity, .59)
        ink = blend(blend(tint, white, .97), blend(saturated, white, .94), pigment)

    gradients = {node.get("id"): node for node in root[0]}
    plate_id = {"apps": "linearGradient3", "store": "d"}.get(kind, "b")
    for stop in gradients[plate_id]:
        stop.set("stop-color", color(plate))
        stop.set("stop-opacity", str(opacity))
    if not clear and not dark and pigment:
        gradients[plate_id][0].set("stop-color", color(blend(plate, white, .045 * pigment)))
        gradients[plate_id][-1].set("stop-color", color(blend(plate, black, .07 * pigment)))
    if kind == "finder":
        for stop in gradients["c"]:
            stop.set("stop-color", color(ink))
        # Follow the existing vertical face division with a hard paint stop.
        smile = gradients["h"]
        smile.set("x1", "4.196")
        smile.set("x2", "12.737")
        dark_ink = blend(plate, black, .75)
        for stop, offset, paint in zip(smile, ["0", "1"], [ink, dark_ink]):
            stop.set("offset", offset)
            stop.set("stop-color", color(paint))
        for index, paint in enumerate([ink, dark_ink], 1):
            smile.insert(index, ET.Element(smile[0].tag, {
                "offset": ".50", "stop-color": color(paint)}))
        for node in root.iter():
            if node.get("stroke") in ("url(#j)", "#000"):
                node.set("stroke", "url(#h)")
        root.find("{*}rect").set("fill", color(dark_ink))
        root[-1].find("{*}rect").set("fill", color(ink))
    elif kind == "photos":
        # The eight overlap shapes already exist in the bundled artwork.
        for node in root.findall("{*}rect"):
            node.set("fill", color(ink))
            node.set("fill-opacity", ".63")
        for node in root.findall("{*}path"):
            fill = node.get("fill", "")
            if fill.startswith("#") and fill != "#fff":
                node.set("fill", color(ink))
                node.set("fill-opacity", ".26")
            elif fill == "#fff":
                node.set("opacity", ".17")
        for stop in gradients["a"]:
            stop.set("stop-color", color(ink))
    elif kind == "settings" and not clear and not dark:
        for key, top, bottom in (("g", .49, .29), ("j", .91, .56)):
            for stop, strength in zip(gradients[key], (top, bottom)):
                stop.set("stop-color", color(blend(plate, ink, strength)))
        # The original soft gear layer adds depth behind the fine teeth.
        root[2].set("fill", color(blend(plate, ink, .75)))
        root[2].set("opacity", ".80")
        for node in root.findall("{*}path"):
            if node.get("fill") == "#fff":
                node.set("fill", color(blend(plate, ink, .45)))
    elif kind == "settings":
        for key, strength in (("g", .48), ("j", .78)):
            for stop, factor in zip(gradients[key], [strength, strength * .70]):
                stop.set("stop-color", color(ink))
                stop.set("stop-opacity", str(factor))
    elif kind == "apps":
        for node in root.iter():
            if node.get("fill", "").startswith("#"):
                node.set("fill", color(ink))
                node.set("fill-opacity", ".68")
        root[2].set("opacity", ".16")
        for key, gradient in gradients.items():
            if key != plate_id:
                for stop in gradient:
                    if stop.tag.endswith("}stop"):
                        stop.set("stop-color", color(ink))
                        if key == "linearGradient69":
                            stop.set("stop-opacity", ".64")
    elif kind == "store":
        for key in ("a", "h", "b", "j", "q", "r"):
            for stop in gradients[key]:
                stop.set("stop-color", color(ink))
                stop.set("stop-opacity", str(float(stop.get("stop-opacity", 1)) * .72))
    return raster_svg(ET.tostring(root), image.width)


def render_installer(prepared: tuple, style: str, mode: str, tint: tuple[int, int, int],
                     material: GlassMaterial = DEFAULT_GLASS) -> Image.Image:
    """Repaint the original layers without creating tiles, rims or shadows.

    Default preserves the original paint. Clear uses neutral translucent paint;
    tinted light colors the background, tinted dark colors the foreground.
    Unlayered assets retain their own silhouette, including both Trash states.
    """
    if style not in {"regular", "glass", "clear"} or mode not in {"light", "dark"}:
        raise ValueError("Unknown installer icon material")
    image, shape, classification, artwork, _ = prepared
    background = image.info.get("icon_background")
    if style == "regular":
        if mode == "light" or classification != "vector-light" or background is None:
            return image.copy()
        background = _recolor_layer(background, (8, 8, 10), (48, 48, 51))
        result = Image.alpha_composite(background, dark_foreground(artwork))
        result.putalpha(image.getchannel("A"))
        return result
    if "material_svg" in image.info:
        return _render_dock_layers(image, style, mode, tint)
    dark = mode == "dark"
    if image.info.get("artwork_name") in ("user-trash", "user-trash-full"):
        # Both Dock states use a neutral material independent of the accent.
        if dark:
            return _recolor_layer(image, (8, 8, 8), (78, 78, 78), gamma=2.5)
        return _recolor_layer(image, (45, 45, 45), (243, 243, 243), gamma=1.45)
    clear = style == "clear"
    light_glass_artwork = image.info.get("artwork_name") if not dark and not clear else None
    browser_or_mail = light_glass_artwork in ("firefox", "thunderbird")
    rgb = (142, 142, 147) if clear else tint
    def mix(amount, white=0):
        return tuple(round(c * amount + white * (1 - amount)) for c in rgb)
    if dark:
        plate_low, plate_high = (4, 4, 6), (35, 35, 39)
        low, high = mix(.30), mix(.78, 255)
    else:
        plate_low, plate_high = mix(.48), mix(.78, 255)
        low, high = mix(material.shadow_tint), mix(.08, 255)
    if clear:
        plate_low, plate_high = ((12, 12, 14), (58, 58, 62)) if dark else ((170, 174, 180), (245, 247, 250))
        low, high = ((135, 140, 148), (250, 252, 255)) if dark else ((35, 40, 48), (250, 252, 255))
    if background is None or artwork is None:
        # No background layer exists. Do not invent a squircle behind the asset.
        return _recolor_layer(image, low if dark or clear else mix(.30),
                              high if dark or clear else mix(.65, 255), opacity=.85 if clear else 1)
    if browser_or_mail:
        plate_low, plate_high = mix(.36), mix(.67)
    plate = _recolor_layer(background, plate_low, plate_high,
                           opacity=.60 if clear else 1)
    # Sparse dark lettering needs the opposite polarity against a dark tile.
    sparse = sum(artwork.getchannel("A").histogram()[128:]) < image.width * image.height * material.sparse_fraction
    if browser_or_mail:
        foreground = _recolor_layer(artwork, mix(material.relief_tint * .8, 255), high, gamma=1.25)
    elif sparse:
        ink = ImageOps.grayscale(artwork).point(
            lambda value: round(255 * (value / 255) ** material.sparse_gamma))
        foreground = ImageOps.colorize(ink, high if dark else low, low if dark else high,
                                      blackpoint=material.ink_blackpoint).convert("RGBA")
        foreground.putalpha(artwork.getchannel("A"))
    else:
        lifted = dark_foreground(artwork)
        foreground = _recolor_layer(lifted if dark else artwork,
                                    low if dark or clear else mix(material.relief_tint * .4375, 255), high)
        if not dark and not clear:
            # Exposed black strokes (Finder's face) keep dark ink; the broad
            # illustration uses pale tint paint, as in Tahoe's light appearance.
            changed = ImageChops.difference(lifted, artwork).convert("RGB")
            mask = ImageChops.lighter(ImageChops.lighter(*changed.split()[:2]), changed.split()[2])
            r, g, b = artwork.convert("RGB").split()
            peak = ImageChops.lighter(ImageChops.lighter(r, g), b)
            floor = ImageChops.darker(ImageChops.darker(r, g), b)
            neutral = ImageChops.subtract(peak, floor).point(lambda v: max(0, 255 - v * 12))
            black = peak.point(lambda v: max(0, min(255, (95 - v) * 8)))
            mask = ImageChops.lighter(mask.point(lambda v: 255 if v else 0), ImageChops.multiply(neutral, black))
            ink = _recolor_layer(artwork, low, high, gamma=1.4)
            if light_glass_artwork == "file-manager":
                # The smile is beveled in the original, so parts of it are
                # neither black nor strictly neutral. Keep their ink connected.
                stroke = peak.point(lambda v: max(0, min(255, (152 - v) * 6)))
                near_neutral = ImageChops.subtract(peak, floor).point(
                    lambda v: max(0, min(255, (53 - v) * 10)))
                mask = ImageChops.lighter(mask, ImageChops.multiply(stroke, near_neutral))
                ink = _recolor_layer(artwork, low, mix(.65), gamma=1.4)
            foreground = Image.composite(ink, foreground, mask)
    result = Image.alpha_composite(plate, foreground)
    original_alpha = image.getchannel("A")
    result.putalpha(ImageChops.darker(result.getchannel("A"), original_alpha) if clear else original_alpha)
    return result
