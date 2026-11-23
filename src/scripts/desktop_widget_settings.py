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
    "city-1": "World Clock I",
    "city-2": "World Clock II",
    "city-3": "World Clock III",
    "city-digital": "Digital World Clock",
    "calendar": "Calendar",
    "music": "Music",
    "weather": "Weather",
    "timer": "Timer",
    "photos": "Photos",
}
CONTEXT_ACTIONS = {
    "calendar": "openCalendarAction, newEventAction, manageCalendarsAction",
    "music": "playPauseAction, nextAction, previousAction",
    "weather": "refreshAction",
    "timer": "toggleAction, resetAction",
    "photos": "openAction, nextAction",
}
WEATHER_FIELDS = ("location", "latitude", "longitude", "temperatureUnit")
# Present in the upstream schema without a widget binding or a config control.
INACTIVE_FIELDS = {"music": {"spectrumBars", "lyricsFont"}}
CALENDAR_SOURCES = {
    "pimevents": "PIM Events (Akonadi)",
    "holidaysevents": "Holidays",
    "astronomicalevents": "Astronomical Events",
}
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
    "World clocks": {"clocks": "Time zones"},
    "Calendar": {"firstDayOfWeek": "First day of the week", "eventLookaheadDays": "Show events for",
                 "enabledCalendarPlugins": "Calendar sources", "autoFontSize": "Scale text with widget size",
                 "gridFontSize": "Calendar grid text size", "eventFontSize": "Event list text size"},
    "Players": {"filterMode": "Player filter", "playerFilter": "Media players",
                "autoHideEnabled": "Hide the widget when nothing is playing", "autoHideTimeout": "Hide after",
                "artRefreshEnabled": "Refresh album art on track changes"},
    "Lyrics": {"showTrackTitleInLyrics": "Show the track title above the lyrics",
               "lyricsBlur": "Blur upcoming lines",
               "lyricsActiveOpacity": "Current line opacity", "lyricsInactiveOpacity": "Other line opacity",
               "lyricsFontSizeWide": "Wide layout text size", "lyricsFontSizeTall": "Tall layout text size"},
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
    "firstDayOfWeek": ("Sunday", "Monday"),
    "eventLookaheadDays": ("7 days", "14 days", "30 days", "60 days"),
    "filterMode": ("Show selected players", "Hide selected players"),
    "temperatureUnit": ("Celsius (°C)", "Fahrenheit (°F)"),
}
RANGES = {
    "cornerRadius": (0, 200), "roundnessX10": (20, 100), "tintAlphaPct": (0, 100),
    "refractThickness": (1, 80), "refractScale": (0, 300), "refractIORx100": (100, 400),
    "chromaStrengthPct": (0, 100), "specStrengthPct": (0, 100), "blurRadiusPx": (0, 100),
    "textTintPct": (0, 100),
    "intervalMinutes": (1, 1440),
    "gridFontSize": (8, 48), "eventFontSize": (8, 48),
    "autoHideTimeout": (5, 600), "lyricsActiveOpacity": (50, 100), "lyricsInactiveOpacity": (5, 80),
    "lyricsFontSizeWide": (40, 150), "lyricsFontSizeTall": (30, 120),
    "latitude": (-90, 90), "longitude": (-180, 180),
}


@dataclass
class WidgetSchema:
    DEFAULTS: dict
    CHOICES = {key: range(len(choices)) for key, choices in CHOICES.items()}
    RANGES = RANGES


def read_schema(package):
    editable = {key for fields in PAGES.values() for key in fields}.union(WEATHER_FIELDS)
    entries = ElementTree.parse(package / "contents/config/main.xml").findall(".//{*}entry")
    convert = {"Bool": lambda value: value == "true", "Int": int, "String": str, "Double": float,
               "StringList": lambda value: [item for item in value.split(",") if item]}
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
    if schema.DEFAULTS.keys() != all_keys - INACTIVE_FIELDS.get(variant, set()):
        return
    text = text.replace(component_import, component_import +
                        'import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Settings\n')
    text = text.replace(anchor, f"""    // {MARKER}
    Settings.SettingsEntry {{ id: settingsEntry; widgetId: Plasmoid.id; section: "desktop_widget" }}
    Plasmoid.hasConfigurationInterface: !settingsEntry.available
    Plasmoid.contextualActions: [{actions}, settingsEntry].concat(settingsEntry.available
        ? [commonActions.separatorBottom, commonActions.support] : commonActions.list)""")
    main.write_text(text, encoding="utf-8")
