"""Native component behavior, isolated from the user's desktop and system bus."""
import os
import subprocess
import sys


def test_desktop_controls_native_state_and_actions(repo, tmp_path, launcher_popup_module):
    runtime = tmp_path / 'runtime'; runtime.mkdir(mode=0o700)
    env = dict(os.environ, QML_IMPORT_PATH=str(launcher_popup_module), QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
               XDG_RUNTIME_DIR=str(runtime), XDG_CONFIG_HOME=str(tmp_path / 'config'),
               XDG_DATA_HOME=str(tmp_path / 'data'), XDG_CACHE_HOME=str(tmp_path / 'cache'),
               DBUS_SYSTEM_BUS_ADDRESS='unix:path=' + str(tmp_path / 'no-system-bus'),
               PULSE_SERVER='unix:' + str(tmp_path / 'no-audio-server'))
    result = subprocess.run(['dbus-run-session', '--', sys.executable,
                             str(repo / 'tests/desktop_controls_probe.py'), str(repo)],
                            env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'DESKTOP_CONTROLS_OK' in result.stdout
