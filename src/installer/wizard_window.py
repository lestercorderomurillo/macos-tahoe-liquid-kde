"""Native, single-window installation and removal wizard.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
import json
import math
import os
import shutil
import unicodedata
import subprocess
import time

from PyQt6 import sip
from PyQt6.QtCore import Qt, QEvent, QFileSystemWatcher, QSettings, QStandardPaths, QPoint, QPointF, QProcess, QRectF, QSize, QTimer, QUrl
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QIcon, QKeySequence, QPainter, QPainterPath, QLinearGradient, QPalette, QPen, QPixmap, QPolygonF, QRegion, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFrame,
    QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QKeySequenceEdit, QLabel, QLineEdit, QPlainTextEdit, QProgressBar, QPushButton,
    QRadioButton, QScrollArea, QSizePolicy, QSpinBox, QStyle, QStyleOptionSpinBox, QTabWidget, QToolButton,
    QVBoxLayout, QWidget,
)

from installer_choices import COLORS, GLASS_PRESETS, defaults, validate
from window_controls import button_svg
from progress_model import ProgressModel, elapsed_text

ASSETS = Path(__file__).with_name("assets")
ASSET_FILES = json.loads((ASSETS / "sources.json").read_text())
CONTROL_SYMBOLS = (ASSETS.parents[1] / "offline/plasmoids"
                   / "org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui/symbols")
STEPS = (
    ("welcome", ""), ("appearance", "Which appearance would you like?"),
    ("icons", "Which icons and color would you like?"),
    ("wallpaper", "Which wallpaper would you like?"),
    ("desktop_widgets", "Desktop widgets"),
    ("launcher", "Which launcher would you like?"),
    ("layout", "What would you like to add to your desktop?"),
    ("effects", "Which effects would you like to enable?"),
    ("window_controls", "Which window controls would you like?"),
    ("button_position", "Where should the window buttons go?"),
    ("shadows", "Which window shadows would you like?"),
    ("fonts", "Which fonts would you like to use?"),
    ("firefox", "Apply the theme to Firefox?"),
    ("files", "Install Nautilus as your file manager?"),
    ("glass_style", "Which window glass would you like?"),
    ("boot", "Change the boot animation?"),
    ("oled", "Enable OLED protection?"),
    ("summary", "Review your installation"),
)


# The individual panel IDs remain available to the screenshot harness. Only
# these grouped routes participate in the interactive installation flow.
SECTIONS = {
    "theme": ("Appearance", "appearance", ("#777fc0", "#262c68"), ("appearance", "icons", "fonts")),
    "desktop": ("Desktop", "stage-manager", ("#61adbf", "#1d5973"), ("wallpaper", "desktop_widgets")),
    "dock_bar": ("Desktop & Dock", "mirroring", ("#718dc0", "#3a507c"), ("launcher", "layout")),
    "windows": ("Windows", "airplay", ("#69a38e", "#305e55"),
                ("effects", "window_controls", "button_position", "shadows", "glass_style", "acrylic_glass_editor")),
    "applications": ("Applications", "screenshot", ("#8c83bd", "#4d427b"), ("files", "firefox")),
    "startup": ("Startup & Display", "sun", ("#bc945f", "#795336"), ("boot", "oled")),
}
INSTALL_SECTIONS = {
    "theme": ("Appearance", ("appearance",)),
    "personalization": ("Icons & Typography", ("icons", "fonts")),
    "desktop": ("Desktop", SECTIONS["desktop"][3]),
    "dock_bar": ("Desktop & Dock", SECTIONS["dock_bar"][3]),
    "windows": ("Effects", ("effects", "glass_style")),
    "window_details": ("Windows", ("window_controls", "button_position", "shadows")),
    "applications": ("Applications", SECTIONS["applications"][3]),
    "startup": ("Startup & Display", SECTIONS["startup"][3]),
}
INSTALL_FLOW = ("welcome", *INSTALL_SECTIONS, "summary")
PANEL_LABELS = {
    "appearance": "Theme", "icons": "Icons", "fonts": "Fonts",
    "wallpaper": "Wallpaper", "desktop_widgets": "Desktop widgets",
    "launcher": "Launcher", "layout": "Dock and menu bar", "effects": "Effects",
    "window_controls": "Window controls", "button_position": "Window buttons",
    "shadows": "Window shadows", "files": "Files", "firefox": "Firefox",
    "glass_style": "Window glass", "acrylic_glass_editor": "Acrylic Glass",
    "boot": "Boot animation", "oled": "OLED protection",
}
SETTINGS_PAGES = {
    "general": ("General", "settings", ("#99a9bc", "#3e506a"), ()),
    **SECTIONS,
}
SECTION_ALIASES = {"appearance": "theme", "acrylic_glass": "windows", "weather_panel": "desktop", "desktop_widget": "desktop"}
PANEL_SECTIONS = {panel: section for section, (_, _, _, panels) in SECTIONS.items() for panel in panels}
PANEL_STEPS = {panel: step for step, (_, panels) in INSTALL_SECTIONS.items() for panel in panels}

def settings_icon(symbol, colors):
    """Mount the project's existing symbols on small frosted tiles."""
    size = 24
    pixmap = QPixmap(size * 3, size * 3)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.scale(3, 3)
    tile = QPainterPath()
    tile.addRoundedRect(QRectF(1, 1, 22, 22), 6, 6)
    fill = QLinearGradient(3, 0, 20, 24)
    fill.setColorAt(0, QColor(colors[0]))
    fill.setColorAt(1, QColor(colors[1]))
    painter.fillPath(tile, fill)
    rim = QLinearGradient(0, 1, 0, 23)
    rim.setColorAt(0, QColor(255, 255, 255, 188))
    rim.setColorAt(1, QColor(255, 255, 255, 28))
    painter.strokePath(tile, QPen(rim, .8))
    glyph = QPixmap()
    artwork = (CONTROL_SYMBOLS / f"mttkde-control-{symbol}.svg").read_bytes()
    artwork = artwork.replace(b'width="24" height="24"', b'width="72" height="72"', 1)
    glyph.loadFromData(artwork.replace(b"currentColor", b"#ffffff"), "SVG")
    painter.drawPixmap(QRectF(4.6, 4.6, 14.8, 14.8), glyph, QRectF(glyph.rect()))
    painter.end()
    pixmap.setDevicePixelRatio(3)
    return QIcon(pixmap)


def search_text(value):
    return "".join(char for char in unicodedata.normalize("NFKD", value.casefold())
                   if not unicodedata.combining(char))


def picture(name, width, height, other=None, *, cover=False, crop=None):
    """Contain full screenshots; diagonal splits share the same canvas."""
    canvas = QPixmap(width*2, height*2)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.scale(2, 2)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for index, filename in enumerate((name, other)):
        if not filename:
            continue
        source = QPixmap(str(filename if isinstance(filename, Path) else ASSETS / ASSET_FILES[filename]["file"]))
        if source.isNull():
            continue
        if crop is not None:
            source = source.copy(*crop)
        fitted = source.scaled(width*2, height*2, Qt.AspectRatioMode.KeepAspectRatioByExpanding if cover else Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        fitted.setDevicePixelRatio(2)
        if index:
            painter.setClipRegion(QRegion(
                QPolygonF([QPointF(width * .61, 0), QPointF(width, 0),
                           QPointF(width, height), QPointF(width * .39, height)]).toPolygon()))
        painter.drawPixmap(round((width - fitted.width()/2) / 2), round((height - fitted.height()/2) / 2), fitted)
    if other:
        painter.setClipping(False)
        painter.setPen(QPen(QColor("#baffffff"), 1))
        painter.drawLine(QPointF(width*.61, 0), QPointF(width*.39, height))
    painter.end()
    canvas.setDevicePixelRatio(2)
    return canvas


def current_wallpaper_preview(width, height):
    """Read the user's saved desktops without changing or capturing the desktop."""
    from theme_switch import _wallpapers_from_config
    images = []
    for desktop in _wallpapers_from_config():
        value = str(desktop["image"])
        url = QUrl(value)
        path = Path(url.toLocalFile() if url.isLocalFile() else value)
        if path.is_dir():
            candidates = [sorted((path / "contents" / folder).glob("*"))
                          for folder in ("images", "images_dark")]
            paths = [next((p for p in files if p.is_file() and not QPixmap(str(p)).isNull()), None)
                     for files in candidates]
        else:
            paths = [path]
            if path.parent.name in ("images", "images_dark"):
                alternate = path.parent.parent / ("images_dark" if path.parent.name == "images" else "images") / path.name
                paths = [path, alternate] if path.parent.name == "images" else [alternate, path]
        for candidate in paths:
            if candidate and candidate not in images and not QPixmap(str(candidate)).isNull():
                images.append(candidate)
    if images:
        return picture(images[0], width, height, images[1] if len(images) > 1 else None, cover=True)
    canvas = QPixmap(width * 2, height * 2)
    canvas.fill(QApplication.palette().window().color())
    canvas.setDevicePixelRatio(2)
    return canvas


def installer_fonts(app):
    """Load bundled SF faces into this process, without installing desktop fonts."""
    cached = app.property("installerFontFamilies")
    if cached:
        return cached
    import tarfile
    from PyQt6.QtCore import QByteArray
    from paths import REPO_ROOT
    folder = REPO_ROOT / "src/offline/fonts"
    families = set()
    def register(data):
        font_id = QFontDatabase.addApplicationFontFromData(QByteArray(data))
        families.update(QFontDatabase.applicationFontFamilies(font_id))
    register((folder / "SF-Pro-Display-Regular.otf").read_bytes())
    wanted = {f"SF-Pro-{face}-{weight}.otf" for face in ("Text", "Display")
              for weight in ("Regular", "Medium", "Semibold", "Bold")}
    with tarfile.open(folder / "fonts.tar.xz", "r:xz") as archive:
        for member in archive:
            if member.name in wanted and member.isfile():
                with archive.extractfile(member) as stream:
                    register(stream.read())
    if not {"SF Pro Text", "SF Pro Display"} <= families:
        raise RuntimeError("The bundled SF Pro installer fonts could not be loaded")
    result = ["SF Pro Text", "SF Pro Display"]
    app.setProperty("installerFontFamilies", result)
    return result


def relative_font(widget, scale=1, weight=None):
    font = QFont(widget.font())
    font.setPointSizeF(max(8.5, font.pointSizeF() * scale))
    if weight is not None:
        font.setWeight(weight)
    return font


def paint_glass_control(widget, painter, *, pressed=False):
    """Keep the face even; concentrate reflections along the capsule edge."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    light = widget.window().palette().window().color().lightnessF() > .5
    rect = QRectF(1, 1, widget.width()-2, widget.height()-3)
    radius = rect.height()/2
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(0, 0, 0, 12 if light else 28), 1))
    painter.drawRoundedRect(rect.translated(0, .8), radius, radius)
    alpha = 80 if light else 16
    if widget.underMouse() and widget.isEnabled():
        alpha += 14
    fill = QColor(0, 0, 0, 8) if pressed and light else QColor(255, 255, 255, 9 if pressed else alpha)
    painter.setBrush(fill)
    painter.setPen(QPen(QColor(0, 0, 0, 22) if light else QColor(255, 255, 255, 24), .5))
    painter.drawRoundedRect(rect, radius, radius)
    # Opposing highlights fade around the sides rather than banding the face.
    rim = QLinearGradient(rect.topLeft(), rect.bottomRight())
    for position, alpha in ((0, 240 if light else 125), (.22, 160 if light else 65),
                            (.44, 12), (.62, 6), (.84, 135 if light else 60),
                            (1, 220 if light else 115)):
        rim.setColorAt(position, QColor(255, 255, 255, alpha))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(rim, 1))
    edge = rect.adjusted(.45, .45, -.45, -.45)
    painter.drawRoundedRect(edge, radius-.45, radius-.45)
    if widget.hasFocus() and getattr(widget, "keyboard_focus", False):
        painter.setPen(QPen(QColor(65, 65, 65, 145) if light else QColor(225, 225, 225, 150), 1))
        painter.drawRoundedRect(rect, radius, radius)


class ColorSwatch(QPushButton):
    """Native color choice with the separated selection ring used by Appearance."""

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.setFixedSize(25, 27)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        circle = QRectF(5, 5.5, 16, 16)
        painter.setPen(QPen(QColor(0, 0, 0, 25), .7))
        painter.setBrush(self.color)
        painter.drawEllipse(circle)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.isChecked():
            painter.setPen(QPen(QColor("#007aff"), 2))
            painter.drawEllipse(circle.adjusted(-3, -3, 3, 3))
        elif self.hasFocus():
            painter.setPen(QPen(self.palette().text().color(), 1, Qt.PenStyle.DotLine))
            painter.drawEllipse(circle.adjusted(-3, -3, 3, 3))


class GlassButton(QPushButton):
    def focusInEvent(self, event):
        self.keyboard_focus = event.reason() in (
            Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
            Qt.FocusReason.ShortcutFocusReason)
        super().focusInEvent(event)
        self.update()

    def sizeHint(self):
        return QSize(max(92, self.fontMetrics().horizontalAdvance(self.text())+34), 32)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_glass_control(self, painter, pressed=self.isDown())
        light = self.window().palette().window().color().lightnessF() > .5
        painter.setPen(QColor("#292929" if light else "#eeeeee") if self.isEnabled()
                       else QColor("#777777" if light else "#aaaaaa"))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()


class DetailsButton(GlassButton):
    def sizeHint(self):
        return QSize(44, 30)

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_glass_control(self, painter, pressed=self.isDown())
        painter.setPen(QPen(self.palette().text().color(), 1.5,
                           Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        x, y = self.width() / 2, self.height() / 2 - 1
        direction = -1 if self.isChecked() else 1
        painter.drawPolyline(QPolygonF([QPointF(x-4, y-direction*2),
                                        QPointF(x, y+direction*2),
                                        QPointF(x+4, y-direction*2)]))


class ProgressSpinner(QWidget):
    """A smooth circular progress arc, animated only while visible."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.frame = 0
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)

    def tick(self):
        self.frame = (self.frame + 6) % 360
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.timer.start()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ring = QRectF(3, 3, 18, 18)
        color = QColor(self.palette().text().color())
        color.setAlphaF(.12)
        painter.setPen(QPen(color, 2.2))
        painter.drawEllipse(ring)
        color.setAlphaF(.85)
        painter.setPen(QPen(color, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(ring, (90 - self.frame) * 16, -260 * 16)


class GlassComboBox(QComboBox):
    def focusInEvent(self, event):
        self.keyboard_focus = event.reason() in (
            Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
            Qt.FocusReason.ShortcutFocusReason)
        super().focusInEvent(event)
        self.update()

    def sizeHint(self):
        return QSize(max((self.fontMetrics().horizontalAdvance(self.itemText(i)) for i in range(self.count())), default=0) + 42, 32)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_glass_control(self, painter)
        painter.setPen(self.palette().text().color())
        painter.drawText(QRectF(12, 0, self.width()-36, self.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.fontMetrics().elidedText(self.currentText(), Qt.TextElideMode.ElideRight, self.width()-36))
        x, y = self.width()-15, self.height()/2
        painter.setPen(QPen(self.palette().text().color(), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(x-3, y-1.5), QPointF(x, y+1.5))
        painter.drawLine(QPointF(x, y+1.5), QPointF(x+3, y-1.5))


class GlassSpinBox(QSpinBox):
    def __init__(self):
        super().__init__()
        self.setFixedSize(68, 32)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setStyleSheet("""
            QSpinBox { background: transparent; border: none; }
            QSpinBox::up-button, QSpinBox::down-button {
                subcontrol-origin: border; width: 23px; height: 16px;
            }
            QSpinBox::up-button { subcontrol-position: top right; }
            QSpinBox::down-button { subcontrol-position: bottom right; }
        """)
        self.lineEdit().setStyleSheet("background: transparent; border: none;")
        self.lineEdit().setTextMargins(7, 0, 5, 0)

    def focusInEvent(self, event):
        self.keyboard_focus = event.reason() in (
            Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
            Qt.FocusReason.ShortcutFocusReason)
        super().focusInEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_glass_control(self, painter)

        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        control = QStyle.ComplexControl.CC_SpinBox
        up = self.style().subControlRect(control, option, QStyle.SubControl.SC_SpinBoxUp, self)
        down = self.style().subControlRect(control, option, QStyle.SubControl.SC_SpinBoxDown, self)
        ink = self.palette().text().color()
        separator = QColor(ink)
        separator.setAlphaF(.18)
        painter.setPen(QPen(separator, .75))
        painter.drawLine(QPointF(up.left(), 6), QPointF(up.left(), self.height() - 7))
        for rect, direction, step in ((up, -1, self.StepEnabledFlag.StepUpEnabled),
                                      (down, 1, self.StepEnabledFlag.StepDownEnabled)):
            color = QColor(ink)
            if not self.isEnabled() or not option.stepEnabled & step:
                color.setAlphaF(.38)
            painter.setPen(QPen(color, 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                                Qt.PenJoinStyle.RoundJoin))
            x, y = rect.center().x() - 1, rect.center().y()
            painter.drawPolyline(QPolygonF([QPointF(x - 3, y - direction * 1.5),
                                            QPointF(x, y + direction * 1.5),
                                            QPointF(x + 3, y - direction * 1.5)]))


class LanguageSelector(GlassComboBox):
    pass


class WindowLight(QPushButton):
    """Use the bundled GTK controls that also theme Nautilus."""
    def __init__(self, parent, action):
        super().__init__(parent)
        self.action = action
        self._pixmaps = {}
        self.setFixedSize(16, 16)
        self.setEnabled(action == "close")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        dark = self.window().palette().window().color().lightnessF() <= .5
        active = self.isEnabled() and self.window().isActiveWindow()
        hover = self.isEnabled() and (self.underMouse() or self.hasFocus())
        state = ("-active" if active and self.isDown() else
                 "-hover" if active and hover else "" if active else
                 "-backdrop-hover" if hover else "-backdrop")
        mode = "Dark" if dark else "Light"
        action = "restore" if self.action == "maximize" and self.window().isMaximized() else self.action
        if self.window().choices["window_controls"] == "glassy":
            svg_state = ("deactivated" if not self.isEnabled() else
                         {"": "active", "-active": "pressed", "-hover": "hover",
                          "-backdrop-hover": "hover-inactive", "-backdrop": "inactive"}[state])
            key = ("glassy", mode, action, svg_state)
            if key not in self._pixmaps:
                pixmap = QPixmap()
                pixmap.loadFromData(button_svg(action, mode, svg_state).encode(), "SVG")
                self._pixmaps[key] = pixmap
            painter.drawPixmap(self.rect(), self._pixmaps[key])
            return
        filename = f"titlebutton-{action}{state}{'-dark' if dark else ''}@2.png"
        key = (mode, filename)
        if key not in self._pixmaps:
            asset = (Path(__file__).resolve().parents[1] / "offline/gtk" /
                     f"MacTahoeLiquidKde-{mode}" / "gtk-4.0/windows-assets" / filename)
            self._pixmaps[key] = QPixmap(str(asset))
        painter.drawPixmap(self.rect(), self._pixmaps[key])

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()


class WindowHeader(QWidget):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()
            event.accept()
        else:
            super().mousePressEvent(event)


class HistoryControl(QWidget):
    def __init__(self, back, forward):
        super().__init__()
        self.setObjectName("settingsHistoryControl")
        row = QHBoxLayout(self)
        row.setContentsMargins(3, 2, 3, 3)
        row.setSpacing(1)
        row.addWidget(back)
        row.addWidget(forward)
        self.setFixedSize(row.sizeHint())

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_glass_control(self, painter)


class HistoryButton(QPushButton):
    def __init__(self, direction):
        super().__init__()
        self.direction = direction
        self.setFixedSize(27, 24)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().buttonText().color()
        if not self.isEnabled():
            color.setAlphaF(.36)
        painter.setPen(QPen(color, 1.7, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        x, y = self.width() / 2, self.height() / 2
        tip = 2.5 * self.direction
        painter.drawPolyline(QPolygonF([QPointF(x - tip, y - 4.5), QPointF(x + tip, y),
                                        QPointF(x - tip, y + 4.5)]))


class CheckOption(QCheckBox):
    """Keep native checkbox behavior with the same mark as selection cards."""
    content_margin = 0
    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text())+26+2*self.content_margin,
                     max(32, self.fontMetrics().height()+14))

    def hitButton(self, point):
        return self.rect().contains(point)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.content_margin, 0)
        accent = QColor(self.window().accent)
        y = (self.height()-16)/2
        box = QRectF(1, y, 16, 16)
        painter.setPen(QPen(accent if self.isChecked() or self.hasFocus() else QColor(self.window().line), 1))
        painter.setBrush(accent if self.isChecked() else self.palette().base())
        painter.drawRoundedRect(box, 4, 4)
        if self.isChecked():
            painter.setPen(QPen(Qt.GlobalColor.white, 1.5, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            path = QPainterPath(QPointF(5, y+8)); path.lineTo(8, y+11); path.lineTo(13, y+5)
            painter.drawPath(path)
        painter.setPen(self.palette().text().color())
        painter.drawText(QRectF(26, 0, self.width()-26-2*self.content_margin, self.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())


class GlassCheckOption(CheckOption):
    content_margin = 12

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_glass_control(self, painter, pressed=self.isDown())
        painter.end()
        super().paintEvent(event)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()


class RadioOption(QRadioButton):
    content_margin = 0
    sizeHint = CheckOption.sizeHint
    hitButton = CheckOption.hitButton

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        accent = QColor(self.window().accent)
        center = QPointF(9, self.height()/2)
        painter.setPen(QPen(accent if self.isChecked() or self.hasFocus() else QColor(self.window().line), 1))
        painter.setBrush(self.palette().base())
        painter.drawEllipse(center, 7.5, 7.5)
        if self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(accent)
            painter.drawEllipse(center, 4, 4)
        painter.setPen(self.palette().text().color())
        painter.drawText(QRectF(26, 0, self.width()-26, self.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())


class StepDots(QWidget):
    """Paint equally spaced indicators independently of the active system font."""
    def __init__(self):
        super().__init__()
        self.index = 1
        self.count = len(STEPS) - 1
        self.setFixedSize(132, 20)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(1, self.count + 1):
            active = index == self.index
            painter.setBrush(self.palette().windowText() if active else self.palette().mid())
            radius = 3 if active else 2
            painter.drawEllipse(QPointF(5 + (index - 1) * (self.width() - 10) / max(1, self.count - 1), 10), radius, radius)


class PreviewImage(QWidget):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.pixmap = pixmap
        self.cover = False
        self.setFixedHeight(round(pixmap.deviceIndependentSize().height()))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # The image canvas has the card's exact aspect ratio; the source was
        # contained by picture(), so no desktop edges are lost here.
        window = self.window()
        if window.page in INSTALL_SECTIONS and not window.settings_mode:
            size = self.pixmap.size()
            fit = Qt.AspectRatioMode.KeepAspectRatioByExpanding if self.cover else Qt.AspectRatioMode.KeepAspectRatio
            size.scale(self.size(), fit)
            bounds = QRectF(self.rect())
            target = QRectF(0, 0, size.width(), size.height())
            target.moveCenter(bounds.center())
            painter.drawPixmap(target, self.pixmap, QRectF(self.pixmap.rect()))
        else:
            painter.drawPixmap(self.rect(), self.pixmap)


class ChoiceCard(QPushButton):
    def __init__(self, title, detail, pixmap, checked, parent=None, *, independent=False, compact=False,
                 small_caption=False):
        super().__init__(parent)
        self.setFont(parent.window().font())
        self.independent = independent
        self.caption_minimum = 34 if small_caption else 42 if compact or not detail else 58
        self.photo = None
        self.row_cards = [self]
        self.setCheckable(True)
        self.setChecked(checked)
        self.setAccessibleName(title)
        self.setAccessibleDescription(detail)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        if pixmap:
            self.photo = PreviewImage(pixmap)
            layout.addWidget(self.photo)
        copy = QWidget()
        copy.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text = QVBoxLayout(copy)
        if small_caption:
            text.setContentsMargins(10, 8, 34, 8)
        else:
            text.setContentsMargins(15, 11 if compact else 13, 40, 11 if compact else 14)
        text.setSpacing(4)
        label = QLabel(title)
        label.setWordWrap(True)
        label.setFont(relative_font(self, .64 if small_caption else .86,
                                    QFont.Weight.Medium if small_caption else QFont.Weight.DemiBold))
        text.addWidget(label)
        if detail:
            description = QLabel(detail)
            description.setWordWrap(True)
            description.setFont(relative_font(self, .79))
            description.setObjectName("detail")
            text.addWidget(description)
        copy.setMinimumHeight(self.caption_minimum)
        layout.addWidget(copy)
        self.copy = copy
        self.setFixedHeight(layout.sizeHint().height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.size().width() == event.oldSize().width():
            return
        # Translated descriptions can wrap to different line counts. Reserve
        # the tallest caption and preview for every card in the same row.
        copy_height = max(max(card.caption_minimum,
                              card.copy.layout().heightForWidth(card.width()-2))
                          for card in self.row_cards)
        height = max((round((card.width()-2) * card.photo.pixmap.height()
                            / card.photo.pixmap.width()) if card.photo else 0)
                     for card in self.row_cards)
        for card in self.row_cards:
            card.copy.setFixedHeight(copy_height)
            if card.photo:
                card.photo.setFixedHeight(height)
                path = QPainterPath()
                path.addRoundedRect(QRectF(0, 0, card.width()-2, height+8), 7, 7)
                card.photo.setMask(QRegion(path.toFillPolygon().toPolygon()))
            card.setFixedHeight(height + copy_height + 2)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        accent = QColor(self.window().accent)
        focused = self.hasFocus()
        checked = self.isChecked()
        border = accent if checked or focused else QColor(self.window().line)
        dashed = self.window().settings_mode and focused and not checked
        pen_style = Qt.PenStyle.DashLine if dashed else Qt.PenStyle.SolidLine
        painter.setPen(QPen(border, 2 if not dashed and (checked or focused) else 1, pen_style))
        painter.setBrush(self.palette().base())
        painter.drawRoundedRect(QRectF(1, 1, self.width()-2, self.height()-2), 8, 8)
        caption_center = self.copy.geometry().center().y()
        indicator = QRectF(self.width()-31, caption_center-9, 18, 18)
        painter.setPen(QPen(accent if self.isChecked() else QColor(self.window().line), 1))
        painter.setBrush(accent if self.isChecked() else self.palette().base())
        if self.independent:
            painter.drawRoundedRect(indicator, 4, 4)
        else:
            painter.drawEllipse(indicator)
        if self.isChecked():
            painter.setPen(QPen(Qt.GlobalColor.white, 1.6, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            path = QPainterPath(QPointF(indicator.x()+5, indicator.y()+9))
            path.lineTo(indicator.x()+8, indicator.y()+12)
            path.lineTo(indicator.x()+13, indicator.y()+6)
            painter.drawPath(path)

    def keyPressEvent(self, event):
        arrows = (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down)
        if event.key() in arrows and self.group():
            buttons = self.group().buttons()
            direction = -1 if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up) else 1
            target = buttons[(buttons.index(self) + direction) % len(buttons)]
            target.setFocus(); target.click(); event.accept()
            return
        super().keyPressEvent(event)


class OpaqueSurface(QWidget):
    """Paint the entire dirty region, including when a transparent style is active."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.surface_color = QColor(self.palette().window().color())
        self.top_border = None
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def paintEvent(self, event):
        painter = QPainter(self)
        color = QColor(self.surface_color)
        color.setAlpha(255)
        painter.fillRect(event.rect(), color)
        if self.top_border is not None:
            painter.setPen(self.top_border)
            painter.drawLine(0, 0, self.width(), 0)


class WizardFrame(QWidget):
    """Finish the shared install/remove window after its opaque pages paint."""
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, event):
        if self.window().isMaximized() or self.window().isFullScreen():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.rect())
        inset = 0.375
        left, top = inset, inset
        right, bottom = bounds.width() - inset, bounds.height() - inset
        radius = 28 - inset
        # Tangent handles follow the installed 28-unit continuous window corner.
        handle = radius * 0.73
        path = QPainterPath(QPointF(left + radius, top))
        path.lineTo(right - radius, top)
        path.cubicTo(right - radius + handle, top, right, top + radius - handle, right, top + radius)
        path.lineTo(right, bottom - radius)
        path.cubicTo(right, bottom - radius + handle, right - radius + handle, bottom, right - radius, bottom)
        path.lineTo(left + radius, bottom)
        path.cubicTo(left + radius - handle, bottom, left, bottom - radius + handle, left, bottom - radius)
        path.lineTo(left, top + radius)
        path.cubicTo(left, top + radius - handle, left + radius - handle, top, left + radius, top)
        path.closeSubpath()
        outside = QPainterPath()
        outside.addRect(bounds)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillPath(outside.subtracted(path), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        highlight = QLinearGradient(0, top, 0, bottom)
        highlight.setColorAt(0, QColor(142, 142, 142, 148))
        highlight.setColorAt(1, QColor(98, 98, 98, 187))
        painter.strokePath(path, QPen(highlight, 2 * inset))



class PageScrollArea(QScrollArea):
    def __init__(self):
        super().__init__()
        self.surface_color = QColor(self.palette().window().color())
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def paintEvent(self, event):
        # QAbstractScrollArea redirects viewport paint events here.
        painter = QPainter(self.viewport())
        color = QColor(self.surface_color)
        color.setAlpha(255)
        painter.fillRect(event.rect(), color)


def installer_palette(dark):
    """The wizard owns its colors; desktop settings only select light or dark."""
    palette = QPalette(QApplication.style().standardPalette())
    colors = {
        QPalette.ColorRole.Window: "#292929" if dark else "#f6f6f6",
        QPalette.ColorRole.Base: "#333333" if dark else "#ffffff",
        QPalette.ColorRole.AlternateBase: "#383838" if dark else "#eeeeee",
        QPalette.ColorRole.Button: "#333333" if dark else "#f6f6f6",
        QPalette.ColorRole.WindowText: "#eeeeee" if dark else "#292929",
        QPalette.ColorRole.Text: "#eeeeee" if dark else "#292929",
        QPalette.ColorRole.ButtonText: "#eeeeee" if dark else "#292929",
        QPalette.ColorRole.ToolTipBase: "#333333" if dark else "#ffffff",
        QPalette.ColorRole.ToolTipText: "#eeeeee" if dark else "#292929",
        QPalette.ColorRole.Highlight: "#007aff",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.Link: "#007aff",
        QPalette.ColorRole.LinkVisited: "#af52de",
        QPalette.ColorRole.Mid: "#626262" if dark else "#c9c9c9",
        QPalette.ColorRole.Light: "#626262" if dark else "#ffffff",
        QPalette.ColorRole.Dark: "#191919" if dark else "#a0a0a0",
        QPalette.ColorRole.Shadow: "#121212" if dark else "#686868",
        QPalette.ColorRole.PlaceholderText: "#bcbcbc" if dark else "#686868",
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#aaaaaa" if dark else "#777777"))
    return palette


class InstallerWindow(OpaqueSurface):
    def __init__(self, bridge, *, uninstall=False, mode="install", section="appearance", widget=None):
        # Fusion ships with Qt. Use it only in this installer process so native
        # controls cannot acquire Breeze/Kvantum geometry or transparent fills.
        app = QApplication.instance()
        desktop_palette = QPalette(app.palette())
        desktop_font = app.property("installerDesktopFont") or QFont(app.font())
        app.setProperty("installerDesktopFont", desktop_font)
        text_family, display_family = installer_fonts(app)
        ui_font = QFont(desktop_font)
        ui_font.setFamily(text_family)
        dark = desktop_palette.window().color().lightnessF() <= .5
        app.setStyle("Fusion")
        app.setPalette(installer_palette(dark))
        app.setFont(ui_font)
        super().__init__()
        self.setPalette(installer_palette(dark))
        self.bridge = bridge
        self._display_family = display_family
        self._log_font = QFont(ui_font)
        self._operation_started = None
        self._details_expanded = False
        self._eta_timer = QTimer(self)
        self._eta_timer.setInterval(1000)
        self._eta_timer.timeout.connect(self.refresh_progress)
        self.defaults = defaults()
        self.defaults["wallpaper_explicit"] = False
        self.choices = dict(self.defaults)
        self.edition = "Golden Gate" if bridge.editionName == "MacGoldenGate" else "Tahoe"
        self.asset_edition = "golden-gate" if self.edition == "Golden Gate" else "tahoe"
        self.settings_mode = mode == "settings"
        self.requested_widget = widget
        self.requested_weather_panel = self.settings_mode and section == "weather_panel"
        self.requested_desktop_widget = self.settings_mode and section == "desktop_widget"
        self.acrylic_glass_editor = None
        self.requested_glass_editor = self.settings_mode and section == "acrylic_glass"
        section = SECTION_ALIASES.get(section, section)
        self.page = section if self.settings_mode else "uninstall" if uninstall else "welcome"
        self.requested_install_panel = None
        self.panel_frames = {}
        self.settings_baseline = None
        self.reconfiguring = False
        self.appearance_process = None
        self.appearance_error = ""
        if self.settings_mode:
            self.load_settings_choices()
        self.editing = False
        self.action = "install"
        self.close_pending = False
        self.update_available = ""
        self.updating = False
        self.groups = []
        self.setObjectName("installerWindow")
        self.setWindowTitle(self.t("Install") + " " + self.edition)
        # Honor the desktop text scale while using the installer’s SF family.
        self.settings_font = relative_font(self)
        self.setFont(self.settings_font)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.resize(900, 680)
        self.setMinimumSize(820, 640)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.header = WindowHeader(self)
        self.header.setFixedHeight(44)
        lights = QHBoxLayout(self.header)
        lights.setContentsMargins(14, 14, 14, 14)
        lights.setSpacing(8)
        self.close_button = WindowLight(self.header, "close")
        self.close_button.setObjectName("closeButton")
        self.close_button.clicked.connect(self.close)
        lights.addWidget(self.close_button)
        self.minimize_button = WindowLight(self.header, "minimize")
        lights.addWidget(self.minimize_button)
        self.maximize_button = WindowLight(self.header, "maximize")
        self.minimize_button.clicked.connect(self.showMinimized)
        self.maximize_button.clicked.connect(self.toggle_maximized)
        lights.addWidget(self.maximize_button)
        lights.addStretch()
        self.layout.addWidget(self.header)

        self.main_row = QHBoxLayout()
        self.main_row.setSpacing(0)
        self.layout.addLayout(self.main_row, 1)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("settingsSidebar")
        self.sidebar.setFixedWidth(176)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(0, 0, 1, 0)
        self.sidebar_layout.setSpacing(0)
        navigation = QWidget()
        sidebar = QVBoxLayout(navigation)
        sidebar.setContentsMargins(9, 1, 9, 12)
        sidebar.setSpacing(2)
        self.sidebar_layout.addWidget(navigation, 1)
        self.search = QLineEdit()
        self.search.setObjectName("settingsSearch")
        self.search.setFont(relative_font(self, .8))
        self.search.setClearButtonEnabled(True)
        self.search.addAction(QIcon.fromTheme("edit-find"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self.filter_settings)
        self.search.returnPressed.connect(self.open_search_result)
        sidebar.addWidget(self.search)
        sidebar.addSpacing(9)
        self.section_buttons = {}
        for page, (_, symbol, colors, _) in SETTINGS_PAGES.items():
            button = QPushButton()
            button.setObjectName("section-" + page)
            button.setProperty("navigation", "section")
            button.setFont(relative_font(self, .80, QFont.Weight.Medium))
            button.setIconSize(QSize(18, 18))
            button.setIcon(settings_icon(symbol, colors))
            button.setCheckable(True)
            button.clicked.connect(lambda _, target=page: self.navigate_settings(target))
            sidebar.addWidget(button)
            self.section_buttons[page] = button
        self.no_results = self.label("No matching settings")
        self.no_results.setObjectName("detail")
        sidebar.addWidget(self.no_results)
        sidebar.addStretch()
        self.main_row.addWidget(self.sidebar)
        self.find_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.Find), self)
        self.find_shortcut.activated.connect(self.focus_search)
        self.history_shortcuts = []
        for standard, key, direction in ((QKeySequence.StandardKey.Back, "Alt+Left", -1),
                                         (QKeySequence.StandardKey.Forward, "Alt+Right", 1)):
            shortcut = QShortcut(self)
            keys = QKeySequence.keyBindings(standard)
            explicit = QKeySequence(key)
            if explicit not in keys:
                keys.append(explicit)
            shortcut.setKeys(keys)
            shortcut.activated.connect(lambda offset=direction: self.move_settings_history(offset))
            self.history_shortcuts.append(shortcut)
        self.settings_history = [(section, 0)]
        self.settings_index = 0
        self.rendered_settings_index = None
        content_column = QVBoxLayout()
        content_column.setSpacing(0)
        self.main_row.addLayout(content_column, 1)
        self.settings_toolbar = WindowHeader(self)
        self.settings_toolbar.setObjectName("settingsToolbar")
        self.settings_toolbar.setFixedHeight(41)
        toolbar = QHBoxLayout(self.settings_toolbar)
        toolbar.setContentsMargins(12, 5, 14, 5)
        toolbar.setSpacing(3)
        self.settings_back = HistoryButton(-1)
        self.settings_back.setObjectName("settingsBack")
        self.settings_back.clicked.connect(lambda: self.move_settings_history(-1))
        self.settings_forward = HistoryButton(1)
        self.settings_forward.setObjectName("settingsForward")
        self.settings_forward.clicked.connect(lambda: self.move_settings_history(1))
        toolbar.addWidget(HistoryControl(self.settings_back, self.settings_forward))
        toolbar.addSpacing(6)
        self.settings_review = GlassButton()
        self.settings_review.setObjectName("settingsReview")
        self.settings_review.setFont(relative_font(self, .78, QFont.Weight.DemiBold))
        self.settings_review.clicked.connect(self.review_settings_changes)
        self.settings_title = self.label("")
        self.settings_title.setFont(relative_font(self, .91, QFont.Weight.DemiBold))
        toolbar.addWidget(self.settings_title, 1)
        toolbar.addWidget(self.settings_review)
        content_column.addWidget(self.settings_toolbar)
        self.scroll = PageScrollArea()
        self.scroll.setObjectName("pageScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        content_column.addWidget(self.scroll, 1)
        self.footer = OpaqueSurface()
        self.footer.setObjectName("footer")
        self.footer_layout = QGridLayout(self.footer)
        self.footer_layout.setContentsMargins(24, 16, 24, 16)
        self.footer_layout.setVerticalSpacing(6)
        self.version_label = QLabel(f"v{bridge.version}")
        self.version_label.setObjectName("versionLabel")
        self.version_label.setFont(relative_font(self, .75))
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_layout.addWidget(self.version_label, 0, 1)
        self.footer_layout.setColumnStretch(0, 1)
        self.footer_layout.setColumnStretch(2, 1)
        self.back = GlassButton()
        self.back.setObjectName("backButton")
        self.back.setFont(relative_font(self, .86))
        self.back.setFixedHeight(32)
        self.back.clicked.connect(self.previous)
        self.footer_layout.addWidget(self.back, 1, 0, Qt.AlignmentFlag.AlignLeft)
        self.language = self.language_selector()
        self.welcome_actions = QWidget()
        welcome_layout = QHBoxLayout(self.welcome_actions)
        welcome_layout.setContentsMargins(0, 0, 0, 0)
        welcome_layout.setSpacing(12)
        welcome_layout.addWidget(self.language)
        self.express = GlassButton()
        self.express.setObjectName("expressButton")
        self.express.setFont(relative_font(self, .86))
        self.express.setFixedHeight(32)
        self.express.clicked.connect(self.express_install)
        welcome_layout.addWidget(self.express)
        self.footer_layout.addWidget(self.welcome_actions, 1, 1, Qt.AlignmentFlag.AlignCenter)
        self.dots = StepDots()
        self.dots.setObjectName("stepDots")
        self.footer_layout.addWidget(self.dots, 1, 1, Qt.AlignmentFlag.AlignCenter)
        self.next = GlassButton()
        self.next.setObjectName("nextButton")
        self.next.setFont(relative_font(self, .86, QFont.Weight.DemiBold))
        self.next.setFixedHeight(32)
        self.next.setDefault(True)
        self.next.clicked.connect(self.advance)
        self.footer_layout.addWidget(self.next, 1, 2, Qt.AlignmentFlag.AlignRight)
        self.layout.addWidget(self.footer)
        self.frame_edge = WizardFrame(self)
        self.frame_edge.setGeometry(self.rect())
        app.styleHints().colorSchemeChanged.connect(self.system_scheme_changed)
        # KDE replaces kdeglobals atomically. Watch its directory so the next
        # switch is observed even after a new inode replaces the original.
        config = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.ConfigLocation)
        self.desktop_config = Path(config) / "kdeglobals"
        from theme_switch import _appearance_state_path
        self.appearance_state = _appearance_state_path()
        if self.desktop_config.is_file() or self.appearance_state.parent.is_dir():
            self.config_timer = QTimer(self)
            self.config_timer.setSingleShot(True)
            self.config_timer.setInterval(150)
            self.config_timer.timeout.connect(self.refresh_desktop_scheme)
            self.config_timer.timeout.connect(self.refresh_settings_appearance)
            dirs = [str(path) for path in (Path(config), self.appearance_state.parent) if path.is_dir()]
            self.config_watcher = QFileSystemWatcher(dirs, self)
            self.config_watcher.directoryChanged.connect(lambda _: self.config_timer.start())
        bridge.runningChanged.connect(self.refresh_window_controls)
        bridge.finished.connect(self.finished)
        bridge.progressChanged.connect(self.refresh_progress)
        bridge.summaryChanged.connect(self.refresh_progress)
        bridge.currentStepChanged.connect(self.refresh_progress)
        bridge.logAppended.connect(self.append_log)
        bridge.updateChecked.connect(self.update_checked)
        bridge.updateReturned.connect(self.update_returned)
        self.configure_window_mode()
        self.render()
        if self.settings_mode:
            self.focus_search()
        else:
            self.next.setFocus(Qt.FocusReason.OtherFocusReason)

    def focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def visible_steps(self):
        if self.page in PANEL_SECTIONS:
            return [page for page, _ in STEPS if page != "glass_style" or self.show_glass_style()]
        return INSTALL_FLOW

    def configure_window_mode(self):
        self.sidebar.setVisible(self.settings_mode)
        self.settings_toolbar.setVisible(self.settings_mode)
        self.footer.setVisible(not self.settings_mode)
        font = QFont(self.settings_font)
        if not self.settings_mode:
            font.setPointSizeF(max(8.5, font.pointSizeF() * .96))
        self.setFont(font)
        self.find_shortcut.setEnabled(self.settings_mode)
        for shortcut in self.history_shortcuts:
            shortcut.setEnabled(self.settings_mode)
        if self.settings_mode:
            self.layout.removeWidget(self.header)
            self.sidebar_layout.insertWidget(0, self.header)
            self.header.show()
            self.setMinimumSize(700, 425)
            self.resize(790, 535)
        else:
            self.sidebar_layout.removeWidget(self.header)
            self.layout.insertWidget(0, self.header)
            self.header.show()
            self.setMinimumSize(820, 640)
            self.resize(900, 680)

    def navigate_settings(self, page):
        if not self.settings_mode or page not in SETTINGS_PAGES:
            return
        if page == self.page:
            self.section_buttons[page].setChecked(True)
            return
        del self.settings_history[self.settings_index + 1:]
        self.settings_history.append((page, 0))
        self.settings_index += 1
        self.page = page
        self.render()

    def move_settings_history(self, direction):
        index = self.settings_index + direction
        if self.settings_mode and 0 <= index < len(self.settings_history):
            self.settings_index = index
            self.page, _ = self.settings_history[index]
            if self.section_buttons[self.page].isHidden():
                self.search.clear()
            self.render()

    def filter_settings(self):
        query = search_text(self.search.text()).split()
        matches = []
        for page, button in self.section_buttons.items():
            title, _, _, panels = SETTINGS_PAGES[page]
            terms = (title, *(PANEL_LABELS[panel] for panel in panels))
            if page == "general":
                terms += ("Language",)
            elif page == "theme":
                terms += ("Light", "Dark", "Auto", "Icon appearance", "Icon color palette", "Tinted")
            elif page == "desktop":
                terms += ("Weather (Panel)", "Temperature unit", "Widget settings", "Clock", "Timer", "Photos")
            elif page == "dock_bar":
                from system_menu_preferences import FORMS as system_menu_forms

                terms += tuple(label for form in system_menu_forms.values() for label in form.values())
                terms += ("Trash", "Empty trash icon", "Full trash icon", "Dock icons",
                          "System menu",
                          "Apps preferences", "Open from Apps", "Launcher position", "Grid icon size",
                          "Activation shortcut", "Hover magnification", "Control Center", "Widget shortcuts",
                          "Wi-Fi", "Bluetooth", "Battery", "Downloads", "Notifications")
            keywords = search_text(" ".join((*terms, *(self.t(term) for term in terms))))
            match = all(term in keywords for term in query)
            button.setVisible(match)
            if match:
                matches.append(page)
        self.no_results.setVisible(not matches)
        return matches

    def open_search_result(self):
        matches = self.filter_settings()
        if matches:
            self.navigate_settings(matches[0])
            self.section_buttons[matches[0]].setFocus()

    def sync_appearance_choice(self):
        from theme_switch import _read_appearance_state
        state = _read_appearance_state()
        selection = state.get("preference")
        if selection == "native-auto":
            selection = "auto"
        if selection not in ("light", "dark", "auto"):
            selection = "dark" if self.palette().window().color().lightnessF() <= .5 else "light"
        self.choices["appearance"] = selection

    def refresh_settings_appearance(self):
        if self.settings_mode and self.appearance_process is None:
            before = self.choices["appearance"]
            self.sync_appearance_choice()
            if self.settings_baseline is not None:
                self.settings_baseline["appearance"] = self.choices["appearance"]
            if before != self.choices["appearance"] and self.page == "theme":
                self.render()

    def apply_appearance_choice(self, value):
        if self.appearance_process is not None:
            return
        binary = shutil.which("mac-tahoe-theme-switch")
        if binary is None:
            local = Path.home() / ".local/bin/mac-tahoe-theme-switch"
            if os.access(local, os.X_OK):
                binary = str(local)
        if binary is None:
            self.appearance_error = "Install the theme to change the desktop appearance."
            self.render()
            return
        process = QProcess(self)
        self.appearance_process = process
        self.appearance_error = ""
        process.finished.connect(lambda code, _: self.appearance_applied(code))
        process.errorOccurred.connect(
            lambda error: self.appearance_applied(1) if error == QProcess.ProcessError.FailedToStart else None)
        self.render()
        process.start(binary, [value])

    def appearance_applied(self, code):
        process = self.appearance_process
        self.appearance_process = None
        process.deleteLater()
        self.appearance_error = "" if code == 0 else "Could not apply the appearance. Try again."
        self.sync_appearance_choice()
        if self.settings_baseline is not None:
            self.settings_baseline["appearance"] = self.choices["appearance"]
        self.render()

    def load_settings_choices(self, applied=None):
        from installer_choices import installed_choices
        saved = applied if applied is not None else installed_choices()
        self.choices = dict(self.defaults if saved is None else saved)
        self.choices.update(reset_layout=False, wallpaper_explicit=False)
        self.sync_appearance_choice()
        self.settings_baseline = dict(self.choices) if saved is not None else None

    def update_settings_review(self):
        self.settings_review.setVisible(self.settings_mode and self.settings_baseline is not None
                                        and self.choices != self.settings_baseline)

    def review_settings_changes(self):
        if self.settings_baseline is None or self.choices == self.settings_baseline:
            return
        self.reconfiguring = True
        self.settings_mode = False
        self.page = "summary"
        self.configure_window_mode()
        self.render()

    def open_installed_settings(self):
        self.settings_mode = True
        if hasattr(self, "config_watcher") and self.appearance_state.parent.is_dir():
            directory = str(self.appearance_state.parent)
            if directory not in self.config_watcher.directories():
                self.config_watcher.addPath(directory)
        if not self.reconfiguring:
            self.settings_history = [("theme", 0)]
            self.settings_index = 0
            self.rendered_settings_index = None
        target, _ = self.settings_history[self.settings_index]
        self.load_settings_choices(self.choices)
        self.reconfiguring = False
        self.configure_window_mode()
        self.page = target
        self.render()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.settings_mode:
            # This part of the window can blend with the desktop compositor.
            # The search field and lettering remain above the translucent tint.
            painter = QPainter(self)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(self.sidebar.geometry().intersected(event.rect()), Qt.GlobalColor.transparent)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.frame_edge.setGeometry(self.rect())

    def refresh_desktop_scheme(self):
        settings = QSettings(str(self.desktop_config), QSettings.Format.IniFormat)
        rgb = settings.value("Colors:Window/BackgroundNormal")
        if isinstance(rgb, list) and len(rgb) >= 3:
            try:
                color = QColor(*(int(v) for v in rgb[:3]))
            except (TypeError, ValueError):
                return
            if color.isValid():
                self.system_scheme_changed(Qt.ColorScheme.Dark if color.lightnessF() <= .5 else Qt.ColorScheme.Light)

    def system_scheme_changed(self, scheme):
        if scheme == Qt.ColorScheme.Unknown:
            return
        dark = scheme == Qt.ColorScheme.Dark
        if dark != (self.surface_color.lightnessF() <= .5):
            self.setPalette(installer_palette(dark))
            self.render()
            self.frame_edge.update()

    def express_install(self):
        if self.page != "welcome" or self.bridge.running or self.updating:
            return
        self.choices = dict(self.defaults)
        self.editing = False
        self.action = "install"
        self.page = "summary"
        self.render()
        self.next.setFocus(Qt.FocusReason.OtherFocusReason)

    def toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def refresh_window_controls(self):
        self.close_button.setEnabled(not self.bridge.running and self.appearance_process is None)
        self.minimize_button.setEnabled(self.settings_mode)
        self.maximize_button.setEnabled(self.settings_mode)
        self.maximize_button.setAccessibleName(self.t("Restore" if self.isMaximized() else "Maximize"))
        self.minimize_button.setAccessibleName(self.t("Minimize"))
        for light in self.header.findChildren(WindowLight):
            light.setToolTip(light.accessibleName())
            light.update()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.ActivationChange, QEvent.Type.WindowStateChange) and hasattr(self, "header"):
            self.refresh_window_controls()

    def update_checked(self, status):
        self.update_available = status.get("latest", "") if status.get("available") else ""
        if self.page == "welcome":
            self.render()

    def update_returned(self):
        self.updating = False
        self.render()

    def update_installer(self):
        self.updating = True
        self.render()
        self.bridge.updateInstaller()

    def t(self, text):
        from wizard_translations import wizard_translate
        return wizard_translate(text, self.bridge.language)

    def language_selector(self):
        control = LanguageSelector()
        control.setObjectName("languageSelector")
        control.setFont(relative_font(self, .86))
        for item in self.bridge.languages:
            control.addItem(item["label"], item["code"])
        control.setCurrentIndex(max(0, control.findData(self.bridge.language)))
        control.currentIndexChanged.connect(control.updateGeometry)
        control.currentIndexChanged.connect(lambda: self.change_language(control.currentData()))
        return control

    def change_language(self, code):
        if self.bridge.setLanguage(code):
            self.render()

    def label(self, text, *, heading=False):
        widget = QLabel(self.t(text))
        widget.setFont(self.font())
        widget.setWordWrap(True)
        widget.setTextFormat(Qt.TextFormat.PlainText)
        if heading:
            font = widget.font(); font.setFamily(self._display_family)
            font.setPointSizeF(font.pointSizeF() * 1.36)
            font.setWeight(QFont.Weight.DemiBold); widget.setFont(font)
            widget.setObjectName("pageTitle")
        return widget

    def image(self, filename, width=730, height=270, other=None, *, background=None):
        widget = QLabel()
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if self.page in (SECTIONS if self.settings_mode else INSTALL_SECTIONS) and width > 460:
            available = 448 if self.settings_mode else 682
            height = round(height * available / width)
            width = available
        pixmap = picture(filename, width, height, other)
        if background:
            canvas = QPixmap(pixmap.size()); canvas.setDevicePixelRatio(pixmap.devicePixelRatio())
            canvas.fill(QColor(background))
            painter = QPainter(canvas); painter.drawPixmap(0, 0, pixmap); painter.end()
            pixmap = canvas
        widget.setPixmap(pixmap)
        return widget

    def ordered(self, key, values):
        return sorted(values, key=lambda value: value != self.defaults[key])

    def bind_choice(self, key, value, button):
        self.choice_widgets.setdefault(key, []).append((value, button))

    def select(self, key, value):
        if self.settings_mode and key == "appearance":
            self.apply_appearance_choice(value)
            return
        self.update_choice(key, value)
        if key == "wallpaper":
            self.choices["wallpaper_explicit"] = True
        if key == "window_controls":
            self.refresh_window_controls()
            for position, card in self.choice_widgets.get("button_position", ()):
                card.photo.pixmap = self.button_position_sample(position)
                card.photo.update()
        controls = self.choice_widgets.get(key, [])
        groups = {button.group() for _, button in controls if button.group()}
        for group in groups:
            group.setExclusive(False)
        try:
            for selected, button in controls:
                button.setChecked(selected == value)
        finally:
            for group in groups:
                group.setExclusive(True)
        if key == "color" and "icons" in self.choice_widgets:
            self.glass_preview.setIcon(self.icon_sample("glass"))
        elif key == "wallpaper":
            self.wallpaper_filename.setText(Path(self.choices["wallpaper_path"]).name)
            self.wallpaper_filename.setVisible(value == "custom")
        elif key == "dock":
            button = self.content.findChild(QPushButton, "edit-dock-apps")
            if button:
                button.setEnabled(value)
            self.content.findChild(QWidget, "dock-visibility").setEnabled(value)
        elif key == "files":
            self.bookmarks.setVisible(value == "nautilus")
        elif key == "oled_care":
            for spin in self.content.findChildren(QSpinBox):
                spin.setEnabled(value)
        if key == "wallpaper":
            self.update_settings_review()

    def update_choice(self, key, value):
        self.choices[key] = value
        self.update_settings_review()
        if key in ("files", "acrylic_glass") and "glass_style" in self.panel_frames:
            self.panel_frames["glass_style"].setVisible(self.show_glass_style())

    def cards(self, key, items, *, columns=2, independent=False, compact=False, default_first=True):
        grid = QGridLayout()
        grid.setHorizontalSpacing(18 if columns == 2 else 14)
        grid.setVerticalSpacing(14)
        group = None
        if not independent:
            group = QButtonGroup(self.content)
            group.setExclusive(True)
            self.groups.append(group)
            if default_first:
                items = sorted(items, key=lambda item: item[0] != self.defaults[key])
        row_cards = []
        for i, (value, title, detail, pixmap) in enumerate(items):
            choice_key = value if independent else key
            checked = self.choices[choice_key] if independent else self.choices[key] == value
            card = ChoiceCard(self.t(title), self.t(detail), pixmap, checked, self.content,
                              independent=independent, compact=compact,
                              small_caption=key == "wallpaper")
            if key == "wallpaper" and card.photo is not None:
                card.photo.cover = True
            card.setObjectName(f"choice-{choice_key}-{value}")
            self.bind_choice(choice_key, True if independent else value, card)
            if group:
                group.addButton(card)
            card.clicked.connect(lambda checked, k=choice_key, v=value:
                                 self.select(k, checked if independent else v))
            grid.addWidget(card, i // columns, i % columns, Qt.AlignmentFlag.AlignTop)
            if i % columns == 0:
                row_cards = []
            row_cards.append(card)
            card.row_cards = row_cards
        self.body.addLayout(grid)
        return group

    def radio(self, key, values, *, inline=False, font_scale=.93, option_layout=None):
        group = QButtonGroup(self.content)
        self.groups.append(group)
        row = option_layout if option_layout is not None else QHBoxLayout() if inline else self.body
        if inline and option_layout is None:
            row.setSpacing(22)
        for value, label in sorted(values, key=lambda item: item[0] != self.defaults[key]):
            button = RadioOption(self.t(label))
            button.setFont(relative_font(self, font_scale))
            button.setObjectName(f"choice-{key}-{value}")
            self.bind_choice(key, value, button)
            button.setChecked(self.choices[key] == value)
            group.addButton(button)
            button.clicked.connect(lambda _, k=key, v=value: self.select(k, v))
            row.addWidget(button, 1 if inline else 0)
        if inline and option_layout is None:
            self.body.addLayout(row)

    def checkbox(self, key, text):
        button = CheckOption(self.t(text))
        button.setFont(relative_font(self, .93))
        button.setObjectName(f"choice-{key}")
        button.setChecked(self.choices[key])
        button.toggled.connect(lambda value: self.update_choice(key, value))
        self.body.addWidget(button)
        return button

    def render(self):
        updates_enabled = self.updatesEnabled()
        self.setUpdatesEnabled(False)
        try:
            self._render()
        finally:
            self.setUpdatesEnabled(updates_enabled)

    def _render(self):
        scroll_bar = self.scroll.verticalScrollBar()
        if self.rendered_settings_index is not None:
            page, _ = self.settings_history[self.rendered_settings_index]
            self.settings_history[self.rendered_settings_index] = (page, scroll_bar.value())
        self.rendered_settings_index = self.settings_index if self.settings_mode else None
        if self.acrylic_glass_editor is not None:
            self.acrylic_glass_editor.hide()
            self.acrylic_glass_editor.setParent(self)
        # Qt stylesheets can resolve child palettes from the application rather
        # than their parent. Keep that application-local palette consistent too.
        QApplication.setPalette(self.palette())
        focused = QApplication.focusWidget()
        focus_name = focused.objectName() if focused else ""
        # The live desktop selects the window palette. Wizard choices affect previews only.
        self.accent = "#007aff"
        light = self.window().palette().window().color().lightnessF() > .5
        surface, footer = ("#f6f6f6", "#eeeeee") if light else ("#292929", "#242424")
        if self.settings_mode:
            surface = "#fbfcfd" if light else "#25262c"
        self.surface_color = QColor(surface)
        self.scroll.surface_color = QColor(surface)
        self.footer.surface_color = QColor(footer)
        self.line = "#c9c9c9" if light else "#626262"
        self.footer.top_border = QColor(self.line)
        muted = "#686868" if light else "#bcbcbc"
        foreground = "#292929" if light else "#eeeeee"
        operation = "Uninstall" if self.page in ("uninstall", "removed") or (self.page in ("progress", "error") and self.action == "uninstall") else "Install"
        title = self.edition + " " + self.t("Settings") if self.settings_mode else self.t(operation) + " " + self.edition
        self.setWindowTitle(title + " · v" + self.bridge.version)
        if self.settings_mode:
            self.settings_title.setText(self.t(SETTINGS_PAGES[self.page][0]))
            self.settings_back.setAccessibleName(self.t("Back"))
            self.settings_forward.setAccessibleName(self.t("Forward"))
            self.settings_back.setToolTip(self.settings_back.accessibleName())
            self.settings_forward.setToolTip(self.settings_forward.accessibleName())
            self.settings_back.setEnabled(self.settings_index > 0)
            self.settings_forward.setEnabled(self.settings_index + 1 < len(self.settings_history))
        self.settings_review.setText(self.t("Review changes"))
        self.update_settings_review()
        self.search.setPlaceholderText(self.t("Search settings"))
        self.search.setAccessibleName(self.t("Search settings"))
        self.no_results.setText(self.t("No matching settings"))
        for page, button in self.section_buttons.items():
            button.setText(self.t(SETTINGS_PAGES[page][0]).replace("&", "&&"))
            button.setChecked(page == self.page)
        self.filter_settings()
        sidebar_top, sidebar_bottom = (("rgba(244, 250, 253, 238)", "rgba(223, 233, 241, 232)") if light
                                       else ("rgba(49, 58, 72, 242)", "rgba(32, 38, 51, 238)"))
        field_surface = "rgba(255, 255, 255, 163)" if light else "rgba(255, 255, 255, 22)"
        hover = "rgba(94, 134, 175, 28)" if light else "rgba(153, 182, 226, 32)"
        selected_top, selected_bottom = ("#267bbc", "#175794") if light else ("#3b78b7", "#2a527f")
        separator = "#e2e7ec" if light else "#3b4049"
        panel_surface = "#f0f3f6" if light else "#30343d"
        self.close_button.setAccessibleName(self.t("Close"))
        self.close_button.setToolTip(self.t("Close"))
        self.refresh_window_controls()
        stylesheet = f"""
            QFrame#settingsSidebar {{
                background: qlineargradient(x1: 0, y1: 0, x2: .75, y2: 1,
                    stop: 0 {sidebar_top}, stop: 1 {sidebar_bottom});
                border-right: 1px solid {separator};
            }}
            QFrame#settingsPanel {{ background: {panel_surface}; border-radius: 10px; }}
            QScrollArea#pageScroll > QScrollBar:vertical,
            QScrollArea#pageScroll QScrollBar:vertical {{ background: transparent; width: 8px; margin: 5px 1px; }}
            QScrollArea#pageScroll QScrollBar::handle:vertical {{
                background: {self.line}; min-height: 24px; border-radius: 3px;
            }}
            QScrollArea#pageScroll QScrollBar::add-line:vertical,
            QScrollArea#pageScroll QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollArea#pageScroll QScrollBar::add-page:vertical,
            QScrollArea#pageScroll QScrollBar::sub-page:vertical {{ background: transparent; }}
            QFrame#optionPanel {{
                background: {panel_surface}; border: 1px solid {separator}; border-radius: 10px;
            }}
            QFrame#settingsOptionPanel {{
                background: {panel_surface}; border: 1px solid {separator}; border-radius: 8px;
            }}
            QTabWidget#widgetPreferenceTabs::pane, QWidget#acrylicGlassEditor QTabWidget::pane {{ border: 0; }}
            QTabWidget#widgetPreferenceTabs QTabBar::tab, QWidget#acrylicGlassEditor QTabBar::tab {{
                background: {field_surface}; color: {muted}; padding: 5px 12px;
                border: 1px solid {separator}; border-radius: 6px;
                margin-right: 4px;
            }}
            QTabWidget#widgetPreferenceTabs QTabBar::tab:selected, QWidget#acrylicGlassEditor QTabBar::tab:selected {{
                background: {hover}; color: {foreground};
            }}
            QTabWidget#widgetPreferenceTabs QTabBar::tab:focus {{ border-color: {self.accent}; }}
            QWidget#acrylicGlassEditor QTabBar::tab:focus {{ border-color: {self.accent}; }}
            QWidget#acrylicGlassEditor QComboBox, QWidget#acrylicGlassEditor QAbstractSpinBox,
            QWidget#acrylicGlassEditor QPlainTextEdit, QWidget#acrylicGlassEditor QPushButton {{
                background: {field_surface}; color: {foreground};
                border: 1px solid {separator}; border-radius: 6px; padding: 4px 6px;
            }}
            QWidget#acrylicGlassEditor QPushButton:enabled:hover {{ background: {hover}; }}
            QWidget#acrylicGlassEditor QPushButton:disabled {{ color: {muted}; }}
            QWidget#acrylicGlassEditor QGroupBox {{
                border: 1px solid {separator}; border-radius: 8px;
                margin-top: 9px; padding: 6px;
            }}
            QWidget#acrylicGlassEditor QGroupBox::title {{
                subcontrol-origin: margin; left: 10px; padding: 0 4px;
            }}
            QWidget[widgetPreferenceRow="true"] QCheckBox {{ padding: 3px 0; }}
            QWidget#settingsToolbar {{
                background: {surface}; border-bottom: 1px solid {separator};
            }}
            QPushButton#settingsBack, QPushButton#settingsForward {{
                color: {foreground}; background: transparent; border: 1px solid transparent;
                border-radius: 10px; padding: 0;
            }}
            QPushButton#settingsBack:enabled:hover, QPushButton#settingsForward:enabled:hover {{ background: {hover}; }}
            QPushButton#settingsBack:pressed, QPushButton#settingsForward:pressed {{ background: {field_surface}; }}
            QPushButton#settingsBack:focus, QPushButton#settingsForward:focus {{ border-color: {self.accent}; }}
            QToolButton[iconStyleChoice="true"] {{
                color: {foreground}; background: transparent;
                border: 1px solid transparent; border-radius: 8px; padding: 5px 7px;
                min-width: 54px;
            }}
            QToolButton[iconStyleChoice="true"]:hover {{ background: {hover}; }}
            QToolButton[iconStyleChoice="true"]:checked {{
                background: {field_surface}; border-color: {self.accent};
            }}
            QToolButton[iconStyleChoice="true"]:focus:!checked {{ border-color: {muted}; }}
            QLineEdit#settingsSearch, QLineEdit#widgetSettingField {{
                background: {field_surface}; color: {foreground};
                border: 1px solid {separator}; border-radius: 8px; padding: 3px 6px;
            }}
            QLineEdit#settingsSearch:focus, QLineEdit#widgetSettingField:focus {{ border-color: {self.accent}; }}
            QKeySequenceEdit QLineEdit {{
                background: {field_surface}; color: {foreground};
                border: 1px solid {separator}; border-radius: 8px; padding: 3px 6px;
            }}
            QKeySequenceEdit QLineEdit:focus {{ border-color: {self.accent}; }}
            QPushButton[navigation="section"] {{
                color: {foreground}; text-align: left; border: 1px solid transparent;
                border-radius: 7px; padding: 3px 6px;
            }}
            QPushButton[navigation="section"]:hover {{ background: {hover}; }}
            QPushButton[navigation="section"]:checked {{
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 {selected_top}, stop: 1 {selected_bottom});
                border-top-color: rgba(255, 255, 255, 45); color: white;
            }}
            QPushButton[navigation="section"]:focus {{ border-color: {self.accent}; }}
            QLabel {{ background: transparent; color: {foreground}; }}
            QLabel#detail, QLabel#versionLabel {{ color: {muted}; }}
            QRadioButton, QCheckBox {{ spacing: 9px; padding: 7px 0; background: transparent; }}
            QRadioButton::indicator, QCheckBox::indicator {{ width: 15px; height: 15px; }}
            QRadioButton::indicator {{ border: 1px solid {self.line}; border-radius: 8px; background: palette(base); }}
            QRadioButton::indicator:checked {{ border: 3px solid {self.accent}; width: 11px; height: 11px; }}
            QComboBox#languageSelector {{ border: 0; background: transparent; }}
            QPushButton#textLink {{ border: 0; background: transparent; color: {self.accent}; padding: 4px 0; }}
            QProgressBar {{ border: 0; border-radius: 4px; background: {self.line}; min-height: 8px; max-height: 8px; }}
            QProgressBar::chunk {{ border-radius: 4px; background: {self.accent}; }}
        """
        if self.styleSheet() != stylesheet:
            self.setStyleSheet(stylesheet)
        self.groups = []
        self.choice_widgets = {}
        self.panel_frames = {}
        self.widget_settings_target = None
        self.content = OpaqueSurface()
        self.content.surface_color = QColor(surface)
        self.content.setObjectName("wizardContent")
        self.content.setPalette(self.palette())
        self.content.setFont(self.font())
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(*((18, 16, 18, 18) if self.settings_mode else (38, 28, 38, 22)))
        self.body.setSpacing(9 if self.settings_mode else 12)
        sections = SECTIONS if self.settings_mode else INSTALL_SECTIONS
        if not self.settings_mode and self.page in INSTALL_SECTIONS:
            self.body.setContentsMargins(28, 20, 28, 22)
        titles = {} if self.settings_mode else (dict(STEPS) | {key: value[0] for key, value in INSTALL_SECTIONS.items()})
        if self.page in titles and titles[self.page]:
            self.body.addWidget(self.label(titles[self.page], heading=True))
            self.body.addSpacing(10)
        if self.page in sections:
            self.page_section()
        else:
            getattr(self, "page_" + self.page)()
        self.body.addStretch()
        self.scroll.setWidget(self.content)
        if self.settings_mode:
            content = self.content
            _, offset = self.settings_history[self.settings_index]

            def position_settings_page():
                if self.content is content:
                    if self.widget_settings_target is not None:
                        self.reveal_requested_widget()
                    else:
                        scroll_bar.setValue(offset)

            QTimer.singleShot(0, position_settings_page)
        elif self.requested_install_panel is not None:
            panel = self.panel_frames.get(self.requested_install_panel)
            self.requested_install_panel = None
            if panel is not None:
                content = self.content

                def reveal_install_panel():
                    if self.content is content:
                        scroll_bar.setValue(max(0, panel.y() - 12))

                QTimer.singleShot(0, reveal_install_panel)
        visible_steps = self.visible_steps()
        index = visible_steps.index(self.page) if self.page in visible_steps else -1
        self.version_label.setVisible(self.page == "welcome")
        self.welcome_actions.setVisible(self.page == "welcome")
        self.express.setText(self.t("Express install"))
        self.express.setToolTip(self.t("Use the defaults and review before installing."))
        self.express.setEnabled(not self.updating and not self.bridge.running)
        self.dots.setVisible(not self.settings_mode and index > 0)
        self.dots.count = len(visible_steps) - 1
        self.dots.index = index
        self.dots.update()
        self.dots.setAccessibleName(self.t("Step") + f" {index}/{len(visible_steps)-1}")
        self.back.setVisible(self.page not in ("progress", "done", "removed"))
        self.back.setText(self.t("Cancel" if self.reconfiguring and self.page == "summary" else "Uninstall" if self.page == "welcome" else "Back"))
        self.next.setText(self.t(
            "Save" if self.editing else
            "Install" if self.page in ("welcome", "summary") else
            "Uninstall" if self.page == "uninstall" else
            "Cancel" if self.page == "progress" else
            "Open Settings" if self.page == "done" and self.install_activated() else
            "Close" if self.page in ("done", "removed") else
            "Retry" if self.page == "error" else "Next"))
        self.next.setEnabled(not self.updating)
        self.back.setEnabled(not self.updating)
        target = self.findChild(QWidget, focus_name) if focus_name else None
        if target:
            target.setFocus()

    def separator(self):
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {self.line};")
        self.body.addWidget(line)

    def page_welcome(self):
        self.body.addStretch()
        dark = self.surface_color.lightnessF() <= .5
        variant = "golden-gate-dark" if self.asset_edition == "golden-gate" and dark else self.asset_edition
        self.body.addWidget(self.image(f"logo-{variant}.png", 180, 180))
        title = self.label(self.t("Install") + " " + self.edition, heading=True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter); self.body.addWidget(title)
        if self.update_available:
            text = self.t("Update available:") + " " + self.update_available
            update = QPushButton(text)
            update.setEnabled(not self.updating)
            update.clicked.connect(self.update_installer)
            self.body.addWidget(update)

    def option_card(self):
        frame = QFrame(self.content)
        frame.setObjectName("settingsOptionPanel" if self.settings_mode else "optionPanel")
        if not self.settings_mode:
            shadow = QGraphicsDropShadowEffect(frame)
            shadow.setBlurRadius(15)
            shadow.setOffset(0, 2)
            shadow.setColor(QColor(0, 0, 0, 30))
            frame.setGraphicsEffect(shadow)
        return frame

    def page_section(self):
        panels = SECTIONS[self.page][3] if self.settings_mode else INSTALL_SECTIONS[self.page][1]
        original = self.body
        original.setSpacing(14 if self.settings_mode else 17)
        for panel in panels:
            section = QWidget()
            layout = QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)
            if panel not in ("icons", "fonts") and (self.settings_mode or len(panels) > 1):
                title = self.label(PANEL_LABELS[panel])
                desktop_title = panel in ("wallpaper", "desktop_widgets")
                title.setFont(relative_font(self, .72 if desktop_title else .88,
                                            QFont.Weight.Medium if desktop_title else QFont.Weight.DemiBold))
                title.setContentsMargins(4, 0, 0, 0)
                layout.addWidget(title)
            frame = self.option_card()
            layout.addWidget(frame)
            self.panel_frames[panel] = section
            self.body = QVBoxLayout(frame)
            self.body.setContentsMargins(*((12, 10, 12, 10) if self.settings_mode else (14, 13, 14, 13)))
            self.body.setSpacing(9)
            if panel == "acrylic_glass_editor":
                self.mount_acrylic_glass_editor(self.body)
            else:
                getattr(self, "page_" + panel)()
            if self.settings_mode and self.settings_baseline is None and panel not in ("appearance", "acrylic_glass_editor"):
                frame.setEnabled(False)
            self.body = original
            original.addWidget(section)
        if "glass_style" in self.panel_frames:
            self.panel_frames["glass_style"].setVisible(self.show_glass_style())
        if not self.settings_mode:
            return
        if self.requested_glass_editor:
            self.widget_settings_target = self.panel_frames.get("acrylic_glass_editor")
            self.requested_glass_editor = False

        if self.page == "dock_bar":
            self.page_dock_and_menu_widgets()
        if self.page == "desktop":
            self.page_weather_panel()
            from desktop_widget_editor import DesktopWidgetEditor, installed_instances
            widgets = installed_instances()
            if widgets:
                panel = self.option_card()
                layout = QVBoxLayout(panel)
                layout.addWidget(DesktopWidgetEditor(widgets, self.requested_widget, self))
                self.body.addWidget(panel)
                if self.requested_desktop_widget and self.requested_widget in widgets:
                    self.widget_settings_target = panel
                    self.requested_desktop_widget = False

    def page_weather_panel(self):
        from plasmoid_settings import apply, instances
        from weather_panel_settings import installed_package

        package = installed_package()
        if package is None:
            return
        try:
            widgets = instances("weather_panel")
        except RuntimeError:
            widgets = {}
        if not widgets:
            return
        from weather_panel_editor import WeatherForm, weather_about

        self.requested_weather_panel, reveal = False, self.requested_weather_panel
        panel = self.option_card()
        column = QVBoxLayout(panel)
        column.setContentsMargins(12, 10, 12, 10)
        header = QHBoxLayout()
        heading = self.label("Weather (Panel)")
        heading.setFont(relative_font(self, .85, QFont.Weight.DemiBold))
        header.addWidget(heading, 1)
        save = GlassButton(self.t("Save"))
        header.addWidget(save)
        column.addLayout(header)
        picker = GlassComboBox()
        for instance in sorted(widgets):
            picker.addItem(self.t("Widget {id}").format(id=instance), instance)
        selected = picker.findData(self.requested_widget)
        picker.setCurrentIndex(max(0, selected))
        picker.setVisible(len(widgets) > 1)
        picker.setAccessibleName(self.t("Widget instance"))
        column.addWidget(picker)
        shortcut_row = QHBoxLayout()
        shortcut_row.addWidget(self.label("Activation shortcut"), 1)
        shortcut = QKeySequenceEdit()
        shortcut.setAccessibleName(self.t("Activation shortcut"))
        shortcut.setClearButtonEnabled(True)
        shortcut_row.addWidget(shortcut)
        column.addLayout(shortcut_row)
        tabs = QTabWidget()
        tabs.setObjectName("widgetPreferenceTabs")
        general = WeatherForm(self.t, tabs)
        tabs.addTab(general, self.t("Weather"))
        tabs.addTab(weather_about(self.t, tabs), self.t("About"))
        column.addWidget(tabs)
        result = self.label("")
        result.setObjectName("detail")
        result.hide()
        column.addWidget(result)
        baseline = {}

        def load():
            values = widgets[picker.currentData()]
            general.load(values)
            baseline.clear()
            baseline.update(general.values())
            shortcut.setKeySequence(QKeySequence.fromString(values["activationShortcut"]))
            save.setEnabled(bool(baseline))
            result.hide()

        def save_weather():
            instance = picker.currentData()
            changed = {key: value for key, value in general.values().items()
                       if value is not None and value != baseline[key]}
            sequence = shortcut.keySequence().toString()
            if sequence != widgets[instance]["activationShortcut"]:
                changed["activationShortcut"] = sequence
            try:
                if changed:
                    widgets[instance] = apply("weather_panel", instance, changed)
            except (RuntimeError, ValueError) as error:
                result.setText(self.t(str(error)))
            else:
                baseline.update(general.values())
                result.setText(self.t("Saved"))
            result.show()

        picker.currentIndexChanged.connect(load)
        save.clicked.connect(save_weather)
        load()
        self.body.addWidget(panel)
        if reveal:
            self.widget_settings_target = panel

    def mount_acrylic_glass_editor(self, layout):
        if layout.count():
            return
        if self.acrylic_glass_editor is None:
            from acrylic_glass_editor import create_acrylic_glass_editor
            self.acrylic_glass_editor = create_acrylic_glass_editor(self)
        if self.acrylic_glass_editor is None:
            layout.addWidget(self.label("Install Acrylic Glass to edit its materials."))
        else:
            self.acrylic_glass_editor.setFont(relative_font(self, .90))
            layout.addWidget(self.acrylic_glass_editor)
            self.acrylic_glass_editor.show()

    def reveal_requested_widget(self):
        if self.widget_settings_target is not None:
            top = self.widget_settings_target.mapTo(self.content, QPoint(0, 0)).y()
            self.scroll.verticalScrollBar().setValue(max(0, top - 10))
            self.widget_settings_target = None
            self.requested_widget = None

    def page_dock_and_menu_widgets(self):
        import dock_preferences
        from dock_apps import desktop_applications
        from plasmoid_settings import (
            apply, instances, BAR_WIDGET_LABELS, CONTROL_CENTER_FIELDS, SHORTCUT_WIDGETS, TYPED_PREFERENCES,
        )
        text_fields = {
            "trash": (
                ("emptyIcon", "Empty trash icon", "user-trash"),
                ("fullIcon", "Full trash icon", "user-trash-full"),
            ),
        }
        for kind, title in (("dock", "Dock preferences"), ("launcher", "Apps preferences"),
                            ("trash", "Trash"), ("control_center", "Control Center"),
                            ("bar_shortcuts", "Widget shortcuts"), ("system_menu", "System menu")):
            try:
                widgets = instances(kind)
            except RuntimeError:
                widgets = {}
            if not widgets and kind in ("control_center", "bar_shortcuts"):
                continue
            panel = self.option_card()
            column = QVBoxLayout(panel)
            column.setContentsMargins(12, 10, 12, 10)
            heading = self.label(title)
            heading.setFont(relative_font(self, .85, QFont.Weight.DemiBold))
            header = QHBoxLayout()
            header.addWidget(heading, 1)
            column.addLayout(header)
            if not widgets:
                column.addWidget(self.label("No matching widgets in this Plasma session."))
                self.body.addWidget(panel)
                continue

            picker = GlassComboBox()
            if kind == "bar_shortcuts":
                names = {instance: self.t(BAR_WIDGET_LABELS[record["_plugin"]])
                         for instance, record in widgets.items()}
                for instance, name in sorted(names.items(), key=lambda item: (item[1].casefold(), item[0])):
                    suffix = f" ({instance})" if list(names.values()).count(name) > 1 else ""
                    picker.addItem(name + suffix, instance)
            else:
                for instance in sorted(widgets):
                    picker.addItem(self.t("Widget {id}").format(id=instance), instance)
            preferred = picker.findData(self.requested_widget)
            if preferred >= 0:
                picker.setCurrentIndex(preferred)
                self.widget_settings_target = panel
            picker.setAccessibleName(self.t("Widget instance"))
            picker.setVisible(len(widgets) > 1 or kind == "bar_shortcuts")
            column.addWidget(picker)
            controls = {}
            rows = {}
            displayed = {}
            typed = TYPED_PREFERENCES.get(kind)
            if typed is not None:
                tabs = QTabWidget()
                tabs.setObjectName("widgetPreferenceTabs")
                tabs.setFont(relative_font(self, .9))
                pages = ({"Appearance": dock_preferences.APPEARANCE, "Behavior": dock_preferences.BEHAVIOR}
                         if kind == "dock" else typed.FORMS)
                for label, labels in pages.items():
                    tab = QWidget()
                    form = QVBoxLayout(tab)
                    form.setContentsMargins(0, 6, 0, 0)
                    form.setSpacing(4)
                    for key, text in labels.items():
                        row = QWidget()
                        row.setProperty("widgetPreferenceRow", True)
                        line = QHBoxLayout(row)
                        line.setContentsMargins(0, 0, 0, 0)
                        if isinstance(typed.DEFAULTS[key], bool):
                            field = CheckOption(self.t(text))
                            line.addWidget(field, 1)
                        else:
                            title_label = self.label(text)
                            title_label.setWordWrap(True)
                            title_label.setMinimumWidth(130)
                            line.addWidget(title_label, 1)
                            if key == "launcherApplication":
                                field = GlassComboBox()
                                field.setMinimumContentsLength(16)
                                field.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                                field.addItem(self.t("Launchpad"), "")
                                for app_id, name in sorted(desktop_applications().items(), key=lambda app: app[1].casefold()):
                                    field.addItem(name, app_id)
                            elif key in typed.CHOICES:
                                field = GlassComboBox()
                                for value, choice in typed.CHOICES[key].items():
                                    field.addItem(self.t(choice), value)
                            elif key in typed.RANGES:
                                field = QSpinBox()
                                field.setRange(*typed.RANGES[key])
                                if key == "dockMagnification":
                                    field.setSuffix("%")
                                    field.setSingleStep(5)
                            else:
                                field = QLineEdit()
                                field.setObjectName("widgetSettingField")
                                placeholder = "Icon name or file"
                                if kind == "system_menu":
                                    placeholder = "plasma-discover" if key == "cmdAppStore" else typed.DEFAULTS[key]
                                    field.setMinimumWidth(175)
                                field.setPlaceholderText(self.t(placeholder))
                            field.setAccessibleName(title_label.text())
                            line.addWidget(field, 2 if kind == "system_menu" else 0)
                            if key == "customButtonImage":
                                browse = GlassButton(self.t("Choose…"))
                                browse.clicked.connect(lambda _, target=field, enabled=controls["useCustomButtonImage"]:
                                                       self.choose_launcher_image(target, enabled))
                                line.addWidget(browse)
                            if kind == "system_menu" and (key == "menuIcon" or key.startswith("icon")):
                                preview = QLabel()
                                preview.setFixedSize(18, 18)
                                line.insertWidget(line.indexOf(field), preview)
                                default_icon = typed.DEFAULTS[key]

                                def refresh_menu_icon(value, target=preview, fallback=default_icon):
                                    name = value or fallback
                                    path = QUrl(name).toLocalFile() or name
                                    icon = QIcon(path) if Path(path).is_absolute() else QIcon.fromTheme(name)
                                    target.setPixmap(icon.pixmap(target.size(), target.devicePixelRatioF()))

                                field.textChanged.connect(refresh_menu_icon)
                                refresh_menu_icon(field.text())
                                browse = GlassButton(self.t("Choose…"))
                                browse.clicked.connect(lambda _, target=field: self.choose_system_menu_icon(target))
                                line.addWidget(browse)
                        field.setProperty("preferenceKey", key)
                        if not isinstance(field, QLineEdit):
                            field.setObjectName(key)
                        rows[key] = row
                        controls[key] = field
                        form.addWidget(row)
                    if kind == "launcher" and label == "Icon":
                        preview = QLabel()
                        preview.setFixedSize(38, 38)
                        icon, custom, use_custom = (controls[key] for key in
                                                    ("icon", "customButtonImage", "useCustomButtonImage"))

                        def refresh_icon(*_, target=preview, base=icon, image=custom, use=use_custom):
                            value = image.text() if use.isChecked() else base.text()
                            url = QUrl(value)
                            filename = url.toLocalFile() if url.isLocalFile() else value
                            artwork = QIcon(filename) if Path(filename).is_absolute() else QIcon.fromTheme(filename)
                            target.setPixmap(artwork.pixmap(36, 36))

                        reset_icon = GlassButton(self.t("Clear Icon"))

                        def clear_icon(*_, base=icon, use=use_custom):
                            base.setText("start-here-kde-symbolic")
                            use.setChecked(False)

                        reset_icon.clicked.connect(clear_icon)
                        icon.textChanged.connect(refresh_icon)
                        custom.textChanged.connect(refresh_icon)
                        use_custom.toggled.connect(refresh_icon)
                        icon_preview = QHBoxLayout()
                        icon_preview.addWidget(preview)
                        icon_preview.addStretch()
                        icon_preview.addWidget(reset_icon)
                        form.insertLayout(0, icon_preview)
                    form.addStretch()
                    tabs.addTab(tab, self.t(label))
                if kind == "system_menu":
                    def fit_menu_tab(index, target=tabs):
                        form = target.widget(index).layout()
                        target.setFixedHeight(target.tabBar().sizeHint().height() + form.sizeHint().height() + 4)

                    tabs.currentChanged.connect(fit_menu_tab)
                    fit_menu_tab(tabs.currentIndex())
                column.addWidget(tabs)
            elif kind == "control_center":
                grid = QGridLayout()
                for index, (key, label) in enumerate(CONTROL_CENTER_FIELDS.items()):
                    checkbox = CheckOption(self.t(label))
                    checkbox.setObjectName(key)
                    controls[key] = checkbox
                    grid.addWidget(checkbox, index // 2, index % 2)
                column.addLayout(grid)
            elif kind in text_fields:
                grid = QGridLayout()
                grid.setColumnStretch(0, 1)
                grid.setColumnStretch(2, 2)
                for row, (key, label, placeholder) in enumerate(text_fields[kind]):
                    title_label = self.label(label)
                    field = QLineEdit()
                    field.setObjectName("widgetSettingField")
                    field.setAccessibleName(title_label.text())
                    field.setPlaceholderText(placeholder)
                    grid.addWidget(title_label, row, 0)
                    if key in ("iconAppStore", "emptyIcon", "fullIcon"):
                        preview = QLabel()
                        preview.setFixedSize(24, 24)
                        field.textChanged.connect(
                            lambda value, icon=preview, fallback=placeholder:
                            icon.setPixmap(QIcon.fromTheme(value or fallback).pixmap(20, 20)))
                        grid.addWidget(preview, row, 1)
                    grid.addWidget(field, row, 2)
                    controls[key] = field
                column.addLayout(grid)
            buttons = QHBoxLayout()
            result = self.label("")
            result.setObjectName("detail")
            save = GlassButton(self.t("Save"))
            save_in_header = typed is not None or kind in ("control_center", "bar_shortcuts")
            if save_in_header:
                header.addWidget(save)
            else:
                buttons.addStretch()
                buttons.addWidget(save)
            if kind in SHORTCUT_WIDGETS:
                shortcut = QKeySequenceEdit()
                shortcut.setObjectName("activationShortcut")
                shortcut.setClearButtonEnabled(True)
                shortcut.setAccessibleName(self.t("Activation shortcut"))
                shortcut_row = QHBoxLayout()
                shortcut_row.addWidget(self.label("Activation shortcut"), 1)
                shortcut_row.addWidget(shortcut)
                if typed is not None:
                    column.insertLayout(column.indexOf(tabs), shortcut_row)
                else:
                    column.addLayout(shortcut_row)
                controls["activationShortcut"] = shortcut
            if kind == "trash":
                storage = GlassButton(self.t("Trash Settings…"))
                shell = shutil.which("kcmshell6")
                storage.setEnabled(shell is not None)
                if shell is not None:
                    storage.clicked.connect(lambda: subprocess.Popen(
                        [shell, "kcm_trash"], start_new_session=True))
                buttons.addWidget(storage)
            if not save_in_header:
                column.addLayout(buttons)
            result.hide()
            column.addWidget(result)

            def update_dock_dependencies(*_, fields=controls):
                grouped = fields["groupingStrategy"].currentData() != 0
                fields["groupedTaskVisualization"].setEnabled(grouped)
                fields["groupPopups"].setEnabled(grouped)
                fields["onlyGroupWhenFull"].setEnabled(grouped and fields["groupPopups"].isChecked())
                fields["interactiveMute"].setEnabled(fields["indicateAudioStreams"].isChecked())
                fields["wheelSkipMinimized"].setEnabled(fields["wheelEnabled"].currentData() != 0)
                fields["separateLaunchers"].setEnabled(fields["sortingStrategy"].currentData() == 1)
                fields["forceStripes"].setEnabled(fields["maxStripes"].value() > 1)

            def update_launcher_dependencies(*_, fields=controls, launcher_rows=rows):
                centered = fields["launcherPosition"].currentData() == 2
                fields["floating"].setEnabled(not centered)
                if centered:
                    fields["floating"].setChecked(True)
                for key in ("offsetX", "offsetY"):
                    launcher_rows[key].setVisible(centered or fields["floating"].isChecked())
                launcher_rows["customButtonImage"].setEnabled(fields["useCustomButtonImage"].isChecked())

            def field_value(field):
                if isinstance(field, QKeySequenceEdit):
                    return field.keySequence().toString()
                if isinstance(field, QLineEdit):
                    return field.text()
                if isinstance(field, QSpinBox):
                    return field.value()
                if isinstance(field, QComboBox):
                    return field.currentData()
                return field.isChecked()

            def load(*_, selected=picker, fields=controls, values=widgets, status=result,
                     widget_rows=rows, category=kind, dock_dependencies=update_dock_dependencies,
                     launcher_dependencies=update_launcher_dependencies, baseline=displayed):
                saved = values[selected.currentData()]
                if category == "dock":
                    icons_only = saved.get("_plugin") == dock_preferences.DOCK_ICONS
                    for key, row in widget_rows.items():
                        row.setVisible((key not in dock_preferences.ICONS_ONLY or icons_only)
                                       and (key not in dock_preferences.TASKS_ONLY or not icons_only)
                                       and (key != "taskMaxWidth" or not saved.get("_vertical")))
                for key, field in fields.items():
                    value = saved.get(key, "")
                    if isinstance(field, QKeySequenceEdit):
                        field.setKeySequence(QKeySequence.fromString(value))
                    elif isinstance(field, QLineEdit):
                        field.setText(value)
                        field.setCursorPosition(0)
                    elif isinstance(field, QSpinBox):
                        field.setValue(value)
                    elif isinstance(field, QComboBox):
                        if key == "launcherApplication" and field.findData(value) == -1:
                            field.addItem(value, value)
                        field.setCurrentIndex(field.findData(value))
                    else:
                        field.setChecked(value is True or str(value).lower() == "true")
                if category == "dock":
                    dock_dependencies()
                elif category == "launcher":
                    launcher_dependencies()
                baseline.update((key, field_value(field)) for key, field in fields.items())
                status.clear()
                status.hide()

            def save_widget(*_, selected=picker, fields=controls, values=widgets, category=kind, status=result,
                            widget_rows=rows, baseline=displayed):
                identifier = selected.currentData()
                desired = {}
                for key, field in fields.items():
                    if key in widget_rows and widget_rows[key].isHidden():
                        continue
                    value = field_value(field)
                    if value is not None and value != baseline[key]:
                        desired[key] = value
                if desired.get("maxStripes") == 1:
                    desired["forceStripes"] = False
                if "launcherPosition" in desired:
                    desired["floating"] = fields["floating"].isChecked()
                try:
                    if desired:
                        values[identifier] = apply(category, identifier, desired)
                except (RuntimeError, ValueError) as error:
                    status.setText(self.t(str(error)))
                else:
                    for key, value in desired.items():
                        if isinstance(fields[key], QCheckBox):
                            fields[key].setChecked(value)
                        baseline[key] = field_value(fields[key])
                    status.setText(self.t("Saved"))
                status.show()

            if kind == "dock":
                for key in ("groupingStrategy", "wheelEnabled", "sortingStrategy"):
                    controls[key].currentIndexChanged.connect(update_dock_dependencies)
                for key in ("groupPopups", "indicateAudioStreams"):
                    controls[key].toggled.connect(update_dock_dependencies)
                controls["maxStripes"].valueChanged.connect(update_dock_dependencies)
            elif kind == "launcher":
                controls["launcherPosition"].currentIndexChanged.connect(update_launcher_dependencies)
                for key in ("floating", "useCustomButtonImage"):
                    controls[key].toggled.connect(update_launcher_dependencies)
            picker.currentIndexChanged.connect(load)
            save.clicked.connect(save_widget)
            load()
            if kind == "system_menu" and preferred >= 0:
                self.body.insertWidget(0, panel)
            else:
                self.body.addWidget(panel)

    def choose_launcher_image(self, field, enabled):
        filename, _ = QFileDialog.getOpenFileName(self, self.t("Choose an icon"), "",
                                                   self.t("Icons (*.png *.xpm *.svg *.svgz)"))
        if filename:
            field.setText(QUrl.fromLocalFile(filename).toString())
            enabled.setChecked(True)

    def choose_system_menu_icon(self, field):
        picker = shutil.which("kdialog")
        if picker is None:
            filename, _ = QFileDialog.getOpenFileName(self, self.t("Choose an icon"), "",
                                                       self.t("Icons (*.png *.xpm *.svg *.svgz)"))
            if filename:
                field.setText(filename)
            return
        process = QProcess(self)

        def chosen(code, status):
            if code == 0 and status == QProcess.ExitStatus.NormalExit:
                icon = bytes(process.readAllStandardOutput()).decode(errors="replace").strip()
                if icon and not sip.isdeleted(field):
                    field.setText(icon)
            process.deleteLater()

        process.finished.connect(chosen)
        process.errorOccurred.connect(lambda error: process.deleteLater()
                                      if error == QProcess.ProcessError.FailedToStart else None)
        process.start(picker, ["--geticon", "Desktop", "--title", self.t("Choose an icon")])

    def page_general(self):
        panel = QFrame()
        panel.setObjectName("settingsPanel")
        row = QHBoxLayout(panel)
        row.setContentsMargins(12, 9, 12, 9)
        label = self.label("Language")
        selector = self.language_selector()
        selector.setAccessibleName(self.t("Language"))
        row.addWidget(label)
        row.addStretch()
        row.addWidget(selector)
        self.body.addWidget(panel)

    def page_appearance(self):
        if self.page not in SECTIONS and self.page not in INSTALL_SECTIONS:
            self.body.addSpacing(10)
        stem = f"desktop-{self.asset_edition}-"
        group = self.cards("appearance", [
            ("auto", "Auto", "", picture(stem+"light.jpg", 232, 131, stem+"dark.jpg")),
            ("light", "Light", "", picture(stem+"light.jpg", 232, 131)),
            ("dark", "Dark", "", picture(stem+"dark.jpg", 232, 131)),
        ], columns=3, compact=True, default_first=False)
        if self.settings_mode:
            for button in group.buttons():
                button.setMaximumWidth(154)
            if self.appearance_process:
                for button in group.buttons():
                    button.setEnabled(False)
                self.body.addWidget(self.label("Applying appearance…"))
            if self.appearance_error:
                self.body.addWidget(self.label(self.appearance_error))

    def icon_sample(self, style):
        mode = "dark" if style == "dark" else self.mode
        color = self.choices["color"] if style == "glass" else "neutral"
        return QIcon(picture(f"weather-{style}-{mode}-{color}.png", 34, 34))

    def page_icons(self):
        rows = QGridLayout()
        rows.setHorizontalSpacing(12)
        rows.setVerticalSpacing(6)
        rows.setColumnStretch(0, 1)
        for index, text in ((0, "Icons"), (2, "Icon appearance"), (3, "Color")):
            label = self.label(text)
            label.setFont(relative_font(self, .78, QFont.Weight.Medium))
            rows.addWidget(label, index, 0)

        group = QButtonGroup(self.content)
        self.groups.append(group)
        styles = QHBoxLayout()
        styles.setSpacing(6)
        for value, label in (("regular", "Default"), ("dark", "Dark"), ("clear", "Clear"), ("glass", "Tinted")):
            button = QToolButton()
            button.setObjectName("choice-icons-" + value)
            button.setProperty("iconStyleChoice", True)
            button.setFont(relative_font(self, .72, QFont.Weight.Medium))
            button.setText(self.t(label))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setIcon(self.icon_sample(value))
            button.setIconSize(QSize(32, 32))
            button.setCheckable(True)
            group.addButton(button)
            button.setChecked(self.choices["icons"] == value)
            button.clicked.connect(lambda _, style=value: self.select("icons", style))
            self.bind_choice("icons", value, button)
            styles.addWidget(button)
            if value == "glass":
                self.glass_preview = button
        rows.addLayout(styles, 0, 1)

        keep = RadioOption(self.t("Keep my icons"))
        keep.setObjectName("choice-icons-keep")
        keep.setFont(relative_font(self, .76))
        group.addButton(keep)
        keep.setChecked(self.choices["icons"] == "keep")
        keep.clicked.connect(lambda: self.select("icons", "keep"))
        self.bind_choice("icons", "keep", keep)
        rows.addWidget(keep, 1, 1, Qt.AlignmentFlag.AlignRight)

        appearance = QHBoxLayout()
        # The radio and color swatch centers share the same left guide.
        appearance.setContentsMargins(4, 0, 0, 0)
        appearance.setSpacing(8)
        self.radio("icon_appearance", [("auto", "Automatic"), ("light", "Light"), ("dark", "Dark")],
                   inline=True, font_scale=.76, option_layout=appearance)
        rows.addLayout(appearance, 2, 1)

        colors = QHBoxLayout()
        colors.setSpacing(3)
        self.color_buttons = {}
        for name, color in COLORS.items():
            if self.color_buttons:
                colors.addStretch()
            button = ColorSwatch(color)
            button.setObjectName("color-"+name)
            button.setAccessibleName(self.t(name.capitalize()))
            button.setToolTip(self.t(name.capitalize()))
            button.setChecked(self.choices["color"] == name)
            self.bind_choice("color", name, button)
            self.color_buttons[name] = button
            button.clicked.connect(lambda _, value=name: self.select("color", value))
            colors.addWidget(button)
        rows.addLayout(colors, 3, 1)
        self.body.addLayout(rows)

    @property
    def mode(self):
        return "dark" if self.choices["appearance"] == "dark" else "light"

    def page_wallpaper(self):
        items = [(key, label, "", picture(key+".jpg", 170, 112, key+"-dark.jpg", cover=True))
                 for key, label in (("tahoe", "Tahoe"), ("golden", "Golden Gate"),
                                    ("landscape", "Landscape"), ("sonoma", "Sonoma"),
                                    ("prism", "Prism"), ("macos", "Monterey"), ("exuma", "Exuma"))]
        items.append(("keep", "Keep my wallpaper", "", current_wallpaper_preview(170, 112)))
        self.cards("wallpaper", items, columns=4, compact=True)
        row = QHBoxLayout()
        row.addStretch()
        button = QPushButton(self.t("Choose a file…"))
        button.setFont(relative_font(self, .72, QFont.Weight.Medium))
        button.clicked.connect(self.choose_file)
        button.setObjectName("textLink")
        row.addWidget(button)
        self.body.addLayout(row)
        self.wallpaper_filename = self.label(Path(self.choices["wallpaper_path"]).name)
        self.wallpaper_filename.setFont(relative_font(self, .72))
        self.wallpaper_filename.setVisible(self.choices["wallpaper"] == "custom")
        self.body.addWidget(self.wallpaper_filename)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, self.t("Choose a wallpaper"), "", self.t("Images (*.png *.jpg *.jpeg *.webp)"))
        if path and not QPixmap(path).isNull():
            self.choices["wallpaper_path"] = path
            self.select("wallpaper", "custom")

    def page_desktop_widgets(self):
        from steps.plasmoids import WIDGETS_STATE

        removal = "Remove any widgets previously installed by this theme." if WIDGETS_STATE.is_file() else ""
        self.cards("desktop_widgets", [
            (False, "Skip widgets", removal, picture("desktop-widgets-off.jpg", 368, 207, cover=True)),
            (True, "Install widgets", "", picture("desktop-widgets-on.jpg", 368, 207, cover=True)),
        ], default_first=False)

    def launcher_notice(self):
        from steps.clipboard import HISTORY_DIR
        from steps.plasmoids import DEST_DIR, LAUNCHER_ID
        if not self.choices["reset_layout"]:
            return ""
        if HISTORY_DIR.is_dir():
            return "Remove Launchpad and its saved clipboard history."
        if (DEST_DIR / LAUNCHER_ID).is_dir():
            return "Remove the installed Launchpad widget."
        return ""

    def page_launcher(self):
        self.cards("launcher", [
            ("tahoe", "Tahoe", "Categories and apps in one window.", picture("launcher-tahoe.jpg", 362, 204)),
            ("golden", "Golden Gate", "Separate search and application grid.", picture("launcher-golden.jpg", 362, 204)),
            ("keep", "Use my launcher", self.launcher_notice(), None),
        ])

    def page_layout(self):
        self.body.addSpacing(4)
        reset = self.checkbox("reset_layout", "Reset Dock and panel customization")
        reset_hint = self.label("Clear this option to keep your panels, widgets and pinned apps.")
        reset_hint.setObjectName("detail")
        reset_hint.setFont(relative_font(self, .85))
        self.body.addWidget(reset_hint)
        reset_hint.setVisible(reset.isChecked())
        reset.toggled.connect(reset_hint.setVisible)
        self.cards("", [
            ("panel", "Top bar", "", picture("panel-detail.jpg", 362, 160)),
            ("dock", "Dock", "", picture("dock.jpg", 362, 160)),
        ], independent=True)
        def enable_layout_options():
            for key in ("panel", "dock"):
                for _, card in self.choice_widgets.get(key, ()):
                    card.setEnabled(self.choices["reset_layout"])
        reset.toggled.connect(enable_layout_options)
        enable_layout_options()
        row = QHBoxLayout()
        label = self.label("Dock visibility")
        row.addWidget(label, 1)
        visibility = GlassComboBox()
        visibility.setObjectName("dock-visibility")
        visibility.setAccessibleName(label.text())
        visibility.setFont(relative_font(self, .86))
        for value, text in (("autohide", "Auto-hide"),
                            ("none", "Show outside full screen"),
                            ("dodgewindows", "Hide on overlap")):
            visibility.addItem(self.t(text), value)
        visibility.setCurrentIndex(visibility.findData(self.choices["dock_visibility"]))
        visibility.setEnabled(self.choices["dock"])
        visibility.currentIndexChanged.connect(lambda: self.select("dock_visibility", visibility.currentData()))
        row.addWidget(visibility)
        self.body.addLayout(row)

        button = GlassButton(self.t("Dock apps…"))
        button.setObjectName("edit-dock-apps")
        button.setEnabled(self.choices["dock"])
        button.clicked.connect(self.edit_dock_apps)
        self.body.addWidget(button, alignment=Qt.AlignmentFlag.AlignRight)

    def edit_dock_apps(self):
        from dock_apps import OPTIONAL, LABELS, installed_apps, recommendation
        choices = self.choices.copy()
        choices["dock_apps"] = list(choices["dock_apps"])
        installed = installed_apps()
        dialog = QDialog(self)
        # Custom checkbox painting uses the colors of its containing window.
        # A modal QDialog is a separate window even with the wizard as parent.
        dialog.setPalette(self.palette())
        dialog.setAutoFillBackground(True)
        dialog.accent = self.accent
        dialog.line = self.line
        dialog.setWindowTitle(self.t("Dock apps"))
        dialog.setMinimumWidth(620)
        body = QVBoxLayout(dialog)
        body.addWidget(self.label("Dock appearance"))
        appearance = GlassComboBox()
        appearance.setObjectName("dock-appearance")
        for key, label in (("auto", "Automatic"), ("keep", "Keep current Dock icons"), ("macos", "macOS-style Dock icons"), ("native", "Application icons")):
            appearance.addItem(self.t(label), key)
        appearance.setCurrentIndex(appearance.findData(choices["dock_appearance"]))
        appearance.setEnabled(choices["dock"] and choices["reset_layout"])
        appearance.currentIndexChanged.connect(lambda: choices.update(dock_appearance=appearance.currentData()))
        body.addWidget(appearance)

        source = GlassComboBox()
        source.setObjectName("dock-apps-source")
        source.addItem(self.t("Distribution repositories"), "native")
        source.addItem(self.t("Flatpak for my user (installs Flatpak if needed)"), "flatpak")
        source.setCurrentIndex(0 if choices["dock_apps_source"] == "native" else 1)
        body.addWidget(source)
        remote = GlassCheckOption(self.t("Allow adding Flathub for my user if it is missing"))
        remote.setObjectName("dock-add-flathub")
        remote.setChecked(choices["dock_add_flathub"])
        remote.toggled.connect(lambda checked: choices.update(dock_add_flathub=checked))
        body.addWidget(remote)
        options = {}
        for category in OPTIONAL:
            option = GlassCheckOption("")
            option.setObjectName("dock-app-" + category)
            option.setFont(relative_font(self, .93))
            def choose(checked, key=category):
                chosen = set(choices["dock_apps"])
                chosen.add(key) if checked else chosen.discard(key)
                choices["dock_apps"] = [key for key in OPTIONAL if key in chosen]
            option.toggled.connect(choose)
            options[category] = option
            body.addWidget(option)
        def refresh():
            choices["dock_apps_source"] = source.currentData()
            remote.setVisible(source.currentData() == "flatpak")
            for category, option in options.items():
                proposal = recommendation(category, source.currentData())
                existing = installed.get(category)
                title = self.t(LABELS[category]) + " — "
                if existing:
                    title += existing + " · " + self.t("Installed")
                elif proposal:
                    title += proposal[0] + " (" + proposal[1] + ")"
                else:
                    title += self.t("Unavailable from this source")
                option.setText(title)
                option.setEnabled(bool(proposal) and not existing)
                option.setChecked(category in choices["dock_apps"] and option.isEnabled())
            # Already-unchecked controls do not emit toggled when a saved
            # selection becomes installed or unavailable on reopening.
            choices["dock_apps"] = [key for key, option in options.items() if option.isChecked()]
        source.currentIndexChanged.connect(refresh)
        refresh()
        body.addWidget(self.label("Availability is checked during installation. Failed apps remain pending; removing the theme keeps your apps."))
        buttons = QDialogButtonBox()
        accept = GlassButton(self.t("Continue"))
        accept.setObjectName("dock-apps-continue")
        accept.setDefault(True)
        cancel = GlassButton(self.t("Cancel"))
        cancel.setObjectName("dock-apps-cancel")
        buttons.addButton(accept, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(cancel, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        body.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            for key in ("dock_apps", "dock_apps_source", "dock_add_flathub", "dock_appearance"):
                self.choices[key] = choices[key]
            self.render()

    def page_effects(self):
        for key, label in (("acrylic_glass", "Transparency and blur"),
                           ("rounded_corners", "Rounded corners")):
            self.bind_choice(key, True, self.checkbox(key, label))

    def page_window_controls(self):
        self.cards("window_controls", [
            ("flat", "Flat", "",
             picture(f"window-controls-flat-{self.mode}.png", 362, 190)),
            ("glassy", "Glassy", "",
             picture(f"window-controls-glassy-{self.mode}.png", 362, 190)),
        ])

    def button_position_sample(self, position):
        dark = self.mode == "dark"
        mode = "Dark" if dark else "Light"
        style = self.choices["window_controls"]
        width, height, size = 232, 96, 14
        canvas = QPixmap(width*2, height*2)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.scale(2, 2)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#1f2024" if dark else "#d7dae0"))
        painter.drawRect(0, 0, width, height)
        window = QRectF(18, 18, width-36, height-30)
        painter.setPen(QPen(QColor(255, 255, 255, 34) if dark else QColor(0, 0, 0, 40), .75))
        painter.setBrush(QColor("#2d2e32" if dark else "#fafafa"))
        painter.drawRoundedRect(window, 9, 9)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 18) if dark else QColor(0, 0, 0, 22))
        painter.drawRoundedRect(QRectF(width/2-18, 27, 36, 6), 3, 3)
        for row in range(3):
            painter.drawRoundedRect(QRectF(32, 50 + row*11, (width-64) * (.82, .6, .72)[row], 5), 2.5, 2.5)
        order = ("minimize", "maximize", "close") if position == "right" else ("close", "minimize", "maximize")
        for index, action in enumerate(order):
            left = window.left() + 14 + index * 21
            right = window.right() - 14 - size - (2 - index) * 21
            target = QRectF(right if position == "right" else left, 30 - size/2, size, size)
            if position == "keep":
                painter.setBrush(QColor(255, 255, 255, 46) if dark else QColor(0, 0, 0, 38))
                for x in (left, right):
                    painter.drawEllipse(QRectF(x, 30 - size/2, size, size).adjusted(1, 1, -1, -1))
                continue
            pixmap = QPixmap()
            if style == "glassy":
                pixmap.loadFromData(button_svg(action, mode, "active").encode(), "SVG")
            else:
                asset = (Path(__file__).resolve().parents[1] / "offline/gtk" / f"MacTahoeLiquidKde-{mode}" /
                         "gtk-4.0/windows-assets" / f"titlebutton-{action}{'-dark' if dark else ''}@2.png")
                pixmap.load(str(asset))
            painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
        painter.end()
        canvas.setDevicePixelRatio(2)
        return canvas

    def page_button_position(self):
        self.cards("button_position", [
            ("left", "Left", "Close, minimize, maximize.", self.button_position_sample("left")),
            ("right", "Right", "Minimize, maximize, close.", self.button_position_sample("right")),
            ("keep", "Keep my layout", "", self.button_position_sample("keep")),
        ], columns=3)

    def page_glass_style(self):
        mode = self.mode
        automatic = self.choices["appearance"] == "auto"
        items = []
        for preset in GLASS_PRESETS:
            stem = "glass-preset-" + preset["photo"]
            preview = picture(f"{stem}-{mode}.png", 360, 116,
                              f"{stem}-dark.png" if automatic else None,
                              cover=True, crop=(1788, 565, 1320, 425))
            items.append((preset["choice"], preset["title"], "", preview))
        self.cards("glass_style", items, columns=2, compact=True)

    def page_shadows(self):
        self.cards("shadows", [
            (level, label, "", picture(f"window-shadows-{level}-{self.mode}.png", 362, 116))
            for level, label in (("none", "None"), ("soft", "Soft"),
                                 ("medium", "Medium"), ("hard", "Hard"))
        ], columns=4 if self.page == "window_details" else 2, compact=True)

    def page_fonts(self):
        row = QHBoxLayout()
        label = self.label("Fonts")
        label.setFont(relative_font(self, .78, QFont.Weight.Medium))
        row.addWidget(label, 1)
        selector = GlassComboBox()
        selector.setObjectName("choice-fonts")
        selector.setAccessibleName(label.text())
        selector.setFont(relative_font(self, .76))
        selector.addItem("SF Pro", True)
        selector.addItem(self.t("Keep my fonts"), False)
        selector.setCurrentIndex(selector.findData(self.choices["fonts"]))
        selector.currentIndexChanged.connect(lambda: self.update_choice("fonts", selector.currentData()))
        row.addWidget(selector)
        self.body.addLayout(row)

    def page_firefox(self):
        self.body.addWidget(self.image("firefox-"+self.mode+".jpg", width=744, height=298, background="#e5e8ec"))
        self.radio("firefox", [(True, "Apply the theme"), (False, "Keep Firefox as it is")], inline=True)

    def page_files(self):
        self.radio("files", [("nautilus", "Install Nautilus"), ("dolphin", "Use Dolphin"),
                             ("keep", "Keep my file manager")])
        self.bookmarks = self.checkbox("nautilus_bookmarks", "Add folder shortcuts to the sidebar")
        self.bookmarks.setVisible(self.choices["files"] == "nautilus")

    def page_boot(self):
        preview = self.image("boot-preview.png", width=200, height=200)
        preview.setObjectName("bootAnimationPreview")
        self.body.addWidget(preview, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.body.addSpacing(8)
        self.radio("plymouth", [(True, "Use the theme animation"), (False, "Keep my boot animation")])

    def page_oled(self):
        self.radio("oled_care", [(False, "Do not enable"), (True, "Enable pixel shifting")])
        for key, title, maximum in (("oled_interval", "Interval (minutes)", 59),
                                    ("oled_max_shift", "Maximum shift (pixels)", 16)):
            row = QHBoxLayout()
            label = self.label(title)
            row.addWidget(label, 1)
            spin = GlassSpinBox()
            spin.setObjectName(key)
            spin.setAccessibleName(label.text())
            spin.setFont(relative_font(self, .85))
            spin.setRange(1, maximum)
            spin.setValue(self.choices[key])
            spin.setEnabled(self.choices["oled_care"])
            spin.valueChanged.connect(lambda value, preference=key: self.update_choice(preference, value))
            row.addWidget(spin)
            self.body.addLayout(row)

    def dock_app_summary(self):
        from dock_apps import recommendation
        names = [recommendation(key, self.choices["dock_apps_source"])
                 for key in self.choices["dock_apps"]] if self.choices["dock"] else []
        selected = ", ".join(item[0] for item in names if item)
        if not selected:
            return self.t("Use installed apps only")
        source = self.t("Distribution repositories") if self.choices["dock_apps_source"] == "native" else "Flatpak"
        return selected + " · " + source

    def page_summary(self):
        self.body.setSpacing(8)
        if self.reconfiguring:
            notice = self.label("Applying these changes may reinstall components and restart Plasma.")
            notice.setObjectName("detail")
            self.body.addWidget(notice)
        summary = QHBoxLayout()
        summary.setSpacing(14)
        c = self.choices
        names = {"auto": "Automatic", "light": "Light", "dark": "Dark",
                 "glass": "Tinted", "regular": "Default", "clear": "Clear", "keep": "Keep", "golden": "Golden Gate", "tahoe": "Tahoe",
                 "landscape": "Landscape", "sonoma": "Sonoma", "macos": "Monterey", "custom": "Custom file",
                 "nautilus": "Nautilus", "dolphin": "Dolphin",
                 **{preset["choice"]: preset["title"] for preset in GLASS_PRESETS}}
        value = lambda key: self.t(names.get(str(c[key]), str(c[key]).capitalize()))
        enabled = lambda key: self.t("Enabled" if c[key] else "Disabled")
        desktop = " + ".join(self.t(label) for key, label in (("panel", "Top bar"), ("dock", "Dock")) if c[key])
        keep_layout = not c["reset_layout"]
        if keep_layout:
            desktop = self.t("Keep current layout")
        elif desktop:
            desktop = self.t("Reset layout") + ": " + desktop
        effects = " + ".join(self.t(label) for key, label in (("acrylic_glass", "Glass"), ("rounded_corners", "Rounded corners")) if c[key])
        rows = (
            ("appearance", "Appearance", value("appearance"), "appearance"),
            ("icons", "Icons", value("icons"), "icons"),
            ("color", "Color", value("color"), "icons"),
            ("wallpaper", "Background", value("wallpaper"), "wallpaper"),
            ("desktop_widgets", "Desktop widgets", enabled("desktop_widgets"), "desktop_widgets"),
            ("launcher", "Launcher", self.t("Use my launcher") if c["launcher"] == "keep" else value("launcher"), "launcher"),
            ("panel", "Desktop", desktop or self.t("Keep"), "layout"),
            ("dock_apps", "Dock apps", self.dock_app_summary() + (" · " + self.t("macOS-style Dock icons" if c["dock_appearance"] == "macos" else "Application icons") if not keep_layout and c["dock"] and c["dock_appearance"] not in ("auto", "keep") else ""), "layout"),
            ("acrylic_glass", "Effects", effects or self.t("Disabled"), "effects"),
            ("window_controls", "Window controls", value("window_controls"), "window_controls"),
            ("button_position", "Window buttons", value("button_position"), "button_position"),
            ("shadows", "Window shadows", value("shadows"), "shadows"),
            ("fonts", "Fonts", self.t("Theme fonts" if c["fonts"] else "Keep"), "fonts"),
            ("firefox", "Firefox", enabled("firefox"), "firefox"),
            ("files", "Files", self.t("Keep my file manager") if c["files"] == "keep" else value("files"), "files"),
            *((("glass_style", "Glass", value("glass_style"), "glass_style"),)
              if self.show_glass_style() else ()),
            ("plymouth", "Boot", enabled("plymouth"), "boot"),
            ("oled_care", "OLED", enabled("oled_care"), "oled"),
        )
        sections = {}
        for ordered_sections in (("theme", "dock_bar", "applications"), ("desktop", "windows", "startup")):
            stack = QVBoxLayout()
            stack.setSpacing(7)
            for section in ordered_sections:
                card = self.option_card()
                column = QVBoxLayout(card)
                column.setContentsMargins(10, 5, 10, 5)
                column.setSpacing(0)
                heading = self.label(SECTIONS[section][0])
                heading.setFont(relative_font(self, .82, QFont.Weight.DemiBold))
                column.addWidget(heading)
                sections[section] = column
                stack.addWidget(card)
            stack.addStretch()
            summary.addLayout(stack, 1)
        for key, title, text, step in rows:
            entry = QWidget()
            entry.setObjectName("summaryEntry")
            entry.setStyleSheet(f"QWidget#summaryEntry {{ border-bottom: 1px solid {self.line}; }}")
            row = QHBoxLayout(entry); row.setContentsMargins(0, 1, 0, 1); row.setSpacing(9)
            label = self.label(title); label.setObjectName("detail"); label.setFixedWidth(94)
            label.setFont(relative_font(self, .81)); row.addWidget(label)
            choice = self.label(text); choice.setFont(relative_font(self, .81)); row.addWidget(choice, 1)
            button = QPushButton(self.t("Change")); button.setFlat(True)
            button.setFont(relative_font(self, .79))
            button.setStyleSheet(f"border:0; background:transparent; color:{self.accent}; padding:0;")
            button.setObjectName("edit-"+key); button.setAccessibleName(self.t("Change")+" "+self.t(title))
            button.clicked.connect(lambda _, page=step: self.edit(page)); row.addWidget(button)
            sections[PANEL_SECTIONS[step]].addWidget(entry)
        self.body.addLayout(summary)
        notices = []
        if c["launcher"] == "keep" and (launcher_warning := self.launcher_notice()):
            notices.append(launcher_warning)
        if c["reset_layout"] and (c["panel"] or c["dock"]):
            notices.append("Reset Dock and panel customization")
        if notices:
            warning = self.label("")
            warning.setObjectName("summaryWarning")
            warning.setText("\n".join(self.t(message) for message in notices))
            dark = self.palette().window().color().lightnessF() <= .5
            red = "#ff9994" if dark else "#a32322"
            warning.setStyleSheet(f"border-left: 3px solid {red}; padding-left: 8px; color: {red};")
            self.body.addWidget(warning)



    def edit(self, page):
        self.editing = True
        self.page = PANEL_STEPS.get(page, page)
        self.requested_install_panel = page if page in PANEL_STEPS else None
        self.render()

    def operation_text(self, message):
        # Existing locales use the English diagnostic view.
        from localization import effective_language
        return self.t(message) if effective_language(self.bridge.language) == "it" else message

    def details(self):
        self.details_toggle = QPushButton(self.operation_text("Show details"))
        self.details_toggle.setObjectName("detailsToggle")
        self.details_toggle.setCheckable(True)
        controls = QHBoxLayout()
        controls.setSpacing(18)
        controls.addWidget(self.details_toggle)
        controls.addStretch()
        copy = QPushButton(self.operation_text("Copy diagnostic"))
        copy.setObjectName("copyInstallationLog")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.bridge.logText()))
        controls.addWidget(copy)
        save = QPushButton(self.operation_text("Save log…"))
        save.setObjectName("saveInstallationLog")
        save.clicked.connect(self.save_log)
        controls.addWidget(save)
        for button in (self.details_toggle, copy, save):
            button.setFlat(True)
            button.setFont(relative_font(self, .85))
            button.setStyleSheet(f"border:0; background:transparent; color:{self.accent}; padding:4px 0;")
        self.body.addLayout(controls)
        self.full_output_toggle = QPushButton(self.operation_text("Show technical output"))
        self.full_output_toggle.setCheckable(True)
        self.full_output_toggle.setFlat(True)
        self.full_output_toggle.setFont(relative_font(self, .85))
        self.full_output_toggle.setStyleSheet(f"border:0; background:transparent; color:{self.accent}; padding:4px 0; text-align:left;")
        self.full_output_toggle.setObjectName("fullTechnicalOutput")
        self.full_output_toggle.setToolTip(self.operation_text("Latest 2,000 lines. Copy or save includes the complete output."))
        self.full_output_toggle.setChecked(False)
        self.full_output_toggle.toggled.connect(lambda _: self.refresh_log(force=True))
        self.body.addWidget(self.full_output_toggle)
        self.log = QPlainTextEdit()
        self.log.setObjectName("installationLog")
        self.log.setReadOnly(True)
        self.log.setAccessibleName(self.t("Installation details"))
        self.log.setFont(self._log_font)
        self.log.document().setDefaultFont(self._log_font)
        self.log.setMaximumBlockCount(2000)
        # Explicit font properties survive theme/font changes during installation.
        family = self._log_font.family().replace("\\", "\\\\").replace('"', '\\"')
        size = self._log_font.pointSizeF()
        font_size = f"{size}pt" if size > 0 else f"{self._log_font.pixelSize()}px"
        self.log.setStyleSheet(f'''
            QPlainTextEdit {{ background: #191b20; color: #d6dae1;
                border: 1px solid #343740; border-radius: 10px; padding: 12px;
                font-family: "{family}"; font-size: {font_size};
                font-weight: normal; font-style: normal;
                selection-background-color: #36577c; selection-color: #ffffff; }}
        ''')
        self.log.setFixedHeight(260)
        self.body.addWidget(self.log)
        def expanded(value):
            self._details_expanded = value
            self.log.setVisible(value)
            self.full_output_toggle.setVisible(value)
            self.refresh_log(force=True)
            title = self.operation_text("Hide details" if value else "Show details")
            self.details_toggle.setText(title)
            self.details_toggle.setAccessibleName(title)
            self.details_toggle.setToolTip(title)
            self.details_toggle.update()
        self.details_toggle.toggled.connect(expanded)
        self.details_toggle.setChecked(self._details_expanded)
        expanded(self._details_expanded)

    def save_log(self):
        path, _ = QFileDialog.getSaveFileName(self, self.operation_text("Save installation log"), "installation.log", self.operation_text("Log files (*.log);;All files (*)"))
        if not path:
            return
        try:
            self.bridge.saveLog(path)
        except OSError as exc:
            self.log.appendPlainText(self.operation_text("Couldn't save log: {error}").format(error=exc))
            self.details_toggle.setChecked(True)

    def page_progress(self):
        self.body.setSpacing(6)
        self.body.addSpacing(95)
        self.operation_detail = self.label("")
        self.operation_detail.setObjectName("detail")
        self.operation_detail.setTextFormat(Qt.TextFormat.PlainText)
        self.body.addWidget(self.operation_detail)
        row = QHBoxLayout()
        self.spinner = ProgressSpinner()
        self.spinner.setAccessibleName(self.operation_text("Removing components" if self.action == "uninstall" else "Installing components"))
        row.addWidget(self.spinner)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setAccessibleName(self.spinner.accessibleName())
        self.progress.setTextVisible(False)
        row.addWidget(self.progress, 1)
        self.body.addLayout(row)
        self.remaining_label = self.label("")
        self.remaining_label.setObjectName("detail")
        self.body.addWidget(self.remaining_label)
        self.details()
        self._eta_timer.start()
        self.refresh_progress()

    def refresh_progress(self):
        if self.page != "progress" or not hasattr(self, "progress"):
            self._eta_timer.stop()
            return
        fraction = max(0.0, min(1.0, self.bridge.progress))
        self.progress.setValue(round(fraction * 1000))
        self.progress.setAccessibleDescription(self.bridge.currentStep)
        elapsed = time.monotonic() - self._operation_started if self._operation_started is not None else 0
        self.remaining_label.setText(self.operation_text("Elapsed {duration}").format(duration=elapsed_text(elapsed, self.operation_text)))
        active = self.bridge.summary.phases.get(self.bridge.summary.active, {})
        self.operation_detail.setText(self.operation_text('Cancelling…' if self.bridge.cancelRequested else active.get('label', 'Preparing…')))
        self.refresh_log()

    def refresh_log(self, force=False):
        if self.page not in ('progress', 'done', 'removed', 'error') or not hasattr(self, 'log'):
            return
        self.full_output_toggle.setText(self.operation_text("Show summary" if self.full_output_toggle.isChecked() else "Show technical output"))
        if self.full_output_toggle.isChecked():
            if not force:
                return
            text = self.bridge.logTail()
        else:
            title = self.operation_text("Removing {edition}" if self.action == "uninstall" else "Installing {edition}").format(edition=self.edition)
            context = self.operation_text("{appearance} appearance · {launcher} launcher").format(
                appearance=self.operation_text(self.choices["appearance"].capitalize()),
                launcher=self.choices["launcher"].replace("golden", "Golden Gate").replace("tahoe", "Tahoe"))
            text = title + '\n' + context + '\n\n' + self.bridge.summary.text(self.operation_text)
            if self.bridge.statusMessage:
                text += '\n\n' + self.bridge.statusMessage
        if self.log.toPlainText() != text:
            bar = self.log.verticalScrollBar()
            position = bar.value()
            self.log.setPlainText(text)
            bar.setValue(position)

    def append_log(self, text):
        if self.page in ("progress", "error", "done", "removed") and hasattr(self, "log") and self.full_output_toggle.isChecked():
            bar = self.log.verticalScrollBar()
            following = bar.value() == bar.maximum()
            position = bar.value()
            self.log.appendPlainText(text)
            if not following:
                bar.setValue(position)

    def page_done(self):
        skipped = self.bridge.summary.phases.get('apply', {}).get('state') == 'skipped'
        title = self.t("{edition} files are installed" if skipped else "{edition} is ready").format(edition=self.edition)
        if self.bridge.summary.warnings:
            title = "Installation completed with warnings"
        self.body.addWidget(self.label(title, heading=True))
        if skipped:
            self.body.addWidget(self.label("Desktop preferences were left unchanged."))
        self.completion()

    def page_removed(self):
        self.body.addWidget(self.label("Removal completed", heading=True))
        self.completion()

    def completion(self):
        elapsed = getattr(self, '_operation_elapsed', 0)
        self.body.addWidget(self.label(self.t("Completed in {duration}").format(duration=elapsed_text(elapsed, self.t))))
        if self.bridge.summary.warnings:
            self.body.addWidget(self.label(self.t("{count} warning(s) · See details").format(count=len(self.bridge.summary.warnings))))
        self.details()

    def page_uninstall(self):
        self.body.addWidget(self.label(self.t("Uninstall")+" "+self.edition, heading=True))
        for text in ("Icons, fonts, sounds and appearance.", "Top bar, Dock and project widgets.",
                     "Effects and scheduled tasks."):
            line = self.label("•  " + self.t(text))
            self.body.addWidget(line)
        self.body.addSpacing(8)
        self.body.addWidget(self.label("The desktop will return to Breeze. Previous settings are restored where a backup exists."))
        note = self.label("Your documents and personal applications are kept.")
        note.setObjectName("detail"); self.body.addWidget(note)

    def page_error(self):
        cancelled = getattr(self, '_operation_code', None) == 130
        title = "Operation cancelled" if cancelled else self.t(
            "Couldn't build {component}" if self.bridge.summary.active == "build" else "Couldn't complete {component}"
        ).format(component=self.t(self.bridge.summary.failed_label()))
        self.body.addWidget(self.label(title, heading=True))
        note = self.label("Review the log before retrying. Some changes may already have been applied.")
        note.setObjectName("detail")
        self.body.addWidget(note)
        self._details_expanded = True
        self.details()
        self.full_output_toggle.setChecked(True)

    def previous(self):
        if self.reconfiguring and self.page in ("summary", "error"):
            self.reconfiguring = False
            self.settings_mode = True
            self.page, _ = self.settings_history[self.settings_index]
            self.configure_window_mode()
        elif self.editing:
            self.editing = False; self.page = "summary"
        elif self.page == "welcome":
            self.page = "uninstall"
        elif self.page in ("uninstall", "error"):
            self.page = "welcome"
        else:
            steps = self.visible_steps()
            self.page = steps[max(0, steps.index(self.page) - 1)]
        self.render()

    def show_glass_style(self):
        return self.choices["files"] == "nautilus" and self.choices["acrylic_glass"]

    def install_activated(self):
        return self.bridge.summary.phases.get("apply", {}).get("state") != "skipped"

    def advance(self):
        if self.page == "done" and self.install_activated():
            self.open_installed_settings()
            return
        if self.editing:
            self.editing = False; self.page = "summary"
        elif self.page in ("done", "removed"):
            self.close(); return
        elif self.page == "progress":
            self.bridge.cancel(); self.next.setEnabled(False); return
        elif self.page in ("summary", "uninstall", "error"):
            if self.page != "error":
                self.action = "uninstall" if self.page == "uninstall" else "install"
            self.bridge.setChoices(validate(self.choices))
            self.bridge.summary = ProgressModel(self.action)
            self._operation_started = time.monotonic()
            self._details_expanded = False
            self.page = "progress"; self.render(); self.bridge.start(self.action); return
        else:
            steps = self.visible_steps()
            self.page = steps[steps.index(self.page) + 1]
        self.render()

    def finished(self, code):
        self._operation_code = code
        self._operation_elapsed = time.monotonic() - self._operation_started if self._operation_started is not None else 0
        self._eta_timer.stop()
        if self.close_pending:
            self.close(); return
        self.next.setEnabled(True)
        self.page = ("removed" if self.action == "uninstall" else "done") if code == 0 else "error"
        self.render()

    def closeEvent(self, event):
        if self.appearance_process is not None:
            event.ignore()
        elif self.bridge.running:
            self.close_pending = True; self.bridge.cancel(); event.ignore()
        else:
            event.accept()
