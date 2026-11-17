"""Offline generation, artwork preservation and bundle boundary regressions."""
import io
import json
import shutil
import sys
import tarfile
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/scripts"))
from icon_materials import prepare_source, render, svg_input, validate_svg
from icon_sources import digest, unpack
from icon_toolset import BASE, color, main, theme_name, verify


ARTWORK = b'''<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">
<rect x="4" y="4" width="56" height="56" rx="13" fill="#f8f8f8"/>
<circle cx="32" cy="32" r="12" fill="#f05020"/>
<circle cx="32" cy="32" r="5" fill="#ffffff"/>
</svg>'''


@pytest.fixture
def source(tmp_path):
    archive = tmp_path / "base.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name, data in [
            (BASE + "/index.theme", b"[Icon Theme]\nName=Base\n"),
            (BASE + "-dark/index.theme", b"[Icon Theme]\nName=Dark\n"),
            (BASE + "/COPYING", b"Original asset notice\n"),
            (BASE + "/apps/scalable/demo.svg", ARTWORK),
        ]:
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            tar.addfile(entry, io.BytesIO(data))
        alias = tarfile.TarInfo(BASE + "/apps/scalable/org.example.Demo.svg")
        alias.type = tarfile.SYMTYPE
        alias.linkname = "demo.svg"
        tar.addfile(alias)
    return archive


@pytest.fixture
def built(source, tmp_path):
    if not shutil.which("rsvg-convert"):
        pytest.skip("rsvg-convert is required for material rendering")
    output = tmp_path / "bundle"
    assert main(["build", "--source", str(source), "--output", str(output), "--sizes", "64"]) == 0
    return output


def test_build_preserves_base_and_aliases_and_verifies(built):
    manifest = verify(built)
    assert len(manifest["variants"]) == 8
    assert manifest["icons"]["demo"]["classification"] == "vector-light"
    assert (built / "themes" / BASE / "COPYING").read_bytes() == b"Original asset notice\n"
    for variant in manifest["variants"]:
        path = built / "themes" / theme_name(variant) / "apps/64/org.example.Demo.png"
        assert path.is_symlink()
        assert path.resolve().name == "demo.png"


def test_materials_preserve_color_detail_and_glass_alpha(built):
    def icon(variant):
        return Image.open(built / "themes" / theme_name(variant) / "apps/64/demo.png").convert("RGBA")
    light, dark, glass = icon("light"), icon("dark"), icon("clear-dark")
    # Neutral tile changes, saturated logo keeps its identity and white inset remains white.
    assert light.getpixel((32, 9))[0] > 220
    assert dark.getpixel((32, 9))[0] < 70
    assert light.getpixel((32, 32))[:3] == (255, 255, 255)
    for image in (light, dark):
        red = image.getpixel((32, 24))
        assert red[0] > red[1] * 2
    assert 0 < glass.getpixel((32, 9))[3] < 180
    assert glass.getpixel((32, 24))[3] > 240
    assert glass.getpixel((0, 0))[3] < 8
    assert icon("black").getpixel((32, 24))[:3] != icon("black").getpixel((32, 32))[:3]


@pytest.mark.parametrize("background", ["#5865f2", "#1db954", "url(#brand)"])
def test_regular_dark_keeps_colored_brand_plates(tmp_path, background):
    from icon_materials import render_installer
    if not shutil.which("rsvg-convert"):
        pytest.skip("rsvg-convert is required for material rendering")
    source = tmp_path / "brand.svg"
    source.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">
    <defs><linearGradient id="brand" x2="0" y2="1">
      <stop stop-color="#ffffff"/><stop offset=".15" stop-color="#ffffff"/>
      <stop offset=".5" stop-color="#5865f2"/><stop offset="1" stop-color="#5865f2"/>
    </linearGradient></defs>
    <rect x="4" y="4" width="56" height="56" rx="13" fill="{background}"/>
    <circle cx="32" cy="32" r="12" fill="white"/></svg>''')
    prepared = prepare_source(source, 64, clean_rim=True)
    assert prepared[2] == "vector-colored"
    dark = render_installer(prepared, "regular", "dark", (0, 122, 255))
    assert dark.tobytes() == prepared[0].tobytes()


def test_regular_dark_keeps_unclassified_raster_artwork(tmp_path):
    from icon_materials import render_installer
    source = tmp_path / "brand.png"
    Image.new("RGBA", (64, 64), "#5865f2").save(source)
    prepared = prepare_source(source, 64)
    assert render_installer(prepared, "regular", "dark", (0, 122, 255)).tobytes() == prepared[0].tobytes()


def test_regular_dark_preserves_white_negative_space_between_brand_panels(tmp_path):
    from icon_materials import render_installer
    if not shutil.which("rsvg-convert"):
        pytest.skip("rsvg-convert is required for material rendering")
    source = tmp_path / "split-brand.svg"
    source.write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">
    <rect x="4" y="4" width="56" height="56" rx="13" fill="white"/>
    <path d="M17 4 H26 V60 H17 Q4 60 4 47 V17 Q4 4 17 4" fill="#ff9500"/>
    <path d="M47 4 H38 V60 H47 Q60 60 60 47 V17 Q60 4 47 4" fill="#293a78"/>
    </svg>''')
    prepared = prepare_source(source, 128, clean_rim=True)
    assert prepared[2] == "vector-colored"
    assert render_installer(prepared, "regular", "dark", (0, 122, 255)).tobytes() == prepared[0].tobytes()


def test_dark_foreground_lifts_black_glyph_but_keeps_brand_and_enclosed_details():
    from PIL import ImageDraw
    from icon_materials import dark_foreground
    artwork = Image.new("RGBA", (128, 128))
    draw = ImageDraw.Draw(artwork)
    draw.rectangle((12, 20, 40, 90), fill="#151515")
    draw.ellipse((65, 20, 115, 70), fill="#f05020")
    draw.ellipse((80, 35, 100, 55), fill="#151515")
    result = dark_foreground(artwork)
    assert result.getpixel((25, 45))[0] > 170
    assert result.getpixel((70, 45)) == artwork.getpixel((70, 45))
    assert result.getpixel((90, 45)) == artwork.getpixel((90, 45))
    assert result.getchannel("A").tobytes() == artwork.getchannel("A").tobytes()


def test_dark_foreground_preserves_connected_illustration_and_smooth_glyph_shading():
    from PIL import ImageDraw
    from icon_materials import dark_foreground
    artwork = Image.new("RGBA", (128, 128))
    draw = ImageDraw.Draw(artwork)
    draw.ellipse((65, 20, 115, 90), fill="#f05020", outline="#151515", width=5)
    for y in range(20, 100):
        value = 40 + y
        draw.line((12, y, 40, y), fill=(value, value, value, 255))
    result = dark_foreground(artwork)
    assert result.crop((60, 0, 128, 128)).tobytes() == artwork.crop((60, 0, 128, 128)).tobytes()
    values = [result.getpixel((25, y))[0] for y in range(20, 100)]
    assert min(values) > 170
    assert max(abs(a-b) for a, b in zip(values, values[1:])) <= 1


def test_installer_glass_tint_changes_artwork_and_preserves_aliases(source, tmp_path):
    from icon_toolset import installer_themes
    staging = tmp_path / "source"
    unpack(source, staging)
    (staging / BASE / "apps/scalable/system-file-manager.svg").symlink_to("demo.svg")
    (staging / BASE / "apps/scalable/view-app-grid.svg").symlink_to("demo.svg")
    places = staging / BASE / "places/scalable"
    places.mkdir(parents=True)
    for name, shape in (("user-trash", '<rect x="30" y="20" width="60" height="90"/>'),
                        ("user-trash-full", '<circle cx="64" cy="64" r="45"/>')):
        (places / (name + ".svg")).write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
            + shape + '</svg>')
    blue, green = tmp_path / "blue", tmp_path / "green"
    names = installer_themes(staging, blue, "glass", "#007aff")
    installer_themes(staging, green, "glass", "#28cd41")
    for name in names:
        first = blue / name / "apps/256/demo.png"
        second = green / name / "apps/256/demo.png"
        assert digest(first) != digest(second)
        assert (blue / name / "apps/256/org.example.Demo.png").resolve() == first
        assert (blue / name / "THIRD_PARTY_NOTICES.md").is_file()
        assert json.loads((blue / name / "generation.json").read_text())["tint"] == "#007aff"
        image = Image.open(first).convert("RGBA")
        assert image.getpixel((0, 0))[3] < 8
        assert image.getpixel((128, 36))[3] == 255  # Tinted preserves original coverage.
        for icon in ("view-app-grid", "user-trash", "user-trash-full"):
            rendered = blue / name / "apps/256" / (icon + ".png")
            assert Image.open(rendered).getbbox()
            assert digest(rendered) != digest(green / name / "apps/256" / rendered.name)
        assert digest(blue / name / "apps/256/user-trash.png") != digest(
            blue / name / "apps/256/user-trash-full.png")


@pytest.mark.parametrize("style", ["regular", "glass"])
def test_installer_duplicate_extensions_produce_one_icon_per_name(source, tmp_path, style, monkeypatch):
    from icon_toolset import installer_themes
    from itertools import count
    ticks = count(0, 6)
    monkeypatch.setattr("icon_toolset.monotonic", lambda: next(ticks))
    staging = tmp_path / "source"
    unpack(source, staging)
    apps = staging / BASE / "apps/scalable"
    # These two differently cased aliases coexist in the bundled archive.
    for name in ("FreeFileSync.svg", "Grsync.SVG", "Grsync.svg", "system-file-manager.svg"):
        (apps / name).symlink_to("demo.svg")
    # Prefer vector artwork when a raster source also has the same output name.
    Image.new("RGBA", (64, 64), "red").save(apps / "Grsync.png")
    before = {p.name: digest(p) for p in apps.iterdir()}
    outputs = [tmp_path / "first", tmp_path / "reinstall"]
    for output in outputs:
        updates = []
        names = installer_themes(staging, output, style, "#007aff",
                                 progress=lambda done, total: updates.append((done, total)))
        assert updates == [(done, 5) for done in range(6)]
        for name in names:
            generated = output / name / "apps/256"
            canonical = generated / "FreeFileSync.png"
            assert not canonical.is_symlink()
            assert (generated / "Grsync.png").resolve(strict=True) == canonical
            assert {p.name for p in generated.iterdir()} == {
                "FreeFileSync.png", "Grsync.png", "demo.png",
                "org.example.Demo.png", "system-file-manager.png",
            }
            records = json.loads((output / name / "generation.json").read_text())["sources"]
            assert records["Grsync.svg"] == before["Grsync.svg"]
            assert "Grsync.SVG" not in records and "Grsync.png" not in records
    assert {p.name: digest(p) for p in apps.iterdir()} == before
    from icon_sources import inventory
    assert inventory(outputs[0]) == inventory(outputs[1])



def test_maintainer_build_keeps_reserved_menu_aliases_in_base(source, tmp_path):
    staging = tmp_path / "source"
    unpack(source, staging)
    apps = staging / BASE / "apps/scalable"
    reserved = ("computer", "preferences", "preferences-system",
                "software", "software-store", "software-store-symbolic")
    for name in (*reserved, "systemsettings", "org.kde.discover"):
        (apps / f"{name}.svg").symlink_to("demo.svg")
    archive = tmp_path / "menu-base.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in (BASE, BASE + "-dark"):
            tar.add(staging / name, arcname=name)
    output = tmp_path / "bundle"
    assert main(["build", "--source", str(archive), "--output", str(output),
                 "--sizes", "32", "--variants", "dark"]) == 0
    manifest = verify(output)
    assert {"systemsettings", "org.kde.discover"} <= manifest["icons"].keys()
    for name in reserved:
        assert name not in manifest["icons"]
        assert (output / "themes" / BASE / "apps/scalable" / f"{name}.svg").read_bytes() == ARTWORK

def test_verify_rejects_changes_extra_files_and_escaping_links(built, tmp_path):
    extra = built / "unexpected"
    extra.write_text("tamper")
    with pytest.raises(ValueError, match="integrity"):
        verify(built)
    extra.unlink()
    extra.symlink_to(tmp_path)
    with pytest.raises(ValueError, match="escapes"):
        verify(built)


def test_every_alias_uses_original_geometry_in_both_regular_modes(tmp_path):
    from icon_materials import raster
    from icon_toolset import ROOT, installer_themes
    manifest = json.loads((ROOT / 'src/offline/icons/overrides/sources.json').read_text())
    extracted = tmp_path / 'archive'
    unpack(ROOT / 'src/offline/icons/MacTahoeLiquidKde-Icons.tar.zst', extracted)
    source = tmp_path / 'selected'
    apps = source / BASE / 'apps/scalable'
    apps.mkdir(parents=True)
    for index, entry in enumerate(manifest.values()):
        original = extracted / entry['source'].split(':', 1)[1]
        assert digest(original) == entry['source_sha256']
        (apps / f'app-{index}.svg').write_bytes(original.read_bytes())
        (apps / f'alias-{index}.svg').symlink_to(f'app-{index}.svg')
    names = installer_themes(source, tmp_path / 'generated', 'regular', '#007aff')
    for index in range(len(manifest)):
        original = apps / f'app-{index}.svg'
        for name in names:
            generated = tmp_path / 'generated' / name / 'apps/256'
            assert (generated / f'alias-{index}.png').resolve() == (generated / f'app-{index}.png').resolve()
            expected = raster(original, 512).resize((256, 256), Image.Resampling.LANCZOS)
            actual = Image.open(generated / f'app-{index}.png').convert('RGBA')
            assert actual.getchannel('A').tobytes() == expected.getchannel('A').tobytes()
            if name.endswith('-Light'):
                assert actual.tobytes() == expected.tobytes()


def test_regular_dark_removes_partial_colored_rim_without_losing_foreground(tmp_path):
    path = tmp_path / 'partial-rim.svg'
    path.write_bytes(ARTWORK.replace(b'</svg>', b'<path d="M4 32 V17 A13 13 0 0 1 17 4 H47 A13 13 0 0 1 60 17" fill="none" stroke="#00ffff" stroke-width="2"/></svg>'))
    old = prepare_source(path, 256)
    cleaned = prepare_source(path, 256, clean_rim=True)
    assert old[0].tobytes() == cleaned[0].tobytes()
    assert old[3].getpixel((128, 16))[3] > 0
    assert cleaned[3].getpixel((128, 16))[3] == 0
    assert old[3].crop((80, 80, 176, 176)).tobytes() == cleaned[3].crop((80, 80, 176, 176)).tobytes()


def test_pack_is_reproducible_and_sample_requires_opt_in(built, tmp_path):
    first, second = tmp_path / "first.tar.gz", tmp_path / "second.tar.gz"
    assert main(["pack", str(built), "--output", str(first)]) == 0
    assert main(["pack", str(built), "--output", str(second)]) == 0
    assert digest(first) == digest(second)
    path = built / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["partial"] = True
    path.write_text(json.dumps(manifest))
    assert main(["pack", str(built), "--output", str(tmp_path / "sample.tar.gz")]) == 1
    assert main(["pack", str(built), "--output", str(tmp_path / "sample.tar.gz"), "--allow-partial"]) == 0


def test_build_is_reproducible_and_never_overwrites(source, built, tmp_path):
    second = tmp_path / "second"
    assert main(["build", "--source", str(source), "--output", str(second), "--sizes", "64"]) == 0
    assert (built / "manifest.json").read_bytes() == (second / "manifest.json").read_bytes()
    before = digest(built / "manifest.json")
    assert main(["build", "--source", str(source), "--output", str(built)]) == 1
    assert digest(built / "manifest.json") == before


@pytest.mark.parametrize("name,target,kind", [
    ("../outside", None, "file"), ("/absolute", None, "file"),
    ("theme/escape", "../../outside", "link"),
    ("theme/escape", "/etc/passwd", "link"),
    ("theme/loop", "loop", "link"),
    ("theme/pipe", None, "fifo"),
])
def test_archive_boundaries(tmp_path, name, target, kind):
    archive = tmp_path / "unsafe.tar"
    with tarfile.open(archive, "w") as tar:
        member = tarfile.TarInfo(name)
        if kind == "link":
            member.type, member.linkname = tarfile.SYMTYPE, target
        elif kind == "fifo":
            member.type = tarfile.FIFOTYPE
        tar.addfile(member)
    with pytest.raises(ValueError):
        unpack(archive, tmp_path / "out")
    assert not (tmp_path.parent / "outside").exists()


def test_archive_link_parent_is_rejected_before_extraction(tmp_path):
    archive = tmp_path / "unsafe.tar"
    with tarfile.open(archive, "w") as tar:
        link = tarfile.TarInfo("theme/link")
        link.type, link.linkname = tarfile.SYMTYPE, "target"
        tar.addfile(link)
        tar.addfile(tarfile.TarInfo("theme/link/child"))
    with pytest.raises(ValueError, match="non-directory"):
        unpack(archive, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("body", [
    '<image href="file:///etc/passwd"/>', '<image href="https://example.com/icon.png"/>',
    '<rect fill="url(https://example.com/a)"/>', '<style>@import "remote.css";</style>',
    '<script>alert(1)</script>', '<foreignObject/>',
])
def test_svg_external_resources_rejected(body):
    with pytest.raises(ValueError):
        validate_svg(('<svg xmlns="http://www.w3.org/2000/svg">'+body+'</svg>').encode())


def test_override_adds_missing_glyph_and_carries_notice(source, tmp_path):
    if not shutil.which("rsvg-convert"):
        pytest.skip("rsvg-convert required")
    (tmp_path / "glyph.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><circle cx="32" cy="32" r="20" fill="red"/></svg>')
    (tmp_path / "NOTICE").write_text("Local fixture artwork")
    overrides = tmp_path / "overrides.json"
    overrides.write_text(json.dumps({"new-app": {"source": "glyph.svg", "kind": "glyph", "notice": "NOTICE"}}))
    output = tmp_path / "generated"
    assert main(["build", "--source", str(source), "--output", str(output), "--overrides", str(overrides),
                 "--icons", "new-app", "--sizes", "64"]) == 0
    manifest = verify(output)
    assert manifest["partial"]
    assert manifest["icons"]["new-app"]["classification"] == "glyph"
    assert (output / "overrides/new-app/NOTICE").read_text() == "Local fixture artwork"
    assert main(["preview", str(output), "--output", str(tmp_path / "preview.png")]) == 0
    assert (tmp_path / "preview.png").is_file()


@pytest.mark.parametrize("tint", ["#000000", "#ffffff", "#ff0000", "#00ff00", "#0000ff", "#fF7a18", "#123456"])
def test_arbitrary_rgb_tints_preserve_glyph_and_original_coverage(tmp_path, tint):
    if not shutil.which("rsvg-convert"):
        pytest.skip("rsvg-convert required")
    path = tmp_path / "demo.svg"
    path.write_bytes(ARTWORK)
    prepared = prepare_source(path, 64)
    for variant in ("tinted-light", "tinted-dark"):
        image = render(prepared, variant, color(tint))
        assert image.getchannel("A").tobytes() == prepared[0].getchannel("A").tobytes()
        assert image.getpixel((32, 24))[3] > 240
        assert image.getpixel((32, 9))[:3] != image.getpixel((32, 24))[:3]


def test_unavailable_external_image_is_removed_and_reported(tmp_path):
    data = ARTWORK.replace(b"</svg>", b'<image href="http://localhost:6080/missing"/></svg>')
    cleaned, removed = svg_input(data)
    assert removed == 1
    assert b"localhost" not in cleaned
    assert b"circle" in cleaned


def test_punctuation_in_base_aliases_is_preserved(source, tmp_path):
    if not shutil.which("rsvg-convert"):
        pytest.skip("rsvg-convert required")
    overrides = tmp_path / "overrides.json"
    (tmp_path / "art.svg").write_bytes(ARTWORK)
    (tmp_path / "NOTICE").write_text("fixture")
    overrides.write_text(json.dumps({"garry's-mod": {"source": "art.svg", "notice": "NOTICE", "kind": "icon"}}))
    output = tmp_path / "bundle"
    assert main(["build", "--source", str(source), "--output", str(output), "--overrides", str(overrides),
                 "--icons", "garry's-mod", "--sizes", "64", "--variants", "dark"]) == 0
    assert "garry's-mod" in verify(output)["icons"]


def test_manifest_source_provenance_and_output_boundaries(built):
    for command, filename in (("preview", "preview.png"), ("pack", "pack.tar.gz")):
        assert main([command, str(built), "--output", str(built / filename)]) == 1
        assert not (built / filename).exists()
    path = built / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["icons"]["demo"]["source_sha256"] = "0" * 64
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="provenance"):
        verify(built)


def test_glass_finder_eyes_and_calendar_text_remain_legible_on_both_wallpapers(tmp_path):
    """Use the shipped artwork at Dock size, not synthetic replacement glyphs."""
    from statistics import median
    from icon_materials import render_installer
    from icon_toolset import ROOT
    from installer_choices import COLORS
    unpack(ROOT / 'src/offline/icons/MacTahoeLiquidKde-Icons.tar.zst', tmp_path / 'original')
    base = tmp_path / 'original' / BASE / 'apps/scalable'
    prepared = {name: prepare_source(base / (name + '.svg'), 512)
                for name in ('system-file-manager', 'calendar')}
    original = prepared['calendar'][0].resize((64, 64), Image.Resampling.LANCZOS)
    letters = [(x, y) for y in range(12, 22) for x in range(20, 47)
               if (lambda p: p[0] > 210 and p[1] < 130 and p[2] < 130 and p[3] > 240)(original.getpixel((x, y)))]
    assert letters
    def luminance(rgb):
        return sum((v/255/12.92 if v/255 <= .04045 else ((v/255+.055)/1.055)**2.4)*w
                   for v, w in zip(rgb, (.2126, .7152, .0722)))
    def contrast(a, b):
        low, high = sorted((luminance(a), luminance(b)))
        return (high + .05) / (low + .05)
    for tint in COLORS.values():
        rgb = tuple(bytes.fromhex(tint[1:]))
        for mode in ('light', 'dark'):
            icons = {name: render_installer(source, 'glass', mode, rgb)
                     .resize((256, 256), Image.Resampling.LANCZOS)
                     .resize((64, 64), Image.Resampling.LANCZOS)
                     for name, source in prepared.items()}
            for background in ('#101010', '#eeeeee'):
                images = {name: Image.alpha_composite(Image.new('RGBA', im.size, background), im).convert('RGB')
                          for name, im in icons.items()}
                finder = images['system-file-manager']
                assert contrast(finder.getpixel((20, 23)), finder.getpixel((17, 23))) >= 3, (tint, mode, background, 'eye')
                calendar = images['calendar']
                assert median(contrast(calendar.getpixel(pt), calendar.getpixel((12, 17)))
                              for pt in letters) >= 3, (tint, mode, background, 'letters')


def test_small_kernel_erosion_is_pixel_identical():
    from PIL import ImageFilter, ImageChops
    from icon_materials import minimum_filter
    image = Image.frombytes('L', (37, 29), bytes((i * 53 + i // 37 * 17) % 256 for i in range(37 * 29)))
    for width in (3, 7, 19):
        assert ImageChops.difference(minimum_filter(image, width),
                                    image.filter(ImageFilter.MinFilter(width))).getbbox() is None


def test_installer_recipe_is_reproducible_and_parameters_change_pixels(source, tmp_path, monkeypatch):
    import icon_toolset
    from icon_sources import inventory
    staging = tmp_path / 'recipe-source'
    unpack(source, staging)
    (staging / BASE / 'apps/scalable/second.svg').write_bytes(ARTWORK.replace(b'#f05020', b'#20a060'))
    archive = tmp_path / 'recipe.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for child in sorted(staging.iterdir()):
            tar.add(child, arcname=child.name)
    source = archive
    calls = []
    original = icon_toolset.render_installer
    def counted(*args, **kwargs):
        calls.append(args[2])
        return original(*args, **kwargs)
    monkeypatch.setattr(icon_toolset, 'render_installer', counted)
    recipe = tmp_path / 'material.json'
    recipe.write_text('{"relief_tint": 0.4}')
    outputs = [tmp_path / name for name in ('first', 'repeat', 'default')]
    for output in outputs:
        args = ['installer-build', '--source', str(source), '--output', str(output),
                '--tint', '#ff7a18', '--jobs', '1' if output == outputs[0] else '4',
                '--icons', 'demo', 'org.example.Demo', 'second']
        if output != outputs[-1]:
            args += ['--material', str(recipe)]
        assert main(args) == 0
    assert calls.count('light') == calls.count('dark') == 6  # aliases share each mode's output
    assert inventory(outputs[0]) == inventory(outputs[1])
    theme = BASE + '-Glass-Light'
    icon = Path(theme) / 'apps/256/demo.png'
    assert (outputs[0] / icon).read_bytes() != (outputs[-1] / icon).read_bytes()
    assert (outputs[0] / icon).read_bytes() != (outputs[0] / (BASE + '-Glass-Dark') / 'apps/256/demo.png').read_bytes()
    metadata = json.loads((outputs[0] / theme / 'generation.json').read_text())
    assert metadata['partial'] and metadata['material']['relief_tint'] == .4
    assert metadata['renderer']['pillow'] and metadata['generator']['icon_materials.py']
    for invalid in ('{"unknown": 1}', '{"sparse_gamma": 0}', '{"shadow_tint": NaN}', '{"ink_blackpoint": 2.5}'):
        recipe.write_text(invalid)
        output = tmp_path / 'invalid'
        assert main(['installer-build', '--source', str(source), '--output', str(output), '--material', str(recipe)]) == 1
        assert not output.exists()


def test_installer_worker_failure_never_publishes_partial_output(source, tmp_path, monkeypatch):
    import icon_toolset
    def fail(*args, **kwargs):
        raise ValueError("render failed")
    monkeypatch.setattr(icon_toolset, 'render_installer', fail)
    output = tmp_path / 'failed'
    assert main(['installer-build', '--source', str(source), '--output', str(output)]) == 1
    assert not output.exists()
    assert not list(tmp_path.glob('icon-installer-*'))


def test_variants_preserve_original_geometry_including_unplated_icons(tmp_path):
    """Every mode keeps the source contour, interior cutouts and existing rim."""
    from icon_materials import VARIANTS
    from PIL import ImageChops
    for name, svg in {
        "layered": ARTWORK,
        "unplated": b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><path fill="#aaa" fill-rule="evenodd" d="M18 10H46L42 55H22Z M27 20H37V38H27Z"/><path d="M16 10H48" stroke="white" stroke-width="2"/></svg>',
    }.items():
        path = tmp_path / (name + ".svg")
        path.write_bytes(svg)
        source = prepare_source(path, 128)
        alpha = source[0].getchannel("A")
        mask = alpha.point(lambda v: 255 if v else 0)
        for tint in ((255, 59, 48), (0, 122, 255)):
            for variant in VARIANTS:
                result = render(source, variant, tint)
                coverage = result.getchannel("A")
                assert ImageChops.subtract(coverage.point(lambda v: 255 if v else 0), mask).getbbox() is None, (name, variant)
                if not variant.startswith("clear-"):
                    assert coverage.tobytes() == alpha.tobytes(), (name, variant)
                else:
                    assert coverage.getbbox() == alpha.getbbox(), (name, variant)
            assert render(source, "tinted-light", tint).tobytes() != render(source, "tinted-dark", tint).tobytes()


@pytest.mark.parametrize("style", ["dark", "clear"])
def test_installer_selector_styles_generate_matching_overlays(source, tmp_path, style):
    from icon_toolset import installer_themes
    staging = tmp_path / "source"
    unpack(source, staging)
    blue, red = tmp_path / "blue", tmp_path / "red"
    names = installer_themes(staging, blue, style, "#007aff")
    installer_themes(staging, red, style, "#ff3b30")
    images = []
    for name in names:
        icon = blue / name / "apps/256/demo.png"
        assert digest(icon) == digest(red / name / "apps/256/demo.png")
        assert (blue / name / "apps/256/org.example.Demo.png").resolve() == icon
        image = Image.open(icon).convert("RGBA")
        assert image.getpixel((0, 0))[3] == 0
        images.append(image.tobytes())
    if style == "dark":
        assert images[0] == images[1]  # Dark remains dark in a light desktop.
    else:
        assert images[0] != images[1]  # Clear follows the desktop appearance.
        assert 0 < Image.open(blue / names[0] / "apps/256/demo.png").getpixel((128, 36))[3] < 255
