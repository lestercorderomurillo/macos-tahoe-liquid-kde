"""Rebuild installer icon samples from the same offline renderer as installation."""

import argparse
import json
from pathlib import Path
import tempfile

from PIL import Image

from icon_materials import prepare_source, raster, render_installer
from icon_sources import digest, unpack
from icon_toolset import BASE, ROOT, new_destination
from installer_choices import COLORS

SAMPLES = ("org.kde.dolphin", "firefox", "systemsettings", "org.kde.konsole",
           "org.kde.kate", "gwenview", "org.kde.discover", "vlc")


def build(output):
    output = new_destination(output)
    output.mkdir()
    source = ROOT / "src/offline/icons/MacTahoeLiquidKde-Icons.tar.zst"
    records = {}
    source_hash = digest(source)
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


def build_selectors(output):
    """Render Weather selectors from original bundled layers, without new artwork."""
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / "sources.json"
    records = json.loads(manifest.read_text()) if manifest.exists() else {}
    source = ROOT / "src/offline/icons/MacTahoeLiquidKde-Icons.tar.zst"
    with tempfile.TemporaryDirectory(prefix="weather-selectors-") as temporary:
        extracted = Path(temporary) / "source"
        unpack(source, extracted)
        icon = extracted / BASE / "apps/scalable/indicator-weather.svg"
        prepared = prepare_source(icon, 512)
        for style in ("regular", "dark", "clear", "glass"):
            for mode in ("light", "dark"):
                for color in (COLORS if style == "glass" else ("neutral",)):
                    tint = COLORS.get(color, "#8e8e93")
                    rgb = tuple(int(tint[i:i+2], 16) for i in (1, 3, 5))
                    # The macOS selector uses Weather's neutral dark plate. Keep
                    # its original cloud/sun layers and change only that plate's paint.
                    selector = (*prepared[:2], "vector-light", *prepared[3:]) if style == "dark" else prepared
                    sample_mode = "dark" if style == "dark" else "light" if style == "regular" else mode
                    image = render_installer(selector, "regular" if style == "dark" else style,
                                             sample_mode, rgb)
                    key = f"weather-{style}-{mode}-{color}.png"
                    target = output / key
                    image.resize((192, 192), Image.Resampling.LANCZOS).save(target)
                    checksum = digest(target)
                    filename = target.stem + "-" + checksum[:12] + ".png"
                    target.rename(output / filename)
                    previous = records.get(key, {}).get("file")
                    if previous and previous != filename:
                        (output / previous).unlink(missing_ok=True)
                    records[key] = dict(file=filename, sha256=checksum,
                        source="src/offline/icons/MacTahoeLiquidKde-Icons.tar.zst",
                        source_sha256=digest(source), artwork_sha256=digest(icon),
                        sample="indicator-weather", style=style, mode=mode, tint=tint,
                        generator="src/scripts/installer_preview_assets.py", kind="generated-icon-preview")
    manifest.write_text(json.dumps(records, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--selectors-only", action="store_true")
    args = parser.parse_args()
    (build_selectors if args.selectors_only else build)(args.output)
