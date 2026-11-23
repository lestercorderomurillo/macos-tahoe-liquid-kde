"""Preferences for the system menu and the About window."""

from pathlib import Path
from xml.etree import ElementTree

PLUGIN = "org.kde.mac.tahoe.liquid.globalmenu"
FORMS = {
    "General": {
        "menuIcon": "Menu icon",
        "useSystemFont": "Use system font in About This Computer",
    },
    "Icons": {
        "iconAbout": "About This Computer icon",
        "iconSystemSettings": "System Settings icon",
        "iconAppStore": "App Store icon",
        "iconForceQuit": "Force Quit icon",
        "iconSleep": "Sleep icon",
        "iconRestart": "Restart icon",
        "iconShutDown": "Shut Down icon",
        "iconLockScreen": "Lock Screen icon",
        "iconLogOut": "Log Out icon",
    },
    "Actions": {
        "cmdAppStore": "App Store command",
        "cmdSleep": "Sleep command",
        "cmdRestart": "Restart command",
        "cmdShutDown": "Shut Down command",
        "cmdLockScreen": "Lock Screen command",
        "cmdLogOut": "Log Out command",
    },
}
CHOICES = {}
RANGES = {}


def _defaults():
    schema = Path(__file__).resolve().parents[1] / "offline/plasmoids" / PLUGIN / "main.xml"
    fields = {key for form in FORMS.values() for key in form}
    return {
        entry.attrib["name"]: (entry.findtext("{*}default") == "true" if entry.attrib["type"] == "Bool"
                               else entry.findtext("{*}default", ""))
        for entry in ElementTree.parse(schema).findall(".//{*}entry")
        if entry.attrib["name"] in fields
    }


DEFAULTS = _defaults()
