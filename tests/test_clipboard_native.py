"""Exercise the compiled clipboard store on a private session bus and data directory."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest


def test_native_clipboard_persistence_pins_and_invalid_paths(repo, tmp_path):
    pytest.importorskip('PyQt6.QtDBus')
    for command in ('cmake', 'dbus-run-session'):
        if not shutil.which(command):
            pytest.skip(f'{command} unavailable')
    build = tmp_path / 'build'
    env = os.environ | {'QT_QPA_PLATFORM': 'offscreen',
                        'XDG_DATA_HOME': str(tmp_path / 'data'),
                        'XDG_RUNTIME_DIR': str(tmp_path / 'runtime')}
    Path(env['XDG_RUNTIME_DIR']).mkdir(mode=0o700)
    for command in (["cmake", "-S", str(repo / 'src/offline/clipboard/clipd'), '-B', str(build)],
                    ['cmake', '--build', str(build), '-j2'],
                    ['dbus-run-session', '--', shutil.which('python3'),
                     str(repo / 'tests/native/clipboard_store.py'), str(build / 'mac-tahoe-clipd')]):
        result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr

    if not shutil.which('xvfb-run'):
        pytest.fail('xvfb-run is required for native clipboard capture qualification')
    env['QT_QPA_PLATFORM'] = 'xcb'
    env['XDG_DATA_HOME'] = str(tmp_path / 'x11-data')
    result = subprocess.run(['xvfb-run', '-a', 'dbus-run-session', '--', shutil.which('python3'),
                             str(repo / 'tests/native/clipboard_capture.py'),
                             str(build / 'mac-tahoe-clipd'),
                             str(repo / 'tests/vm/clipboard_producer.py')],
                            env=env, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
