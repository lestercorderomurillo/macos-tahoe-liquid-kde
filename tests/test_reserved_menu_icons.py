"""Generated app tiles must not replace the system menu's interface artwork."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/scripts'))
from icon_sources import unpack
from icon_toolset import BASE, ROOT, installer_themes


@pytest.fixture(scope="session")
def kde_icon_probe(tmp_path_factory):
    if not shutil.which("cmake"):
        pytest.skip("CMake required for native KDE icon lookup")
    build = tmp_path_factory.mktemp("kde-menu-icon-build")
    source = Path(__file__).parent / "native_menu_icons"
    configured = subprocess.run(["cmake", "-S", str(source), "-B", str(build)],
                                capture_output=True, text=True, timeout=60)
    if configured.returncode and "Could not find a package configuration file provided by" in configured.stderr:
        pytest.skip("Qt6/KF6 icon development packages required: " + configured.stderr)
    assert configured.returncode == 0, configured.stdout + configured.stderr
    compiled = subprocess.run(["cmake", "--build", str(build)],
                              capture_output=True, text=True, timeout=120)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    return build / "menu_icon_lookup"


@pytest.mark.parametrize('style', ['regular', 'glass'])
def test_menu_icons_keep_base_artwork_while_app_icons_change(tmp_path, style, kde_icon_probe):
    pytest.importorskip('PyQt6.QtGui')
    extracted = tmp_path / 'base'
    unpack(ROOT / 'src/offline/icons/MacTahoeLiquidKde-Icons.tar.zst', extracted)
    selected = tmp_path / 'selected' / BASE / 'apps/scalable'
    selected.mkdir(parents=True)
    # Include the colliding aliases as well as the launcher's application names.
    for name in ('preferences', 'preferences-system', 'systemsettings', 'software',
                 'software-store', 'org.kde.discover'):
        original = extracted / BASE / 'apps/scalable' / f'{name}.svg'
        (selected / f'{name}.svg').write_bytes(original.read_bytes())
    generated = tmp_path / 'generated'
    names = installer_themes(selected.parents[2], generated, style, '#28cd41')
    for name in names:
        shutil.move(str(generated / name), extracted / name)
    env = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG')}
    env.update(HOME=str(tmp_path), XDG_CONFIG_HOME=str(tmp_path / 'config'),
               QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='generic')
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'icons').symlink_to(extracted, target_is_directory=True)
    env['XDG_DATA_HOME'] = str(data)
    probes = ([sys.executable, __file__, '--probe', str(extracted), *names],
              [str(kde_icon_probe), BASE, BASE + '-dark', *names])
    for command in probes:
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        _check_menu_and_application_icons(json.loads(result.stdout), extracted, names, style)


def _check_menu_and_application_icons(rendered, extracted, names, style):
    for name in names:
        base = BASE + ('-dark' if name.endswith('-Dark') else '')
        for icon in ('computer', 'preferences-system', 'software-store-symbolic'):
            assert rendered[name][icon] == rendered[base][icon], (name, icon)
        # Application launchers still get their newly selected appearance.
        for icon in ('systemsettings', 'org.kde.discover'):
            assert (extracted / name / 'apps/256' / f'{icon}.png').is_file()
            if style == 'glass' or name.endswith('-Dark'):
                assert rendered[name][icon] != rendered[base][icon], (name, icon)


def _probe():
    from PyQt6.QtCore import QSize
    from PyQt6.QtGui import QIcon, QImage
    from PyQt6.QtWidgets import QApplication
    app = QApplication([])
    QIcon.setThemeSearchPaths([sys.argv[2]])
    QIcon.setFallbackThemeName('')
    output = {}
    for theme in (BASE, BASE + '-dark', *sys.argv[3:]):
        QIcon.setThemeName(theme)
        output[theme] = {}
        for name in ('computer', 'preferences-system', 'software-store-symbolic',
                     'systemsettings', 'org.kde.discover'):
            hashes = []
            for size in (16, 22, 32):
                for scale in (1.0, 2.0):
                    image = QIcon.fromTheme(name).pixmap(QSize(size, size), scale).toImage()
                    assert not image.isNull(), (theme, name)
                    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
                    hashes.append(hashlib.sha256(image.constBits().asstring(image.sizeInBytes())).hexdigest())
            output[theme][name] = hashes
    print(json.dumps(output))


if __name__ == '__main__':
    _probe()
