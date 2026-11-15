"""Run a real clipboard service and launcher on the caller's isolated bus/display."""
import subprocess
import sys
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtDBus import QDBusConnection, QDBusInterface
app = QApplication([])
daemon = subprocess.Popen([sys.argv[1]])
try:
    for _ in range(50):
        iface = QDBusInterface('org.mactahoe.Clipboard', '/Clipboard', 'org.mactahoe.Clipboard', QDBusConnection.sessionBus())
        if iface.isValid(): break
        time.sleep(.1)
    assert iface.isValid()
    for text in ('Clipboard reference comparison', 'Searchable second entry', '<b>Literal clipboard text</b>'):
        iface.call('addText', text, False)
    sys.exit(subprocess.call(sys.argv[2:]))
finally:
    daemon.terminate()
    daemon.wait(timeout=5)
