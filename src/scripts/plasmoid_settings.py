"""Read and update widget preferences through Plasma's live instance API."""

from __future__ import annotations

import json

from theme_switch import _evaluate_plasma_script

SETTINGS = {
    "trash": (
        {"org.kde.mac-tahoe-liquid-kde.trashcan"}, "General",
        {"emptyIcon": "user-trash", "fullIcon": "user-trash-full"},
    ),
    "dock": (
        {"org.kde.mac.tahoe.liquid.icontasks", "org.kde.mac.tahoe.liquid.taskmanager"}, "General",
        {"macOSDockIcons": False},
    ),
    "system_menu": (
        {"org.kde.mac.tahoe.liquid.globalmenu"}, "Appearance",
        {"iconAppStore": "software-store-symbolic", "cmdAppStore": "",
         "cmdLogOut": "qdbus6 org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptLogout"},
    ),
}


def _request(kind, instance=None, changes=None):
    plugins, group, defaults = SETTINGS[kind]
    if instance is not None and (type(instance) is not int or instance <= 0):
        raise ValueError("Invalid widget ID")
    if changes is not None and (instance is None or any(
        key not in defaults or type(value) is not type(defaults[key])
        or isinstance(value, str) and (len(value) > 4096 or any(c in value for c in "\0\r\n"))
        for key, value in changes.items()
    )):
        raise ValueError("Invalid widget preferences")
    payload = json.dumps({"plugins": sorted(plugins), "group": group, "defaults": defaults,
                          "instance": instance, "changes": changes})
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
            for (const key of Object.keys(request.changes))
                widget.writeConfig(key, request.changes[key]);
            widget.reloadConfig();
        }
        const values = {};
        for (const key of Object.keys(request.defaults)) {
            let fallback = request.defaults[key];
            if (request.group === "Appearance") {
                widget.currentConfigGroup = [];
                fallback = widget.readConfig(key, fallback);
                widget.currentConfigGroup = [request.group];
            }
            values[key] = widget.readConfig(key, fallback);
        }
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
