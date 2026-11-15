#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
import sys,subprocess,os,json,time,importlib.util,hashlib
from pathlib import Path
repo=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(repo/'src/scripts'))
from release_capture_guest import session
session()
sys.path.insert(0,str(repo/'src/scripts'))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QMimeData
from PyQt6.QtGui import QImage,QColor
spec=importlib.util.spec_from_file_location('clip',Path.home()/'.local/share/mac-tahoe-liquid-kde/clipboard.py')
clip=importlib.util.module_from_spec(spec);spec.loader.exec_module(clip)
app=QApplication([]); app.setApplicationName('clipboard-qualification')
be=clip.DaemonBackend();assert be.available()
w=clip.Popup(be,auto_close=False);w.show();w.activateWindow()
def pump(seconds=.5):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.processEvents();time.sleep(.02)
def wait(pred):
    for _ in range(100):
        pump(.05)
        if pred():return
    raise AssertionError('timed out')
pump()
producer=subprocess.Popen(['python3',str(repo/'tests/vm/clipboard_producer.py'),'text']);pump(2)
wait(lambda:any(i.get('text')=='Clipboard qualification text' for i in be.entries()))
text=next(i for i in be.entries() if i.get('text')=='Clipboard qualification text')
be.set_pinned(text['id'],True)
img=QImage(200,120,QImage.Format.Format_RGB32);img.fill(QColor('#4488cc'))
producer.terminate();producer.wait();producer=subprocess.Popen(['python3',str(repo/'tests/vm/clipboard_producer.py'),'image']);pump(2)
wait(lambda:any(i['kind']=='image' for i in be.entries()))
image=next(i for i in be.entries() if i['kind']=='image')
be.copy(text['id']);pump(1);assert be.current_id()==text['id']
be.copy(image['id']);pump(1);assert be.current_id()==image['id']
producer.terminate();producer.wait();producer=subprocess.Popen(['python3',str(repo/'tests/vm/clipboard_producer.py'),'secret']);pump(3)
assert not any(i.get('text')=='DO-NOT-RECORD' for i in be.entries())
records=[]
for mode in ('light','dark','light'):
    r=subprocess.run(['plasma-apply-colorscheme','MacTahoeLiquidKde'+mode.title()],capture_output=True,text=True);assert r.returncode==0,r.stderr
    pump(2)
    dark=w.palette().color(w.palette().ColorRole.Window).lightnessF()<.5
    assert dark==(mode=='dark'),(mode,dark)
    assert w.rows, 'live clipboard rows missing'
    assert (w.rows[0].label.palette().color(w.palette().ColorRole.WindowText).lightnessF()>.5)==dark if w.rows[0].label else True
    assert (w.findChildren(clip.KeyCap)[0].palette().color(w.palette().ColorRole.WindowText).lightnessF()>.5)==dark
    w.grab().save(f'/home/tester/release-capture/clipboard-{mode}.png')
    records.append({'mode':mode,'window_color':w.palette().color(w.palette().ColorRole.Window).name(),'text_color':w.palette().color(w.palette().ColorRole.WindowText).name()})
be.clear();pump();assert any(i['id']==text['id'] for i in be.entries())
print(json.dumps({'clipboard_capture':True,'copy_back_text_image':True,'secret_exclusion':True,'palette_transitions':records,'daemon_sha256':hashlib.sha256((Path.home()/'.local/bin/mac-tahoe-clipd').read_bytes()).hexdigest()}),flush=True)
w.close()

producer.terminate();producer.wait()
