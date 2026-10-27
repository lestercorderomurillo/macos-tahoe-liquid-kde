"""Rebuild installer icon samples from the same offline renderer as installation."""

import argparse
import json
from pathlib import Path
import tempfile

from PIL import Image

from icon_materials import prepare_source, raster, render_installer
from icon_sources import digest, unpack
from icon_toolset import BASE, ROOT, new_destination, installer_dark_sources
from installer_choices import COLORS

SAMPLES = ("org.kde.dolphin", "firefox", "systemsettings", "org.kde.konsole",
           "org.kde.kate", "gwenview", "org.kde.discover", "vlc")


def build(output):
    output = new_destination(output)
    output.mkdir()
    source = ROOT / "src/offline/icons/MacTahoeLiquidKde-Icons.tar.zst"
    records = {}
    source_hash = digest(source)
    dark_sources = installer_dark_sources()
    with tempfile.TemporaryDirectory(prefix="installer-preview-") as temporary:
        extracted = Path(temporary) / "source"
        unpack(source, extracted)
        for index, name in enumerate(SAMPLES):
            icon = extracted / BASE / "apps/scalable" / (name + ".svg")
            prepared = prepare_source(icon, 512)
            regular = prepare_source(icon, 512, clean_rim=True)
            for mode in ("light", "dark"):
                variants = [(f"regular-{mode}-{index}.png", mode, "blue")]
                if index < 4:
                    variants += [(f"glass-{mode}-{color}-{index}.png", "tinted-"+mode, color) for color in COLORS]
                for filename, variant, color in variants:
                    tint = tuple(int(COLORS[color][i:i+2], 16) for i in (1, 3, 5))
                    original = icon
                    if variant == "dark" and digest(icon) in dark_sources:
                        original = dark_sources[digest(icon)]
                        image = raster(original, 512)
                    else:
                        glass = variant.startswith("tinted-")
                        image = render_installer(prepared if glass else regular,
                                                 "glass" if glass else "regular", mode, tint)
                    image = image.resize((256, 256), Image.Resampling.LANCZOS)
                    image.resize((128, 128), Image.Resampling.LANCZOS).save(output / filename)
                    records[filename] = {
                        "source": "src/offline/icons/MacTahoeLiquidKde-Icons.tar.zst",
                        "source_sha256": source_hash, "artwork_sha256": digest(original),
                        "variant": variant, "tint": COLORS[color], "sample": name,
                        "generator": "src/scripts/installer_preview_assets.py",
                        "sha256": digest(output / filename), "kind": "generated-icon-preview",
                    }
    (output / "sources.json").write_text(json.dumps(records, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output)
