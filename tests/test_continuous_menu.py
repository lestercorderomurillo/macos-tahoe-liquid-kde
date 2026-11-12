"""Render the installed Qt style against the measured continuous menu contour."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.fixture(scope="module")
def menu_plugin(tmp_path_factory):
    root = Path(__file__).resolve().parents[1]
    build = tmp_path_factory.mktemp("continuous-menu")
    subprocess.run(["cmake", "-S", str(root / "src/offline/menu-style"), "-B", str(build)], check=True, capture_output=True)
    subprocess.run(["cmake", "--build", str(build), "-j2"], check=True, capture_output=True)
    plugins = build / "plugins/styles"
    plugins.mkdir(parents=True)
    shutil.copy2(build / "libmactahoestyle.so", plugins)
    return plugins.parent


@pytest.mark.parametrize("mode", ("", "Dark"))
@pytest.mark.parametrize("scale", ("1", "2"))
def test_contour_and_content_inset(menu_plugin, tmp_path, repo, mode, scale):
    config = tmp_path / "Kvantum"
    profile = "mac-tahoe-liquid-kde" + mode
    shutil.copytree(repo / "src/offline/kvantum/mac-tahoe-liquid-kde", config / profile)
    (config / "kvantum.kvconfig").write_text(f"[General]\ntheme={profile}\n")
    env = dict(os.environ, QT_PLUGIN_PATH=str(menu_plugin), QT_QPA_PLATFORM="offscreen",
               QT_QPA_PLATFORMTHEME="generic", QT_SCALE_FACTOR=scale,
               XDG_CONFIG_HOME=str(tmp_path), QT_STYLE_OVERRIDE="MacTahoe")
    result = subprocess.run([sys.executable, __file__, "--probe"], env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["inset"] == [5, 5]
    # Real reference: first opaque edge at x=17 for y=1 (2x pixels).
    # A 9px circular corner reaches this row around x=11 instead.
    assert abs(report["reference_edge"] - 17) <= 2
    assert report["center"] == report["base_center"]
    assert report["fallback_same"], "Other Kvantum themes must retain their own geometry"


def probe():
    from PyQt6.QtCore import QRect, Qt
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtWidgets import QApplication, QMenu, QStyle, QStyleFactory, QStyleOption
    app = QApplication([])
    style = app.setStyle("MacTahoe")
    assert style is not None
    menu = QMenu(); menu.addAction("About Finder"); menu.ensurePolished()
    option = QStyleOption(); option.initFrom(menu); option.rect = QRect(0, 0, 240, 140)
    def render(style):
        image = QImage(480, 280, QImage.Format.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(2); image.fill(Qt.GlobalColor.transparent)
        p = QPainter(image); style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelMenu, option, p, menu); p.end()
        return image
    base = QStyleFactory.create("kvantum")
    image = render(style); previous = render(base)
    edge = next(x for x in range(80) if image.pixelColor(x, 1).alpha() > 127)
    inset = [menu.actionGeometry(menu.actions()[0]).x(), menu.actionGeometry(menu.actions()[0]).y()]
    center, base_center = image.pixelColor(240, 140).rgba(), previous.pixelColor(240, 140).rgba()
    (Path(os.environ["XDG_CONFIG_HOME"]) / "Kvantum/kvantum.kvconfig").write_text("[General]\ntheme=unrelated\n")
    same = render(style) == render(base)
    print(json.dumps(dict(inset=inset, reference_edge=edge, center=center, base_center=base_center, fallback_same=same)))


if __name__ == "__main__":
    probe()
