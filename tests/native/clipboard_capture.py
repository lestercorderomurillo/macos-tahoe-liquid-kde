"""Real X11 clipboard traffic between independent Qt producer and history service."""
import json
import subprocess
import sys
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtDBus import QDBusConnection, QDBusInterface

app = QApplication([])
daemon = subprocess.Popen([sys.argv[1]])
producer = None

def pump(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(.02)

def entries():
    return json.loads(iface.call('list').arguments()[0])

def wait(predicate):
    for _ in range(100):
        pump(.05)
        if predicate():
            return
    raise AssertionError('clipboard capture timed out')

try:
    for _ in range(100):
        iface = QDBusInterface('org.mactahoe.Clipboard', '/Clipboard',
                              'org.mactahoe.Clipboard', QDBusConnection.sessionBus())
        if iface.isValid():
            break
        pump(.05)
    assert iface.isValid()
    for mode in ('text', 'image', 'secret'):
        if producer:
            producer.terminate()
            producer.wait(timeout=5)
        producer = subprocess.Popen([sys.executable, sys.argv[2], mode])
        pump(1.5)
        if mode == 'secret':
            pump(.5)
            assert not any(item.get('text') == 'DO-NOT-RECORD' for item in entries())
        else:
            wait(lambda: any(item['kind'] == mode for item in entries()))
    for item in entries():
        iface.call('copy', item['id'])
        if item['kind'] == 'text':
            wait(lambda: app.clipboard().text() == item['text'])
        else:
            wait(lambda: not app.clipboard().image().isNull())
    print('X11_CLIPBOARD_OK')
finally:
    for process in (producer, daemon):
        if process:
            process.terminate()
            process.wait(timeout=5)
