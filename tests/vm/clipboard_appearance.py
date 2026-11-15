#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
import sys,subprocess,os,json,time,importlib.util
from pathlib import Path
repo=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(repo/'src/scripts'))
from release_capture_guest import session, windows
session()
from PyQt6.QtWidgets import QApplication
spec=importlib.util.spec_from_file_location('clip',Path.home()/'.local/share/mac-tahoe-liquid-kde/clipboard.py')
clip=importlib.util.module_from_spec(spec);spec.loader.exec_module(clip)
app=QApplication([]);be=clip.DaemonBackend()
assert be.available()
if not be.entries(): be.add_text('Clipboard appearance qualification',False)
w=clip.Popup(be,auto_close=False);w.show()
children=[];records=[]
def pump(seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.processEvents();time.sleep(.02)
def run(*args):
    with open('/tmp/clipboard-transition-command.log','w') as log:
        p=subprocess.Popen(list(args),stdout=log,stderr=subprocess.STDOUT)
        start=time.monotonic()
        while p.poll() is None:
            pump(.05)
            if time.monotonic()-start>120:p.kill();raise AssertionError('command timed out '+str(args))
    assert p.returncode==0,(args,Path('/tmp/clipboard-transition-command.log').read_text()[-1500:])
def check(mode,label,timeout=45,check_gtk=True):
    start=time.monotonic();dark=mode=='dark'
    while time.monotonic()-start<timeout:
        pump(.1)
        palette=w.palette()
        gtk=[]
        for version in ('3','4'):
            try:gtk.append(json.loads(Path(f'/tmp/clipboard-gtk{version}.json').read_text()))
            except (OSError,ValueError):pass
        gtk_ready=len(gtk)==2 and all(
            entry.get('background') and entry.get('foreground') and
            (sum(entry['background'][:3])/3<.5)==dark and
            (sum(entry['foreground'][:3])/3>.5)==dark for entry in gtk)
        if ((palette.color(palette.ColorRole.Window).lightnessF()<.5)==dark and
            (w.rows[0].caption.palette().color(palette.ColorRole.WindowText).lightnessF()>.5)==dark and
            (gtk_ready or not check_gtk)):break
    else:raise AssertionError(('wrong rendered palette',mode,label,
                              palette.color(palette.ColorRole.Window).name(),gtk))
    assert all(p.poll() is None for p in children)
    records.append({'selection':label,'mode':mode,'popup_pid':os.getpid(),'gtk_pids':[p.pid for p in children],
                    'gtk_palettes':gtk if check_gtk else 'transition still in flight'})
try:
    for version in ('3','4'):
        children.append(subprocess.Popen(['python3',str(repo/'tests/vm/appearance_gtk_probe.py'),'--gtk',version,'--output',f'/tmp/clipboard-gtk{version}.json'],stdout=open(f'/tmp/clipboard-gtk{version}.log','w'),stderr=subprocess.STDOUT))
    pump(1)
    # Keep each GTK window visible: an occluded Wayland surface can defer its
    # frame-clock style validation, making a cached context a false failure.
    windows('for (const win of workspace.windowList()) {'
            'if (win.caption === "GTK 3 appearance") win.frameGeometry={x:20,y:40,width:380,height:180};'
            'if (win.caption === "GTK 4 appearance") win.frameGeometry={x:420,y:40,width:380,height:180};'
            'if (win.caption === "Clipboard") win.frameGeometry={x:20,y:300,width:800,height:240};'
            '}')
    pump(.5)
    switch=str(Path.home()/'.local/bin/mac-tahoe-theme-switch')
    for mode in ('dark','light'):
        run(switch,mode);check(mode,'standalone-'+mode)
    for mode in ('dark','light'):
        run('gsettings','set','org.gnome.desktop.interface','color-scheme','prefer-'+mode);check(mode,'gtk-preference-'+mode)
    requests=[]
    for mode in ('dark','light','dark','light'):
        requests.append(subprocess.Popen([switch,mode],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL));pump(.1)
    while any(p.poll() is None for p in requests):pump(.1)
    assert all(p.returncode==0 for p in requests)
    check('light','rapid-latest-wins')
    run('sudo','timedatectl','set-ntp','false');run('sudo','timedatectl','set-timezone','UTC')
    run('sudo','date','-s','2026-01-01 17:59:00')
    run(switch,'auto');check('light','auto-before-boundary')
    run('sudo','date','-s','2026-01-01 17:59:58')
    check('dark','auto-crossed-1800')
    run('plasma-apply-colorscheme','MacTahoeLiquidKdeLight');check('light','native-manual-after-completed-auto')
    run('sudo','date','-s','2026-01-01 17:59:00')
    run(switch,'auto');check('light','auto-before-overlap')
    run('sudo','date','-s','2026-01-01 17:59:58')
    check('dark','auto-transition-in-flight',check_gtk=False)
    run('plasma-apply-colorscheme','MacTahoeLiquidKdeLight');check('light','native-manual-supersedes-auto')
    pump(3);check('light','manual-remains-light')
    print(json.dumps(records),flush=True)
finally:
    for p in children:p.terminate();p.wait()
    w.close()
