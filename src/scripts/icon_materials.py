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
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps


VARIANTS = ("light", "dark", "black", "white", "clear-light", "clear-dark",
            "tinted-light", "tinted-dark")


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
                                               plate_alpha.filter(ImageFilter.MinFilter(7)))
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
    inset_alpha = plate_alpha.filter(ImageFilter.MinFilter(13))
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
    image, plate, classification, artwork, _ = prepared
    size = image.width
    dark = variant in {"dark", "black", "clear-dark", "tinted-dark"}
    glass = variant.startswith(("clear-", "tinted-"))
    mono = variant not in {"light", "dark"}
    if artwork is not None:
        if classification == "vector-colored" and not mono:
            return image.copy()
        glyph = artwork.copy()
        lum = ImageOps.grayscale(glyph)
        if mono:
            if not dark:
                lum = ImageOps.invert(lum)
            low, high = ((130, 138, 150), (255, 255, 255)) if dark else ((18, 25, 35), (90, 100, 115))
            glyph = ImageOps.colorize(lum, low, high).convert("RGBA")
            glyph.putalpha(artwork.getchannel("A"))
        elif (dark and classification == "vector-light") or (not dark and classification == "vector-dark"):
            r, g, b = glyph.convert("RGB").split()
            spread = ImageChops.subtract(ImageChops.lighter(ImageChops.lighter(r, g), b),
                                         ImageChops.darker(ImageChops.darker(r, g), b))
            neutral = spread.point(lambda v: 255 if v < 18 else 0)
            extreme = lum.point(lambda v: 255 if (v < 85 if dark else v > 180) else 0)
            inverted = ImageOps.invert(glyph.convert("RGB")).convert("RGBA")
            inverted.putalpha(glyph.getchannel("A"))
            glyph = Image.composite(inverted, glyph, ImageChops.multiply(neutral, extreme))
        material = tile(size, variant, tint)
        material.putalpha(ImageChops.multiply(material.getchannel("A"), plate))
        # An inset highlight follows the actual SVG tile contour, including squircles.
        inset = plate.filter(ImageFilter.MinFilter(3))
        rim = ImageChops.subtract(plate, inset).point(lambda v: round(v * (.4 if glass else .16)))
        edge = Image.new("RGBA", image.size, "white")
        edge.putalpha(rim)
        return Image.alpha_composite(Image.alpha_composite(material, edge), glyph)
    result = image.copy()
    lum = ImageOps.grayscale(image)
    if mono:
        # Preserve luminance differences: flattening alpha into one color erases logos.
        if classification == "light-plate" or (classification == "glyph" and dark):
            lum = ImageOps.invert(lum)
        low, high = ((115, 125, 142), (255, 255, 255)) if dark else ((15, 23, 35), (110, 120, 135))
        result = ImageOps.colorize(lum, low, high).convert("RGBA")
        result.putalpha(image.getchannel("A"))
    elif plate is not None:
        # Preserve colored branding while giving neutral foregrounds contrast.
        r, g, b = image.convert("RGB").split()
        spread = ImageChops.subtract(ImageChops.lighter(ImageChops.lighter(r, g), b),
                                     ImageChops.darker(ImageChops.darker(r, g), b))
        neutral = spread.point(lambda v: 255 if v < 18 else 0)
        extreme = lum.point(lambda v: 255 if (v < 85 if dark else v > 180) else 0)
        if (dark and classification == "light-plate") or (not dark and classification == "dark-plate"):
            change = ImageChops.multiply(neutral, extreme)
            change = ImageChops.multiply(change, ImageOps.invert(plate))
            inverted = ImageOps.invert(image.convert("RGB")).convert("RGBA")
            inverted.putalpha(image.getchannel("A"))
            result = Image.composite(inverted, result, change)
    material = tile(size, variant, tint)
    if plate is not None:
        material.putalpha(ImageChops.multiply(material.getchannel("A"), image.getchannel("A")))
        result = Image.composite(material, result, plate)
    elif classification == "glyph":
        shape = Image.new("L", image.size)
        ImageDraw.Draw(shape).rounded_rectangle((size*.065, size*.065, size*.935, size*.935),
                                               radius=size*.205, fill=255)
        material.putalpha(ImageChops.multiply(material.getchannel("A"), shape))
        result = Image.alpha_composite(material, result)
    # Unknown backgrounds keep their geometry and alpha; never blindly erase a logo.
    if plate is not None or classification == "glyph":
        edge = Image.new("RGBA", image.size)
        ImageDraw.Draw(edge).rounded_rectangle((size*.067, size*.067, size*.933, size*.933),
                                              radius=size*.20,
                                              outline=(255, 255, 255, 75 if glass else 35),
                                              width=max(1, round(size/192)))
        result = Image.alpha_composite(result, edge)
    return result


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


def render_installer(prepared: tuple, style: str, mode: str, tint: tuple[int, int, int]) -> Image.Image:
    """Use the wizard's approved materials for both previews and installed icons.

    Preserve the original foreground in regular icons. Glass uses that same
    artwork's luminance and alpha, with a tinted relief and translucent plate.
    """
    if style not in {"regular", "glass"} or mode not in {"light", "dark"}:
        raise ValueError("Unknown installer icon material")
    image, shape, _, artwork, _ = prepared
    size = image.width
    if style == "regular":
        if mode == "light" or prepared[2] != "vector-light":
            return image.copy()
        if artwork is None or shape is None:
            return image.copy()
        plate = gradient(size, (52, 52, 54, 255), (12, 12, 14, 255))
        plate.putalpha(shape)
        # One subdued neutral rim replaces the light icon's partial colored rims.
        inset = shape.filter(ImageFilter.MinFilter(3))
        rim = ImageChops.subtract(shape, inset)
        edge = gradient(size, (255, 255, 255, 65), (255, 255, 255, 12))
        edge.putalpha(ImageChops.multiply(rim, edge.getchannel("A")))
        plate = Image.alpha_composite(plate, edge)
        return Image.alpha_composite(plate, dark_foreground(artwork))
    if artwork is None or shape is None:
        # Unclassified artwork keeps its silhouette and interior detail.
        artwork = image
        shape = Image.new("L", image.size)
        ImageDraw.Draw(shape).rounded_rectangle((size*.065, size*.065, size*.935, size*.935),
                                                radius=size*.205, fill=255)
    gray = ImageOps.grayscale(artwork)
    silver = ImageOps.colorize(gray, (60, 82, 101), (247, 252, 255))
    shadow = tuple(round(c*.22) for c in tint)
    middle = tuple(round(c*.8+255*.2) for c in tint)
    relief = ImageOps.colorize(ImageOps.grayscale(silver), black=shadow, white=(248, 252, 255),
                              mid=middle, midpoint=164).convert("RGBA")
    relief.putalpha(artwork.getchannel("A"))
    ramp = Image.linear_gradient("L").resize((size*2, size*2)).rotate(-35)
    ramp = ramp.crop((size//2, size//2, size//2+size, size//2+size))
    stops = [(0, (255, 255, 255, 171)), (107, (*tint, 122)),
             (196, (*tint, 191)), (255, (255, 255, 255, 156))]
    colors = []
    for value in range(256):
        left, right = next((a, b) for a, b in zip(stops, stops[1:]) if a[0] <= value <= b[0])
        t = (value-left[0])/(right[0]-left[0])
        colors.append(tuple(round(a+(b-a)*t) for a,b in zip(left[1], right[1])))
    plate = Image.merge("RGBA", [ramp.point([c[channel] for c in colors]) for channel in range(4)])
    plate.putalpha(ImageChops.multiply(plate.getchannel("A"), shape))
    inset = shape.filter(ImageFilter.MinFilter(max(3, (round(size*.012)//2)*2+1)))
    rim = ImageChops.subtract(shape, inset).filter(ImageFilter.GaussianBlur(size*.002))
    edge = Image.new("RGBA", image.size, "white"); edge.putalpha(rim.point(lambda v: round(v*.72)))
    result = Image.alpha_composite(plate, relief)
    bevel_width = max(3, (round(size*.035)//2)*2+1)
    bevel = ImageChops.subtract(shape, shape.filter(ImageFilter.MinFilter(bevel_width)))
    shine = gradient(size, (255, 255, 255, 220), (195, 225, 255, 90))
    shine.putalpha(ImageChops.multiply(shine.getchannel("A"), bevel))
    result = Image.alpha_composite(Image.alpha_composite(result, shine), edge)
    shadow = Image.new("RGBA", image.size, (20, 35, 60))
    shadow.putalpha(ImageChops.offset(shape, 0, round(size*.025)).filter(
        ImageFilter.GaussianBlur(size*.025)).point(lambda value: round(value*.24)))
    return Image.alpha_composite(shadow, result)
