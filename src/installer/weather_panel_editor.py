"""Location search and information for the bundled panel weather widget."""

import json
import math

from PyQt6.QtCore import QTimer, Qt, QUrl, QUrlQuery
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import QComboBox, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


class WeatherForm(QWidget):
    def __init__(self, translate, parent):
        super().__init__(parent)
        self.translate = translate
        self.selected_location = ""
        self.coordinates = (0.0, 0.0)
        self.network = QNetworkAccessManager(self)
        self.pending = None
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(250)
        self.debounce.timeout.connect(self.search)

        layout = QVBoxLayout(self)
        self.location = QLineEdit()
        self.location.setObjectName("widgetSettingField")
        self.location.setAccessibleName(translate("Location"))
        self.location.setPlaceholderText(translate("City name (e.g. London)"))
        self.location.textEdited.connect(self.schedule_search)
        layout.addWidget(QLabel(translate("Location")))
        layout.addWidget(self.location)
        self.results = QListWidget()
        self.results.setAccessibleName(translate("Matching locations"))
        self.results.setMaximumHeight(145)
        self.results.hide()
        self.results.itemActivated.connect(self.select_location)
        self.results.itemClicked.connect(self.select_location)
        layout.addWidget(self.results)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.hide()
        layout.addWidget(self.status)
        unit_label = QLabel(translate("Temperature unit"))
        self.unit = QComboBox()
        self.unit.setAccessibleName(unit_label.text())
        self.unit.addItem(translate("Celsius (°C)"), 0)
        self.unit.addItem(translate("Fahrenheit (°F)"), 1)
        layout.addWidget(unit_label)
        layout.addWidget(self.unit)
        note = QLabel(translate("Location search and forecasts use Open-Meteo."))
        note.setWordWrap(True)
        note.setObjectName("detail")
        layout.addWidget(note)
        layout.addStretch()

    def load(self, values):
        self.debounce.stop()
        self.clear_search()
        self.selected_location = values["location"]
        self.coordinates = (values["latitude"], values["longitude"])
        self.location.setText(self.selected_location)
        self.unit.setCurrentIndex(self.unit.findData(values["temperatureUnit"]))

    def values(self):
        name = self.location.text().strip()
        latitude, longitude = self.coordinates if name == self.selected_location else (0.0, 0.0)
        return {"location": name, "latitude": latitude, "longitude": longitude,
                "temperatureUnit": self.unit.currentData()}

    def clear_search(self):
        if self.pending is not None:
            reply, self.pending = self.pending, None
            reply.abort()
        self.results.hide()
        self.results.clear()
        self.status.clear()
        self.status.hide()

    def schedule_search(self):
        self.clear_search()
        self.debounce.start()

    def search(self):
        name = self.location.text().strip()
        if len(name) < 2:
            return
        url = QUrl(GEOCODING_URL)
        query = QUrlQuery()
        for key, value in (("name", name), ("count", "8"), ("language", "en"), ("format", "json")):
            query.addQueryItem(key, value)
        url.setQuery(query)
        request = QNetworkRequest(url)
        request.setTransferTimeout(6000)
        self.pending = self.network.get(request)
        self.pending.finished.connect(lambda reply=self.pending: self.show_results(reply))

    def show_results(self, reply):
        if reply is not self.pending:
            reply.deleteLater()
            return
        self.pending = None
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.status.setText(self.translate("Location search is unavailable."))
                self.status.show()
                return
            response = json.loads(bytes(reply.readAll()))
            for location in response.get("results", []):
                name = location.get("name")
                latitude = location.get("latitude")
                longitude = location.get("longitude")
                if not name or not all(isinstance(value, (float, int)) and math.isfinite(value)
                                       for value in (latitude, longitude)):
                    continue
                item = QListWidgetItem(", ".join(part for part in
                    (name, location.get("admin1"), location.get("country")) if part))
                item.setData(Qt.ItemDataRole.UserRole, (name, float(latitude), float(longitude)))
                self.results.addItem(item)
            self.results.setVisible(self.results.count() > 0)
            if self.results.count() == 0:
                self.status.setText(self.translate("No matching locations."))
                self.status.show()
        except (TypeError, ValueError, AttributeError):
            self.status.setText(self.translate("Location search is unavailable."))
            self.status.show()
        finally:
            reply.deleteLater()

    def select_location(self, item):
        name, latitude, longitude = item.data(Qt.ItemDataRole.UserRole)
        self.clear_search()
        self.selected_location = name
        self.coordinates = (latitude, longitude)
        self.location.setText(name)


def weather_about(translate, parent):
    page = QWidget(parent)
    layout = QVBoxLayout(page)
    layout.addWidget(QLabel(translate("Liquid Glass Widgets")))
    description = QLabel(translate("Calendar, Clock, World Clock, Timer, Weather and Music widgets for KDE Plasma."))
    description.setWordWrap(True)
    layout.addWidget(description)
    for label, url in (("Browse the widget collection", "https://github.com/jaxparrow07/liquidglass-kde-widgets"),
                       ("Get Nothing Widgets", "https://github.com/jaxparrow07/nothing-kde-widgets"),
                       ("Buy me a coffee", "https://buymeacoffee.com/jaxparrow07"),
                       ("Website", "https://jackfaithweb.com"),
                       ("Reddit", "https://reddit.com/user/zinxyzcool")):
        link = QLabel(f'<a href="{url}">{translate(label)}</a>')
        link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        link.setOpenExternalLinks(True)
        layout.addWidget(link)
    layout.addStretch()
    return page
