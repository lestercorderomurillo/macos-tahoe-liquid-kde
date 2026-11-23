"""Settings and package integration for the bundled panel weather widget."""

import os
from pathlib import Path


PLUGIN = "com.jaxparrow07.macoswidgets.weatherpanel"
DEFAULTS = {"location": "New York", "latitude": 40.7128, "longitude": -74.0060, "temperatureUnit": 0}
CHOICES = {"temperatureUnit": {0, 1}}
RANGES = {"latitude": (-90.0, 90.0), "longitude": (-180.0, 180.0)}
MARKER = "Weather Settings integration"


def installed_package():
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    package = data / "plasma/plasmoids" / PLUGIN
    main = package / "contents/ui/main.qml"
    return package if main.is_file() and MARKER in main.read_text(encoding="utf-8") else None


def stage_configuration_route(package):
    main = package / "contents/ui/main.qml"
    if not main.is_file():
        return
    text = main.read_text(encoding="utf-8")
    anchor = "    Plasmoid.contextualActions: [refreshAction].concat(commonActions.list)"
    component_import = 'import "components"\n'
    buttons = "acceptedButtons: Qt.LeftButton | Qt.RightButton"
    if MARKER in text or any(text.count(match) != 1 for match in (anchor, component_import, buttons)):
        return
    text = text.replace(component_import, component_import +
                        'import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Settings\n', 1)
    text = text.replace(anchor, f"""    // {MARKER}
    Settings.SettingsEntry {{ id: settingsEntry; widgetId: Plasmoid.id; section: "weather_panel" }}
    Plasmoid.hasConfigurationInterface: !settingsEntry.available
    Plasmoid.contextualActions: [refreshAction, settingsEntry].concat(commonActions.list)""")
    text = text.replace(buttons, "acceptedButtons: Qt.LeftButton | (settingsEntry.available ? Qt.NoButton : Qt.RightButton)")
    main.write_text(text, encoding="utf-8")
