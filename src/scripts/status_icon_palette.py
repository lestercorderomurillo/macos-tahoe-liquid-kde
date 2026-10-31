"""Apply KDE palette roles to the bundled status artwork in a staging tree.

SPDX-License-Identifier: GPL-3.0-or-later
Copyright (C) 2026 Lester Cordero Murillo
"""
from __future__ import annotations

from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


SVG = "http://www.w3.org/2000/svg"
FOREGROUND = frozenset({"#363636", "#dedede", "#eff0f1", "#f2f2f2"})
NOTICE = "Status foreground adapted to the KDE palette, 2026-10-30."


def palette_svg(text: str) -> str:
    """Keep geometry and warning colors; recolor only fixed neutral foregrounds."""
    root = ET.fromstring(text, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
    changed = False
    for node in root.iter():
        recolored = False
        for attribute in ("fill", "stroke"):
            if node.get(attribute, "").lower() in FOREGROUND:
                node.set(attribute, "currentColor")
                recolored = True
        style = node.get("style", "")
        updated = re.sub(
            r"\b(fill|stroke)\s*:\s*(#[0-9a-fA-F]{6})(?=\s*(?:;|$))",
            lambda m: f"{m[1]}:currentColor" if m[2].lower() in FOREGROUND else m[0],
            style,
        )
        if updated != style:
            node.set("style", updated)
            recolored = True
        if recolored:
            classes = node.get("class", "").split()
            if "ColorScheme-Text" not in classes:
                classes.append("ColorScheme-Text")
            node.set("class", " ".join(classes))
            # A literal SVG color overrides the palette class on charging bolts.
            if node.get("color", "").lower() in FOREGROUND:
                del node.attrib["color"]
            changed = True
    if not changed:
        return text
    if not any(node.get("id") == "current-color-scheme" for node in root.iter()):
        style = ET.Element(f"{{{SVG}}}style", {"id": "current-color-scheme", "type": "text/css"})
        style.text = ".ColorScheme-Text { color:#363636; }"
        root.insert(0, style)
    root.insert(0, ET.Comment(" " + NOTICE + " "))
    ET.register_namespace("", SVG)
    return ET.tostring(root, encoding="unicode") + "\n"


def apply_status_palette(directory: Path) -> None:
    """Normalize extracted base themes once, including their shared size aliases."""
    directory = directory.resolve()
    visited = set()
    for theme in ("MacTahoeLiquidKde-Icons", "MacTahoeLiquidKde-Icons-dark"):
        for path in sorted((directory / theme / "status").glob("*/*.svg")):
            target = path.resolve()
            if not target.is_relative_to(directory):
                raise ValueError(f"Status icon escapes staging: {path}")
            if target in visited or not target.is_file():
                continue
            visited.add(target)
            text = target.read_text()
            updated = palette_svg(text)
            if updated != text:
                target.write_text(updated)


if __name__ == "__main__":
    apply_status_palette(Path(sys.argv[1]))
