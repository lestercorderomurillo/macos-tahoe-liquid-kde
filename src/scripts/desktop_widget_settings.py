"""Configuration for supported members of the bundled desktop widget pack."""

from dataclasses import dataclass
import os
import re
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


def active_desktop_widgets():
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    try:
        text = (config / "plasma-org.kde.plasma.desktop-appletsrc").read_text()
    except (OSError, UnicodeError):
        return []
    plugins = re.findall(r"^plugin=" + re.escape(PREFIX) + r"([a-z0-9-]+)$", text, re.MULTILINE)
    return sorted(set(plugins).intersection(NAMES))


def installed_schema(plugin):
    if not plugin.startswith(PREFIX) or plugin.removeprefix(PREFIX) not in NAMES:
        return None
    package = installed_package(plugin)
    try:
        if MARKER in (package / "contents/ui/main.qml").read_text(encoding="utf-8"):
            return read_schema(package)
    except (OSError, ValueError, KeyError, ElementTree.ParseError):
        pass
    return None


def installed_package(plugin):
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    return data / "plasma/plasmoids" / plugin


def stage_appearance(package, variant):
    """Align the bundled widget's default and glass foreground with Plasma."""
    contents = package / "contents"
    config = contents / "config/main.xml"
    text = config.read_text(encoding="utf-8")
    dark_default = '<entry name="appearance" type="Int">\n            <default>0</default>'
    config.write_text(text.replace(dark_default, dark_default.replace(">0<", ">2<")), encoding="utf-8")

    palette = contents / "ui/components/MacOSColors.qml"
    text = palette.read_text(encoding="utf-8")
    for token in ("labelPrimary", "labelSecondary", "labelTertiary", "labelQuaternary", "separator"):
        lines = text.splitlines(keepends=True)
        text = "".join(line.replace("isLight ?", "effectiveLight ?")
                       if f"color {token}:" in line else line for line in lines)
    if variant == "weather":
        text = text.replace('color weatherForeground: "#ffffff"',
                            'color weatherForeground: isGlass ? foreground : "#ffffff"')
    palette.write_text(text, encoding="utf-8")


def stage_glass_text(package):
    """Adapt painted Text elements in the bundled widget, preserving each color binding."""
    ui = package / "contents/ui"
    profile = "widget." + package.name.removeprefix(PREFIX)
    for filename in ("LiquidGlass.qml", "TextGlass.qml"):
        material = ui / "components" / filename
        if not material.is_file():
            continue
        source = material.read_text()
        if '"mttkde-widget-material"' in source:
            continue
        source = source.replace("Item {", 'Item {\n    objectName: "mttkde-widget-material"', 1)
        props = """
    readonly property NativeInk.GlassSettings contrastSettings: NativeInk.GlassSettings {}
    readonly property NativeInk.MaterialSample contrastMaterial: NativeInk.MaterialSample {
        source: glass.contrastSettings.dynamicTinting ? glass : null
    }
    Connections {
        target: glass
        function onTintChanged() { glass.contrastMaterial.invalidate() }
        function onTintAlphaChanged() { glass.contrastMaterial.invalidate() }
        function onSolidColorChanged() { glass.contrastMaterial.invalidate() }
        function onSolidModeChanged() { glass.contrastMaterial.invalidate() }
    }
"""
        # Generated bindings run only on the material; foreground changes
        # never trigger a readback of the text.
        source = source.replace("id: glass", "id: glass" + props, 1)
        source = source.replace("function invalidateBackdrop() {", "function invalidateBackdrop() {\n        contrastMaterial.invalidate()")
        source = source.replace("function markDirty() {", "function markDirty() {\n        contrastMaterial.invalidate()")
        material.write_text("import org.kde.mac.tahoe.launcher as NativeInk\n" + source)
    # Upstream puts each Text declaration and its closing brace at the same
    # indentation. Match its own color, leaving nested effects and icons alone.
    element = re.compile(r"^(?P<indent> *)(?P<prefix>(?:contentItem: |delegate: )?)Text \{\n"
                         r"(?P<body>.*?)^(?P=indent)\}", re.M | re.S)

    def adapt(match):
        indent = match["indent"]
        body, count = re.subn(r"^" + indent + r"    color:", indent + "    baseColor:",
                              match["body"], count=1, flags=re.M)
        if not count:
            return match[0]
        member = re.escape(indent + "    ")
        # Stored upstream rich-text bindings keep their markup and links.
        if (not re.search(r"^" + member + "textFormat:", body, re.M)
                and not package.name.endswith(".clock-glass-text")):
            body, found = re.subn("^" + member + "text:", indent + "    sourceText:", body, count=1, flags=re.M)
            if found:
                body += (indent + "    textFormat: useRuns ? Text.StyledText : Text.AutoText\n"
                         + indent + "    text: useRuns ? glyphText() : sourceText\n")
        return (indent + match["prefix"] + "NativeInk.AdaptiveWidgetText {\n"
                + indent + f'    contrastProfile: "{profile}"\n' + body + indent + "}")


    for file in (ui / "main.qml", *(ui / "widget").glob("*.qml")):
        if not file.is_file():
            continue
        source = file.read_text()
        adapted = element.sub(adapt, source)
        if package.name.endswith(".clock-glass-text") and file.name == "GlassClockText.qml":
            adapted = adapted.replace("property int hour12:", "property bool adaptOverlay: false\n    property int hour12:")
            adapted = re.sub(r"(NativeInk.AdaptiveWidgetText \{.*?)(\n +)text: ([^\n]+)",
                             r"\1\2clockOverlay: root.adaptOverlay\2sourceText: \3"
                             r"\2textFormat: useRuns ? Text.StyledText : Text.PlainText"
                             r"\2text: useRuns ? glyphText() : sourceText", adapted, flags=re.S)
        if package.name.endswith(".clock-glass-text") and file.name == "main.qml":
            adapted = adapted.replace("id: overlay", "id: overlay\n            adaptOverlay: true")
        if adapted != source:
            file.write_text("import org.kde.mac.tahoe.launcher as NativeInk\n" + adapted)


def stage_configuration_route(package):
    variant = package.name.removeprefix(PREFIX)
    if not package.name.startswith(PREFIX) or variant not in NAMES:
        return
    stage_appearance(package, variant)
    stage_glass_text(package)
    main = package / "contents/ui/main.qml"
    if not main.is_file():
        return
    text = main.read_text(encoding="utf-8")
    if variant == "weather":
        text = text.replace("MacSpinner {\n            anchors.centerIn",
                            "MacSpinner {\n            color: colors.weatherForeground\n            anchors.centerIn")
        if "import QtQuick.Effects" not in text:
            text = text.replace("import QtQuick.Layouts", "import QtQuick.Layouts\nimport QtQuick.Effects")
        location = 'source: Qt.resolvedUrl("icons/location.png")'
        if "colorizationColor: colors.weatherForeground" not in text:
            text = text.replace(location, location + """
                    layer.enabled: true
                    layer.effect: MultiEffect {
                        autoPaddingEnabled: false
                        colorization: 1
                        colorizationColor: colors.weatherForeground
                    }""")
    if variant == "music":
        text = text.replace('    readonly property string _noAlbumUrl: Qt.resolvedUrl("icons/no_album.png")\n', '')
        text = text.replace('property string albumArt: _noAlbumUrl', 'property string albumArt: ""')
        text = text.replace('albumArt = _noAlbumUrl', 'albumArt = ""')
        text = text.replace('        if (_rawAlbumArt === "") return', """        if (_rawAlbumArt === "") {
            _artDebounceTimer.stop()
            albumArt = ""
            return
        }""")
    if variant == "clock-analog":
        text = text.replace('color _dialColor: _realLight ? "#000000" : "#ffffff"',
                            'color _dialColor: colors.foreground')
    main.write_text(text, encoding="utf-8")
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
