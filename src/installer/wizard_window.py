"""Native, single-window installation and removal wizard.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
import json

from PyQt6.QtCore import Qt, QEvent, QPointF, QRectF, QSize
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QLinearGradient, QPen, QPixmap, QPolygonF, QRegion
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton,
    QRadioButton, QScrollArea, QSizePolicy, QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

from installer_choices import COLORS, defaults, validate

ASSETS = Path(__file__).with_name("assets")
ASSET_FILES = json.loads((ASSETS / "sources.json").read_text())
STEPS = (
    ("welcome", ""), ("appearance", "Which appearance would you like?"),
    ("icons", "Which icons and color would you like?"),
    ("wallpaper", "Which wallpaper would you like?"),
    ("launcher", "Which launcher would you like?"),
    ("layout", "What would you like to add to your desktop?"),
    ("effects", "Which effects would you like to enable?"),
    ("window_controls", "Which window controls would you like?"),
    ("fonts", "Which fonts would you like to use?"),
    ("firefox", "Apply the theme to Firefox?"),
    ("files", "Install Nautilus as your file manager?"),
    ("boot", "Change the boot animation?"),
    ("oled", "Enable OLED protection?"),
    ("summary", "Review your installation"),
)


def picture(name, width, height, other=None, *, cover=False):
    """Contain full screenshots; diagonal splits share the same canvas."""
    canvas = QPixmap(width*2, height*2)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.scale(2, 2)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for index, filename in enumerate((name, other)):
        if not filename:
            continue
        source = QPixmap(str(ASSETS / ASSET_FILES[filename]["file"]))
        if source.isNull():
            continue
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


def relative_font(widget, scale=1, weight=None):
    font = QFont(widget.font())
    font.setPointSizeF(font.pointSizeF() * scale)
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


class LanguageSelector(QComboBox):
    def focusInEvent(self, event):
        self.keyboard_focus = event.reason() in (
            Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
            Qt.FocusReason.ShortcutFocusReason)
        super().focusInEvent(event)
        self.update()

    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.currentText()) + 42, 32)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_glass_control(self, painter)
        painter.setPen(self.palette().text().color())
        painter.drawText(QRectF(12, 0, self.width()-36, self.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.currentText())
        x, y = self.width()-15, self.height()/2
        painter.setPen(QPen(self.palette().text().color(), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(x-3, y-1.5), QPointF(x, y+1.5))
        painter.drawLine(QPointF(x, y+1.5), QPointF(x+3, y-1.5))


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


class CheckOption(QCheckBox):
    """Keep native checkbox behavior with the same mark as selection cards."""
    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text())+26,
                     max(32, self.fontMetrics().height()+14))

    def hitButton(self, point):
        return self.rect().contains(point)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
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
        painter.drawText(QRectF(26, 0, self.width()-26, self.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())


class RadioOption(QRadioButton):
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
        self.setFixedSize(132, 20)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(1, len(STEPS)):
            active = index == self.index
            painter.setBrush(self.palette().windowText() if active else self.palette().mid())
            radius = 3 if active else 2
            painter.drawEllipse(QPointF(5 + (index - 1) * 11, 10), radius, radius)


class PreviewImage(QWidget):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.pixmap = pixmap
        self.setFixedHeight(round(pixmap.deviceIndependentSize().height()))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # The image canvas has the card's exact aspect ratio; the source was
        # contained by picture(), so no desktop edges are lost here.
        painter.drawPixmap(self.rect(), self.pixmap)


class ChoiceCard(QPushButton):
    def __init__(self, title, detail, pixmap, checked, parent=None, *, independent=False, compact=False):
        super().__init__(parent)
        self.setFont(parent.window().font())
        self.independent = independent
        self.compact = compact
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
        text.setContentsMargins(15, 11 if compact else 13, 40, 11 if compact else 14)
        text.setSpacing(4)
        label = QLabel(title)
        label.setWordWrap(True)
        label.setFont(relative_font(self, .93, QFont.Weight.Bold))
        text.addWidget(label)
        if detail:
            description = QLabel(detail)
            description.setWordWrap(True)
            description.setFont(relative_font(self, .79))
            description.setObjectName("detail")
            text.addWidget(description)
        copy.setMinimumHeight(40 if compact else 66)
        layout.addWidget(copy)
        self.copy = copy
        self.setFixedHeight(layout.sizeHint().height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.size().width() == event.oldSize().width():
            return
        # Translated descriptions can wrap to different line counts. Reserve
        # the tallest caption and preview for every card in the same row.
        copy_height = max(max(40 if card.compact else 66,
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
        border = accent if self.isChecked() or self.hasFocus() else QColor(self.window().line)
        painter.setPen(QPen(border, 2 if self.isChecked() or self.hasFocus() else 1))
        painter.setBrush(self.palette().base())
        painter.drawRoundedRect(QRectF(1, 1, self.width()-2, self.height()-2), 8, 8)
        indicator = QRectF(self.width()-31, self.height()-(29 if self.compact else 36) if self.photo else (self.height()-18)/2, 18, 18)
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


class InstallerWindow(OpaqueSurface):
    def __init__(self, bridge, *, uninstall=False):
        super().__init__()
        self.bridge = bridge
        self.defaults = defaults()
        self.choices = dict(self.defaults)
        from cli import _theme_is_already_installed
        self.existing_install = _theme_is_already_installed()
        self.edition = "Golden Gate" if bridge.editionName == "MacGoldenGate" else "Tahoe"
        self.asset_edition = "golden-gate" if self.edition == "Golden Gate" else "tahoe"
        self.page = "uninstall" if uninstall else "welcome"
        self.editing = False
        self.action = "install"
        self.close_pending = False
        self.update_available = ""
        self.updating = False
        self.groups = []
        self.setObjectName("installerWindow")
        self.setWindowTitle(self.t("Install") + " " + self.edition)
        # Use the system face and scale its hierarchy together with accessibility settings.
        self.setFont(relative_font(self, 7/6))
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.resize(820, 606)
        self.setMinimumSize(820, 606)
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
        lights.addWidget(self.maximize_button)
        lights.addStretch()
        self.layout.addWidget(self.header)
        self.scroll = PageScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.layout.addWidget(self.scroll, 1)
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
        self.language = LanguageSelector()
        self.language.setObjectName("languageSelector")
        self.language.setFont(relative_font(self, .86))
        for item in bridge.languages:
            self.language.addItem(item["label"], item["code"])
        self.language.setCurrentIndex(max(0, self.language.findData(bridge.language)))
        self.language.currentIndexChanged.connect(self.language.updateGeometry)
        self.language.currentIndexChanged.connect(self.change_language)
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
        bridge.runningChanged.connect(self.refresh_window_controls)
        bridge.finished.connect(self.finished)
        bridge.progressChanged.connect(self.refresh_progress)
        bridge.currentStepChanged.connect(self.refresh_progress)
        bridge.logAppended.connect(self.append_log)
        bridge.updateChecked.connect(self.update_checked)
        bridge.updateReturned.connect(self.update_returned)
        self.render()
        self.next.setFocus(Qt.FocusReason.OtherFocusReason)

    def express_install(self):
        if self.page != "welcome" or self.bridge.running or self.updating:
            return
        self.choices = dict(self.defaults)
        self.editing = False
        self.action = "install"
        self.page = "summary"
        self.render()
        self.next.setFocus(Qt.FocusReason.OtherFocusReason)

    def refresh_window_controls(self):
        self.close_button.setEnabled(not self.bridge.running)
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

    def change_language(self):
        if self.bridge.setLanguage(self.language.currentData()):
            self.render()

    def label(self, text, *, heading=False):
        widget = QLabel(self.t(text))
        widget.setFont(self.font())
        widget.setWordWrap(True)
        widget.setTextFormat(Qt.TextFormat.PlainText)
        if heading:
            font = widget.font(); font.setPointSizeF(font.pointSizeF() * 1.57)
            font.setWeight(QFont.Weight.Bold); widget.setFont(font)
            widget.setObjectName("pageTitle")
        return widget

    def image(self, filename, width=730, height=270, other=None, *, background=None):
        widget = QLabel()
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self.choices[key] = value
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
        if self.page == "icons":
            if key == "color":
                for name, button in self.color_buttons.items():
                    button.setText("✓" if name == value else "")
                self.glass_preview.pixmap = self.icon_sample(True)
                self.glass_preview.update()
                self.accent_preview.setPixmap(picture(
                    f"accent-{self.asset_edition}-{self.mode}-{value}.jpg", 236, 133))
            elif key == "icons":
                self.icon_caption.setText(self.t("Icons, selections, top bar and Dock."
                                                if value == "glass" else "Selections, top bar and Dock."))
        elif self.page == "wallpaper" and key == "wallpaper":
            self.wallpaper_filename.setText(Path(self.choices["wallpaper_path"]).name)
            self.wallpaper_filename.setVisible(value == "custom")
        elif self.page == "files" and key == "files":
            self.bookmarks.setVisible(value == "nautilus")
        elif self.page == "oled" and key == "oled_care":
            for spin in self.content.findChildren(QSpinBox):
                spin.setEnabled(value)

    def cards(self, key, items, *, columns=2, independent=False, compact=False):
        grid = QGridLayout()
        grid.setHorizontalSpacing(18 if columns == 2 else 14)
        grid.setVerticalSpacing(14)
        group = None
        if not independent:
            group = QButtonGroup(self.content)
            group.setExclusive(True)
            self.groups.append(group)
            items = sorted(items, key=lambda item: item[0] != self.defaults[key])
        row_cards = []
        for i, (value, title, detail, pixmap) in enumerate(items):
            choice_key = value if independent else key
            checked = self.choices[choice_key] if independent else self.choices[key] == value
            card = ChoiceCard(self.t(title), self.t(detail), pixmap, checked, self.content,
                              independent=independent, compact=compact)
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

    def radio(self, key, values, *, inline=False):
        group = QButtonGroup(self.content)
        self.groups.append(group)
        row = QHBoxLayout() if inline else self.body
        if inline:
            row.setSpacing(22)
        for value, label in sorted(values, key=lambda item: item[0] != self.defaults[key]):
            button = RadioOption(self.t(label))
            button.setFont(relative_font(self, .93))
            button.setObjectName(f"choice-{key}-{value}")
            self.bind_choice(key, value, button)
            button.setChecked(self.choices[key] == value)
            group.addButton(button)
            button.clicked.connect(lambda _, k=key, v=value: self.select(k, v))
            if inline:
                row.addWidget(button, 1)
            else:
                row.addWidget(button)
        if inline:
            self.body.addLayout(row)

    def checkbox(self, key, text):
        button = CheckOption(self.t(text))
        button.setFont(relative_font(self, .93))
        button.setObjectName(f"choice-{key}")
        button.setChecked(self.choices[key])
        button.toggled.connect(lambda value: self.choices.update({key: value}))
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
        focused = QApplication.focusWidget()
        focus_name = focused.objectName() if focused else ""
        # Follow the desktop appearance; the installation choices affect previews only.
        self.accent = "#007aff"
        light = self.window().palette().window().color().lightnessF() > .5
        surface, footer = ("#f6f6f6", "#eeeeee") if light else ("#292929", "#242424")
        self.surface_color = QColor(surface)
        self.scroll.surface_color = QColor(surface)
        self.footer.surface_color = QColor(footer)
        self.line = "#c9c9c9" if light else "#626262"
        self.footer.top_border = QColor(self.line)
        muted = "#686868" if light else "#bcbcbc"
        foreground = "#292929" if light else "#eeeeee"
        operation = "Uninstall" if self.page in ("uninstall", "removed") or (self.page in ("progress", "error") and self.action == "uninstall") else "Install"
        self.setWindowTitle(self.t(operation) + " " + self.edition)
        self.close_button.setAccessibleName(self.t("Close"))
        self.close_button.setToolTip(self.t("Close"))
        self.refresh_window_controls()
        stylesheet = f"""
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
        self.content = OpaqueSurface()
        self.content.surface_color = QColor(surface)
        self.content.setObjectName("wizardContent")
        self.content.setPalette(self.palette())
        self.content.setFont(self.font())
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(38, 28, 38, 22)
        self.body.setSpacing(12)
        titles = dict(STEPS)
        if self.page in titles and titles[self.page]:
            self.body.addWidget(self.label(titles[self.page], heading=True))
            self.body.addSpacing(10)
        getattr(self, "page_" + self.page)()
        self.body.addStretch()
        self.scroll.setWidget(self.content)
        index = next((i for i, item in enumerate(STEPS) if item[0] == self.page), -1)
        self.version_label.setVisible(self.page == "welcome")
        self.welcome_actions.setVisible(self.page == "welcome")
        self.express.setText(self.t("Express install"))
        self.express.setToolTip(self.t("Use the defaults and review before installing."))
        self.express.setEnabled(not self.updating and not self.bridge.running)
        self.dots.setVisible(0 < index < len(STEPS))
        self.dots.index = index
        self.dots.update()
        self.dots.setAccessibleName(self.t("Step") + f" {index}/{len(STEPS)-1}")
        self.back.setVisible(self.page not in ("progress", "done", "removed"))
        self.back.setText(self.t("Uninstall" if self.page == "welcome" else "Back"))
        self.next.setText(self.t(
            "Save" if self.editing else
            "Install" if self.page in ("welcome", "summary") else
            "Uninstall" if self.page == "uninstall" else
            "Cancel" if self.page == "progress" else
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
        self.body.addWidget(self.image("logo-27.png" if self.edition == "Golden Gate" else "logo-26.png", 180, 180))
        title = self.label(self.t("Install") + " " + self.edition, heading=True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter); self.body.addWidget(title)
        text = self.label("Choose your options and begin installation.")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter); self.body.addWidget(text)
        if self.update_available:
            text = self.t("Update available:") + " " + self.update_available
            update = QPushButton(text)
            update.setEnabled(not self.updating)
            update.clicked.connect(self.update_installer)
            self.body.addWidget(update)

    def page_appearance(self):
        self.body.addSpacing(28)
        stem = f"desktop-{self.asset_edition}-"
        self.cards("appearance", [
            ("auto", "Automatic", "Light by day, dark at night.", picture(stem+"light.jpg", 232, 131, stem+"dark.jpg")),
            ("light", "Light", "", picture(stem+"light.jpg", 232, 131)),
            ("dark", "Dark", "", picture(stem+"dark.jpg", 232, 131)),
        ], columns=3)

    def icon_sample(self, glass=False):
        pixmap = QPixmap(724, 220); pixmap.fill(QColor("#edf0f3"))
        painter = QPainter(pixmap); painter.scale(2, 2)
        if glass:
            stage = QLinearGradient(0, 0, 362, 110)
            stage.setColorAt(0, QColor("#e9edf2")); stage.setColorAt(.65, QColor("#d5e0eb")); stage.setColorAt(1, QColor("#f4f6f8"))
            painter.fillRect(0, 0, 362, 110, stage)
            for i in range(4):
                icon = picture(f"glass-{self.mode}-{self.choices['color']}-{i}.png", 55, 55)
                painter.drawPixmap(55+i*65, 27, icon)
        else:
            painter.fillRect(181, 0, 181, 110, QColor("#333a45"))
            for side, mode in enumerate(("light", "dark")):
                painter.setFont(relative_font(self, .71))
                painter.setPen(QColor("#686868" if side == 0 else "#d8dce3"))
                painter.drawText(QRectF(side*181, 9, 181, 15), Qt.AlignmentFlag.AlignCenter,
                                 self.t("Light" if mode == "light" else "Dark"))
                for i in range(8):
                    painter.drawPixmap(side*181+17+(i%4)*39, 29+(i//4)*35,
                                       picture(f"regular-{mode}-{i}.png", 32, 32))
        painter.end(); pixmap.setDevicePixelRatio(2); return pixmap

    def page_icons(self):
        group = self.cards("icons", [
            ("regular", "Regular", "Light and dark, following your appearance.", self.icon_sample()),
            ("glass", "Glass", "Translucent, with your chosen color.", self.icon_sample(True)),
        ])
        keep = ChoiceCard(self.t("Keep my icons"), "", None, self.choices["icons"] == "keep", self.content, compact=True)
        keep.setObjectName("choice-icons-keep")
        group.addButton(keep)
        self.bind_choice("icons", "keep", keep)
        self.glass_preview = next(button.photo for button in group.buttons()
                                  if button.objectName() == "choice-icons-glass")
        keep.clicked.connect(lambda: self.select("icons", "keep")); self.body.addWidget(keep)
        self.separator()
        row = QHBoxLayout(); controls = QVBoxLayout()
        title = self.label("Theme color")
        title.setFont(relative_font(self, .93, QFont.Weight.Bold))
        controls.addWidget(title)
        swatches = QHBoxLayout()
        swatches.setContentsMargins(4, 4, 0, 4)
        swatches.setSpacing(14)
        self.color_buttons = {}
        for name, color in COLORS.items():
            button = QPushButton("✓" if self.choices["color"] == name else "")
            button.setObjectName("color-"+name); button.setAccessibleName(self.t(name.capitalize()))
            button.setFixedSize(23, 23)
            button.setCheckable(True)
            button.setChecked(self.choices["color"] == name)
            button.setStyleSheet(f"QPushButton {{ background:{color};color:white;border:1px solid #00000018;"
                                 "border-radius:11px;padding:0 } QPushButton:checked { border:2px solid #555 }")
            self.bind_choice("color", name, button)
            self.color_buttons[name] = button
            button.clicked.connect(lambda _, value=name: self.select("color", value))
            swatches.addWidget(button)
        swatches.addStretch()
        controls.addLayout(swatches)
        caption = self.label("Icons, selections, top bar and Dock." if self.choices["icons"] == "glass" else "Selections, top bar and Dock.")
        caption.setFont(relative_font(self, .79)); caption.setObjectName("detail")
        self.icon_caption = caption
        controls.addWidget(caption); controls.addStretch(); row.addLayout(controls, 1)
        self.accent_preview = self.image(f"accent-{self.asset_edition}-{self.mode}-{self.choices['color']}.jpg", 236, 133)
        row.addWidget(self.accent_preview)
        self.body.addLayout(row)

    @property
    def mode(self):
        return "dark" if self.choices["appearance"] == "dark" else "light"

    def page_wallpaper(self):
        group = self.cards("wallpaper", [(key, label, "", picture(key+".jpg", 362, 112, key+"-dark.jpg", cover=True))
                   for key, label in (("tahoe", "Tahoe"), ("golden", "Golden Gate"),
                                      ("landscape", "Landscape"), ("sonoma", "Sonoma"))], compact=True)
        row = QHBoxLayout()
        keep = RadioOption(self.t("Keep my wallpaper"))
        keep.setFont(relative_font(self, .93))
        keep.setChecked(self.choices["wallpaper"] == "keep")
        group.addButton(keep)
        self.bind_choice("wallpaper", "keep", keep)
        keep.clicked.connect(lambda: self.select("wallpaper", "keep"))
        row.addWidget(keep); row.addStretch()
        button = QPushButton(self.t("Choose a file…")); button.clicked.connect(self.choose_file)
        button.setObjectName("textLink")
        row.addWidget(button); self.body.addLayout(row)
        self.wallpaper_filename = self.label(Path(self.choices["wallpaper_path"]).name)
        self.wallpaper_filename.setVisible(self.choices["wallpaper"] == "custom")
        self.body.addWidget(self.wallpaper_filename)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, self.t("Choose a wallpaper"), "", "Images (*.png *.jpg *.jpeg *.webp)")
        if path and not QPixmap(path).isNull():
            self.choices["wallpaper_path"] = path
            self.select("wallpaper", "custom")

    def page_launcher(self):
        self.cards("launcher", [
            ("tahoe", "Tahoe", "Categories and apps in one window.", picture("launcher-tahoe.jpg", 362, 204)),
            ("golden", "Golden Gate", "Separate search and application grid.", picture("launcher-golden.jpg", 362, 204)),
        ])
        if self.existing_install and not self.choices["reset_layout"]:
            self.body.addWidget(self.label("The current launcher setup is kept unless you reset the layout."))

    def page_layout(self):
        self.body.addSpacing(4)
        reset = self.checkbox("reset_layout", "Reset Dock and panel customization")
        self.body.addWidget(self.label("Reinstall keeps your layout, sizes, hiding behavior and widgets unless reset is selected."))
        self.cards("", [
            ("panel", "Top bar", "Global menu, clock and system controls.", picture("panel-detail.jpg", 362, 160)),
            ("dock", "Dock", "Pinned apps and open windows.", picture("dock.jpg", 362, 160)),
        ], independent=True)
        def enable_layout_options():
            for card in self.content.findChildren(ChoiceCard):
                card.setEnabled(not self.existing_install or self.choices["reset_layout"])
        reset.toggled.connect(enable_layout_options)
        enable_layout_options()

    def corner_sample(self):
        source = QPixmap(str(ASSETS / ASSET_FILES["corners.jpg"]["file"]))
        canvas = QPixmap(724, 330); canvas.fill(QColor("#dbe3e8"))
        painter = QPainter(canvas)
        fitted = source.scaledToWidth(round(724*2.2), Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap(0, 0, fitted); painter.end(); canvas.setDevicePixelRatio(2)
        return canvas

    def page_effects(self):
        self.cards("", [
            ("acrylic_glass", "Transparency and blur", "Panels, menus and windows.", picture("glass.jpg", 362, 165, cover=True)),
            ("rounded_corners", "Rounded corners", "Preserves your radius settings.", self.corner_sample()),
        ], independent=True)

        self.body.addWidget(self.label("Window shadows"))
        self.radio("shadows", [("none", "None"), ("soft", "Soft"),
                               ("medium", "Medium"), ("hard", "Hard")], inline=True)
        self.body.addWidget(self.label("Applies to the theme's window decorations and GTK windows."))

    def page_window_controls(self):
        self.cards("window_controls", [
            ("flat", "Flat", "Simple, solid colors.",
             picture(f"window-controls-flat-{self.mode}.png", 362, 190)),
            ("glassy", "Glassy", "Soft gradients and reflective highlights.",
             picture(f"window-controls-glassy-{self.mode}.png", 362, 190)),
        ])
        self.body.addWidget(self.label("Close, minimize and maximize buttons."))

    def page_fonts(self):
        self.cards("fonts", [
            (True, "Theme fonts", "SF Pro", self.font_sample(True)),
            (False, "Keep my fonts", "Keep the current typography.", self.font_sample(False)),
        ])

    def font_sample(self, theme):
        from PyQt6.QtGui import QFontDatabase
        font = QFont(self.font())
        if theme:
            from paths import REPO_ROOT
            if not hasattr(self, "specimen_family"):
                candidates = sorted((REPO_ROOT / "src/offline/fonts").rglob("SF-Pro-Display-Regular.otf"))
                families = QFontDatabase.applicationFontFamilies(QFontDatabase.addApplicationFont(str(candidates[0]))) if candidates else []
                self.specimen_family = families[0] if families else ""
            if self.specimen_family:
                font = QFont(self.specimen_family, font.pointSize())
        canvas = QPixmap(724, 468); canvas.fill(self.palette().base().color())
        painter = QPainter(canvas); painter.scale(2, 2); painter.setPen(self.palette().text().color())
        font.setPointSizeF(self.font().pointSizeF()*2.4); font.setWeight(QFont.Weight.Bold); painter.setFont(font)
        painter.drawText(22, 78, self.t("Your files."))
        font.setPointSizeF(self.font().pointSizeF()*1.07); font.setWeight(QFont.Weight.Normal); painter.setFont(font)
        painter.drawText(22, 120, self.t("Documents, photos and ideas."))
        painter.drawText(22, 142, self.t("Everything in its place."))
        font.setPointSizeF(self.font().pointSizeF()*1.5); painter.setFont(font)
        painter.drawText(22, 184, "09:41    0123456789"); painter.end()
        canvas.setDevicePixelRatio(2)
        return canvas

    def page_firefox(self):
        self.body.addWidget(self.image("firefox-"+self.mode+".jpg", width=744, height=298, background="#e5e8ec"))
        self.radio("firefox", [(True, "Apply the theme"), (False, "Keep Firefox as it is")], inline=True)

    def page_files(self):
        self.body.addSpacing(5)
        group = self.cards("files", [
            ("nautilus", "Install Nautilus", "Install and use as the default file manager.", picture("nautilus-"+self.mode+".jpg", 362, 180)),
            ("dolphin", "Use Dolphin", "Skip Nautilus and use KDE's file manager.", picture("dolphin-"+self.mode+".jpg", 362, 180)),
        ])
        keep = RadioOption(self.t("Skip Nautilus and keep my file manager"))
        keep.setObjectName("choice-files-keep")
        keep.setFont(relative_font(self, .93))
        keep.setChecked(self.choices["files"] == "keep")
        group.addButton(keep)
        self.bind_choice("files", "keep", keep)
        keep.clicked.connect(lambda: self.select("files", "keep"))
        self.body.addWidget(keep)
        self.bookmarks = self.checkbox("nautilus_bookmarks", "Add folder shortcuts to the sidebar")
        self.bookmarks.setVisible(self.choices["files"] == "nautilus")

    def page_boot(self):
        self.body.addWidget(self.image("boot.jpg", width=744, height=255, background="#000000"))
        self.radio("plymouth", [(True, "Use the theme animation"), (False, "Keep my boot animation")], inline=True)

    def page_oled(self):
        self.radio("oled_care", [(False, "Do not enable"), (True, "Enable pixel shifting")])
        for key, title, maximum in (("oled_interval", "Interval (minutes)", 59), ("oled_max_shift", "Maximum shift (pixels)", 16)):
            row = QHBoxLayout(); label = self.label(title)
            label.setMinimumWidth(290); row.addWidget(label)
            spin = QSpinBox(); spin.setRange(1, maximum); spin.setValue(self.choices[key])
            spin.setEnabled(self.choices["oled_care"]); spin.setObjectName(key)
            spin.valueChanged.connect(lambda value, k=key: self.choices.update({k: value}))
            spin.setFixedWidth(80)
            row.addWidget(spin); row.addStretch(); self.body.addLayout(row)

    def page_summary(self):
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(0)
        c = self.choices
        names = {"auto": "Automatic", "light": "Light", "dark": "Dark", "regular": "Regular",
                 "glass": "Glass", "keep": "Keep", "golden": "Golden Gate", "tahoe": "Tahoe",
                 "landscape": "Landscape", "sonoma": "Sonoma", "custom": "Custom file",
                 "nautilus": "Nautilus", "dolphin": "Dolphin"}
        value = lambda key: self.t(names.get(str(c[key]), str(c[key]).capitalize()))
        enabled = lambda key: self.t("Enabled" if c[key] else "Disabled")
        desktop = " + ".join(self.t(label) for key, label in (("panel", "Top bar"), ("dock", "Dock")) if c[key])
        keep_layout = self.existing_install and not c["reset_layout"]
        if keep_layout:
            desktop = self.t("Keep current layout")
        elif self.existing_install and desktop:
            desktop = self.t("Reset layout") + ": " + desktop
        effects = " + ".join(self.t(label) for key, label in (("acrylic_glass", "Glass"), ("rounded_corners", "Rounded corners")) if c[key])
        effects = (effects or self.t("Disabled")) + " · " + self.t({
            "none": "No shadows", "soft": "Soft shadows",
            "medium": "Medium shadows", "hard": "Hard shadows"}[c["shadows"]])
        rows = (
            ("appearance", "Appearance", value("appearance"), "appearance"),
            ("icons", "Icons", value("icons"), "icons"),
            ("color", "Color", value("color"), "icons"),
            ("wallpaper", "Background", value("wallpaper"), "wallpaper"),
            ("launcher", "Launcher", self.t("Keep") if keep_layout else value("launcher"), "launcher"),
            ("panel", "Desktop", desktop or self.t("Keep"), "layout"),
            ("acrylic_glass", "Effects", effects or self.t("Disabled"), "effects"),
            ("window_controls", "Window controls", value("window_controls"), "window_controls"),
            ("fonts", "Fonts", self.t("Theme fonts" if c["fonts"] else "Keep"), "fonts"),
            ("firefox", "Firefox", enabled("firefox"), "firefox"),
            ("files", "Files", self.t("Keep my file manager") if c["files"] == "keep" else value("files"), "files"),
            ("plymouth", "Boot", enabled("plymouth"), "boot"),
            ("oled_care", "OLED", enabled("oled_care"), "oled"),
        )
        for i, (key, title, text, step) in enumerate(rows):
            entry = QWidget()
            entry.setObjectName("summaryEntry")
            entry.setStyleSheet(f"QWidget#summaryEntry {{ border-bottom: 1px solid {self.line}; }}")
            row = QHBoxLayout(entry); row.setContentsMargins(0, 9, 0, 9); row.setSpacing(12)
            label = self.label(title); label.setObjectName("detail"); label.setFixedWidth(94)
            label.setFont(relative_font(self, .86)); row.addWidget(label)
            choice = self.label(text); choice.setFont(relative_font(self, .86)); row.addWidget(choice, 1)
            button = QPushButton(self.t("Change")); button.setFlat(True)
            button.setFont(relative_font(self, .79))
            button.setStyleSheet(f"border:0; background:transparent; color:{self.accent}; padding:0;")
            button.setObjectName("edit-"+key); button.setAccessibleName(self.t("Change")+" "+self.t(title))
            button.clicked.connect(lambda _, page=step: self.edit(page)); row.addWidget(button)
            grid.addWidget(entry, i//2, i%2)
        self.body.addLayout(grid)
        self.body.addSpacing(8)
        self.separator()
        title = self.label("Included with the theme")
        title.setFont(relative_font(self, .93, QFont.Weight.Bold)); self.body.addWidget(title)
        included = self.label("Global menu, window theme, cursors, sounds, Qt and GTK styles and file dialogs.")
        included.setObjectName("detail")
        included.setFont(relative_font(self, .86)); self.body.addWidget(included)
        note = self.label("The theme is applied immediately when installation finishes.")
        note.setFont(relative_font(self, .86)); self.body.addWidget(note)

    def edit(self, page):
        self.editing = True; self.page = page; self.render()

    def details(self):
        toggle = QToolButton()
        toggle.setText(self.t("Installation details"))
        toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toggle.setArrowType(Qt.ArrowType.RightArrow)
        toggle.setCheckable(True)
        toggle.setAutoRaise(True)
        self.body.addWidget(toggle, 0, Qt.AlignmentFlag.AlignLeft)
        self.log = QPlainTextEdit(self.bridge.logTail()); self.log.setReadOnly(True)
        self.log.setAccessibleName(self.t("Installation details"))
        self.log.setMinimumHeight(110)
        self.body.addWidget(self.log)
        self.log.hide()
        def expanded(value):
            self.log.setVisible(value)
            toggle.setArrowType(Qt.ArrowType.DownArrow if value else Qt.ArrowType.RightArrow)
        toggle.toggled.connect(expanded)

    def page_progress(self):
        self.body.addWidget(self.label("Uninstalling…" if self.action == "uninstall" else "Installing…", heading=True))
        self.body.addSpacing(60)
        self.step_label = self.label(self.bridge.currentStep or self.t("Preparing…"))
        self.body.addWidget(self.step_label)
        self.progress = QProgressBar(); self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False); self.body.addWidget(self.progress)
        self.body.addSpacing(12)
        self.details()
        self.refresh_progress()

    def refresh_progress(self):
        if self.page == "progress" and hasattr(self, "progress"):
            self.progress.setValue(round(self.bridge.progress * 1000))
            self.step_label.setText(self.bridge.currentStep or self.t("Preparing…"))

    def append_log(self, text):
        if self.page == "progress" and hasattr(self, "log"):
            self.log.appendPlainText(text)

    def page_done(self):
        self.body.addWidget(self.label("Installation complete", heading=True))
        self.body.addWidget(self.label("The theme is now applied. You can close the installer."))
        self.completion()

    def page_removed(self):
        self.body.addWidget(self.label("Uninstallation complete", heading=True))
        self.body.addWidget(self.label("The theme components have been removed."))
        self.completion()

    def completion(self):
        self.body.addSpacing(43)
        mark = self.label("✓")
        mark.setFont(relative_font(self, 2.5))
        mark.setFixedSize(62, 62)
        mark.setStyleSheet("border: 1.5px solid #6b8e71; border-radius:31px; color:#4f7655;")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.addWidget(mark, 0, Qt.AlignmentFlag.AlignLeft)

    def page_uninstall(self):
        self.body.addWidget(self.label(self.t("Uninstall")+" "+self.edition, heading=True))
        self.body.addWidget(self.label("The following theme components will be removed:"))
        for text in ("Icons, fonts, sounds and appearance.", "Top bar, Dock and project widgets.",
                     "Effects and scheduled tasks."):
            line = self.label("•  " + self.t(text))
            self.body.addWidget(line)
        self.body.addSpacing(8)
        self.body.addWidget(self.label("The desktop will return to Breeze. Previous settings are restored where a backup exists."))
        note = self.label("Your documents and personal applications are kept.")
        note.setObjectName("detail"); self.body.addWidget(note)

    def page_error(self):
        self.body.addWidget(self.label("The operation could not be completed", heading=True))
        note = self.label("Review the installation details before trying again.")
        note.setObjectName("detail"); self.body.addWidget(note)
        self.body.addSpacing(12)
        self.details()

    def previous(self):
        if self.editing:
            self.editing = False; self.page = "summary"
        elif self.page == "welcome":
            self.page = "uninstall"
        elif self.page in ("uninstall", "error"):
            self.page = "welcome"
        else:
            index = [item[0] for item in STEPS].index(self.page)
            self.page = STEPS[max(0, index-1)][0]
        self.render()

    def advance(self):
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
            self.page = "progress"; self.render(); self.bridge.start(self.action); return
        else:
            index = [item[0] for item in STEPS].index(self.page)
            self.page = STEPS[index+1][0]
        self.render()

    def finished(self, code):
        if self.close_pending:
            self.close(); return
        self.next.setEnabled(True)
        self.page = ("removed" if self.action == "uninstall" else "done") if code == 0 else "error"
        self.render()

    def closeEvent(self, event):
        if self.bridge.running:
            self.close_pending = True; self.bridge.cancel(); event.ignore()
        else:
            event.accept()
