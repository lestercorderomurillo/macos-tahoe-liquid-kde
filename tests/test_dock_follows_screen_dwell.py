"""The Dock moves to another screen only after the pointer rests on its bottom edge."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / (
    "src/offline/kwin-scripts/mttkde-dock-follows-screen/contents/code/main.js")

HARNESS = r'''
const timers = [];
function QTimer() { this.interval = 0; this.singleShot = false; this.active = false;
    const slots = []; this.timeout = { connect: f => slots.push(f) };
    this.start = () => { this.active = true; }; this.stop = () => { this.active = false; };
    this.fire = () => { if (!this.active) return; this.active = false; slots.forEach(f => f()); };
    timers.push(this); }
function Signal() { const s = []; return { connect: f => s.push(f), emit: () => s.forEach(f => f()) }; }
const screens = [
    { name: "A", geometry: { x: 0, y: 0, width: 1920, height: 1080 } },
    { name: "B", geometry: { x: 1920, y: 0, width: 1920, height: 1080 } },
];
const moves = [];
const workspace = { screens: screens, cursorPos: { x: 100, y: 500 },
    cursorPosChanged: Signal(), screensChanged: Signal(),
    screenAt: p => screens.find(s => p.x >= s.geometry.x && p.x < s.geometry.x + s.geometry.width) };
function callDBus(service, path, iface, method, script) { moves.push(script.match(/screenForConnector\("(\w+)"\)/)[1]); }
function point(x, y) { workspace.cursorPos = { x: x, y: y }; workspace.cursorPosChanged.emit(); }
'''


def run(steps):
    if not shutil.which("node"):
        pytest.skip("node is unavailable")
    program = HARNESS + SCRIPT.read_text().replace('"use strict";', "") + steps + \
        "\nconsole.log(JSON.stringify({moves: moves, interval: timers[0].interval}));"
    return json.loads(subprocess.run(["node", "-e", program], capture_output=True,
                                     text=True, check=True).stdout)


def test_waits_two_seconds_on_the_bottom_edge_before_moving():
    out = run('point(2500, 1079); const before = moves.length; timers[0].fire(); moves.unshift(before);')
    assert out["interval"] >= 2000
    assert out["moves"] == [0, "B"]


def test_leaving_the_edge_before_the_delay_keeps_the_dock_in_place():
    out = run('point(2500, 1079); point(2500, 1000); timers[0].fire();')
    assert out["moves"] == []


def test_sliding_to_another_screen_restarts_the_wait():
    out = run('point(2500, 1079); point(300, 1079); timers[0].fire();')
    assert out["moves"] == ["A"]
