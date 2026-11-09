"""Compile and exercise the actual system-menu style, independently of Plasma."""
import os
import shlex
import subprocess


def test_system_menu_metrics_rendering_and_style_isolation(repo, tmp_path):
    flags = shlex.split(subprocess.check_output(
        ['pkg-config', '--cflags', '--libs', 'Qt6Widgets'], text=True))
    binary = tmp_path / 'system-menu-style'
    source = repo / 'src/offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu'
    subprocess.run(['c++', '-std=c++17', '-fPIC', str(repo / 'tests/system_menu_style_probe.cpp'),
                    '-I', str(source), *flags, '-o', str(binary)], check=True)
    for scale in ('1', '1.5', '2'):
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_SCALE_FACTOR=scale,
                   HOME=str(tmp_path), XDG_CONFIG_HOME=str(tmp_path), QT_STYLE_OVERRIDE='Fusion')
        result = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stdout + result.stderr
