"""Render project artwork into consistent tiles and tonal glass appearances.

SPDX-License-Identifier: GPL-3.0-or-later
Copyright (C) 2026 Lester Cordero Murillo
"""
from __future__ import annotations

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
    if glyph or source.suffix.lower() != ".svg":
        removed = svg_input(source.read_bytes())[1] if source.suffix.lower() == ".svg" else 0
        return (*prepare(image, glyph), None, removed)
    data, removed_images = svg_input(source.read_bytes())
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
    probes = []
    for i, node in enumerate(drawables[:24]):
        for other in drawables:
            other.set("style", other.get("style", "") + ";display:none")
        node.attrib.clear()
        node.attrib.update(originals[i])
        isolated = raster_svg(ET.tostring(root), 64)
        probes.append(isolated)
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
    plate_parts = {plate_index} if plate_index is not None else set()
    if plate_index is None:
        # Some originals draw the tile as adjacent header/body paths (Notes).
        # Recognize their union only when both span the tile's full width and
        # meet without overlapping. Narrow unplated objects remain unplated.
        wide = []
        for index, probe in enumerate(probes):
            alpha = probe.getchannel("A")
            bounds = alpha.point(lambda a: 255 if a > 230 else 0).getbbox()
            if bounds and bounds[0] <= 5 and bounds[2] >= 59:
                wide.append(index)
        for index, first in enumerate(wide):
            for second in wide[index+1:]:
                a, b = (probes[i].getchannel("A") for i in (first, second))
                union = ImageChops.lighter(a, b)
                overlap = sum(ImageChops.darker(a, b).histogram()[128:])
                if (sum(union.crop((12,12,52,52)).histogram()[231:]) > 1600*.94
                        and sum(union.histogram()[231:]) > 4096*.60 and overlap < 40):
                    plate_index = first
                    plate_parts = {first, second}
                    plate_probe = Image.alpha_composite(probes[first], probes[second])
                    removed = list(range(first+1)) + [second]
                    break
            if plate_index is not None:
                break
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
    for index in plate_parts:
        drawables[index].set("style", drawables[index].get("style", "") + ";display:none")
    image.info["icon_background_detail"] = raster_svg(ET.tostring(root), size)
    if artwork.getchannel("A").getbbox() is None:
        return (*prepare(image), None, removed_images)
    for i, node in enumerate(drawables):
        node.attrib.clear()
        node.attrib.update(originals[i])
        if i not in plate_parts:
            node.set("style", node.get("style", "") + ";display:none")
    original_plate = raster_svg(ET.tostring(root), size)
    image.info["icon_plate"] = original_plate
    shape = original_plate.getchannel("A")
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
    image.info["icon_plate_colored"] = colored / len(plate_pixels) > .01
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


def _plate_tones(layer: Image.Image) -> Image.Image:
    """Use the source gradient's range, not the entire 0..255 RGB interval."""
    gray = ImageOps.grayscale(layer)
    values = sorted(v for v, a in zip(gray.getdata(), layer.getchannel("A").getdata()) if a > 240)
    if not values:
        return gray
    low, high = values[len(values)//20], values[len(values)*19//20]
    if high - low < 3:
        return Image.new("L", layer.size, 128)
    return gray.point(lambda v: max(0, min(255, round((v-low)*255/(high-low)))))


def _exposed_ink(artwork: Image.Image) -> Image.Image:
    """Find dark ink on the plate, retaining dark details inside a light symbol.

    Close small holes in the original bright foreground to identify its support.
    This mask selects paint only; it never adds pixels to any original layer.
    """
    probe = artwork.resize((128, 128), Image.Resampling.LANCZOS)
    gray = ImageOps.grayscale(probe)
    bright = ImageChops.multiply(gray.point(lambda v: min(255, max(0, (v-100)*4))),
                                 probe.getchannel("A"))
    support = bright.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9))
    support = support.point(lambda v: min(255, v*3))
    exposed = ImageOps.invert(support).resize(artwork.size, Image.Resampling.BILINEAR)
    dark = ImageOps.grayscale(artwork).point(lambda v: min(255, max(0, (120-v)*4)))
    return ImageChops.multiply(exposed, dark)


def _oklab(rgb):
    r, g, b = [v/3294.6 if v <= 10.31475 else ((v/255+.055)/1.055)**2.4 for v in rgb]
    l = (.4122214708*r+.5363325363*g+.0514459929*b)**(1/3)
    m = (.2119034982*r+.6806995451*g+.1073969566*b)**(1/3)
    s = (.0883024619*r+.2817188376*g+.6299787005*b)**(1/3)
    return (.2104542553*l+.793617785*m-.0040720468*s,
            1.9779984951*l-2.428592205*m+.4505937099*s,
            .0259040371*l+.7827717662*m-.808675766*s)


def _from_oklab(lightness, a, b):
    # Reduce chroma into sRGB rather than clipping channels and shifting hue.
    for _ in range(32):
        l = (lightness+.3963377774*a+.2158037573*b)**3
        m = (lightness-.1055613458*a-.0638541728*b)**3
        s = (lightness-.0894841775*a-1.291485548*b)**3
        rgb = (4.0767416621*l-3.3077115913*m+.2309699292*s,
               -1.2684380046*l+2.6097574011*m-.3413193965*s,
               -.0041960863*l-.7034186147*m+1.707614701*s)
        if min(rgb) >= -.00001 and max(rgb) <= 1.00001:
            break
        a *= .96; b *= .96
    return tuple(round(255 * (12.92*v if v <= .0031308 else 1.055*v**(1/2.4)-.055))
                 for v in (max(0, min(1, c)) for c in rgb))


def _tint_palette(tint):
    """Interpolate measured Tahoe paint transfers in perceptual hue space.

    Anchors: MacMost red/blue Dock frames, 512 Pixels green original PNG.
    Values are lightness changes and chroma ratios, not per-icon colors.
    These captures constrain a paint approximation, not macOS live refraction.
    """
    L, a, b = _oklab(tint)
    hue = math.degrees(math.atan2(b, a)) % 360
    anchors = ((26.9, -.266, -.291, .64, .040, .89, -13.1),
               (147.4, -.203, -.286, .71, .053, .93, 3.2),
               (256.9, -.251, -.298, .48, .048, .90, -5.4),
               (386.9, -.266, -.291, .64, .040, .89, -13.1))
    if hue < anchors[0][0]:
        hue += 360
    left, right = next((x, y) for x, y in zip(anchors, anchors[1:]) if x[0] <= hue <= y[0])
    t = (hue-left[0])/(right[0]-left[0])
    top, bottom, chroma, lift, saturation, rotation = [x+(y-x)*t for x, y in zip(left[1:], right[1:])]
    angle = math.radians(rotation)
    fa = (a*math.cos(angle)-b*math.sin(angle))*saturation
    fb = (a*math.sin(angle)+b*math.cos(angle))*saturation
    # Neutral and very dark inputs keep a usable dark plate without inventing hue.
    return (_from_oklab(max(.16, L+bottom), a*chroma, b*chroma),
            _from_oklab(max(.20, L+top), a*chroma, b*chroma),
            _from_oklab(min(.96, max(.58, L+lift)), fa, fb))


def render_installer(prepared: tuple, style: str, mode: str, tint: tuple[int, int, int],
                     material: GlassMaterial = DEFAULT_GLASS) -> Image.Image:
    """Repaint original layers; preserve all silhouettes, holes and drawn rims."""
    if style not in {"regular", "glass", "clear"} or mode not in {"light", "dark"}:
        raise ValueError("Unknown installer icon material")
    image, shape, classification, artwork, _ = prepared
    background = image.info.get("icon_background")
    if style == "regular" and (mode == "light" or background is None or artwork is None):
        return image.copy()
    if style == "regular" and classification == "vector-colored" and not image.info.get("icon_plate_colored", True):
        # White negative space belongs to split-color brand panels, not a tile.
        return image.copy()
    # Unplated objects (including Trash) keep their own original material.
    if background is None or artwork is None:
        return image.copy()
    dark, clear = mode == "dark", style == "clear"
    original_plate = image.info.get("icon_plate", background)
    tones = _plate_tones(original_plate)
    if style == "regular":
        plate = ImageOps.colorize(tones, (17, 17, 18), (52, 52, 54)).convert("RGBA")
        plate.putalpha(background.getchannel("A"))
    elif dark and not clear:
        # Cached PNGs cannot reproduce macOS backdrop filtering. Keep the dark
        # surface sufficiently opaque to retain detail over bright wallpapers.
        low, high, _ = _tint_palette(tint)
        low = tuple(round(5+c*.10) for c in low)
        high = tuple(round(12+c*.15) for c in high)
        plate = ImageOps.colorize(tones, low, high).convert("RGBA")
        plate.putalpha(background.getchannel("A").point(lambda a: round(a*.94)))
    elif clear:
        plate = Image.new("RGBA", image.size, (0, 0, 0) if dark else (215, 220, 220))
        opacity = tones.point(lambda v: round((.58-.29*v/255)*255) if dark else 35)
        plate.putalpha(ImageChops.multiply(background.getchannel("A"), opacity))
    else:
        low, high, _ = _tint_palette(tint)
        plate = ImageOps.colorize(tones, low, high).convert("RGBA")
        plate.putalpha(background.getchannel("A"))
    # Composite the actual source rim/shadow drawing, never a derived outline.
    detail = image.info.get("icon_background_detail")
    if detail is not None:
        detail = _recolor_layer(detail, (0, 0, 0), (255, 255, 255), opacity=.28 if clear else .10)
        plate = Image.alpha_composite(plate, detail)
    if style == "regular":
        probe = artwork.resize((64, 64), Image.Resampling.LANCZOS)
        pixels = [p for p in probe.getdata() if p[3] > 180]
        neutral = sum(max(p[:3])-min(p[:3]) < 20 for p in pixels) / max(1, len(pixels))
        if classification != "vector-colored" or neutral < .9:
            result = Image.alpha_composite(plate, dark_foreground(artwork))
            result.putalpha(image.getchannel("A") if style == "regular" else ImageChops.darker(result.getchannel("A"), image.getchannel("A")))
            return result
        # A white symbol on a colored plate exchanges its paint roles in Dark.
        pixels = [p for p in original_plate.resize((64, 64)).getdata() if p[3] > 240]
        tint = tuple(round(sum(p[c] for p in pixels)/len(pixels)) for c in range(3))
    if clear:
        low, high = (20, 25, 28), (255, 255, 255)
    elif dark:
        low = tuple(round(c * material.shadow_tint) for c in tint)
        high = _tint_palette(tint)[2] if style != "regular" else tint
    else:
        low = tuple(round(c * material.shadow_tint) for c in tint)
        high = tuple(round(247 + c*.03) for c in tint)
    foreground = _recolor_layer(artwork, low, high, gamma=material.relief_tint/.8)
    exposed = _exposed_ink(artwork)
    sparse = sum(artwork.getchannel("A").histogram()[128:]) < image.width * image.height * material.sparse_fraction
    if sparse:
        exposed = Image.new("L", image.size, 255)
    # Exposed strokes share the symbol paint. Embedded eyes/holes retain dark ink.
    neutral_dark = ImageOps.grayscale(artwork).point(lambda v: max(0, min(255, (100-v)*4)))
    embedded = ImageChops.subtract(neutral_dark, exposed)
    ink = _recolor_layer(artwork, tuple(round(c*.12) for c in high), high)
    foreground = Image.composite(ink, foreground, embedded)
    light_ink = _recolor_layer(artwork, high, high)
    foreground = Image.composite(light_ink, foreground, exposed)
    if style == "regular":
        # Carry the original colored plate gradient into the neutral symbol.
        color = original_plate.convert("RGB")
        tone = ImageOps.grayscale(artwork)
        painted = Image.merge("RGB", tuple(ImageChops.multiply(c, tone) for c in color.split())).convert("RGBA")
        painted.putalpha(artwork.getchannel("A"))
        bright = color.convert("RGBA")
        bright.putalpha(artwork.getchannel("A"))
        foreground = Image.composite(bright, painted, exposed)
    result = Image.alpha_composite(plate, foreground)
    alpha = image.getchannel("A")
    if style != "regular":
        # Even a faint original shadow remains present after opacity scaling.
        alpha = ImageChops.lighter(ImageChops.darker(result.getchannel("A"), alpha),
                                   alpha.point(lambda v: 1 if v else 0))
    result.putalpha(alpha)
    return result
