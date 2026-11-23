"""Read and update widget preferences through Plasma's live instance API."""

from __future__ import annotations

import json

import dock_preferences
import launcher_preferences
import weather_panel_settings
from launcher_defaults import LAUNCHER_ID
from theme_switch import _evaluate_plasma_script

TYPED_PREFERENCES = {"dock": dock_preferences, "launcher": launcher_preferences, "weather_panel": weather_panel_settings}
SHORTCUT_WIDGETS = {"dock", "launcher", "trash", "bar_shortcuts", "control_center", "weather_panel"}
WIDGET_PREFIX = "org.kde.mac-tahoe-liquid-kde."
BAR_WIDGET_LABELS = {
    WIDGET_PREFIX + "acrylicglass": "Acrylic Glass",
    WIDGET_PREFIX + "battery": "Battery",
    WIDGET_PREFIX + "bluetooth": "Bluetooth",
    WIDGET_PREFIX + "dockseparator": "Dock Separator",
    WIDGET_PREFIX + "downloads": "Downloads",
    WIDGET_PREFIX + "notifications": "Notifications",
    WIDGET_PREFIX + "wifi": "Wi-Fi",
}
CONTROL_CENTER_FIELDS = {
    "showWifi": "Wi-Fi",
    "showBluetooth": "Bluetooth",
    "showBattery": "Battery",
    "showMedia": "Now Playing",
    "showSharing": "File Sharing",
    "showOverview": "Overview",
    "showMirroring": "Screen Mirroring",
    "showDarkMode": "Dark Mode",
    "showScreenshot": "Screenshot",
    "showFocus": "Focus",
    "showNotifications": "Notifications",
    "showSettings": "Bluetooth Settings…",
    "showDisplay": "Display",
    "showAudio": "Sound",
}

SETTINGS = {
    "trash": (
        {"org.kde.mac-tahoe-liquid-kde.trashcan"}, "General",
        {"emptyIcon": "user-trash", "fullIcon": "user-trash-full"},
    ),
    "dock": (
        {dock_preferences.DOCK_ICONS, dock_preferences.DOCK_TASKS}, "General", dock_preferences.DEFAULTS,
    ),
    "launcher": (
        {LAUNCHER_ID}, "General", launcher_preferences.DEFAULTS,
    ),
    "bar_shortcuts": (BAR_WIDGET_LABELS.keys(), "General", {}),
    "control_center": (
        {WIDGET_PREFIX + "controlcenter"}, "General",
        dict.fromkeys(CONTROL_CENTER_FIELDS, True) | {"showNotifications": False, "showSettings": False},
    ),
    "weather_panel": ({weather_panel_settings.PLUGIN}, "General", weather_panel_settings.DEFAULTS),
    "system_menu": (
        {"org.kde.mac.tahoe.liquid.globalmenu"}, "Appearance",
        {"iconAppStore": "software-store-symbolic", "cmdAppStore": "",
         "cmdLogOut": "qdbus6 org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptLogout"},
    ),
}


def _request(kind, instance=None, changes=None):
    plugins, group, defaults = SETTINGS[kind]
    typed = TYPED_PREFERENCES.get(kind)
    has_shortcut = kind in SHORTCUT_WIDGETS
    valid_keys = defaults | ({"activationShortcut": ""} if has_shortcut else {})
    if instance is not None and (type(instance) is not int or instance <= 0):
        raise ValueError("Invalid widget ID")
    if changes is not None and (instance is None or any(
        key not in valid_keys or type(value) is not type(valid_keys[key])
        or isinstance(value, str) and (len(value) > 4096 or any(c in value for c in "\0\r\n"))
        for key, value in changes.items()
    )):
        raise ValueError("Invalid widget preferences")
    if typed is not None and changes and any(
        (key in typed.CHOICES and value not in typed.CHOICES[key])
        or (key in typed.RANGES and not typed.RANGES[key][0] <= value <= typed.RANGES[key][1])
        for key, value in changes.items()
    ):
        raise ValueError({"dock": "Invalid Dock preference value", "launcher": "Invalid launcher preference value",
                          "weather_panel": "Invalid weather preference value"}[kind])
    payload = json.dumps({"plugins": sorted(plugins), "group": group, "defaults": defaults,
                          "instance": instance, "changes": changes, "dock": kind == "dock",
                          "hasShortcut": has_shortcut, "identifyPlugin": kind in {"dock", "bar_shortcuts"}})
    script = """
const request = REQUEST;
const result = {};
const containers = [...panels(), ...desktops(), ...desktopsForActivity(currentActivity())];
for (const container of containers) {
    for (const widget of container.widgets()) {
        if (!request.plugins.includes(widget.type)
            || (request.instance !== null && widget.id !== request.instance)
            || Object.prototype.hasOwnProperty.call(result, widget.id))
            continue;
        widget.currentConfigGroup = [request.group];
        if (request.changes !== null) {
            let shortcutAccepted = true;
            if ("activationShortcut" in request.changes) {
                const previous = widget.globalShortcut;
                widget.globalShortcut = request.changes.activationShortcut;
                shortcutAccepted = widget.globalShortcut === request.changes.activationShortcut;
                if (!shortcutAccepted)
                    widget.globalShortcut = previous;
            }
            if (shortcutAccepted) {
                for (const key of Object.keys(request.changes)) {
                    if (key !== "activationShortcut")
                        widget.writeConfig(key, request.changes[key]);
                }
                widget.reloadConfig();
            }
        }
        const values = {};
        if (request.hasShortcut)
            values.activationShortcut = widget.globalShortcut;
        for (const key of Object.keys(request.defaults)) {
            let fallback = request.defaults[key];
            if (request.group === "Appearance") {
                widget.currentConfigGroup = [];
                fallback = widget.readConfig(key, fallback);
                widget.currentConfigGroup = [request.group];
            }
            values[key] = widget.readConfig(key, fallback);
        }
        if (request.identifyPlugin)
            values._plugin = widget.type;
        if (request.dock)
            values._vertical = container.formFactor === "vertical";
        result[widget.id] = values;
    }
}
print(JSON.stringify(result));
""".replace("REQUEST", payload, 1)
    result = _evaluate_plasma_script(script)
    try:
        decoded = json.loads(result)
        if not isinstance(decoded, dict):
            raise ValueError
        if typed is not None or kind == "control_center":
            for values in decoded.values():
                for key, default in defaults.items():
                    value = values.get(key, default)
                    if isinstance(default, bool):
                        values[key] = value is True or str(value).lower() == "true"
                    elif isinstance(default, int) and type(value) is not int:
                        try:
                            values[key] = int(value)
                        except (ValueError, TypeError):
                            values[key] = default
                    elif isinstance(default, str):
                        values[key] = str(value) if value is not None else default
                    elif isinstance(default, float):
                        try:
                            values[key] = float(value)
                        except (ValueError, TypeError):
                            values[key] = default
        return {int(key): value for key, value in decoded.items()}
    except (TypeError, ValueError):
        raise RuntimeError("Could not read widget preferences from Plasma.") from None


def instances(kind):
    return _request(kind)


def apply(kind, instance, changes):
    actual = _request(kind, instance, changes).get(instance)
    if actual is None or any(
        value != actual.get(key) and not (type(value) is bool and str(value).lower() == actual.get(key))
        for key, value in changes.items()
    ):
        raise RuntimeError("Could not save widget preferences in Plasma.")
    return actual
