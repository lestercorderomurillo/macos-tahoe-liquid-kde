"""Shadow choices must reach both decoration paths without changing geometry."""

import json
import re
import shutil
from xml.etree import ElementTree as ET

import pytest

from window_shadows import LEVELS, aurorae_svg, gtk_css


@pytest.mark.parametrize("mode", ["Light", "Dark"])
def test_aurorae_levels_preserve_frames_and_disable_all_shadow_stops(repo, mode):
    source = (repo / f"src/offline/aurorae/MacTahoeLiquidKde-{mode}/decoration.svg").read_text()
    previous = -1
    for level in LEVELS:
        original, changed = ET.fromstring(source), ET.fromstring(aurorae_svg(source, level))
        old_nodes, new_nodes = list(original.iter()), list(changed.iter())
        assert len(old_nodes) == len(new_nodes)
        shadow_stops = {id(stop) for node in changed.iter()
                        if node.get("id") in ("shadow_active", "shadow_inactive") for stop in node}
        total = 0
        assert len(shadow_stops) >= 12
        for old, new in zip(old_nodes, new_nodes):
            if id(new) in shadow_stops:
                total += float(re.search(r"stop-opacity:([\d.]+)", new.get("style"))[1])
                new.set("style", old.get("style"))
            elif old.get("style") != new.get("style"):
                assert "fill:url(#" in old.get("style", "")
                assert re.sub(r"(?<![-\w])opacity:[\d.]+", "", old.get("style")) == re.sub(
                    r"(?<![-\w])opacity:[\d.]+", "", new.get("style"))
                new.set("style", old.get("style"))
            assert old.attrib == new.attrib  # Borders, padding and all geometry survive.
        assert total > previous
        if level == "none":
            assert total == 0
        previous = total


@pytest.mark.parametrize("mode", ["Light", "Dark"])
def test_aurorae_shadow_pixels_are_visible_and_increase_with_level(repo, mode):
    from PyQt6.QtCore import QByteArray, QRectF, QSize
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer
    source = (repo / f"src/offline/aurorae/MacTahoeLiquidKde-{mode}/decoration.svg").read_text()
    for element in ("decoration-bottom", "decoration-inactive-bottom", "decoration-left", "decoration-inactive-left"):
        totals = []
        for level in LEVELS:
            renderer = QSvgRenderer(QByteArray(aurorae_svg(source, level).encode()))
            assert renderer.isValid() and renderer.elementExists(element)
            image = QImage(QSize(200, 120), QImage.Format.Format_ARGB32)
            image.fill(0)
            painter = QPainter(image)
            renderer.render(painter, element, QRectF(0, 0, 200, 120))
            painter.end()
            totals.append(sum(image.pixelColor(x, y).alpha() for x in range(200) for y in range(120)))
        assert totals == sorted(set(totals)), (mode, element, totals)


@pytest.mark.parametrize("mode", ["Light", "Dark"])
@pytest.mark.parametrize("version", [3, 4])
def test_gtk_only_changes_normal_window_shadows(repo, mode, version):
    folder = repo / f"src/offline/gtk/MacTahoeLiquidKde-{mode}/gtk-{version}.0"
    for path in folder.glob("*.css"):
        source = path.read_text()
        for level in LEVELS:
            result = gtk_css(source, level, version)
            before = re.findall(r"([^{}]+)\{([^{}]+)\}", source)
            after = re.findall(r"([^{}]+)\{([^{}]+)\}", result)
            assert len(before) == len(after)
            changed = []
            for (selector, old), (new_selector, new) in zip(before, after):
                assert selector == new_selector
                if old != new:
                    changed.append(selector.strip().split("\n")[-1])
                    assert re.sub(r"box-shadow:[^;]+;", "", old) == re.sub(r"box-shadow:[^;]+;", "", new)
                    if level == "none":
                        value = re.search(r"box-shadow:\s*([^;]+);", new)[1]
                        assert value == "none" or value.startswith("0 0 0 ")
            assert all(s in ("decoration", "decoration:backdrop", "window.csd", "window.csd:backdrop",
                             "window.background.chromium", "window.background.chromium:backdrop") for s in changed)
            if level != "none":
                assert changed


def test_reinstall_rebuilds_shadows_for_both_modes_and_uninstall_removes_them(repo, tmp_path, monkeypatch):
    from steps import window_decorations as wd, gtk
    monkeypatch.setattr(wd, "DEST_DIR", tmp_path / "aurorae")
    monkeypatch.setattr(wd, "kw_write", lambda *a: True)
    monkeypatch.setattr(wd, "qdbus_call", lambda *a: True)
    monkeypatch.setattr(gtk, "DEST_DIR", tmp_path / "gtk")
    monkeypatch.setattr(gtk, "GTK4_DEST", tmp_path / "config-gtk4")
    monkeypatch.setattr(gtk, "_retain_gtk4_css_ownership", lambda _: None)
    monkeypatch.setattr(gtk, "qdbus_call", lambda *a: True)
    monkeypatch.setattr(gtk, "have", lambda _: False)
    def copy(source, dest, label):
        shutil.copytree(source, dest, dirs_exist_ok=True)
        return True
    monkeypatch.setattr(gtk, "install_tree", copy)
    previous = {}
    for level in ("none", "hard", "soft", "medium", "medium"):
        monkeypatch.setenv("MTTKDE_WIZARD_OPTIONS", json.dumps({"shadows": level}))
        wd.install(); gtk.install()
        for mode in ("Light", "Dark"):
            svg = (wd.DEST_DIR / f"MacTahoeLiquidKde-{mode}/decoration.svg").read_text()
            source = (repo / f"src/offline/aurorae/MacTahoeLiquidKde-{mode}/decoration.svg").read_text()
            assert svg == aurorae_svg(source, level)
        current = {str(p): p.read_bytes() for root in (wd.DEST_DIR, gtk.DEST_DIR)
                   for p in root.rglob("*") if p.suffix in (".svg", ".css")}
        if previous.get("level") == level:
            assert current == previous["files"]
        previous = dict(level=level, files=current)
    wd.uninstall(); gtk.uninstall()
    assert not list(wd.DEST_DIR.glob("MacTahoe*"))
    assert not list(gtk.DEST_DIR.glob("MacTahoe*"))
