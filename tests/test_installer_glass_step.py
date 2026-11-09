"""Focused checks for the glass selection step, without installing anything."""
import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize('edition', ['MacTahoe', 'MacGoldenGate'])
@pytest.mark.parametrize('mode', ['light', 'dark', 'auto'])
def test_glass_cards_select_complete_presets(repo, tmp_path, edition, mode):
    script = r'''
import hashlib, json, sys
from pathlib import Path
sys.path[:0] = ['src/scripts', 'src/installer']
from PyQt6.QtWidgets import QApplication, QLabel
from PyQt6.QtGui import QColor, QPalette, QImage
from installer_ui import _make_installer_bridge
import installer_choices, cli
from steps import acrylic_glass
from wizard_window import InstallerWindow, ChoiceCard, ASSETS, ASSET_FILES, picture
installer_choices.edition_name = lambda: sys.argv[1]
cli._theme_is_already_installed = lambda: False
app = QApplication([])
palette = app.palette()
for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base, QPalette.ColorRole.Button):
    palette.setColor(role, QColor('#111111' if sys.argv[2] == 'dark' else '#eeeeee'))
for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
    palette.setColor(role, QColor('#eeeeee' if sys.argv[2] == 'dark' else '#111111'))
app.setPalette(palette)
bridge = _make_installer_bridge()
bridge._language = 'en'
bridge.__class__.editionName = property(lambda _: sys.argv[1])
window = InstallerWindow(bridge)
window.choices['appearance'] = sys.argv[2]
window.page = 'glass_style'; window.render(); window.show(); app.processEvents()
cards = window.content.findChildren(ChoiceCard)
assert len(cards) == 3
assert sum(c.isChecked() for c in cards) == 1
assert window.choices['glass_style'] == ('official' if sys.argv[1] == 'MacGoldenGate' else 'classic')
text = ' '.join(l.text() for l in window.content.findChildren(QLabel))
assert 'Dock' not in text and 'blur strength' not in text and 'Three-color' not in text
acrylic_glass.selected = lambda: window.choices
for key, material, blur, variant in [('classic', '1', '5.0', '0'), ('tinted', '1', '12.0', '1'), ('official', '2', '4.0', '1')]:
    card = window.content.findChild(ChoiceCard, 'choice-glass_style-' + key)
    assert card.photo is not None and not card.photo.pixmap.isNull()
    preset = {'classic': 'tahoe-clear', 'tinted': 'tahoe-frosted', 'official': 'golden-gate-official'}[key]
    actual = card.photo.pixmap.toImage()
    light = picture(f'glass-preset-{preset}-light.png', 232, 220, cover=True,
                    crop=(820, 300, 1280, 1214)).toImage()
    dark = picture(f'glass-preset-{preset}-dark.png', 232, 220, cover=True,
                   crop=(820, 300, 1280, 1214)).toImage()
    if sys.argv[2] == 'auto':
        # Away from the separator: light on the left, dark on the right.
        for x, expected in [(60, light), (400, dark)]:
            for y in (80, 220, 360):
                assert actual.pixelColor(x, y) == expected.pixelColor(x, y)
    else:
        assert actual == (dark if sys.argv[2] == 'dark' else light)
    card.click(); app.processEvents()
    assert window.choices['glass_style'] == key
    assert sum(c.isChecked() for c in cards) == 1
    values = acrylic_glass._edition_preset()
    assert values['MaterialPreset'] == material and values['BlurStrength'] == blur
    writes = []
    acrylic_glass.kw_write = lambda *args: writes.append(args) or True
    assert acrylic_glass._install_backing_tint() and writes[-1][-1] == variant
    window.advance(); window.previous(); app.processEvents()
    assert window.page == 'glass_style' and window.choices['glass_style'] == key
    cards = window.content.findChildren(ChoiceCard)
for name, record in ASSET_FILES.items():
    if not name.startswith('glass-preset-'):
        continue
    path = ASSETS / record['file']
    image = QImage(str(path))
    assert (image.width(), image.height()) == (3840, 2160)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']
'''
    result = subprocess.run([sys.executable, '-c', script, edition, mode], cwd=repo,
                            env=os.environ | {'QT_QPA_PLATFORM': 'offscreen',
                                              'XDG_CONFIG_HOME': str(tmp_path),
                                              'MAC_TAHOE_NO_UPDATE_CHECK': 'true'},
                            text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
