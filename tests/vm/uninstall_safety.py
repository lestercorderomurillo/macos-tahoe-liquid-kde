# SPDX-License-Identifier: GPL-3.0-or-later
import sys,json,os,subprocess,hashlib
from pathlib import Path
repo=Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo/'src/scripts'))
from release_capture_guest import session,run
session()
from steps import gtk,clipboard as cb
import argparse
parser=argparse.ArgumentParser(description='Focused GTK and clipboard lifecycle in a disposable Plasma VM')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
out=args.output;out.mkdir(parents=True,exist_ok=True)
result={'environment':run('plasmashell','--version'),'source_files':{p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in ('src/scripts/steps/gtk.py','src/scripts/steps/clipboard.py','component-hashes.json')},'checks':[]}
for phase in ('install','reinstall'):
 command=['sudo','-n','env','MAC_TAHOE_NO_UPDATE_CHECK=true','MTTKDE_NO_CONFIRM=1','MTTKDE_LANGUAGE=en','MTTKDE_WIZARD_OPTIONS={"appearance":"light","reset_layout":false}', 'python3',str(repo/'src/scripts/installer_backend.py'),'install','--only','--gtk','--clipboard','--no-apply-theme','--light']
 with (out/(phase+'.log')).open('w') as log:
  p=subprocess.run(command,cwd=repo,stdout=log,stderr=subprocess.STDOUT,timeout=600)
 assert p.returncode==0,(phase,(out/(phase+'.log')).read_text()[-8000:])
 result['checks'].append({'phase':phase,'command':command,'returncode':p.returncode})
# Actual installed sources, with both ordinary generated copies and user data.
from theme_switch import _apply_local_extras
_apply_local_extras('light')
config=gtk.GTK4_DEST
custom={config/'gtk.css':'button { padding: 17px; }\n',config/'assets/audit-user.svg':'user artwork',config/'windows-assets/audit-user.svg':'user button',config/'gtk-dark.css':'/* custom dark CSS */'}
for path,data in custom.items():
 path.parent.mkdir(exist_ok=True);path.unlink(missing_ok=True);path.write_text(data)
owned_candidates=[p for p in (config/'assets').rglob('*') if p.is_file() and p not in custom]
assert owned_candidates,'no installed GTK assets'
gtk.uninstall()
for path,data in custom.items():assert path.read_text()==data,str(path)
assert all(not p.exists() for p in owned_candidates)
result['checks'].append({'phase':'gtk-uninstall','preserved':[str(p) for p in custom],'removed_owned_assets':len(owned_candidates)})
# Invalid JSON shape must not abort teardown of the real running daemon.
cb._shortcut_state().write_text('null')
cb.uninstall()
assert not cb.DAEMON_DEST.exists()
result['checks'].append({'phase':'clipboard-invalid-state','result':'passed'})
# Kernel-enforced permissions reproduce actual deletion failure, no stubs.
cb.HISTORY_DIR.mkdir(parents=True,exist_ok=True)
secret=cb.HISTORY_DIR/'index.json';secret.write_text('["private history"]')
cb.HISTORY_DIR.chmod(0o500)
try:
 try:cb.uninstall()
 except PermissionError:pass
 else:raise AssertionError('History removal falsely succeeded')
 assert secret.exists()
finally:cb.HISTORY_DIR.chmod(0o700)
cb.uninstall();assert not cb.HISTORY_DIR.exists()
result['checks'].append({'phase':'clipboard-permission-failure-and-retry','result':'passed'})
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
