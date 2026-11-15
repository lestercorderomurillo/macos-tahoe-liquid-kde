#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Invoke the installed KDE shortcut, including its real singleton toggle."""
import sys
import time
from pathlib import Path
repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'src/scripts'))
from release_capture_guest import session
session()
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
from steps import clipboard as cb
app = QCoreApplication([])
assert cb._shortcut_keys(cb.SERVICE_ID, '_launch') == [cb.META_V]
bus = QDBusConnection.sessionBus()
service = QDBusInterface('org.kde.kglobalaccel', '/kglobalaccel', 'org.kde.KGlobalAccel', bus)
reply = service.call('getComponent', cb.SERVICE_ID)
assert reply.type() != QDBusMessage.MessageType.ErrorMessage, reply.errorMessage()
component = QDBusInterface('org.kde.kglobalaccel', str(reply.arguments()[0]),
                          'org.kde.kglobalaccel.Component', bus)
def running():
    found = []
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            if str(cb.POPUP_DEST).encode() in (process / 'cmdline').read_bytes().split(b'\0'):
                found.append(int(process.name))
        except OSError:
            pass
    return found
assert not running(), 'A prior popup must not interfere with the shortcut test'
for expected in (True, False):
    reply = component.call('invokeShortcut', '_launch')
    assert reply.type() != QDBusMessage.MessageType.ErrorMessage, reply.errorMessage()
    deadline = time.monotonic() + 10
    while bool(running()) != expected and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.05)
    assert bool(running()) == expected, ('shortcut toggle failed', expected)
    if expected:
        time.sleep(1)
        assert running(), 'Popup closed before the second shortcut'
print('REGISTERED_META_V_LAUNCH_AND_TOGGLE_OK')
