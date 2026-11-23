"""Preferences exposed by the Apps launcher configuration."""

from pathlib import Path
from xml.etree import ElementTree

from launcher_defaults import LAUNCHER_ID

FORMS = {
    "General": {
        "launcherApplication": "Open from Apps",
        "launcherPreset": "Launcher layout",
        "launcherPosition": "Launcher position",
        "floating": "Floating launcher",
        "offsetX": "Distance from screen edge",
        "offsetY": "Distance from panel",
        "showSessionActionsButton": "Show session actions",
    },
    "Icon": {
        "icon": "Apps icon",
        "useCustomButtonImage": "Use a custom icon",
        "customButtonImage": "Custom icon",
    },
    "Grids and lists": {
        "appsIconSize": "Grid icon size",
        "numberColumns": "Tahoe columns",
        "goldenGateColumns": "Golden Gate columns",
        "numberOfRows": "Grid rows",
        "compactListItems": "Compact list items",
        "showListItemDescription": "Show list item descriptions",
        "useSystemFontSettings": "Use system font settings",
    },
}
CHOICES = {
    "launcherPreset": {0: "Edition default", 1: "Tahoe", 2: "Golden Gate"},
    "launcherPosition": {0: "Near the Apps button", 1: "Panel center", 2: "Screen center"},
    "appsIconSize": dict(enumerate(("Small", "Medium", "Large", "Huge"))),
}
RANGES = {
    "offsetX": (0, 100),
    "offsetY": (0, 100),
    "numberColumns": (4, 8),
    "goldenGateColumns": (4, 8),
    "numberOfRows": (4, 8),
}


def _defaults():
    schema = (Path(__file__).resolve().parents[1] / "offline/plasmoids" / LAUNCHER_ID
              / "contents/config/main.xml")
    fields = {key for form in FORMS.values() for key in form}
    readers = {"Bool": lambda value: value == "true", "Int": int, "Enum": int, "String": str, "Url": str}
    return {
        entry.attrib["name"]: readers[entry.attrib["type"]](entry.findtext("{*}default", ""))
        for entry in ElementTree.parse(schema).findall(".//{*}entry")
        if entry.attrib["name"] in fields
    }


DEFAULTS = _defaults()
