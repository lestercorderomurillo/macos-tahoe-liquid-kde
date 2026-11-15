# SPDX-License-Identifier: GPL-3.0-or-later
import sys,json
from pathlib import Path
repo=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(repo/'src/scripts'))
from release_capture_guest import session
session()
from steps import clipboard as cb
cb.uninstall()
assert not cb.HISTORY_DIR.exists() and not cb.DAEMON_DEST.exists()
assert cb._bind('plasmashell','show-on-mouse-pos','Show Clipboard Items at Mouse Position',cb.META_V)
cb.install()
assert cb._shortcut_keys('plasmashell','show-on-mouse-pos') in ([],[0])
assert json.loads(cb._shortcut_state().read_text())['keys']==[cb.META_V]
cb.uninstall()
assert cb._shortcut_keys('plasmashell','show-on-mouse-pos')==[cb.META_V]
cb.install()
custom=0x10000000|0x58
assert cb._bind('plasmashell','show-on-mouse-pos','Show Clipboard Items at Mouse Position',custom)
cb.uninstall()
assert cb._shortcut_keys('plasmashell','show-on-mouse-pos')==[custom]
cb.uninstall()
assert cb._shortcut_keys('plasmashell','show-on-mouse-pos')==[custom]
assert not cb.HISTORY_DIR.exists() and not cb.DAEMON_DEST.exists()
print('LIFECYCLE_RESTORE_CUSTOM_AND_NOOP_OK',flush=True)
