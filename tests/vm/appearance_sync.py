#!/usr/bin/env python3
"""Persistent-app appearance qualification inside the disposable Plasma VM."""
import argparse,json,subprocess,time,os
parser=argparse.ArgumentParser()
parser.add_argument("--edition", choices=("tahoe","golden-gate"), default="tahoe")
parser.add_argument("--output", default="appearance-transitions.json")
parser.add_argument("--browser", action="store_true")
args=parser.parse_args()
from pathlib import Path
assert Path('/sys/class/dmi/id/product_name').read_text().strip()=='MTTKDE release capture'
state=Path.home()/'.local/state/mac-tahoe-liquid-kde/appearance.json'
probe=Path.home()/'appearance-probe/probe.json'
results=[]
# Native tools launched over SSH need the same X11 credentials as Plasma.
pid=subprocess.check_output(['pgrep','-u',str(os.getuid()),'-x','plasmashell']).decode().strip()
session=dict(x.decode().split('=',1) for x in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0') if b'=' in x)
os.environ.update({k:v for k,v in session.items() if k in ('DISPLAY','XAUTHORITY','WAYLAND_DISPLAY','XDG_SESSION_TYPE')})
browser = None
if args.browser:
 import desktop_apps
 desktop_apps.check_browser()
 browser = desktop_apps.Marionette()
 browser.call('WebDriver:NewSession', capabilities={})

try:
 initial_shell=subprocess.check_output(['pgrep','-u',str(os.getuid()),'-x','plasmashell']).strip()
 initial_kwin=subprocess.check_output(['pgrep','-u',str(os.getuid()),'-x','kwin_wayland']).strip()
 def qml_snapshots():
  values=[]
  for name in ('org.kde.mac-tahoe-liquid-kde.launcher','org.kde.mac-tahoe-liquid-kde.trashcan','luisbocanegra.panel.colorizer'):
   path=Path.home()/'appearance-plasmoids'/(name+'.log')
   with path.open('rb') as f:
    f.seek(max(0,path.stat().st_size-8192))
    lines=f.read().decode(errors='replace').splitlines()
   data=[json.loads(x.split('APPEARANCE_SNAPSHOT ',1)[1]) for x in lines if 'APPEARANCE_SNAPSHOT ' in x]
   values.append(data[-1])
  return values

 def run(*args):subprocess.run(args,check=True,stdout=subprocess.DEVNULL)
 def wait(mode,label):
  start=time.monotonic()
  while time.monotonic()-start<35:
   try:
    s=json.loads(state.read_text()); p=json.loads(probe.read_text())
    dark=mode=='dark'
    gtk=[json.loads(Path.home().joinpath('appearance-probe/gtk'+v+'.json').read_text()) for v in ('3','4')]
    qml=qml_snapshots()
    qml_ok=all((int(q['background'][1:3],16)<128)==dark and (int(q['text'][1:3],16)>128)==dark for q in qml)
    about=json.loads(Path.home().joinpath('appearance-probe/about.json').read_text())
    expected_alpha=(.01 if dark else .60) if args.edition=='golden-gate' else (.48 if dark else .55)
    about_ok=all(a['dark']==dark and abs(a['surface'][3]-expected_alpha)<.01 for a in about)
    gtk_ok=all(g['background'] is not None and ((sum(g['background'][:3])/3<.5)==dark) and g['foreground'] is not None and ((sum(g['foreground'][:3])/3>.5)==dark) for g in gtk)
    browser_dark = browser.script("return matchMedia('(prefers-color-scheme: dark)').matches;") if browser else dark
    menu_ok=all(abs(p[k]['alpha']/255-expected_alpha)<.02 and ((p[k]['text']>128)==dark) and p[k]['red']==(0 if dark and args.edition=='tahoe' else 255) for k in ('ordinary','system'))
    if browser_dark==dark and menu_ok and qml_ok and about_ok and gtk_ok and s.get('applied')==mode and all(v==mode for k,v in s['observed'].items() if k!='automatic' and v is not None) and ((p['background']<128)==dark):
     results.append({'case':label,'mode':mode,'seconds':round(time.monotonic()-start,2),'state':s,'pixels':p,'gtk':gtk,'qml':qml,'about':about,'browser_dark':browser_dark if browser else None})
     Path.home().joinpath(args.output).write_text(json.dumps(results,indent=2))
     assert subprocess.check_output(['pgrep','-u',str(os.getuid()),'-x','plasmashell']).strip()==initial_shell
     assert subprocess.check_output(['pgrep','-u',str(os.getuid()),'-x','kwin_wayland']).strip()==initial_kwin
     print(label,mode,'passed',flush=True);return
   except (OSError,ValueError):pass
   time.sleep(.25)
  raise AssertionError((label,s,p,gtk,qml,about,browser_dark))
 switch=str(Path.home()/'.local/bin/mac-tahoe-theme-switch')
 run(switch,'light');wait('light','manual-light')
 run('plasma-apply-colorscheme','MacTahoeLiquidKdeDark');wait('dark','native-kde-dark')
 run('plasma-apply-colorscheme','MacTahoeLiquidKdeLight');wait('light','native-kde-light')
 run('plasma-apply-lookandfeel','-a','org.kde.mac-tahoe-liquid-kde.dark');wait('dark','native-global-dark')
 run('plasma-apply-lookandfeel','-a','org.kde.mac-tahoe-liquid-kde.light');wait('light','native-global-light')
 run('gsettings','set','org.gnome.desktop.interface','color-scheme','prefer-dark');wait('dark','native-gtk-dark')
 run('gsettings','set','org.gnome.desktop.interface','color-scheme','prefer-light');wait('light','native-gtk-light')
 for i in range(15):
  run('plasma-apply-colorscheme','MacTahoeLiquidKde'+('Dark' if i%2==0 else 'Light'))
  time.sleep(.08)
 wait('dark','rapid-native-15')
 children=[]
 for mode in ('light','dark','light','dark','light'):
  children.append(subprocess.Popen([switch,mode],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL));time.sleep(.08)
 for c in children:assert c.wait(timeout=60)==0
 wait('light','rapid-cli-5')
 run('sudo','timedatectl','set-ntp','false')
 run('sudo','date','-s','2026-01-01 17:59:00')
 run(switch,'auto');wait('light','auto-before-dusk')
 run('sudo','date','-s','2026-01-01 17:59:58');wait('dark','auto-cross-dusk')
 run('sudo','date','-s','2026-01-02 05:59:58');wait('light','auto-cross-dawn')
 run('plasma-apply-colorscheme','MacTahoeLiquidKdeDark');wait('dark','manual-overrides-auto')
 run(switch,'scheduled');wait('dark','timer-preserves-manual')
 Path.home().joinpath(args.output).write_text(json.dumps(results,indent=2))
finally:
 if browser:
  try:
   browser.call('WebDriver:DeleteSession')
  finally:
   browser.close()
