"""Settings controls for the installed KWin material configuration module."""

from ctypes import CDLL, c_void_p
from functools import cache
import os
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QLibraryInfo, QPoint, QSignalBlocker, Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMenu, QPlainTextEdit, QPushButton,
    QRadioButton, QSlider, QSpinBox, QStyle, QStyleOptionSlider, QTabWidget, QVBoxLayout, QWidget, QWidgetAction,
)

from accent_colors import COLORS
from wizard_window import ColorSwatch, GlassButton, GlassComboBox, SettingsSwitch, relative_font


@cache
def _loaded_editor():
    plugins = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
    backends = ("kwin-x11", "kwin") if os.environ.get("XDG_SESSION_TYPE") == "x11" else ("kwin", "kwin-x11")
    for backend in backends:
        module = plugins / backend / "effects/configs/kwin_liquidglass_config.so"
        if not module.is_file():
            continue
        try:
            library = CDLL(str(module))
            attach = library.mttkde_attach_glass_editor
        except (OSError, AttributeError):
            continue
        attach.argtypes = [c_void_p]
        attach.restype = None
        return library, attach
    return None


class GradientSwatch(ColorSwatch):
    def __init__(self, field, editor):
        super().__init__(field.property("color"))
        self.field = field
        self.editor = editor
        self.setCheckable(False)
        self.setAccessibleName(field.accessibleName())
        self.clicked.connect(self.open_palette)

    def open_palette(self):
        menu = QMenu(self)
        action = QWidgetAction(menu)
        panel = QWidget()
        row = QHBoxLayout(panel)
        row.setContentsMargins(8, 5, 8, 5)
        row.setSpacing(3)
        colors = {"White": "#ffffff", "Black": "#000000", **COLORS}
        for name, value in colors.items():
            dot = ColorSwatch(value)
            dot.setChecked(self.color == dot.color)
            dot.setAccessibleName(self.editor.host.t(name.capitalize()))
            dot.setToolTip(dot.accessibleName())
            dot.clicked.connect(lambda _, color=dot.color: (self.choose(color), menu.close()))
            row.addWidget(dot)
        action.setDefaultWidget(panel)
        menu.addAction(action)
        custom = menu.addAction(QColorDialog.tr("Custom colors") + "…")
        anchor = self.mapToGlobal(QPoint(self.width() - menu.sizeHint().width(), self.height()))
        if menu.exec(anchor) == custom:
            self.choose(QColorDialog.getColor(self.color, self, self.accessibleName()))

    def choose(self, color):
        if color.isValid():
            self.field.setProperty("color", color)
            self.editor.refresh()


class MaterialSlider(QSlider):
    """A track click picks a value and starts a normal Qt drag."""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            option = QStyleOptionSlider()
            self.initStyleOption(option)
            style = self.style()
            handle = style.subControlRect(QStyle.ComplexControl.CC_Slider, option,
                                          QStyle.SubControl.SC_SliderHandle, self)
            if not handle.contains(event.position().toPoint()):
                groove = style.subControlRect(QStyle.ComplexControl.CC_Slider, option,
                                              QStyle.SubControl.SC_SliderGroove, self)
                pos = round(event.position().x()) - groove.left() - handle.width() // 2
                self.setValue(QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(), pos, groove.width() - handle.width(),
                    option.upsideDown))
        super().mousePressEvent(event)


class EmbeddedEditor(QWidget):
    def __init__(self, host, attach):
        super().__init__(host)
        self.host = host
        self.setObjectName("acrylicGlassEditor")
        # KWin owns preset profiles, validation and persistence. Only the Settings
        # controls below are presented; the module provides its loaded field model.
        self.module = QWidget(self)
        self.module.hide()
        attach(sip.unwrapinstance(self.module))
        self.buttons = self.module.findChild(QDialogButtonBox, "glassEditorButtons")
        self.apply_button = self.buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.bindings = []
        self.slider_readouts = []
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(7)
        tabs = self.module.findChild(QTabWidget, "settingsTabs")
        groups = (("presetGroup", "surfaceGroup", "gradientGroup"), ("opticsGroup",),
                  ("groupCornerRadius",), ("groupForceBlurList", "groupMatchMode"))
        for index, group_names in enumerate(groups):
            title = host.label(tabs.tabText(index), heading=True)
            title.setContentsMargins(4, 10, 0, 0)
            self.body.addWidget(title)
            for name in group_names:
                group = self.module.findChild(QGroupBox, name)
                heading = host.label(group.title())
                heading.setFont(relative_font(host, .88, QFont.Weight.DemiBold))
                heading.setContentsMargins(4, 7, 0, 0)
                self.body.addWidget(heading)
                card = self.card(self.body)
                if name == "gradientGroup":
                    self.gradient(card, group)
                elif name == "groupMatchMode":
                    options = group.findChildren(QRadioButton)
                    picker = GlassComboBox()
                    for opt in options:
                        picker.addItem(opt.text())
                    picker.activated.connect(lambda i, items=options: items[i].click())
                    self.bindings.append(lambda p=picker, items=options: p.setCurrentIndex(
                        next((i for i, opt in enumerate(items) if opt.isChecked()), -1)))
                    self.add_row(card, group.title(), picker)
                else:
                    self.form(card, group)
            for control in tabs.widget(index).findChildren(QCheckBox):
                if not any(group.isAncestorOf(control) for group in tabs.widget(index).findChildren(QGroupBox)):
                    self.add_field(card, control.text(), control)
        readout_width = max(label.minimumWidth() for label in self.slider_readouts)
        for label in self.slider_readouts:
            label.setFixedWidth(readout_width)
        actions = QHBoxLayout()
        actions.addStretch()
        for role in (QDialogButtonBox.StandardButton.Reset, QDialogButtonBox.StandardButton.RestoreDefaults):
            self.action(actions, self.buttons.button(role))
        self.body.addLayout(actions)
        self.refresh()

    def card(self, column):
        frame = self.host.option_card()
        column.addWidget(frame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        return layout

    def add_row(self, column, title, field):
        row = QHBoxLayout()
        label = self.host.label(title)
        label.setBuddy(field)
        row.addWidget(label, 1)
        row.addWidget(field)
        (field.focusProxy() or field).setAccessibleName(label.text())
        column.addLayout(row)

    def action(self, row, original):
        button = GlassButton(original.text().replace("&", ""))
        button.clicked.connect(original.click)
        button.clicked.connect(self.refresh)
        row.addWidget(button)
        self.bindings.append(lambda: button.setEnabled(original.isEnabled()))

    def form(self, column, group):
        layout = group.layout()
        if not isinstance(layout, QFormLayout):
            edit = group.findChild(QPlainTextEdit)
            help_text = group.findChild(QLabel)
            column.addWidget(self.host.label(help_text.text()))
            self.add_field(column, group.title(), edit)
            return
        actions = QHBoxLayout()
        actions.addStretch()
        for row in range(layout.rowCount()):
            label = layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
            item = layout.itemAt(row, QFormLayout.ItemRole.FieldRole) or layout.itemAt(row, QFormLayout.ItemRole.SpanningRole)
            if not item:
                continue
            field = item.widget()
            if isinstance(field, QLabel):
                continue
            if item.layout() or isinstance(field, QPushButton):
                originals = [field] if field else [item.layout().itemAt(i).widget() for i in range(item.layout().count())]
                for button in originals:
                    if isinstance(button, QPushButton):
                        self.action(actions, button)
            elif field:
                self.add_field(column, label.widget().text() if label else field.text(), field)

        if actions.count() > 1:
            column.addLayout(actions)

    def gradient(self, column, group):
        grid = group.layout()
        toggle = group.findChild(QCheckBox)
        self.add_field(column, toggle.text(), toggle)
        table = QGridLayout()
        table.setColumnStretch(0, 1)
        table.setHorizontalSpacing(10)
        table.setVerticalSpacing(4)
        for col in (1, 2, 3):
            table.addWidget(self.host.label(grid.itemAtPosition(1, col).widget().text()), 0, col, Qt.AlignmentFlag.AlignCenter)
        for row in (2, 3, 4):
            table.addWidget(self.host.label(grid.itemAtPosition(row, 0).widget().text()), row-1, 0)
            for col in (1, 2, 3):
                field = grid.itemAtPosition(row, col).widget()
                control = self.control(field)
                alignment = Qt.AlignmentFlag.AlignRight if col == 3 else Qt.AlignmentFlag.AlignCenter
                table.addWidget(control, row-1, col, alignment)
        column.addLayout(table)
        field = group.findChild(QDoubleSpinBox, "kcfg_GradientCenterPosition")
        self.add_field(column, grid.itemAtPosition(5, 0).widget().text(), field)

    def add_field(self, layout, title, field):
        control = self.control(field)
        if isinstance(control, (SettingsSwitch, QPlainTextEdit)):
            layout.addWidget(control)
        else:
            self.add_row(layout, title, control)

    def control(self, field):
        if isinstance(field, QCheckBox):
            control = SettingsSwitch(field.text())
            control.setFont(relative_font(self.host, .78, QFont.Weight.Medium))
            control.toggled.connect(field.setChecked)
            sync = lambda: control.setChecked(field.isChecked())
        elif isinstance(field, QComboBox):
            control = GlassComboBox()
            for i in range(field.count()):
                control.addItem(field.itemText(i), field.itemData(i))
            def activate(index):
                field.setCurrentIndex(index)
                field.activated.emit(index)
            control.activated.connect(activate)
            sync = lambda: control.setCurrentIndex(field.currentIndex())
        elif isinstance(field, (QSpinBox, QDoubleSpinBox)):
            return self.number_slider(field)
        elif isinstance(field, QPlainTextEdit):
            control = QPlainTextEdit()
            control.setPlaceholderText(field.placeholderText())
            control.setMaximumHeight(120)
            control.textChanged.connect(lambda: field.setPlainText(control.toPlainText()))
            def sync():
                if control.toPlainText() != field.toPlainText():
                    control.setPlainText(field.toPlainText())
        else:
            control = GradientSwatch(field, self)
            def sync():
                control.color = field.property("color")
                control.update()
        control.setObjectName("glass-" + field.objectName().removeprefix("kcfg_"))
        control.setToolTip(field.toolTip())
        def refresh():
            with QSignalBlocker(control):
                sync()
                control.setEnabled(field.isEnabled())
        self.bindings.append(refresh)
        if isinstance(control, (SettingsSwitch, GlassComboBox)):
            signal = control.toggled if isinstance(control, SettingsSwitch) else control.activated
            signal.connect(self.refresh)
        return control

    def number_slider(self, field):
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        slider = MaterialSlider(Qt.Orientation.Horizontal)
        slider.setObjectName("glass-" + field.objectName().removeprefix("kcfg_"))
        slider.setFixedSize(124, 22)
        slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 4px; border-radius: 2px; background: palette(mid); }
            QSlider::sub-page:horizontal { background: palette(window-text); border-radius: 2px; }
            QSlider::handle:horizontal { width: 16px; margin: -4px 0; border-radius: 6px;
                                         background: palette(window-text); }
        """)
        decimals = field.decimals() if isinstance(field, QDoubleSpinBox) else 0
        scale = 10 ** decimals
        slider.setRange(round(field.minimum() * scale), round(field.maximum() * scale))
        slider.setSingleStep(round(field.singleStep() * scale))
        slider.setPageStep(max(slider.singleStep(), (slider.maximum() - slider.minimum()) // 10))
        readout = QLabel()
        readout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        maximum_text = field.locale().toString(float(field.maximum()), "f", decimals) + field.suffix()
        readout.setMinimumWidth(readout.fontMetrics().horizontalAdvance(maximum_text))
        self.slider_readouts.append(readout)
        row.addWidget(slider)
        row.addWidget(readout)
        container.setFocusProxy(slider)
        container.setToolTip(field.toolTip())
        slider.setAccessibleName(field.accessibleName())
        def sync():
            with QSignalBlocker(slider):
                slider.setValue(round(field.value() * scale))
            readout.setText(field.text())
            slider.setAccessibleDescription(field.text())
            container.setEnabled(field.isEnabled())
        slider.valueChanged.connect(lambda value: field.setValue(value / scale if decimals else value))
        field.valueChanged.connect(sync)
        self.bindings.append(sync)
        return container

    def refresh(self, *_):
        for update in self.bindings:
            update()

    def bind_actions(self, on_change):
        self.on_change = on_change
        self.apply_button.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.EnabledChange:
            QTimer.singleShot(0, self.on_change)
            QTimer.singleShot(0, self.refresh)
        return super().eventFilter(obj, event)


def create_acrylic_glass_editor(parent):
    loaded = _loaded_editor()
    return EmbeddedEditor(parent, loaded[1]) if loaded else None
