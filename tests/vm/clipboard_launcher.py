#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture and exercise the installed Clipboard launcher view in a disposable VM.

Usage: clipboard_launcher.py light|dark /tmp/output-prefix
"""
import sys,time,json,subprocess
from pathlib import Path
repo=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(repo/'src/scripts'))
output=Path(sys.argv[2]) if len(sys.argv)>2 else Path('/tmp/clipboard')
from release_capture_guest import session,run,windows
session()
if len(sys.argv)>1:
 run(str(Path.home()/'.local/bin/mac-tahoe-theme-switch'),sys.argv[1],timeout=180)
run('sudo','python3',str(repo/'tests/vm/clipboard_input.py'),'1')
run('sudo','python3',str(repo/'tests/vm/clipboard_input.py'),'1')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtDBus import QDBusInterface,QDBusConnection
app=QApplication([])
iface=QDBusInterface('org.mactahoe.Clipboard','/Clipboard','org.mactahoe.Clipboard',QDBusConnection.sessionBus())
assert iface.isValid()
iface.call('clearHistory')
iface.call('addText','Tahoe and Golden Gate share your clipboard history.',False)
iface.call('addText','Find something you copied, then copy it again.',False)
run('qdbus6','org.kde.plasmashell','/PlasmaShell','org.kde.PlasmaShell.activateLauncherMenu')
deadline=time.monotonic()+10
while not [w for w in windows() if w['appletPopup'] and not w['hidden'] and 'plasmashell' in w['resourceClass']]:
 if time.monotonic()>deadline: raise AssertionError('Launcher did not open')
 time.sleep(.2)
time.sleep(.3)
run('sudo','python3',str(repo/'tests/vm/clipboard_input.py'),'29','5')
time.sleep(1)
frames=[w for w in windows() if w['appletPopup'] and not w['hidden'] and 'plasmashell' in w['resourceClass']]
print(json.dumps(frames))
assert len(frames)==1,frames
frame=frames[0];assert frame['active'],frame
run('spectacle','-b','-n','-f','-o',str(output)+'-desktop.png')
from PIL import Image
im=Image.open(str(output)+'-desktop.png')
g=frame['geometry']; scale=im.width/app.primaryScreen().geometry().width()
box=tuple(round(v*scale) for v in (g['x']-12,g['y']-12,g['x']+g['width']+12,g['y']+g['height']+12))
im.crop(box).save(str(output)+'-preview.png')
import hashlib
package=Path.home()/'.local/share/plasma/plasmoids/org.kde.mac-tahoe-liquid-kde.launcher'
frame['installed_source_sha256']={str(p.relative_to(package)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((package/'contents/ui').rglob('*')) if p.is_file()}
frame['mode']=run('kreadconfig6','--file','kdeglobals','--group','General','--key','ColorScheme')
frame['edition']=json.loads((repo/'src/scripts/defaults.json').read_text())
# Exercise the actual selected row through Wayland input, not a direct backend call.
expected=json.loads(iface.call('list').arguments()[0])[0]['id']
run('sudo','python3',str(repo/'tests/vm/clipboard_input.py'),'28')
time.sleep(.5)
assert iface.call('currentId').arguments()[0]==expected
assert not [w for w in windows() if w['appletPopup'] and not w['hidden'] and 'plasmashell' in w['resourceClass']]
run('qdbus6','org.kde.plasmashell','/PlasmaShell','org.kde.PlasmaShell.activateLauncherMenu')
time.sleep(.5)
run('sudo','python3',str(repo/'tests/vm/clipboard_input.py'),'29','2')
time.sleep(.5)
apps=[w for w in windows() if w['appletPopup'] and not w['hidden'] and 'plasmashell' in w['resourceClass']]
assert any(w['geometry']['height']>g['height'] for w in apps),apps
frame['checks']=['Ctrl+4 opens Clipboard','Enter copies selected history and closes launcher','Ctrl+1 restores applications']
Path(str(output)+'-frame.json').write_text(json.dumps(frame,indent=2))
