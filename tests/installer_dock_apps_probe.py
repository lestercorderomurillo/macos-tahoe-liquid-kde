"""Exercise the real modal Dock apps editor without starting an installation."""

import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src/scripts'), str(ROOT / 'src/installer')]

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QComboBox, QDialog, QDialogButtonBox, QPushButton

import cli
import dock_apps
from installer_ui import _make_installer_bridge
from wizard_window import CheckOption, InstallerWindow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('light', 'dark'))
    parser.add_argument('--defaults', type=Path)
    parser.add_argument('--capture', type=Path)
    args = parser.parse_args()
    mode = args.mode
    if args.defaults:
        import launcher_defaults
        launcher_defaults.DEFAULTS_FILE = args.defaults
    app = QApplication([])
    palette = app.palette()
    for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base, QPalette.ColorRole.Button):
        palette.setColor(role, QColor('#f6f6f6' if mode == 'light' else '#292929'))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(role, QColor('#292929' if mode == 'light' else '#eeeeee'))
    app.setPalette(palette)
    cli._theme_is_already_installed = lambda: False
    bridge = _make_installer_bridge()
    bridge.start = lambda *_: (_ for _ in ()).throw(AssertionError('Editor must not install'))
    window = InstallerWindow(bridge)
    window.show()
    window.page = 'layout'
    window.render()
    QTest.qWait(30)
    original_palette = app.palette()
    results = []
    # Model installed, missing and source-unavailable applications independently
    # of the machine running the probe. The real widgets and modal loop run.
    for installed in ({}, {'mail': 'Existing Mail'}, {key: key for key in dock_apps.OPTIONAL}):
        dock_apps.installed_apps = lambda: installed
        dock_apps.recommendation = lambda key, source: (
            None if source == 'native' and key == 'photos' else (key.title(), key + '-package'))
        for action in ('cancel', 'accept', 'escape', 'accept'):
            before = copy.deepcopy(window.choices)
            visited = []

            def interact():
                dialog = app.activeModalWidget()
                assert isinstance(dialog, QDialog) and dialog.isVisible()
                # Flush expose/paint events: constructing a hidden dialog missed
                # the fatal Python exception in CheckOption.paintEvent.
                QTest.qWait(30)
                assert not dialog.grab().isNull()
                appearance = dialog.findChild(QComboBox, 'dock-appearance')
                source = dialog.findChild(QComboBox, 'dock-apps-source')
                remote = dialog.findChild(CheckOption, 'dock-add-flathub')
                source.setCurrentIndex(source.findData('native'))
                QTest.qWait(10)
                assert not remote.isVisible()
                for key in dock_apps.OPTIONAL:
                    option = dialog.findChild(CheckOption, 'dock-app-' + key)
                    assert option.isEnabled() == (key not in installed and key != 'photos')
                    if key in installed:
                        assert installed[key] in option.text()
                source.setFocus()
                QTest.keyClick(source, Qt.Key.Key_End)
                QTest.qWait(10)
                assert source.currentData() == 'flatpak' and remote.isVisible()
                remote.setChecked(False)
                remote.setFocus()
                QTest.keyClick(remote, Qt.Key.Key_Space)
                assert remote.isChecked()
                for key in dock_apps.OPTIONAL:
                    option = dialog.findChild(CheckOption, 'dock-app-' + key)
                    assert option.isEnabled() == (key not in installed)
                    if option.isEnabled():
                        option.setChecked(False)
                        QTest.mouseClick(option, Qt.MouseButton.LeftButton)
                        assert option.isChecked()
                appearance.setCurrentIndex(appearance.findData('macos'))
                QTest.qWait(10)
                assert window.choices == before  # Transaction stays local until Continue.
                if args.capture and action == 'accept' and installed == {'mail': 'Existing Mail'}:
                    assert dialog.grab().save(str(args.capture))
                buttons = dialog.findChild(QDialogButtonBox)
                visited.append(True)
                if action == 'escape':
                    QTest.keyClick(dialog, Qt.Key.Key_Escape)
                else:
                    button = (QDialogButtonBox.StandardButton.Ok if action == 'accept'
                              else QDialogButtonBox.StandardButton.Cancel)
                    QTest.mouseClick(dialog.findChild(QPushButton, 'dock-apps-continue' if action == 'accept' else 'dock-apps-cancel'), Qt.MouseButton.LeftButton)

            QTimer.singleShot(60, interact)
            QTest.mouseClick(window.content.findChild(QPushButton, 'edit-dock-apps'), Qt.MouseButton.LeftButton)
            QTest.qWait(10)
            assert visited and app.activeModalWidget() is None and window.isVisible()
            if action == 'accept':
                assert window.choices['dock_apps_source'] == 'flatpak'
                assert window.choices['dock_add_flathub']
                assert window.choices['dock_appearance'] == 'macos'
                assert window.choices['dock_apps'] == [key for key in dock_apps.OPTIONAL if key not in installed], (installed, action, window.choices['dock_apps'])
            else:
                assert window.choices == before
            results.append(action)
    window.choices['dock'] = False
    window.render()
    assert not window.content.findChild(QPushButton, 'edit-dock-apps').isEnabled()
    assert app.palette() == original_palette
    window.close()
    print(json.dumps({'edition': window.edition, 'mode': mode, 'dialogs': len(results),
                      'platform': app.platformName(), 'result': 'passed'}))


if __name__ == '__main__':
    main()
