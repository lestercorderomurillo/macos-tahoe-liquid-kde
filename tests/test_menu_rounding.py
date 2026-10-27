"""Kvantum selection curvature must never change menu layout at any scale."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.parametrize("mode", ["", "Dark"])
@pytest.mark.parametrize("scale", ["1", "1.5", "2"])
def test_native_rounding_preserves_menu_geometry(repo, tmp_path, mode, scale):
    pytest.importorskip("PyQt6.QtWidgets")
    results = []
    for expansion in (0, 12):
        home = tmp_path / str(expansion)
        config = home / ".config/Kvantum"
        profile = "mac-tahoe-liquid-kde" + mode
        theme = config / profile
        theme.mkdir(parents=True)
        source = repo / "src/offline/kvantum/mac-tahoe-liquid-kde"
        shutil.copy2(source / f"{profile}.svg", theme)
        content = (source / f"{profile}.kvconfig").read_text()
        start = content.index("[MenuItem]")
        end = content.index("\n[", start + 1)
        content = content[:start] + content[start:end].replace(
            "frame.expansion=12", f"frame.expansion={expansion}") + content[end:]
        (theme / f"{profile}.kvconfig").write_text(content)
        (config / "kvantum.kvconfig").write_text(f"[General]\ntheme={profile}\n")
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG")}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
                   QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic",
                   QT_SCALE_FACTOR=scale)
        result = subprocess.run([sys.executable, __file__, "--probe"], env=env,
                                capture_output=True, text=True, timeout=20)
        if result.returncode == 77:
            pytest.skip("Kvantum Qt6 style plugin required")
        assert result.returncode == 0, result.stdout + result.stderr
        results.append(json.loads(result.stdout))
    before, after = results
    assert after["geometry"] == before["geometry"]
    assert after["size"] == before["size"]
    assert after["top_inset"] > before["top_inset"]
    assert after["center"] == before["center"]
    assert after["solid_center"]


def _probe():
    from PyQt6.QtCore import QRect, Qt
    from PyQt6.QtGui import QImage, QPainter, QPixmap, QIcon
    from PyQt6.QtWidgets import QApplication, QMenu, QStyle, QStyleOptionMenuItem
    app = QApplication([])
    if not app.setStyle("kvantum"):
        sys.exit(77)
    menu = QMenu()
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.black)
    for label in ("About This Computer", None, "System Settings…", "App Store…",
                  None, "Force Quit…", None, "Sleep", "Restart…", "Shut Down…",
                  None, "Lock Screen", "Log Out Lester…"):
        menu.addSeparator() if label is None else menu.addAction(QIcon(pixmap), label)
    size = menu.sizeHint()
    geometry = [list(menu.actionGeometry(a).getRect()) for a in menu.actions()]
    option = QStyleOptionMenuItem()
    option.initFrom(menu)
    option.menuItemType = QStyleOptionMenuItem.MenuItemType.Normal
    option.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Selected
    option.rect = QRect(0, 0, 200, menu.actionGeometry(menu.actions()[0]).height())
    scale = float(os.environ["QT_SCALE_FACTOR"])
    image = QImage(round(200 * scale), round(option.rect.height() * scale), QImage.Format.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(scale)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    menu.style().drawControl(QStyle.ControlElement.CE_MenuItem, option, painter, menu)
    painter.end()
    y = max(0, round(scale / 2))
    inset = next(x for x in range(image.width()) if image.pixelColor(x, y).alpha() > 240)
    center = image.pixelColor(image.width() // 2, image.height() // 2).rgba()
    solid = all(image.pixelColor(x, image.height() // 2).alpha() == 255
                for x in range(round(8 * scale), image.width() - round(8 * scale)))
    print(json.dumps(dict(geometry=geometry, size=[size.width(), size.height()],
                         top_inset=inset, center=center, solid_center=solid)))


if __name__ == "__main__":
    _probe()
