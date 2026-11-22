"""Menu bars on every screen share their tray icons and widget settings."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

SYNC = Path(__file__).resolve().parents[1] / (
    "src/offline/plasmoids/org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui/MenuBarSync.js")

HARNESS = r'''
function Signal() { this.slots = []; }
Signal.prototype.connect = function (f) { this.slots.push(f); };
Signal.prototype.disconnect = function (f) { this.slots = this.slots.filter(g => g !== f); };
function Config(values) {
    const map = { valueChanged: new Signal(), writes: 0 };
    map.keys = () => Object.keys(values).concat(Object.keys(values).map(k => k + "Default"));
    map.writeConfig = () => { map.writes++; };
    for (const key of Object.keys(values)) {
        let value = values[key];
        Object.defineProperty(map, key, { enumerable: true,
            get: () => value,
            set: v => { value = v; map.valueChanged.slots.forEach(f => f(key, v)); } });
    }
    return map;
}
function applet(plugin, values) { return { pluginName: plugin, configuration: Config(values) }; }
function bar() {
    return { applets: [
        applet("luisbocanegra.panel.colorizer", { panelWidgets: "own-ids" }),
        applet("org.kde.plasma.systemtray", { hiddenItems: ["discord"], iconSpacing: 3 }),
        applet("org.kde.plasma.digitalclock", { showSeconds: 0 }),
    ] };
}
'''


def run(script):
    if not shutil.which("node"):
        pytest.skip("node is unavailable")
    source = SYNC.read_text().replace(".pragma library", "")
    program = HARNESS + source + script
    result = subprocess.run(["node", "-e", program], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def test_tray_icons_and_widget_settings_follow_the_bar_that_changed():
    out = run(r'''
const a = bar(), b = bar(), c = bar();
[a, b, c].forEach(x => register(x));
b.applets[1].configuration.hiddenItems = ["discord", "steam"];
c.applets[2].configuration.showSeconds = 2;
console.log(JSON.stringify([a, b, c].map(x => [x.applets[1].configuration.hiddenItems, x.applets[2].configuration.showSeconds])));
''')
    assert out == [[["discord", "steam"], 2]] * 3


def test_panel_colorizer_keeps_its_own_panel_widgets():
    out = run(r'''
const a = bar(), b = bar();
register(a); register(b);
a.applets[0].configuration.panelWidgets = "ids-of-a";
console.log(JSON.stringify(b.applets[0].configuration.panelWidgets));
''')
    assert out == "own-ids"


def test_a_new_bar_adopts_the_existing_settings():
    out = run(r'''
const a = bar(); a.applets[1].configuration.iconSpacing = 6;
register(a);
const b = bar(); register(b);
console.log(JSON.stringify(b.applets[1].configuration.iconSpacing));
''')
    assert out == 6


def test_unregistered_bar_stops_following():
    out = run(r'''
const a = bar(), b = bar();
register(a); const bb = register(b);
unregister(bb);
a.applets[1].configuration.iconSpacing = 8;
console.log(JSON.stringify(b.applets[1].configuration.iconSpacing));
''')
    assert out == 3
