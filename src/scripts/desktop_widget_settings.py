"""Configuration for supported members of the bundled desktop widget pack."""

from dataclasses import dataclass
import os
from pathlib import Path
from xml.etree import ElementTree

PREFIX = "com.jaxparrow07.macoswidgets."
MARKER = "Desktop Widget Settings integration"
NAMES = {
    "clock-analog": "Analog Clock",
    "clock-analog-2": "Analog Clock II",
    "clock-analog-3": "Analog Clock III",
    "clock-glass-text": "Glass Text Clock",
    "clock-square": "Digital Clock",
    "timer": "Timer",
    "photos": "Photos",
}
CONTEXT_ACTIONS = {"timer": "toggleAction, resetAction", "photos": "openAction, nextAction"}
STYLE_KEYS = {
    "s": "styleMode", "as": "autoStyle", "a": "appearance", "cr": "cornerRadius",
    "rn": "roundnessX10", "ta": "tintAlphaPct", "rt": "refractThickness",
    "ri": "refractIORx100", "rs": "refractScale", "ca": "chromaStrengthPct",
    "ss": "specStrengthPct", "ba": "blurAlgorithm", "br": "blurRadiusPx",
    "rr": "realtimeRefraction", "ob": "opaqueBackground", "gf": "glyphFont",
    "tt": "textTintPct", "tc": "textColor",
}
PAGES = {
    "Clock": {"use24Hour": "Use 24-hour time", "smoothSeconds": "Animate the second hand continuously"},
    "Photos": {"folder": "Folder", "intervalMinutes": "Change photo every", "shuffle": "Shuffle"},
    "Style": {"styleMode": "Style", "autoStyle": "Switch automatically", "appearance": "Appearance",
              "tintAlphaPct": "Glass tint", "cornerRadius": "Corner radius", "roundnessX10": "Corner smoothness",
              "opaqueBackground": "Fully opaque background", "glyphFont": "Digit font",
              "textTintPct": "Text tint", "textColor": "Text color"},
    "Glass": {"refractThickness": "Edge thickness", "refractScale": "Refraction strength",
              "refractIORx100": "Refraction index", "chromaStrengthPct": "Color fringing",
              "specStrengthPct": "Edge highlight"},
    "Blur & performance": {"blurRadiusPx": "Blur radius", "blurAlgorithm": "Blur quality",
                           "realtimeRefraction": "Update the glass every frame"},
}
CHOICES = {
    "styleMode": ("Glass", "Solid"),
    "appearance": ("Dark", "Light", "Follow system"),
    "glyphFont": ("SF Pro Soft", "SF Pro Rounded", "SF Pro Rails", "New York", "SF Pro Stencil"),
    "blurAlgorithm": ("Performance (Dual Kawase)", "Quality (Gaussian)"),
}
RANGES = {
    "cornerRadius": (0, 200), "roundnessX10": (20, 100), "tintAlphaPct": (0, 100),
    "refractThickness": (1, 80), "refractScale": (0, 300), "refractIORx100": (100, 400),
    "chromaStrengthPct": (0, 100), "specStrengthPct": (0, 100), "blurRadiusPx": (0, 100),
    "textTintPct": (0, 100),
    "intervalMinutes": (1, 1440),
}


@dataclass
class WidgetSchema:
    DEFAULTS: dict
    CHOICES = {key: range(len(choices)) for key, choices in CHOICES.items()}
    RANGES = RANGES


def read_schema(package):
    editable = {key for fields in PAGES.values() for key in fields}
    entries = ElementTree.parse(package / "contents/config/main.xml").findall(".//{*}entry")
    convert = {"Bool": lambda value: value == "true", "Int": int, "String": str}
    return WidgetSchema({entry.attrib["name"]: convert[entry.attrib["type"]](entry.findtext("{*}default", ""))
                         for entry in entries if entry.attrib["name"] in editable})


def installed_schema(plugin):
    if not plugin.startswith(PREFIX) or plugin.removeprefix(PREFIX) not in NAMES:
        return None
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    package = data / "plasma/plasmoids" / plugin
    try:
        if MARKER in (package / "contents/ui/main.qml").read_text(encoding="utf-8"):
            return read_schema(package)
    except (OSError, ValueError, KeyError, ElementTree.ParseError):
        pass
    return None


def stage_configuration_route(package):
    variant = package.name.removeprefix(PREFIX)
    if not package.name.startswith(PREFIX) or variant not in NAMES:
        return
    main = package / "contents/ui/main.qml"
    if not main.is_file():
        return
    text = main.read_text(encoding="utf-8")
    actions = CONTEXT_ACTIONS.get(variant, "timeAction")
    anchor = f"    Plasmoid.contextualActions: [{actions}].concat(commonActions.list)"
    component_import = 'import "components"\n'
    if MARKER in text or any(text.count(value) != 1 for value in (anchor, component_import)):
        return
    schema = read_schema(package)
    all_keys = {entry.attrib["name"] for entry in ElementTree.parse(
        package / "contents/config/main.xml").findall(".//{*}entry")}
    if schema.DEFAULTS.keys() != all_keys:
        return
    text = text.replace(component_import, component_import +
                        'import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Settings\n')
    text = text.replace(anchor, f"""    // {MARKER}
    Settings.SettingsEntry {{ id: settingsEntry; widgetId: Plasmoid.id; section: "desktop_widget" }}
    Plasmoid.hasConfigurationInterface: !settingsEntry.available
    Plasmoid.contextualActions: [{actions}, settingsEntry].concat(settingsEntry.available
        ? [commonActions.separatorBottom, commonActions.support] : commonActions.list)""")
    main.write_text(text, encoding="utf-8")
