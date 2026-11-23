"""Appearance and behavior for bundled desktop widgets in shared Settings."""

import json

from PyQt6.QtCore import QStandardPaths, QTimeZone, Qt
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusVariant
from PyQt6.QtGui import QColor, QFont, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout,
    QKeySequenceEdit, QLabel, QLineEdit, QListWidget, QListWidgetItem, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from desktop_widget_settings import (
    CALENDAR_SOURCES, CHOICES, NAMES, PAGES, PREFIX, RANGES, STYLE_KEYS, WEATHER_FIELDS,
    installed_package, installed_schema,
)
from plasmoid_settings import apply, instances
from weather_panel_editor import WeatherForm, weather_about

DISPLAY_SCALE = {"roundnessX10": 10, "refractIORx100": 100}


def media_players():
    bus = QDBusConnection.sessionBus()
    interface = bus.interface()
    if interface is None:
        return {}
    players = {}
    for service in interface.registeredServiceNames().value() or ():
        if not service.startswith("org.mpris.MediaPlayer2."):
            continue
        properties = QDBusInterface(service, "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties", bus)
        properties.setTimeout(300)
        args = properties.call("Get", "org.mpris.MediaPlayer2", "Identity").arguments()
        if args and isinstance(args[0], QDBusVariant) and (name := args[0].variant()):
            players[name] = name
    return players


class CheckedChoices(QListWidget):
    def __init__(self, labels, *, csv=False):
        super().__init__()
        self.labels = labels
        self.csv = csv
        self.setMaximumHeight(118)

    def set_value(self, value):
        checked = value.split(",") if self.csv else value
        self.clear()
        for key, label in (self.labels | {k: k for k in checked if k and k not in self.labels}).items():
            item = QListWidgetItem(label, self)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setCheckState(Qt.CheckState.Checked if key in checked else Qt.CheckState.Unchecked)

    def value(self):
        checked = [item.data(Qt.ItemDataRole.UserRole) for index in range(self.count())
                   if (item := self.item(index)).checkState() == Qt.CheckState.Checked]
        return ",".join(checked) if self.csv else checked


class WorldClocks(QWidget):
    def __init__(self, translate, count):
        super().__init__()
        from wizard_window import GlassComboBox

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        zones = sorted(bytes(zone).decode() for zone in QTimeZone.availableTimeZoneIds())
        self.fields = []
        for number in range(1, count + 1):
            row = QHBoxLayout()
            time_zone = GlassComboBox()
            time_zone.setEditable(True)
            time_zone.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            time_zone.addItems(["", *zones])
            time_zone.setAccessibleName(f'{translate("Time zone")} {number}')
            time_zone.lineEdit().setPlaceholderText(translate("Time zone"))
            label = QLineEdit()
            label.setObjectName("widgetSettingField")
            label.setAccessibleName(f'{translate("Label")} {number}')
            label.setPlaceholderText(translate("Label"))
            row.addWidget(time_zone, 2)
            row.addWidget(label, 1)
            layout.addLayout(row)
            self.fields.append((time_zone, label))

    def set_value(self, value):
        clocks = value.split(",")
        for index, (zone, label) in enumerate(self.fields):
            name, _, nickname = (clocks[index] if index < len(clocks) else "").partition("|")
            zone.setEditText(name)
            label.setText(nickname)

    def value(self):
        return ",".join(f'{name}|{label.text().strip().replace(",", " ")}' for zone, label in self.fields
                        if (name := zone.currentText().strip()))


def installed_instances():
    found = {}
    for name in NAMES:
        plugin = PREFIX + name
        schema = installed_schema(plugin)
        if schema is None:
            continue
        try:
            found.update({identifier: (plugin, schema.DEFAULTS, values)
                          for identifier, values in instances(plugin).items()})
        except RuntimeError:
            continue
    return found


class DesktopWidgetEditor(QWidget):
    def __init__(self, widgets, requested, parent):
        super().__init__(parent)
        # Reuse the shared Settings controls after the wizard module has loaded.
        from wizard_window import GlassButton, GlassComboBox, relative_font

        self.t = parent.t
        self.widgets = widgets
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        heading = QLabel(self.t("Widget settings"))
        heading.setFont(relative_font(parent, .85, QFont.Weight.DemiBold))
        header.addWidget(heading, 1)
        self.save = GlassButton(self.t("Save"))
        self.save.clicked.connect(self.save_settings)
        header.addWidget(self.save)
        layout.addLayout(header)
        self.picker = GlassComboBox()
        self.picker.setAccessibleName(self.t("Widget instance"))
        for identifier, (plugin, _, _) in widgets.items():
            name = self.t(NAMES[plugin.removeprefix(PREFIX)])
            self.picker.addItem(f"{name} ({identifier})", identifier)
        self.picker.setCurrentIndex(max(0, self.picker.findData(requested)))
        layout.addWidget(self.picker)
        shortcut = QHBoxLayout()
        shortcut.addWidget(QLabel(self.t("Activation shortcut")), 1)
        self.shortcut = QKeySequenceEdit()
        self.shortcut.setAccessibleName(self.t("Activation shortcut"))
        self.shortcut.setClearButtonEnabled(True)
        shortcut.addWidget(self.shortcut)
        layout.addLayout(shortcut)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("widgetPreferenceTabs")
        layout.addWidget(self.tabs)
        self.status = QLabel()
        self.status.setObjectName("detail")
        self.status.setWordWrap(True)
        self.status.hide()
        layout.addWidget(self.status)
        self.picker.currentIndexChanged.connect(self.build)
        self.build()

    def build(self):
        from wizard_window import CheckOption, GlassButton, GlassComboBox

        self.plugin, self.defaults, values = self.widgets[self.picker.currentData()]
        self.shortcut.setKeySequence(QKeySequence.fromString(values.get("activationShortcut", "")))
        while self.tabs.count():
            page = self.tabs.widget(0)
            self.tabs.removeTab(0)
            page.deleteLater()
        self.fields = {}
        self.rows = {}
        self.glass_pages = []
        self.weather = None
        self.calendar_providers = {}
        self.status.hide()
        if all(key in self.defaults for key in WEATHER_FIELDS):
            self.weather = WeatherForm(self.t, self.tabs)
            self.weather.load(values)
            self.tabs.addTab(self.weather, self.t("Weather"))
        for title, fields in PAGES.items():
            present = {key: label for key, label in fields.items() if key in self.defaults}
            if not present:
                continue
            page = QWidget()
            layout = QVBoxLayout(page)
            for key, text in present.items():
                row = QWidget()
                line = QHBoxLayout(row)
                line.setContentsMargins(0, 0, 0, 0)
                label = self.t(text)
                default = self.defaults[key]
                if isinstance(default, bool):
                    field = CheckOption(label)
                    line.addWidget(field, 1)
                    field.toggled.connect(self.update_dependencies)
                elif key in ("clocks", "enabledCalendarPlugins", "playerFilter"):
                    if key == "clocks":
                        field = WorldClocks(self.t, 4 if self.plugin.endswith(("city-1", "city-2")) else 1)
                    elif key == "enabledCalendarPlugins":
                        field = CheckedChoices({name: self.t(message) for name, message in CALENDAR_SOURCES.items()})
                    else:
                        field = CheckedChoices(media_players(), csv=True)
                    field.setAccessibleName(label)
                    line.addWidget(QLabel(label), 1)
                    line.addWidget(field, 3)
                    if key == "playerFilter":
                        refresh = GlassButton(self.t("Refresh"))

                        def refresh_players(*_, players=field):
                            selected = players.value()
                            players.labels = media_players()
                            players.set_value(selected)

                        refresh.clicked.connect(refresh_players)
                        line.addWidget(refresh)
                else:
                    line.addWidget(QLabel(label), 1)
                    if key in CHOICES:
                        field = GlassComboBox()
                        for index, choice in enumerate(CHOICES[key]):
                            field.addItem(self.t(choice), index)
                        field.currentIndexChanged.connect(self.update_dependencies)
                    elif key == "textColor":
                        field = GlassButton("")
                        field.clicked.connect(self.choose_color)
                    elif key == "folder":
                        field = QLineEdit()
                        field.setObjectName("widgetSettingField")
                        field.setPlaceholderText(QStandardPaths.writableLocation(
                            QStandardPaths.StandardLocation.PicturesLocation))
                    elif key in DISPLAY_SCALE:
                        scale = DISPLAY_SCALE[key]
                        field = QDoubleSpinBox()
                        field.setDecimals(1 if scale == 10 else 2)
                        field.setRange(*(bound / scale for bound in RANGES[key]))
                        field.setSingleStep(.05 if key == "refractIORx100" else .1)
                    else:
                        field = QSpinBox()
                        field.setRange(*RANGES[key])
                        if key in {"tintAlphaPct", "textTintPct", "refractScale", "chromaStrengthPct", "specStrengthPct"}:
                            field.setSuffix("%")
                        elif key in {"cornerRadius", "blurRadiusPx", "refractThickness", "gridFontSize", "eventFontSize"}:
                            field.setSuffix(" px")
                        elif key == "intervalMinutes":
                            field.setSuffix(self.t(" min"))
                        elif key == "autoHideTimeout":
                            field.setSuffix(self.t(" s"))
                        if key in {"refractScale", "specStrengthPct"}:
                            field.setSingleStep(5)
                        field.valueChanged.connect(self.update_dependencies)
                    field.setAccessibleName(label)
                    if key == "folder":
                        line.addWidget(field, 2)
                        browse = GlassButton(self.t("Browse…"))
                        browse.clicked.connect(self.choose_folder)
                        line.addWidget(browse)
                    else:
                        line.addWidget(field)
                self.fields[key] = field
                self.rows[key] = row
                field.setObjectName(key)
                layout.addWidget(row)
                if key == "folder":
                    note = QLabel(self.t("Leave empty to use your Pictures folder. Subfolders are not included."))
                    note.setObjectName("detail")
                    note.setWordWrap(True)
                    layout.addWidget(note)
            if title == "Style":
                buttons = QHBoxLayout()
                for label, action in (("Copy style", self.copy_style), ("Paste style", self.paste_style)):
                    button = GlassButton(self.t(label))
                    button.clicked.connect(action)
                    buttons.addWidget(button)
                buttons.addStretch()
                layout.addLayout(buttons)
            elif title in ("Glass", "Blur & performance"):
                self.glass_pages.append(page)
                label = "Reset glass settings" if title == "Glass" else "Reset blur settings"
                reset = GlassButton(self.t(label))
                reset.clicked.connect(lambda _, keys=tuple(present): self.set_values(
                    {key: self.defaults[key] for key in keys}))
                layout.addWidget(reset, alignment=Qt.AlignmentFlag.AlignLeft)
            layout.addStretch()
            self.tabs.addTab(page, self.t(title).replace("&", "&&"))
        if "enabledCalendarPlugins" in self.fields:
            from calendar_provider_settings import provider_settings

            self.calendar_providers = provider_settings(self.t, installed_package(self.plugin), self.tabs)
            for source, page in self.calendar_providers.items():
                self.tabs.addTab(page, self.t(CALENDAR_SOURCES[source]))
            self.fields["enabledCalendarPlugins"].itemChanged.connect(self.update_dependencies)
        self.tabs.addTab(weather_about(self.t, self.tabs), self.t("About"))
        self.set_values({key: values[key] for key in self.fields})
        self.baseline = self.values()
        self.shortcut_baseline = self.shortcut.keySequence().toString()

    def values(self):
        values = self.weather.values() if self.weather else {}
        for key, field in self.fields.items():
            if isinstance(field, QCheckBox):
                values[key] = field.isChecked()
            elif isinstance(field, QComboBox):
                values[key] = field.currentData()
            elif isinstance(field, (QSpinBox, CheckedChoices, WorldClocks)):
                values[key] = field.value()
            elif isinstance(field, QDoubleSpinBox):
                values[key] = round(field.value() * DISPLAY_SCALE[key])
            else:
                values[key] = field.text()
        return values

    def set_values(self, values):
        for key, value in values.items():
            field = self.fields[key]
            previous = field.blockSignals(True)
            if isinstance(field, QCheckBox):
                field.setChecked(value)
            elif isinstance(field, QComboBox):
                field.setCurrentIndex(field.findData(value))
            elif isinstance(field, QSpinBox):
                field.setValue(value)
            elif isinstance(field, QDoubleSpinBox):
                field.setValue(value / DISPLAY_SCALE[key])
            elif isinstance(field, (CheckedChoices, WorldClocks)):
                field.set_value(value)
            else:
                field.setText(value)
            field.blockSignals(previous)
        self.update_dependencies()

    def update_dependencies(self, *_):
        values = self.values()
        automatic = values.get("autoStyle", False)
        solid = values.get("styleMode") == 1
        glass = automatic or not solid or values.get("opaqueBackground") is False
        if "styleMode" in self.fields:
            self.fields["styleMode"].setEnabled(not automatic)
        if "opaqueBackground" in self.rows:
            self.rows["opaqueBackground"].setVisible(automatic or solid)
        if "tintAlphaPct" in self.rows:
            self.rows["tintAlphaPct"].setVisible(glass)
        if "textColor" in self.fields:
            self.fields["textColor"].setEnabled(values["textTintPct"] > 0)
        for page in self.glass_pages:
            page.setEnabled(glass)
        for key in ("gridFontSize", "eventFontSize"):
            if key in self.rows:
                self.rows[key].setEnabled(not values["autoFontSize"])
        if "autoHideTimeout" in self.rows:
            self.rows["autoHideTimeout"].setEnabled(values["autoHideEnabled"])
        for source, page in self.calendar_providers.items():
            index = self.tabs.indexOf(page)
            if index >= 0:
                self.tabs.setTabVisible(index, source in values["enabledCalendarPlugins"])

    def choose_color(self):
        field = self.fields["textColor"]
        selected = QColorDialog.getColor(QColor(field.text()), self, self.t("Text color"))
        if selected.isValid():
            field.setText(selected.name())

    def choose_folder(self):
        field = self.fields["folder"]
        folder = QFileDialog.getExistingDirectory(self, self.t("Folder"), field.text() or field.placeholderText())
        if folder:
            field.setText(folder)

    def message(self, text):
        self.status.setText(self.t(text))
        self.status.show()

    def copy_style(self):
        values = self.values()
        QApplication.clipboard().setText(json.dumps({short: values[key] for short, key in STYLE_KEYS.items()
                                                     if key in values and values[key] is not None}))
        self.message("Style copied.")

    def paste_style(self):
        try:
            style = json.loads(QApplication.clipboard().text())
            if not isinstance(style, dict) or "s" not in style:
                raise ValueError
            if "ba" not in style and "blurAlgorithm" in style:
                style["ba"] = style["blurAlgorithm"]
            values = {key: style[short] for short, key in STYLE_KEYS.items()
                      if short in style and key in self.defaults}
            if any(type(value) is not type(self.defaults[key])
                   or (key in CHOICES and value not in range(len(CHOICES[key])))
                   or (key in RANGES and not RANGES[key][0] <= value <= RANGES[key][1])
                   or (key == "textColor" and not QColor(value).isValid())
                   for key, value in values.items()):
                raise ValueError
        except (ValueError, TypeError):
            self.message("The clipboard doesn't contain a copied style.")
            return
        self.set_values(values)
        self.message("Style applied. Press Save to keep it.")

    def save_settings(self):
        changes = {key: value for key, value in self.values().items()
                   if value is not None and value != self.baseline[key]}
        shortcut = self.shortcut.keySequence().toString()
        if shortcut != self.shortcut_baseline:
            changes["activationShortcut"] = shortcut
        identifier = self.picker.currentData()
        try:
            if changes:
                self.widgets[identifier] = (self.plugin, self.defaults, apply(self.plugin, identifier, changes))
        except (RuntimeError, ValueError) as error:
            self.message(str(error))
            return
        if self.calendar_providers:
            from calendar_provider_settings import save_provider_settings

            save_provider_settings({source: page for source, page in self.calendar_providers.items()
                                    if source in self.fields["enabledCalendarPlugins"].value()})
        self.baseline = self.values()
        self.shortcut_baseline = shortcut
        self.message("Saved")
