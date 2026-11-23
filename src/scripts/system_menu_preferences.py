"""Preferences for the system menu and the About window."""

from pathlib import Path
from xml.etree import ElementTree

PLUGIN = "org.kde.mac.tahoe.liquid.globalmenu"
PACKAGE = Path(__file__).resolve().parents[1] / "offline/plasmoids" / PLUGIN
ICON_DIR = PACKAGE / "qml/menu-icons"
DISTRO_ICONS = {
    "arch": "Arch Linux",
    "artix": "Artix Linux",
    "cachyos": "CachyOS",
    "debian": "Debian",
    "endeavouros": "EndeavourOS",
    "fedora": "Fedora",
    "garuda": "Garuda Linux",
    "neon": "KDE neon",
    "manjaro": "Manjaro",
    "nixos": "NixOS",
    "nobara": "Nobara Linux",
    "opensuse-tumbleweed": "openSUSE Tumbleweed",
}
FORMS = {
    "General": {
        "menuIconPreset": "Menu icon",
        "menuIcon": "Custom icon",
        "useSystemFont": "Use system font in About This Computer",
    },
    "Application menus": {
        "enableGenericMenu": "Show common menus for applications without a menu bar",
        "enableMenuSearch": "Search application menu actions",
        "hoverOpensMenu": "Switch open menus on hover",
        "compactView": "Use a single button for the application menu",
        "allScreens": "Show menus for apps on different screens",
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
CHOICES = {"menuIconPreset": {
    "custom": "Custom icon",
    "apple": "Apple",
    "penguin": "Penguin",
    "distro": "Detect distribution",
    "pear": "Pear",
    **DISTRO_ICONS,
}}
RANGES = {}


def detected_distro_icon():
    from distro import current_distro

    name = current_distro()
    if name == "opensuse":
        name = "opensuse-tumbleweed"
    return name if name in DISTRO_ICONS else "penguin"


def _defaults():
    schema = PACKAGE / "main.xml"
    fields = {key for form in FORMS.values() for key in form}
    return {
        entry.attrib["name"]: (entry.findtext("{*}default") == "true" if entry.attrib["type"] == "Bool"
                               else entry.findtext("{*}default", ""))
        for entry in ElementTree.parse(schema).findall(".//{*}entry")
        if entry.attrib["name"] in fields
    }


DEFAULTS = _defaults()
