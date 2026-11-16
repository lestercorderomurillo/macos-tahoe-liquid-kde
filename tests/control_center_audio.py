"""Exercise production volume controls against a private PipeWire audio server.

Run with python3 tests/control_center_audio.py <checkout>. Requires pipewire,
pipewire-pulse, wireplumber, pactl, dbus-run-session and the Control Center QML dependencies.
No physical audio devices or host desktop services are used.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def run(repo):
    with tempfile.TemporaryDirectory(prefix='control-center-audio-') as directory:
        root = Path(directory)
        env = dict(os.environ, XDG_RUNTIME_DIR=directory, PIPEWIRE_RUNTIME_DIR=directory,
                   XDG_CONFIG_HOME=str(root / 'config'), XDG_DATA_HOME=str(root / 'data'),
                   XDG_CACHE_HOME=str(root / 'cache'), XDG_STATE_HOME=str(root / 'state'),
                   PULSE_SERVER='unix:' + directory + '/pulse/native',
                   DBUS_SYSTEM_BUS_ADDRESS='unix:path=' + directory + '/no-system-bus',
                   QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
        result = subprocess.run(['dbus-run-session', '--', sys.executable, __file__,
                                 str(repo), '--private-server'], env=env, timeout=45)
        return result.returncode


def private_server(repo):
    root = Path(os.environ['XDG_RUNTIME_DIR'])
    assert root.name.startswith('control-center-audio-')
    assert os.environ['PULSE_SERVER'] == 'unix:' + str(root / 'pulse/native')
    processes, logs = [], []
    try:
        for command in ('pipewire', 'pipewire-pulse', 'wireplumber'):
            log = (root / (command + '.log')).open('w')
            logs.append(log)
            processes.append(subprocess.Popen([command, '--profile=policy'] if command == 'wireplumber' else [command], stdout=log, stderr=log))
        for _ in range(100):
            if subprocess.run(['pactl', 'info'], capture_output=True).returncode == 0:
                break
            time.sleep(0.05)
        else:
            raise AssertionError('Private audio server did not start')
        time.sleep(0.5)
        probe(repo, processes[1])
    finally:
        for process in reversed(processes):
            process.terminate()
            process.wait(timeout=10)
        for log in logs:
            log.close()


def probe(repo, pulse_server):
    from PyQt6.QtCore import QUrl, QPointF, Qt, qInstallMessageHandler
    from PyQt6.QtQml import QQmlComponent, QQmlEngine
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtQuick import QQuickWindow
    from PyQt6.QtTest import QTest

    def pulse(*args):
        return subprocess.check_output(['pactl', *args], text=True).strip()

    app = QApplication([])
    engine = QQmlEngine()
    errors = []
    def message(kind, context, text):
        if any(token in text for token in ('ReferenceError:', 'TypeError:', 'Unable to assign', 'Binding loop')):
            errors.append(text)
    qInstallMessageHandler(message)
    engine.rootContext().setContextProperty('i18n', engine.evaluate('(function(text) { return text; })'))
    path = repo / 'src/offline/plasmoids/org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui/AudioView.qml'
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(path)))
    assert component.isReady(), [e.toString() for e in component.errors()]
    audio = component.create()
    assert audio is not None
    window = QQuickWindow()
    window.resize(400, 100)
    audio.setParentItem(window.contentItem())
    audio.setWidth(380)
    window.show()
    # QML-generated subclasses differ, so use QObject lookup for named controls.
    from PyQt6.QtCore import QObject
    slider = audio.findChild(QObject, 'volumeSlider')
    mute = audio.findChild(QObject, 'muteButton')

    def wait(predicate):
        for _ in range(100):
            if predicate():
                return
            QTest.qWait(20)
        assert predicate(), errors

    def click(item, fraction=0.5):
        point = item.mapToScene(QPointF(round(item.width() * fraction), round(item.height() / 2)))
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point.toPoint())
        QTest.qWait(30)

    def sinks():
        return {sink['name']: sink for sink in json.loads(pulse('--format=json', 'list', 'sinks'))}

    def volume(name):
        return next(iter(sinks()[name]['volume'].values()))['value']

    wait(lambda: not slider.property('enabled'))
    first = pulse('load-module', 'module-null-sink', 'sink_name=control_first')
    pulse('set-default-sink', 'control_first')
    wait(lambda: slider.property('enabled'))
    pulse('set-sink-volume', 'control_first', '60%')
    wait(lambda: abs(slider.property('value') - 39322) <= 1)
    click(slider, 0.3)
    wait(lambda: abs(volume('control_first') - 19661) < 2000)
    click(mute)
    wait(lambda: sinks()['control_first']['mute'])
    click(slider, 0.7)
    wait(lambda: not sinks()['control_first']['mute'] and volume('control_first') > 40000)
    click(slider, 0)
    wait(lambda: sinks()['control_first']['mute'] and volume('control_first') == 0)

    second = pulse('load-module', 'module-null-sink', 'sink_name=control_second')
    pulse('set-sink-volume', 'control_second', '45%')
    pulse('set-default-sink', 'control_second')
    wait(lambda: abs(slider.property('value') - 29491) <= 1)
    click(slider, 0.8)
    wait(lambda: volume('control_second') > 50000)
    assert volume('control_first') == 0
    pulse('unload-module', second)
    pulse('set-default-sink', 'control_first')
    wait(lambda: slider.property('value') == 0)
    pulse('unload-module', first)
    pulse_server.terminate()
    pulse_server.wait(timeout=10)
    wait(lambda: not slider.property('enabled') and not mute.property('enabled'))
    assert not errors, errors
    window.close()
    print('CONTROL_CENTER_AUDIO_OK: discovery, pointer volume writes, mute/unmute, external changes, output switching, disconnect')


if __name__ == '__main__':
    checkout = Path(sys.argv[1]).resolve()
    if '--private-server' in sys.argv:
        private_server(checkout)
    else:
        sys.exit(run(checkout))
