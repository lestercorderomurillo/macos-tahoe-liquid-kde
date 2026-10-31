"""Offline icon generation, visual review, integrity checks and reproducible bundles.

SPDX-License-Identifier: GPL-3.0-or-later
Copyright (C) 2026 Lester Cordero Murillo
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable
from time import monotonic
from xml.etree.ElementTree import ParseError
from pathlib import Path

import PIL
from PIL import Image, ImageDraw

from icon_materials import VARIANTS, prepare_source, render, render_installer
from icon_sources import digest, inventory, unpack, validate_links
from interface_icons import INTERFACE_ICONS


ROOT = Path(__file__).resolve().parents[2]
BASE = "MacTahoeLiquidKde-Icons"
PREFIX = "MacTahoeGenerated-"
SCHEMA = 1

# QIcon searches the current theme before its parents, including the
# non-symbolic fallback. KDE also tries each hyphen-separated prefix.
# Keep those menu names in the base theme; generate
# systemsettings and org.kde.discover for application launchers instead.
SYSTEM_MENU_ICONS = frozenset({
    "computer", "preferences", "preferences-system",
    "software", "software-store", "software-store-symbolic",
    *INTERFACE_ICONS,
})


def installer_dark_sources() -> dict[str, Path]:
    """Match reviewed dark artwork by content hash, including all base aliases."""
    directory = ROOT / "src/offline/icons/overrides"
    records = json.loads((directory / "sources.json").read_text())
    result = {}
    for name, record in records.items():
        path = directory / name
        if path.parent != directory or path.is_symlink() or digest(path) != record["sha256"]:
            raise ValueError(f"Invalid installer dark artwork: {name}")
        result[record["source_sha256"]] = path
    return result


def installer_themes(source: Path, output: Path, style: str, tint: str, *,
                     progress: Callable[[int, int], None] | None = None) -> list[str]:
    """Build explicitly selected installer overlays in a fresh staging tree.

    The maintainer CLI still never changes installed themes or defaults.
    Application aliases share artwork; interface icons inherit the base pack.
    """
    from utils import check_cancelled
    if style not in ("regular", "glass"):
        raise ValueError("Unknown installer icon style")
    rgb = color(tint)
    output = new_destination(output)
    output.mkdir()
    names = [f"{BASE}-{style.title()}-{mode.title()}" for mode in ("light", "dark")]
    for name, mode in zip(names, ("light", "dark")):
        target = output / name
        (target / "apps/256").mkdir(parents=True)
        (target / "index.theme").write_text(
            f"[Icon Theme]\nName={name}\nInherits={BASE}{'-dark' if mode == 'dark' else ''},hicolor,breeze\n"
            "FollowsColorScheme=true\nDirectories=apps/256\n\n[apps/256]\nSize=256\nType=Scalable\nMinSize=32\nMaxSize=512\nContext=Applications\n")
        (target / "GENERATION-NOTICE.txt").write_text(
            "Generated from the bundled MacTahoe icon archive by icon-toolset.\n"
            "Original artwork retains its notices. Static material, not live refraction.\n"
            "Transformations: Copyright (C) 2026 Lester Cordero Murillo; GPL-3.0-or-later.\n")
        for notice in ("NOTICE", "LICENSING.md", "THIRD_PARTY_NOTICES.md"):
            shutil.copyfile(ROOT / notice, target / notice)
    dark_sources = installer_dark_sources() if style == "regular" else {}
    # Extensions disappear in the PNG output: Grsync.SVG and Grsync.svg
    # must not write the same file twice. Prefer SVG, then lowercase suffixes.
    entries = {}
    for path in sorted((source / BASE / "apps/scalable").iterdir(), key=lambda p: (
            p.suffix.lower() == ".svg", p.suffix == p.suffix.lower(), p.name)):
        if (path.suffix.lower() in (".svg", ".png") and path.is_file()
                and path.stem not in SYSTEM_MENU_ICONS):
            entries[path.stem] = path
    seen = {}
    records = {}
    total = len(entries)
    last_report = monotonic()
    if progress:
        progress(0, total)
    for completed, (_, path) in enumerate(sorted(entries.items()), 1):
        check_cancelled()
        checksum = digest(path)
        if checksum in seen:
            for name in names:
                (output / name / "apps/256" / (path.stem + ".png")).symlink_to(seen[checksum] + ".png")
        else:
            prepared = prepare_source(path, 512, clean_rim=style == "regular")
            for name, mode in zip(names, ("light", "dark")):
                if mode == "dark" and checksum in dark_sources:
                    from icon_materials import raster
                    result = raster(dark_sources[checksum], 512)
                else:
                    result = render_installer(prepared, style, mode, rgb)
                result.resize((256, 256), Image.Resampling.LANCZOS).save(
                    output / name / "apps/256" / (path.stem + ".png"))
            seen[checksum] = path.stem
        records[path.name] = checksum
        if progress and (completed == total or monotonic() - last_report >= 5):
            progress(completed, total)
            last_report = monotonic()
    if not records:
        raise ValueError("No application artwork found")
    for name in names:
        write_json(output / name / "generation.json", {"style": style, "tint": tint, "sources": records,
            "dark_artwork": {path.name: digest(path) for path in dark_sources.values()}})
    return names


def valid_icon_name(name: str) -> bool:
    return isinstance(name, str) and bool(re.fullmatch(r"[^\x00-\x1f/\\]+", name)) and name not in {".", ".."}


def theme_name(variant: str) -> str:
    return PREFIX + "-".join(word.capitalize() for word in variant.split("-"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def color(value: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise argparse.ArgumentTypeError("Tint must be #RRGGBB")
    return tuple(int(value[i:i+2], 16) for i in (1, 3, 5))


def new_destination(path: Path) -> Path:
    path = path.absolute()
    if path.exists() or path.is_symlink():
        raise ValueError(f"Output already exists: {path}; choose a fresh directory or filename")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_overrides(path: Path | None) -> dict:
    if path is None:
        return {}
    entries = json.loads(path.read_text())
    if not isinstance(entries, dict):
        raise ValueError("Overrides must map icon names to artwork descriptions")
    result = {}
    for name, entry in entries.items():
        if not valid_icon_name(name):
            raise ValueError(f"Invalid override icon name: {name}")
        if not isinstance(entry, dict) or set(entry) != {"source", "kind", "notice"}:
            raise ValueError(f"Override {name} requires source, kind and notice")
        if entry["kind"] not in {"glyph", "icon"}:
            raise ValueError(f"Override {name}: kind must be glyph or icon")
        source = (path.parent / entry["source"]).resolve(strict=True)
        notice = (path.parent / entry["notice"]).resolve(strict=True)
        if source.suffix.lower() not in {".svg", ".png"} or not notice.is_file():
            raise ValueError(f"Override {name}: use SVG/PNG artwork and a notice file")
        result[name] = {"source": source, "notice": notice, "kind": entry["kind"]}
    return result


def index_text(variant: str, sizes: list[int]) -> str:
    dark = variant in {"dark", "black", "clear-dark", "tinted-dark"}
    fallback = BASE + ("-dark" if dark else "")
    text = (f"[Icon Theme]\nName={theme_name(variant)}\n"
            "Comment=Generated application icons; small interface icons inherit the base\n"
            f"Inherits={fallback},hicolor,breeze\n"
            "FollowsColorScheme=true\n"
            f"Directories={','.join('apps/'+str(size) for size in sizes)}\n")
    for size in sizes:
        text += f"\n[apps/{size}]\nSize={size}\nType=Fixed\nContext=Applications\n"
    return text


def build(args) -> Path:
    output = new_destination(args.output)
    variants = list(dict.fromkeys(args.variants))
    sizes = sorted(set(args.sizes))
    overrides = load_overrides(args.overrides)
    if not args.source.is_file():
        raise ValueError(f"Source archive not found: {args.source}")
    # A failed build leaves no partial deliverable at the requested destination.
    with tempfile.TemporaryDirectory(prefix="icon-toolset-", dir=output.parent) as temp:
        temp = Path(temp)
        source = temp / "source"
        unpack(args.source.resolve(), source)
        from interface_icons import apply_interface_icons
        apply_interface_icons(source)
        for name in (BASE, BASE + "-dark"):
            if not (source / name / "index.theme").is_file():
                raise ValueError(f"Source archive is missing {name}/index.theme")
        apps = source / BASE / "apps/scalable"
        entries = {p.stem: p for p in sorted(apps.iterdir())
                   if p.suffix.lower() in {".svg", ".png"} and p.is_file()}
        if not entries:
            raise ValueError("Source has no scalable application icons")
        entries.update({name: entry["source"] for name, entry in overrides.items()})
        entries = {name: path for name, path in entries.items() if name not in SYSTEM_MENU_ICONS}
        if any(not valid_icon_name(name) for name in entries):
            raise ValueError("Source contains an unsafe icon filename")
        if args.icons:
            missing = set(args.icons) - entries.keys()
            if missing:
                raise ValueError("Unknown icon names: " + ", ".join(sorted(missing)))
            entries = {name: entries[name] for name in sorted(set(args.icons))}
        bundle = temp / "bundle"
        themes = bundle / "themes"
        themes.mkdir(parents=True)
        for name in (BASE, BASE + "-dark"):
            shutil.copytree(source / name, themes / name, symlinks=True)
        # Keep source notices and provenance gaps visible, including the marked
        # status palette adaptation. This does not resolve third-party ownership.
        notices = bundle / "notices"
        notices.mkdir()
        for name in ("LICENSE", "NOTICE", "LICENSING.md", "THIRD_PARTY_NOTICES.md"):
            shutil.copyfile(ROOT / name, notices / name)
        for variant in variants:
            dest = themes / theme_name(variant)
            dest.mkdir()
            (dest / "index.theme").write_text(index_text(variant, sizes))
            (dest / "GENERATION-NOTICE.txt").write_text(
                "Generated by Tahoe icon-toolset. Original artwork remains subject to its "
                "own notices. See ../../notices and ../../manifest.json.\n"
                "Material transformations: Copyright (C) 2026 Lester Cordero Murillo; "
                "GPL-3.0-or-later. This is a static glass appearance, not live refraction.\n")
            for size in sizes:
                (dest / "apps" / str(size)).mkdir(parents=True)
        records = {}
        cache = {}
        size = max(sizes) * 2
        for number, (name, path) in enumerate(sorted(entries.items()), 1):
            override = overrides.get(name)
            kind = override["kind"] if override else "icon"
            checksum = digest(path)
            key = (checksum, kind)
            if key in cache:
                original, classification, removed_images = cache[key]
                for variant in variants:
                    for width in sizes:
                        target = themes / theme_name(variant) / "apps" / str(width) / f"{name}.png"
                        target.symlink_to(f"{original}.png")
            else:
                prepared = prepare_source(path, size, glyph=kind == "glyph")
                classification = prepared[2]
                removed_images = prepared[4]
                if removed_images:
                    print(f"{name}: omitted {removed_images} external image layer(s); recorded in manifest", flush=True)
                for variant in variants:
                    generated = render(prepared, variant, args.tint)
                    for width in sizes:
                        target = themes / theme_name(variant) / "apps" / str(width) / f"{name}.png"
                        generated.resize((width, width), Image.Resampling.LANCZOS).save(target)
                cache[key] = (name, classification, removed_images)
            record = {"source_sha256": checksum, "classification": classification, "kind": kind,
                      "removed_external_images": removed_images}
            if override:
                target = bundle / "overrides" / name
                target.mkdir(parents=True)
                shutil.copyfile(path, target / ("artwork" + path.suffix.lower()))
                shutil.copyfile(override["notice"], target / "NOTICE")
                record["source"] = str((target / ("artwork" + path.suffix.lower())).relative_to(bundle))
            else:
                record["source"] = "themes/" + path.relative_to(source).as_posix()
            records[name] = record
            if number % 100 == 0:
                print(f"Generated {number}/{len(entries)} names ({len(cache)} unique artworks)", flush=True)
        manifest = {
            "schema": SCHEMA,
            "source_archive_sha256": digest(args.source),
            "variants": variants, "sizes": sizes, "tint": "#%02x%02x%02x" % args.tint,
            "partial": bool(args.icons), "icons": records,
            "generator": {name: digest(Path(__file__).with_name(name)) for name in
                          ("icon_toolset.py", "icon_materials.py", "icon_sources.py")},
            "renderer": {"pillow": PIL.__version__, "librsvg": subprocess.check_output(
                ["rsvg-convert", "--version"], text=True).strip()},
            "files": inventory(bundle),
        }
        write_json(bundle / "manifest.json", manifest)
        verify(bundle)
        if output.exists():
            raise ValueError(f"Output appeared during build: {output}")
        bundle.rename(output)
    print(f"Built {len(records)} icon names in {len(variants)} appearances: {output}")
    counts = {}
    for entry in records.values():
        counts[entry["classification"]] = counts.get(entry["classification"], 0) + 1
    print("Coverage: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    return output


def verify(bundle: Path) -> dict:
    if bundle.is_symlink() or (bundle / "manifest.json").is_symlink():
        raise ValueError("Bundle and manifest must not be symlinks")
    manifest = json.loads((bundle / "manifest.json").read_text())
    if manifest.get("schema") != SCHEMA:
        raise ValueError("Unsupported icon manifest schema")
    variants, sizes = manifest["variants"], manifest["sizes"]
    if not variants or any(v not in VARIANTS for v in variants):
        raise ValueError("Invalid manifest variants")
    if not sizes or any(type(s) is not int or s not in {32, 64, 128, 256} for s in sizes):
        raise ValueError("Invalid manifest sizes")
    validate_links(bundle)
    actual = inventory(bundle)
    actual.pop("manifest.json", None)
    if actual != manifest["files"]:
        changed = sorted(k for k in actual.keys() | manifest["files"].keys()
                         if actual.get(k) != manifest["files"].get(k))
        raise ValueError("Bundle integrity mismatch: " + ", ".join(changed[:8]))
    sources = {}
    for name, record in manifest["icons"].items():
        path = (bundle / record["source"]).resolve(strict=True)
        if not path.is_relative_to(bundle.resolve()):
            raise ValueError(f"Source escapes the bundle: {name}")
        if path not in sources:
            sources[path] = digest(path)
        if sources[path] != record["source_sha256"]:
            raise ValueError(f"Source provenance mismatch: {name}")
    for variant in variants:
        theme = bundle / "themes" / theme_name(variant)
        if (theme / "index.theme").read_text() != index_text(variant, sizes):
            raise ValueError(f"Invalid theme inheritance or size entries: {variant}")
        for name in manifest["icons"]:
            if not valid_icon_name(name):
                raise ValueError(f"Invalid icon name: {name}")
            for size in sizes:
                path = theme / "apps" / str(size) / f"{name}.png"
                with Image.open(path) as image:
                    if image.size != (size, size) or image.mode != "RGBA":
                        raise ValueError(f"Invalid generated image: {path}")
                    image.verify()
    return manifest


def preview(args) -> None:
    manifest = verify(args.bundle)
    names = args.icons or list(manifest["icons"])[:8]
    if len(names) > 24 or not names or set(names) - manifest["icons"].keys():
        raise ValueError("Preview requires 1–24 icon names present in the bundle")
    if args.output.resolve().is_relative_to(args.bundle.resolve()):
        raise ValueError("Preview output must be outside the verified bundle")
    output = new_destination(args.output)
    cell, label, header = 112, 145, 40
    variants = manifest["variants"]
    canvas = Image.new("RGB", (label + cell * len(names), header + 2 * cell * len(variants)))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, canvas.width, header), fill="#353940")
    for i, name in enumerate(names):
        draw.text((label + i*cell+4, 12), name[:17], fill="white")
    for row, variant in enumerate(variants):
        for side, background in enumerate(("#eeeeef", "#202126")):
            y = header + (row*2+side)*cell
            draw.rectangle((0, y, canvas.width, y+cell), fill=background)
            ink = "#202126" if side == 0 else "#eeeeef"
            draw.text((8, y+25), variant, fill=ink)
            draw.text((8, y+45), "light backdrop" if side == 0 else "dark backdrop", fill=ink)
            for col, name in enumerate(names):
                path = args.bundle / "themes" / theme_name(variant) / "apps" / str(max(manifest["sizes"])) / f"{name}.png"
                with Image.open(path) as image:
                    icon = image.resize((80, 80), Image.Resampling.LANCZOS)
                    canvas.paste(icon, (label+col*cell+16, y+16), icon)
    canvas.save(output)
    print(f"Wrote synthetic artwork preview (not a desktop screenshot): {output}")


def pack(args) -> None:
    manifest = verify(args.bundle)
    if manifest["partial"] and not args.allow_partial:
        raise ValueError("Sample builds require --allow-partial to package")
    if args.output.resolve().is_relative_to(args.bundle.resolve()):
        raise ValueError("Pack output must be outside the verified bundle")
    output = new_destination(args.output)
    if not output.name.endswith(".tar.gz"):
        raise ValueError("Pack output must end with .tar.gz")
    with tempfile.TemporaryFile() as temporary:
        with gzip.GzipFile(filename="", mode="wb", fileobj=temporary, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for path in sorted(args.bundle.rglob("*")):
                    info = archive.gettarinfo(str(path), arcname="icon-bundle/" + path.relative_to(args.bundle).as_posix())
                    info.uid = info.gid = info.mtime = 0
                    info.uname = info.gname = ""
                    info.pax_headers = {}
                    info.mode = 0o755 if info.isdir() else (0o777 if info.issym() else 0o644)
                    if info.isfile():
                        with path.open("rb") as stream:
                            archive.addfile(info, stream)
                    else:
                        archive.addfile(info)
        temporary.seek(0)
        with output.open("xb") as stream:
            shutil.copyfileobj(temporary, stream)
    print(f"{digest(output)}  {output}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build", help="Generate themes from the bundled base, offline")
    build_parser.add_argument("--source", type=Path, default=ROOT / "src/offline/icons" / (BASE + ".tar.zst"))
    build_parser.add_argument("--output", type=Path, required=True)
    build_parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    build_parser.add_argument("--sizes", nargs="+", type=int, choices=(32, 64, 128, 256), default=[64, 128, 256])
    build_parser.add_argument("--tint", type=color, default=color("#6796d2"))
    build_parser.add_argument("--icons", nargs="+", help="Build only named icons for review; marks the bundle partial")
    build_parser.add_argument("--overrides", type=Path, help="JSON map of local glyph/icon artwork and notices")
    verify_parser = commands.add_parser("verify", help="Check hashes, aliases, themes and generated image sizes")
    verify_parser.add_argument("bundle", type=Path)
    preview_parser = commands.add_parser("preview", help="Render an artwork contact sheet on light/dark backdrops")
    preview_parser.add_argument("bundle", type=Path)
    preview_parser.add_argument("--output", type=Path, required=True)
    preview_parser.add_argument("--icons", nargs="+")
    pack_parser = commands.add_parser("pack", help="Create a reproducible tar.gz with provenance and original base")
    pack_parser.add_argument("bundle", type=Path)
    pack_parser.add_argument("--output", type=Path, required=True)
    pack_parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            build(args)
        elif args.command == "verify":
            manifest = verify(args.bundle)
            print(f"Verified {len(manifest['icons'])} icon names in {len(manifest['variants'])} appearances")
        elif args.command == "preview":
            preview(args)
        else:
            pack(args)
    except (ValueError, OSError, KeyError, ParseError, subprocess.SubprocessError) as exc:
        print(f"icon-toolset: {exc}", file=sys.stderr)
        return 1
    return 0
