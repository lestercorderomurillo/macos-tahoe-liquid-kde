import hashlib
import json, os, subprocess, sys, time
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtDBus import QDBusConnection, QDBusInterface
app = QApplication([])
def wait(predicate):
    for _ in range(100):
        app.processEvents()
        if predicate(): return
        time.sleep(.03)
    raise AssertionError('timeout')
def start():
    proc = subprocess.Popen([sys.argv[1]])
    def ready():
        global iface
        iface = QDBusInterface('org.mactahoe.Clipboard', '/Clipboard', 'org.mactahoe.Clipboard', QDBusConnection.sessionBus())
        return iface.isValid()
    wait(ready)
    return proc
def call(method,*args):
    reply=iface.call(method,*args)
    assert reply.type()!=reply.MessageType.ErrorMessage, reply.errorMessage()
    return reply.arguments()[0] if reply.arguments() else None
def items(): return json.loads(call('list'))
data=Path(os.environ['XDG_DATA_HOME'])/'mac-tahoe-liquid-kde/clipboard'
data.mkdir(parents=True)
victim=data.parent/'victim.png'
victim.write_text('keep')
legacy=data/'index.json'
legacy_id=hashlib.sha1(b'txtlegacy text').hexdigest()
legacy.write_text(json.dumps([{'id':'../../victim','kind':'image'},
                              {'id':legacy_id,'kind':'text','text':'legacy text'}]))
proc=start()
try:
    assert [row['text'] for row in items()]==['legacy text']
    call('clearHistory')
    call('addText','pinned item',True)
    item=items()[0]
    call('remove',item['id'])
    assert items()==[item]
    for i in range(45): call('addText',f'item {i}',False)
    assert len(items())==41
    call('clearHistory')
    assert [x['text'] for x in items()]==['pinned item']
    call('quit');proc.wait(timeout=5)
    index=data/'index.enc'
    assert index.stat().st_mode&0o777==0o600
    assert data.stat().st_mode&0o777==0o700
    assert not legacy.exists() and b'pinned item' not in index.read_bytes()
    proc=start()
    assert len(items())==1
    call('clearHistory'); assert victim.read_text()=='keep'
    call('setPinned',item['id'],False);call('remove',item['id']);assert items()==[]
    call('quit');proc.wait(timeout=5)
    proc=start(); assert items()==[]
    call('quit');proc.wait(timeout=5)
    damaged=bytearray(index.read_bytes()); damaged[-1] ^= 1
    index.write_bytes(damaged)
    assert subprocess.run([sys.argv[1]], timeout=5).returncode != 0
    assert index.read_bytes()==damaged
    print('NATIVE_STORE_OK')
finally:
    proc.terminate(); proc.wait(timeout=5)
