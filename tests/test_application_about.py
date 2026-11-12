"""Render and interact with the shared application About QML."""
import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize('mode', ('light', 'dark'))
def test_generic_application_about_dialog(repo, tmp_path, mode):
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
               QT_QPA_PLATFORMTHEME='generic', XDG_CONFIG_HOME=str(tmp_path / 'config'),
               XDG_CACHE_HOME=str(tmp_path / 'cache'), XDG_DATA_HOME=str(tmp_path / 'data'))
    result = subprocess.run([sys.executable, str(repo / 'tests/application_about_probe.py'), '--mode', mode],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
