#!/usr/bin/env python3
"""Observe live Kirigami colors in disposable copies of the shipped QML applets."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

if Path('/sys/class/dmi/id/product_name').read_text().strip() != 'MTTKDE release capture':
    raise SystemExit('This probe requires the disposable capture VM')
root = Path.home() / 'appearance-plasmoids'
root.mkdir(exist_ok=True)
source = Path(__file__).resolve().parents[2] / 'src/offline/plasmoids'
pid = subprocess.check_output(['pgrep', '-u', str(os.getuid()), '-x', 'plasmashell']).decode().strip()
session = dict(x.decode().split('=', 1) for x in Path('/proc/' + pid + '/environ').read_bytes().split(b'\0') if b'=' in x)
os.environ.update({k: v for k, v in session.items() if k in ('DISPLAY', 'XAUTHORITY', 'WAYLAND_DISPLAY', 'XDG_SESSION_TYPE')})
processes = []
for package in source.iterdir():
    # Compiled applets resolve QML through their plugin, so instrumenting a
    # loose copy cannot prove their live behavior; exercise those in Plasma.
    if package.name not in ('org.kde.mac-tahoe-liquid-kde.launcher',
                            'org.kde.mac-tahoe-liquid-kde.trashcan',
                            'luisbocanegra.panel.colorizer'):
        continue
    metadata = json.loads((package / 'metadata.json').read_text())
    payload = source / metadata.get('X-Plasma-RootPath', package.name)
    main = payload / 'contents/ui/main.qml'
    if not main.is_file():
        continue  # The compiled global menu has a separate native probe.
    staged = root / package.name
    if staged.exists():
        shutil.rmtree(staged)
    shutil.copytree(payload, staged)
    metadata.pop('X-Plasma-RootPath', None)
    (staged / 'metadata.json').write_text(json.dumps(metadata))
    main = staged / 'contents/ui/main.qml'
    text = main.read_text()
    identity = re.search(r'\bid:\s*(\w+)', text)[1]
    timer = '''
 Timer {
  interval: 250; running: true; repeat: true
  onTriggered: console.warn("APPEARANCE_SNAPSHOT", JSON.stringify({
    id: "%s", background: String(%s.AppearanceProbe.Theme.backgroundColor),
    text: String(%s.AppearanceProbe.Theme.textColor)
  }))
 }
''' % (package.name, identity, identity)
    # QML pragmas must remain before imports (the task manager uses one).
    point = text.index('import ')
    text = text[:point] + 'import org.kde.kirigami as AppearanceProbe\n' + text[point:]
    point = text.rfind('}')
    main.write_text(text[:point] + timer + text[point:])
    with (root / (package.name + '.log')).open('w') as log:
        process = subprocess.Popen(
            ['plasmoidviewer', '-a', str(staged), '-f', 'horizontal', '-l', 'bottomedge'],
            stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True,
            env={**os.environ, 'QT_QPA_PLATFORM': 'wayland', 'QT_FORCE_STDERR_LOGGING': '1'})
    processes.append({'id': package.name, 'pid': process.pid})
(root / 'processes.json').write_text(json.dumps(processes))
