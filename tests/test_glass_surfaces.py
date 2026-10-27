"""Render clear applet surfaces and readable contextual menu backgrounds."""
import gzip
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1] / "src/offline/plasma-theme"


@pytest.mark.parametrize("mode", ["Light", "Dark"])
def test_golden_gate_client_fill_follows_appearance(mode, tmp_path, monkeypatch):
    import glass_surfaces
    svg = pytest.importorskip("PyQt6.QtSvg")
    gui = pytest.importorskip("PyQt6.QtGui")
    core = pytest.importorskip("PyQt6.QtCore")
    monkeypatch.setattr(glass_surfaces, "default_wallpaper", lambda: "MacGoldenGate")
    theme = tmp_path / f"MacTahoeLiquidKde-{mode}"
    shutil.copytree(ROOT / f"MacTahoeLiquidKde-{mode}", theme)
    glass_surfaces.apply_plasma_surface_defaults(theme)
    for name in glass_surfaces.PLASMA_SURFACES:
        original = svg.QSvgRenderer(str(ROOT / f"MacTahoeLiquidKde-{mode}" / name))
        renderer = svg.QSvgRenderer(str(theme / name))
        image = gui.QImage(64, 64, gui.QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = gui.QPainter(image)
        renderer.render(painter, "center", core.QRectF(0, 0, 64, 64))
        painter.end()
        fill = image.pixelColor(32, 32)
        expected = .60 if mode == "Light" else .01
        assert fill.alphaF() == pytest.approx(expected, abs=.005)
        assert fill.red() == 255
        # Alpha-derived blur masks and shadows must survive edition staging.
        for element in ("mask-center", "mask-topleft", "shadow-top", "shadow-topleft"):
            assert original.elementExists(element) == renderer.elementExists(element)
            if not original.elementExists(element):
                continue
            rendered = []
            for source in (original, renderer):
                image.fill(0)
                painter = gui.QPainter(image)
                source.render(painter, element, core.QRectF(0, 0, 64, 64))
                painter.end()
                rendered.append(image.copy())
            assert rendered[0] == rendered[1], (name, element)
    assert svg.QSvgRenderer(str(theme / "dialogs/background.svgz")).elementExists("hint-clear-surface")
    before = {path: path.read_bytes() for path in theme.rglob("*.svgz")}
    glass_surfaces.apply_plasma_surface_defaults(theme)
    assert all(path.read_bytes() == data for path, data in before.items())
    for name in ("widgets/panel-background.svgz", "solid/dialogs/background.svgz"):
        assert (theme / name).read_bytes() == (ROOT / f"MacTahoeLiquidKde-{mode}" / name).read_bytes()


@pytest.mark.parametrize("backdrop", ["black", "white"])
def test_golden_gate_light_plasma_text_is_readable(tmp_path, monkeypatch, backdrop):
    """Render every popup fill over worst-case backdrops using the real SVGs."""
    import configparser
    import glass_surfaces
    svg = pytest.importorskip("PyQt6.QtSvg")
    gui = pytest.importorskip("PyQt6.QtGui")
    core = pytest.importorskip("PyQt6.QtCore")
    monkeypatch.setattr(glass_surfaces, "default_wallpaper", lambda: "MacGoldenGate")
    theme = tmp_path / "MacTahoeLiquidKde-Light"
    shutil.copytree(ROOT / theme.name, theme)
    glass_surfaces.apply_plasma_surface_defaults(theme)
    scheme = configparser.ConfigParser()
    scheme.read(ROOT.parent / "color-schemes/MacTahoeLiquidKdeLight.colors")

    def luminance(color):
        def linear(value):
            return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
        return sum(weight * linear(value) for weight, value in zip(
            (.2126, .7152, .0722), (color.redF(), color.greenF(), color.blueF())))

    for name in glass_surfaces.PLASMA_SURFACES:
        group = "Colors:Tooltip" if name == "widgets/tooltip.svgz" else "Colors:Window"
        foreground = gui.QColor(*map(int, scheme[group]["ForegroundNormal"].split(",")))
        image = gui.QImage(64, 64, gui.QImage.Format.Format_ARGB32)
        image.fill(gui.QColor(backdrop))
        painter = gui.QPainter(image)
        svg.QSvgRenderer(str(theme / name)).render(painter, "center", core.QRectF(0, 0, 64, 64))
        painter.end()
        a, b = sorted((luminance(image.pixelColor(32, 32)), luminance(foreground)))
        assert (b + .05) / (a + .05) >= 4.5, name


@pytest.mark.parametrize("mode", ["Light", "Dark"])
def test_tahoe_plasma_surfaces_remain_byte_identical(mode, tmp_path, monkeypatch):
    import glass_surfaces
    monkeypatch.setattr(glass_surfaces, "default_wallpaper", lambda: "MacTahoe")
    theme = tmp_path / f"MacTahoeLiquidKde-{mode}"
    shutil.copytree(ROOT / theme.name, theme)
    before = {path: path.read_bytes() for path in theme.rglob("*.svgz")}
    glass_surfaces.apply_plasma_surface_defaults(theme)
    assert all(path.read_bytes() == data for path, data in before.items())


@pytest.mark.parametrize("mode", ["", "Dark"])
def test_golden_gate_qt_menu_center_and_frame_follow_appearance(mode, tmp_path, monkeypatch):
    import glass_surfaces
    svg = pytest.importorskip("PyQt6.QtSvg")
    gui = pytest.importorskip("PyQt6.QtGui")
    core = pytest.importorskip("PyQt6.QtCore")
    monkeypatch.setattr(glass_surfaces, "default_wallpaper", lambda: "MacGoldenGate")
    source = ROOT.parent / "kvantum/mac-tahoe-liquid-kde" / f"mac-tahoe-liquid-kde{mode}.svg"
    target = tmp_path / source.name
    shutil.copy2(source, target)
    glass_surfaces.apply_kvantum_surface_defaults(target)
    renderer = svg.QSvgRenderer(str(target))
    for element in ("menu-normal", "path4382-5", "path4714-2"):
        image = gui.QImage(64, 64, gui.QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = gui.QPainter(image)
        renderer.render(painter, element, core.QRectF(0, 0, 64, 64))
        painter.end()
        fill = image.pixelColor(48, 48)
        expected = .01 if mode == "Dark" else .60
        assert fill.alphaF() == pytest.approx(expected, abs=.005) and fill.red() == 255, element
    before = target.read_bytes()
    glass_surfaces.apply_kvantum_surface_defaults(target)
    assert target.read_bytes() == before


@pytest.mark.parametrize("mode", ["", "Dark"])
def test_tahoe_qt_surfaces_remain_byte_identical(mode, tmp_path, monkeypatch):
    import glass_surfaces
    monkeypatch.setattr(glass_surfaces, "default_wallpaper", lambda: "MacTahoe")
    source = ROOT.parent / "kvantum/mac-tahoe-liquid-kde" / f"mac-tahoe-liquid-kde{mode}.svg"
    target = tmp_path / source.name
    shutil.copy2(source, target)
    before = target.read_bytes()
    glass_surfaces.apply_kvantum_surface_defaults(target)
    assert target.read_bytes() == before


@pytest.mark.parametrize("mode", ["", "Dark"])
def test_golden_gate_menu_fix_preserves_other_surfaces(mode, tmp_path, monkeypatch):
    import glass_surfaces
    svg = pytest.importorskip("PyQt6.QtSvg")
    gui = pytest.importorskip("PyQt6.QtGui")
    core = pytest.importorskip("PyQt6.QtCore")
    monkeypatch.setattr(glass_surfaces, "default_wallpaper", lambda: "MacGoldenGate")
    source = ROOT.parent / "kvantum/mac-tahoe-liquid-kde" / f"mac-tahoe-liquid-kde{mode}.svg"
    target = tmp_path / source.name
    shutil.copy2(source, target)
    previous = ET.parse(source).getroot()
    ids = tuple(node.get("id") for node in previous.iter()
                if node.get("id", "").startswith(("menu-normal", "menu-shadow")))
    glass_surfaces.set_surface_fill(previous, ids, "0.01", "#ffffff")
    old = tmp_path / "previous.svg"
    glass_surfaces._write_svg(old, previous)
    glass_surfaces.apply_kvantum_surface_defaults(target)
    if mode == "Dark":
        assert target.read_bytes() == old.read_bytes()
    for element in ("window-normal", "dialog-normal", "tooltip-normal",
                    "toolbar-normal", "menuitem-separator"):
        rendered = []
        for path in (old, target):
            renderer = svg.QSvgRenderer(str(path))
            assert renderer.elementExists(element), element
            image = gui.QImage(64, 64, gui.QImage.Format.Format_ARGB32)
            image.fill(0)
            painter = gui.QPainter(image)
            renderer.render(painter, element, core.QRectF(0, 0, 64, 64))
            painter.end()
            rendered.append(image)
        assert rendered[0] == rendered[1], element


def test_golden_gate_light_menu_text_contrasts_over_black(tmp_path, monkeypatch):
    import configparser
    import glass_surfaces
    svg = pytest.importorskip("PyQt6.QtSvg")
    gui = pytest.importorskip("PyQt6.QtGui")
    core = pytest.importorskip("PyQt6.QtCore")
    monkeypatch.setattr(glass_surfaces, "default_wallpaper", lambda: "MacGoldenGate")
    source = ROOT.parent / "kvantum/mac-tahoe-liquid-kde/mac-tahoe-liquid-kde.svg"
    target = tmp_path / source.name
    shutil.copy2(source, target)
    glass_surfaces.apply_kvantum_surface_defaults(target)
    image = gui.QImage(64, 64, gui.QImage.Format.Format_ARGB32)
    image.fill(gui.QColor("black"))
    painter = gui.QPainter(image)
    svg.QSvgRenderer(str(target)).render(painter, "menu-normal", core.QRectF(0, 0, 64, 64))
    painter.end()
    scheme = configparser.ConfigParser()
    scheme.read(ROOT.parent / "color-schemes/MacTahoeLiquidKdeLight.colors")
    foreground = gui.QColor(*map(int, scheme["Colors:Window"]["ForegroundNormal"].split(",")))
    def luminance(color):
        def linear(value):
            return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
        return sum(weight * linear(value) for weight, value in zip(
            (.2126, .7152, .0722), (color.redF(), color.greenF(), color.blueF())))
    contrast = (luminance(image.pixelColor(32, 32)) + .05) / (luminance(foreground) + .05)
    assert contrast >= 4.5


def _xml(path):
    return ET.fromstring(gzip.decompress(path.read_bytes()))


@pytest.mark.parametrize("mode", ["Light", "Dark"])
def test_shared_dialog_fills_keep_top_bar_clear(mode):
    source = ROOT / f"MacTahoeLiquidKde-{mode}"
    for file in ("dialogs/background.svgz", "dialogs/launcher-search.svgz"):
        root = _xml(source / file)
        center = next(n for n in root.iter() if n.get("id") == "center")
        for node in center.iter():
            if node.tag.endswith("}rect"):
                style = dict(part.split(":", 1) for part in node.get("style", "").split(";") if ":" in part)
                alpha = float(style.get("opacity", node.get("opacity", "1")))
                assert alpha == pytest.approx(.48 if mode == "Dark" else .55)
        # The preset owns the colored gradient. The capsule may retain only
        # a faint edge reflection; a baked dark cap would also affect Tahoe.
        for node in root.iter():
            if node.get("id") in ("top-surface", "bottom-surface"):
                assert all(float(stop.get("stop-opacity", "1")) <= 0.08 for stop in node)
    panel = _xml(source / "widgets/panel-background.svgz")
    top = next(n for n in panel.iter() if n.get("id") == "north-center")
    assert "fill:none" in top.get("style", "")



@pytest.mark.parametrize("mode", ["Light", "Dark"])
def test_qt_renders_transparent_dialogs_and_dock(mode):
    svg = pytest.importorskip("PyQt6.QtSvg")
    gui = pytest.importorskip("PyQt6.QtGui")
    core = pytest.importorskip("PyQt6.QtCore")
    for name, bounds in (("dialogs/background", (.54, .56)),
                         ("dialogs/launcher-search", (.54, .56)),
                         ("widgets/panel-background", (.005, .025)),
                         ("widgets/tooltip", (.54, .56)),
                         ("widgets/background", (.54, .56)),
                         ("widgets/translucentbackground", (.54, .56))):
        renderer = svg.QSvgRenderer(gzip.decompress((ROOT / f"MacTahoeLiquidKde-{mode}/{name}.svgz").read_bytes()))
        image = gui.QImage(64, 64, gui.QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = gui.QPainter(image)
        renderer.render(painter, "center", core.QRectF(0, 0, 64, 64))
        painter.end()
        alpha = image.pixelColor(32, 32).alphaF()
        adjustment = .07 if mode == "Dark" and not name.endswith("panel-background") else 0
        assert bounds[0] - adjustment <= alpha <= bounds[1] - adjustment, (mode, name, alpha)
        if name.startswith("dialogs/"):
            # Render at 200% so the subpixel contour covers a complete pixel.
            size = renderer.boundsOnElement("top").size().toSize() * 2
            edge = gui.QImage(size, gui.QImage.Format.Format_ARGB32)
            edge.fill(0)
            painter = gui.QPainter(edge)
            renderer.render(painter, "top", core.QRectF(0, 0, size.width(), size.height()))
            painter.end()
            rim = edge.pixelColor(size.width() // 2, 0).alphaF()
            interior = edge.pixelColor(size.width() // 2, size.height() // 2).alphaF()
            assert abs(interior - (.48 if mode == "Dark" else .55)) < .01 and interior < rim < .75, (mode, name, rim, interior)
            fill = image.pixelColor(32, 32)
            expected = 255 if mode == "Light" else 0
            assert abs(fill.red() - expected) <= 1
            assert fill.red() == fill.green() == fill.blue()



@pytest.mark.parametrize("mode", ["", "Dark"])
def test_kvantum_blur_corners_match_drawn_svg(mode):
    import configparser
    svg = pytest.importorskip("PyQt6.QtSvg")
    folder = ROOT.parent / "kvantum/mac-tahoe-liquid-kde"
    theme = "mac-tahoe-liquid-kde" + mode
    config = configparser.ConfigParser(strict=False, interpolation=None)
    config.read(folder / (theme + ".kvconfig"))
    renderer = svg.QSvgRenderer(str(folder / (theme + ".svg")))
    for surface in ("menu", "tooltip"):
        corner = renderer.boundsOnElement(surface + "-normal-topleft")
        radius = float(config["%General"][surface + "_blur_radius"])
        assert abs(corner.width() - radius) < .01
        assert abs(corner.height() - radius) < .01


def test_dock_assets_are_identical_between_modes():
    assert (ROOT / "MacTahoeLiquidKde-Light/widgets/panel-background.svgz").read_bytes() == (
        ROOT / "MacTahoeLiquidKde-Dark/widgets/panel-background.svgz").read_bytes()


@pytest.mark.parametrize("mode", ["Light", "Dark"])
@pytest.mark.parametrize("name", ["dialogs/background", "dialogs/launcher-search",
                                  "widgets/tooltip", "widgets/panel-background"])
def test_surface_contours_have_same_dark_outer_and_light_inner_line(mode, name):
    svg = pytest.importorskip("PyQt6.QtSvg")
    gui = pytest.importorskip("PyQt6.QtGui")
    core = pytest.importorskip("PyQt6.QtCore")
    renderer = svg.QSvgRenderer(gzip.decompress((ROOT / f"MacTahoeLiquidKde-{mode}/{name}.svgz").read_bytes()))
    size = renderer.boundsOnElement("top").size().toSize() * 4
    image = gui.QImage(size, gui.QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = gui.QPainter(image)
    renderer.render(painter, "top", core.QRectF(0, 0, size.width(), size.height()))
    painter.end()
    x = size.width() // 2
    outer, inner, body = (image.pixelColor(x, y) for y in (1, 4, 12))
    assert outer.red() < inner.red(), (mode, name, outer.getRgb(), inner.getRgb())
    assert outer.alphaF() > body.alphaF() and inner.alphaF() > body.alphaF()
    # Two adjacent .75 logical-pixel contours; no wider third border.
    assert image.pixelColor(x, 7) == body


@pytest.mark.parametrize("mode", ["Light", "Dark"])
def test_all_dock_corners_keep_both_contours(mode):
    svg = pytest.importorskip("PyQt6.QtSvg")
    gui = pytest.importorskip("PyQt6.QtGui")
    core = pytest.importorskip("PyQt6.QtCore")
    renderer = svg.QSvgRenderer(gzip.decompress((ROOT / f"MacTahoeLiquidKde-{mode}/widgets/panel-background.svgz").read_bytes()))
    for prefix in ("", "south-"):
        for corner in ("topleft", "topright", "bottomleft", "bottomright"):
            image = gui.QImage(128, 128, gui.QImage.Format.Format_ARGB32)
            image.fill(0)
            painter = gui.QPainter(image)
            renderer.render(painter, prefix + corner, core.QRectF(0, 0, 128, 128))
            painter.end()
            contour = [image.pixelColor(x, y) for x in range(128) for y in range(128)
                       if image.pixelColor(x, y).alphaF() > .15]
            assert any(c.red() < 40 for c in contour), (prefix, corner, "dark line missing")
            assert any(c.red() > 240 for c in contour), (prefix, corner, "light line missing")
