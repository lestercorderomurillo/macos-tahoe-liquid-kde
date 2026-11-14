#!/usr/bin/env python3
"""Exercise the installed Launcher through Plasma and measure KWin's real frames.

Run only inside the disposable release VM, after installing the requested edition.
This complements the isolated QML/input cases: a QWindow's declared size can differ
from the surface size accepted by the Wayland compositor.
"""
import argparse
import ast
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/scripts'))
from release_capture_guest import plasma, run, windows


def frames():
    return [w['geometry'] for w in windows() if w['appletPopup'] and not w['hidden']
            and w['resourceClass'] in ('plasmashell', 'org.kde.plasmashell')]


def toggle():
    run('qdbus6', 'org.kde.plasmashell', '/PlasmaShell', 'org.kde.PlasmaShell.activateLauncherMenu')


def preset(value):
    plasma('panels().forEach(p=>p.widgets().filter(w=>w.type==="org.kde.mac-tahoe-liquid-kde.launcher")'
           '.forEach(w=>{w.currentConfigGroup=["General"];w.writeConfig("launcherPreset",'
           + str(value) + ');w.reloadConfig();}));')


def settle(value, expected=None):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        time.sleep(.15)
        current = frames()
        panels = [f for f in current if f['height'] > 250]
        if len(panels) == 1:
            panel = panels[0]
            capsule = [f for f in current if f['height'] <= 250]
            size_matches = expected is None or all(
                abs(panel[k] - expected[k]) <= 1 for k in ('width', 'height'))
            # The compositor configures these two surfaces independently.
            # Wait for both, rather than sampling the capsule mid-transition.
            capsule_matches = not capsule if value == 1 else (
                len(capsule) == 1
                and abs(capsule[0]['width'] / panel['width'] - .617) < .01
                and abs(capsule[0]['x'] + capsule[0]['width']/2
                        - panel['x'] - panel['width']/2) < 2
                and capsule[0]['y'] + capsule[0]['height'] < panel['y'])
            if size_matches and capsule_matches:
                return panel, capsule
    raise AssertionError(f'KWin retained the wrong Launcher geometry: {current}; expected {expected}')


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument('--output', type=Path, required=True)
    opts = args.parse_args()
    assert Path('/sys/class/dmi/id/product_name').read_text().strip() == 'MTTKDE release capture'
    switcher = Path.home()/'.local/bin/mac-tahoe-theme-switch'
    choices = ast.literal_eval(next(line.split('=', 1)[1].strip()
        for line in switcher.read_text().splitlines() if line.startswith('INSTALLER_OPTIONS =')))
    assert choices.get('icons') == 'regular', 'Qualify with the wizard default icon family'
    docks = json.loads(plasma('print(JSON.stringify(panels().filter(p=>p.location==="bottom")'
        '.map(p=>p.widgets().map(w=>w.type))));'))
    assert len(docks) == 1, docks
    assert set(docks[0]) == {'org.kde.mac-tahoe-liquid-kde.launcher',
        'org.kde.mac.tahoe.liquid.icontasks', 'org.kde.mac-tahoe-liquid-kde.trashcan'}, docks
    print('LAUNCHER_DESKTOP_OK', json.dumps({'choices': choices, 'docks': docks}))
    result = []
    try:
        if frames():
            toggle()
            time.sleep(.3)
        sizes = {}
        for value in (1, 2):
            preset(value)
            toggle()
            panel, capsule = settle(value)
            sizes[value] = panel
            result.append({'case': f'fresh-{value}', 'panel': panel, 'capsule': capsule})
            toggle()
            time.sleep(.3)
        assert sizes[2]['width'] > sizes[1]['width'] * 1.4, sizes
        preset(1)
        toggle()
        for value in (1, 2, 1, 2):
            preset(value)
            panel, capsule = settle(value, sizes[value])
            if value == 2:
                assert len(capsule) == 1, capsule
                search = capsule[0]
                assert abs(search['width'] / panel['width'] - .617) < .01, (panel, search)
                assert abs(search['x'] + search['width']/2 - panel['x'] - panel['width']/2) < 2
                assert search['y'] + search['height'] < panel['y']
            else:
                assert not capsule, capsule
            result.append({'case': f'live-{value}', 'panel': panel, 'capsule': capsule})
        for index in range(16):
            preset(index % 2 + 1)
            time.sleep(.04)
        panel, capsule = settle(2, sizes[2])
        result.append({'case': 'rapid-16-final-2', 'panel': panel, 'capsule': capsule})
        print('LAUNCHER_KWIN_OK', json.dumps(result))
    finally:
        opts.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
