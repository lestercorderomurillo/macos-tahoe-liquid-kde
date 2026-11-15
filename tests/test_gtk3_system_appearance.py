"""Exercise the theme picker with GTK's retained startup dark preference."""
import os
from pathlib import Path
import subprocess
import sys


def test_live_gtk3_theme_selection_overrides_retained_startup_dark_flag(repo, tmp_path):
    env = os.environ | {'HOME': str(tmp_path), 'XDG_CONFIG_HOME': str(tmp_path / 'config'),
                        'XDG_DATA_HOME': str(tmp_path / 'data'),
                        'XDG_RUNTIME_DIR': str(tmp_path / 'runtime'), 'GDK_BACKEND': 'x11'}
    env.pop('GTK_THEME', None)
    Path(env['XDG_RUNTIME_DIR']).mkdir(mode=0o700)
    result = subprocess.run(['xvfb-run', '-a', 'dbus-run-session', '--', sys.executable,
                             str(repo / 'tests/native/gtk3_system_appearance.py'),
                             str(repo / 'src/offline/gtk')],
                            env=env, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
