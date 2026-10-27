#!/usr/bin/env python3
"""Exercise visible native apps in the disposable guest, including Firefox input."""
from __future__ import annotations

import argparse
import configparser
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

from desktop_probe import require_guest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src/scripts'))
STATE = Path.home() / '.local/state/mttkde-vm-apps'
PROFILE = Path.home() / '.mozilla/firefox/mttkde-vm-proof'
SNAP_COMMON = Path.home() / 'snap/firefox/common'
if SNAP_COMMON.is_dir() or Path('/snap/firefox/current').is_dir():
    PROFILE = SNAP_COMMON / '.mozilla/firefox/mttkde-vm-proof'
# Confined Firefox must be able to read the fixture as well as its profile.
PAGE = PROFILE / 'browser.html'


class Marionette:
    """Mozilla's framed JSON protocol, confined to guest loopback.

    https://firefox-source-docs.mozilla.org/remote/marionette/Protocol.html
    """
    def __init__(self):
        self.socket = socket.create_connection(('127.0.0.1', 2828), timeout=30)
        self.stream = self.socket.makefile('rb')
        self.sequence = 0
        hello = self.receive()
        if hello.get('marionetteProtocol') != 3:
            raise RuntimeError(f'Unsupported Firefox protocol: {hello}')

    def receive(self):
        length = b''
        while True:
            byte = self.stream.read(1)
            if not byte:
                raise RuntimeError('Firefox closed its automation connection')
            if byte == b':':
                break
            if not byte.isdigit() or len(length) > 9:
                raise RuntimeError('Invalid Firefox response frame')
            length += byte
        return json.loads(self.stream.read(int(length)))

    def call(self, command, **parameters):
        self.sequence += 1
        payload = json.dumps([0, self.sequence, command, parameters]).encode()
        self.socket.sendall(str(len(payload)).encode() + b':' + payload)
        response = self.receive()
        if response[:2] != [1, self.sequence] or response[2] is not None:
            raise RuntimeError(f'{command}: {response}')
        return response[3]

    def script(self, script):
        return self.call('WebDriver:ExecuteScript', script=script, args=[], newSandbox=True,
                         sandbox='default', line=1, filename='vm-proof')['value']

    def close(self):
        self.stream.close()
        self.socket.close()


def prepare():
    # A previous qualification ends with uninstall. Its still-running apps
    # retain the removed style providers; start fresh after the next install.
    for name in ('firefox', 'firefox-esr', 'nautilus', 'dolphin', 'konsole'):
        subprocess.run(['pkill', '-u', str(os.getuid()), '-x', name], check=False)
    time.sleep(2)
    STATE.mkdir(parents=True, exist_ok=True)
    PROFILE.mkdir(parents=True, exist_ok=True)
    (PROFILE / 'prefs.js').touch(exist_ok=True)
    ini = PROFILE.parent / 'profiles.ini'
    config = configparser.ConfigParser()
    config.optionxform = str
    config.read(ini)
    config['ProfileMTTKDEVM'] = {'Name': 'mttkde-vm-proof', 'IsRelative': '1', 'Path': PROFILE.name}
    with ini.open('w') as output:
        config.write(output)
    preferences = {
        'marionette.port': 2828, 'browser.shell.checkDefaultBrowser': False,
        'browser.startup.homepage_override.mstone': 'ignore', 'browser.aboutwelcome.enabled': False,
        'browser.startup.page': 0, 'datareporting.policy.dataSubmissionEnabled': False,
        'toolkit.telemetry.reportingpolicy.firstRun': False,
        'browser.newtabpage.enabled': False,
    }
    # Only create the fixture once: later installs own their appended theme block.
    if not (PROFILE / 'user.js').exists():
        (PROFILE / 'user.js').write_text(''.join(f'user_pref({json.dumps(k)}, {json.dumps(v)});\n'
                                               for k, v in preferences.items()))
    PAGE.write_text('''<!doctype html><meta charset="utf-8"><title>Firefox desktop verification</title>
<style>:root{color-scheme:light dark}body{font-family:system-ui;margin:3%;line-height:1.4}
h1{font-weight:500}input,button{font:inherit;padding:.7em;border-radius:.5em}
section{border:1px solid GrayText;border-radius:1em;padding:1em}output{display:block;margin-top:1em}
</style><section><p>macOS Tahoe inspired KDE theme</p><h1>Firefox desktop verification</h1>
<p>Native rendering, keyboard input and desktop appearance.</p>
<input id="entry" placeholder="Type a test value"><button id="submit">Check input</button>
<output id="result">Ready</output><p id="appearance"></p></section>
<script>submit.onclick=()=>result.textContent=entry.value;
const query=matchMedia('(prefers-color-scheme: dark)');
function update(){appearance.textContent='Browser appearance: '+(query.matches?'dark':'light')}
query.addEventListener('change',update);update();</script>''')
    documents = Path.home() / 'Documents/VM Proof'
    for name in ('Design', 'Projects', 'Screenshots', 'Wallpapers'):
        (documents / name).mkdir(parents=True, exist_ok=True)


def launch(argv):
    with (STATE / (Path(argv[0]).name + '.log')).open('ab') as log:
        return subprocess.Popen(argv, stdout=log, stderr=log, start_new_session=True).pid


def check_browser(mode=None):
    """Exercise the same browser after appearance changes, including removal."""
    deadline = time.monotonic() + 60
    while True:
        try:
            browser = Marionette()
            break
        except (ConnectionError, OSError):
            if time.monotonic() > deadline:
                raise RuntimeError('Firefox did not start its native automation endpoint')
            time.sleep(1)
    try:
        session = browser.call('WebDriver:NewSession', capabilities={})
        browser.call('WebDriver:Navigate', url=PAGE.as_uri())
        field = browser.call('WebDriver:FindElement', using='css selector', value='#entry')['value']
        element = field['element-6066-11e4-a52e-4f735466cecf']
        browser.call('WebDriver:ElementSendKeys', id=element, text='Plasma desktop input passed')
        button = browser.call('WebDriver:FindElement', using='css selector', value='#submit')['value']
        browser.call('WebDriver:ElementClick', id=button['element-6066-11e4-a52e-4f735466cecf'])
        observation = browser.script("return {dark:matchMedia('(prefers-color-scheme: dark)').matches, result:document.querySelector('#result').textContent, userAgent:navigator.userAgent};")
        if (mode is not None and observation['dark'] != (mode == 'dark')) or observation['result'] != 'Plasma desktop input passed':
            raise RuntimeError(f'Firefox interaction/appearance failed: {observation}')
        browser.call('WebDriver:DeleteSession')
    finally:
        browser.close()
    return observation, session["capabilities"]["browserVersion"]


def exercise(mode):
    from utils import restore_desktop_session_env
    from release_capture_guest import windows
    from screenshot_checks import wait_for_session
    restore_desktop_session_env()
    wait_for_session(mode)
    for binary in ('firefox', 'nautilus', 'dolphin', 'konsole'):
        if not shutil.which(binary):
            raise RuntimeError(f'Missing native application: {binary}')
    if not (PROFILE / 'chrome/userChrome.css').is_file():
        raise RuntimeError('The installer did not theme the Firefox QA profile')
    current = windows()
    classes = [w['resourceClass'].lower() for w in current]
    if not any('firefox' in c for c in classes):
        launch(['firefox', '--no-remote', '--marionette', '--profile', str(PROFILE), PAGE.as_uri()])
    documents = str(Path.home() / 'Documents/VM Proof')
    for marker, argv in (
        ('nautilus', ['nautilus', '--new-window', documents]),
        ('dolphin', ['dolphin', '--new-window', documents]),
        ('konsole', ['konsole', '--separate', '--hold', '-e', 'bash', '-c',
                     'cat /etc/os-release; printf "\\n"; plasmashell --version; qmake6 -query QT_VERSION; uname -r']),
    ):
        if not any(marker in c for c in classes):
            launch(argv)
    observation, browser_version = check_browser(mode)
    time.sleep(3)
    windows("""workspace.windowList().filter(w=>w.windowType===0).forEach(w=>{
      w.setMaximize(false,false); w.minimized=false;
    });""")
    time.sleep(1)
    windows("""const positions = [
      ['firefox', {x:45,y:65,width:900,height:475}],
      ['nautilus', {x:975,y:65,width:900,height:475}],
      ['dolphin', {x:45,y:565,width:900,height:475}],
      ['konsole', {x:975,y:565,width:900,height:475}]];
      for (const w of workspace.windowList()) {
        if (w.windowType === 0 && !positions.some(([name])=>String(w.resourceClass).toLowerCase().includes(name))) w.minimized=true;
      }
      for (const [name, geometry] of positions) {
        const w = workspace.windowList().find(w=>String(w.resourceClass).toLowerCase().includes(name));
        if (w) {
          // Keep the native QRectF type: plain JS objects are ignored on KWin 6.8.
          const bounds=workspace.clientArea(KWin.FullArea,w);
          bounds.x=geometry.x; bounds.y=geometry.y;
          bounds.width=geometry.width; bounds.height=geometry.height;
          w.frameGeometry=bounds;
        }
      }""")
    # Wayland clients acknowledge resize requests asynchronously. Sampling
    # their old bounds would check wallpaper pixels instead of the Files view.
    expected_positions = {'firefox': (45, 65), 'nautilus': (975, 65),
                          'dolphin': (45, 565), 'konsole': (975, 565)}
    deadline = time.monotonic() + 30
    previous = None
    while True:
        observed = windows()
        placed = all(any(marker in w['resourceClass'].lower()
                         and abs(w['geometry']['x'] - x) <= 2
                         and abs(w['geometry']['y'] - y) <= 2
                         for w in observed)
                     for marker, (x, y) in expected_positions.items())
        bounds = [w['geometry'] for w in observed]
        if placed and bounds == previous:
            break
        if time.monotonic() > deadline:
            raise RuntimeError(f'Application window placement did not settle: {observed}')
        previous = bounds
        time.sleep(.5)
    classes = [w['resourceClass'].lower() for w in observed]
    for marker in ('firefox', 'nautilus', 'dolphin', 'konsole'):
        if not any(marker in value for value in classes):
            raise RuntimeError(f'No visible {marker} window: {classes}')
    processes = {}
    for name, pattern in [('firefox', 'firefox|firefox-esr'), ('nautilus', 'nautilus'), ('dolphin', 'dolphin'), ('konsole', 'konsole')]:
        processes[name] = subprocess.check_output(['pgrep', '-u', str(os.getuid()), '-x', pattern], text=True).split()
    return {'mode': mode, 'status': 'pass', 'firefox': observation, 'processes': processes,
            'browser_version': browser_version, 'windows': observed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--check-browser', action='store_true')
    parser.add_argument('--mode', choices=('light', 'dark'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    require_guest()
    if args.check_browser:
        print(json.dumps(check_browser()))
    elif args.prepare:
        prepare()
    else:
        report = exercise(args.mode)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
