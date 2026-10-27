"""Edition-specific client fills; compositor gradients remain material-owned."""

import gzip
from pathlib import Path
import xml.etree.ElementTree as ET

from theme_switch import default_wallpaper

PLASMA_SURFACES = (
    "dialogs/background.svgz", "dialogs/launcher-search.svgz",
    "widgets/background.svgz", "widgets/translucentbackground.svgz",
    "widgets/tooltip.svgz",
)
_TILES = ("center", "top", "bottom", "left", "right",
          "topleft", "topright", "bottomleft", "bottomright")
_SVG = "http://www.w3.org/2000/svg"
_XLINK = "http://www.w3.org/1999/xlink"


def surface_nodes(root: ET.Element, ids: tuple[str, ...]):
    """Follow tile references without touching masks, shadows or fallbacks."""
    indexed = {node.get("id"): node for node in root.iter() if node.get("id")}
    seen = set()

    def visit(node):
        if node in seen:
            return
        seen.add(node)
        yield node
        reference = node.get(f"{{{_XLINK}}}href", node.get("href", ""))
        if reference.startswith("#") and reference[1:] in indexed:
            yield from visit(indexed[reference[1:]])
        for child in node:
            yield from visit(child)

    for id_ in ids:
        if id_ in indexed:
            yield from visit(indexed[id_])


def set_surface_fill(root: ET.Element, ids: tuple[str, ...], opacity: str,
                     color: str | None = None) -> None:
    for node in surface_nodes(root, ids):
        style = dict(part.split(":", 1) for part in node.get("style", "").split(";") if ":" in part)
        fill = style.get("fill", node.get("fill"))
        alpha = style.get("opacity", node.get("opacity", "1"))
        if fill not in ("#000000", "#ffffff") or float(alpha) not in (.48, .55):
            continue
        if "opacity" in style:
            style["opacity"] = opacity
        else:
            node.set("opacity", opacity)
        if color:
            if "fill" in style:
                style["fill"] = color
            else:
                node.set("fill", color)
        if style:
            node.set("style", ";".join(f"{key}:{value}" for key, value in style.items()))


def _write_svg(path: Path, root: ET.Element) -> None:
    ET.register_namespace("", _SVG)
    ET.register_namespace("xlink", _XLINK)
    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    path.write_bytes(gzip.compress(data, mtime=0) if path.suffix == ".svgz" else data)


def apply_plasma_surface_defaults(theme: Path) -> None:
    """Apply to a staged copy of the bundled theme, never user configuration."""
    if default_wallpaper() != "MacGoldenGate":
        return
    # Plasma popups and tooltips keep the system foreground, just like QMenus.
    # Dark text needs a light client fill even over a black glass backdrop.
    opacity = "0.60" if theme.name.endswith("-Light") else "0.01"
    for name in PLASMA_SURFACES:
        path = theme / name
        root = ET.fromstring(gzip.decompress(path.read_bytes()))
        set_surface_fill(root, _TILES, opacity, "#ffffff")
        if name == "dialogs/background.svgz" and not any(
                node.get("id") == "hint-clear-surface" for node in root):
            ET.SubElement(root, f"{{{_SVG}}}rect", {
                "id": "hint-clear-surface", "width": "1", "height": "1", "opacity": "0",
            })
        _write_svg(path, root)


def apply_kvantum_surface_defaults(path: Path) -> None:
    if default_wallpaper() != "MacGoldenGate":
        return
    root = ET.parse(path).getroot()
    # The shadow frame also references the menu's surface tiles.
    ids = tuple(node.get("id") for node in root.iter()
                if node.get("id", "").startswith(("menu-normal", "menu-shadow")))
    # Native Qt menus retain dark text in light mode. A translucent white
    # client surface keeps it readable above the compositor's dark gradient.
    opacity = "0.60" if path.stem == "mac-tahoe-liquid-kde" else "0.01"
    set_surface_fill(root, ids, opacity, "#ffffff")
    _write_svg(path, root)
