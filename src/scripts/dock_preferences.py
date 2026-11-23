"""Editable preferences exposed by the Dock's Appearance and Behavior pages."""

from pathlib import Path
from xml.etree import ElementTree

DOCK_ICONS = "org.kde.mac.tahoe.liquid.icontasks"
DOCK_TASKS = "org.kde.mac.tahoe.liquid.taskmanager"

APPEARANCE = {
    "macOSDockIcons": "macOS-style Dock icons",
    "dockMagnification": "Hover magnification",
    "showToolTips": "Show window previews",
    "highlightWindows": "Highlight the hovered window",
    "indicateAudioStreams": "Show audio indicators",
    "interactiveMute": "Mute by clicking the audio indicator",
    "tooltipControls": "Show media and volume controls in previews",
    "fill": "Fill free space on the panel",
    "taskMaxWidth": "Maximum task width",
    "maxStripes": "Maximum rows or columns",
    "forceStripes": "Always use multiple rows or columns",
}
BEHAVIOR = {
    "groupingStrategy": "Group tasks",
    "groupedTaskVisualization": "When clicking a grouped task",
    "groupPopups": "Combine grouped tasks into one button",
    "onlyGroupWhenFull": "Group only when the task manager is full",
    "sortingStrategy": "Sort tasks",
    "separateLaunchers": "Keep launchers separate",
    "hideLauncherOnStart": "Hide launchers after application startup",
    "minimizeActiveTaskOnClick": "Minimize the active task when clicked",
    "middleClickAction": "Middle-click action",
    "wheelEnabled": "Scrolling behavior",
    "wheelSkipMinimized": "Skip minimized tasks when scrolling",
    "showOnlyCurrentDesktop": "Show tasks only from the current desktop",
    "showOnlyCurrentActivity": "Show tasks only from the current activity",
    "showOnlyCurrentScreen": "Show tasks only from the current display",
    "showOnlyMinimized": "Show only minimized tasks",
    "unhideOnAttention": "Show the hidden panel when a window wants attention",
    "reverseMode": "Reverse where new tasks appear",
}
CHOICES = {
    "taskMaxWidth": dict(enumerate(("Narrow", "Medium", "Wide"))),
    "groupingStrategy": dict(enumerate(("Do not group", "By program name"))),
    "groupedTaskVisualization": dict(enumerate(("Cycle through tasks", "Small window previews",
                                                "Large window previews", "Text list"))),
    "sortingStrategy": {0: "Do not sort", 1: "Manually", 2: "Alphabetically", 3: "By desktop",
                        4: "By activity", 6: "By horizontal window position"},
    "middleClickAction": dict(enumerate(("Do nothing", "Close window or group", "Open a new window",
                                         "Minimize or restore", "Toggle grouping", "Bring to current desktop"))),
    "wheelEnabled": dict(enumerate(("Do nothing", "Cycle through all tasks",
                                    "Cycle through the hovered task’s windows", "Adjust the hovered task’s volume"))),
}
RANGES = {"dockMagnification": (100, 150), "maxStripes": (1, 99)}
ICONS_ONLY = {"macOSDockIcons", "dockMagnification"}
TASKS_ONLY = {"taskMaxWidth", "groupPopups", "onlyGroupWhenFull", "separateLaunchers", "hideLauncherOnStart"}


def _defaults():
    schema = (Path(__file__).resolve().parents[1] / "offline/plasmoids" / DOCK_TASKS
              / "contents/config/main.xml")
    return {
        entry.attrib["name"]: (entry.findtext("{*}default") == "true" if entry.attrib["type"] == "Bool"
                               else int(entry.findtext("{*}default")))
        for entry in ElementTree.parse(schema).findall(".//{*}entry")
        if entry.attrib["name"] in APPEARANCE or entry.attrib["name"] in BEHAVIOR
    }


DEFAULTS = _defaults()
