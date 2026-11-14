"""Focused native wizard frames; representative events, never a host capture."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src/installer'), str(ROOT / 'src/scripts')]


def main():
    if Path('/sys/class/dmi/id/product_name').read_text().strip() != 'MTTKDE release capture':
        raise SystemExit('A disposable release-capture VM is required')
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--edition', choices=['tahoe', 'golden-gate'], required=True)
    parser.add_argument('--dark', action='store_true')
    args = parser.parse_args()
    from PyQt6.QtCore import QEvent
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtTest import QTest
    from installer_ui import _make_installer_bridge
    from wizard_window import InstallerWindow, installer_palette
    from progress_model import ProgressModel, COMPONENTS
    app = QApplication([])
    app.setPalette(installer_palette(args.dark))
    bridge = _make_installer_bridge()
    bridge._language = 'en'
    window = InstallerWindow(bridge)
    assert window.edition == ('Tahoe' if args.edition == 'tahoe' else 'Golden Gate')
    window.choices['appearance'] = 'dark' if args.dark else 'light'
    window.page = 'progress'
    window._operation_started = time.monotonic() - 84
    window.render()
    window.show()
    window.activateWindow()
    window.next.setFocus()
    QTest.qWait(800)
    args.output.mkdir(parents=True, exist_ok=True)
    prefix = args.edition + ('-dark' if args.dark else '-light')

    def event(**values):
        bridge._handle_record('__EVENT__\t' + json.dumps(values))

    def capture(name):
        app.processEvents()
        QTest.qWait(300)
        assert window.isVisible() and window.isActiveWindow(), 'Wizard lost focus'
        size = window.size()
        assert window.grab().save(str(args.output / (prefix + '-' + name + '.png')))
        assert window.isActiveWindow() and window.size() == size

    for key in ('system', 'dependencies', 'downloads'):
        event(kind='phase', id=key, state='done')
    event(kind='phase', id='build', state='running')
    for key in COMPONENTS:
        event(kind='build', id=key, state='pending')
    event(kind='build', id='kvantum', state='done')
    event(kind='build', id='plasmoids', state='running')
    bridge._progress = .24
    window.refresh_progress()
    capture('progress')
    if args.edition == 'golden-gate' and not args.dark:
        bridge._append_log('Building Launcher and Dock\nCMake could not find the Plasma development package.')
        window.details_toggle.click()
        capture('details')
        event(kind='build', id='plasmoids', state='failed')
        bridge._finish(1)
        capture('error')
    if args.edition == 'tahoe' and args.dark:
        bridge.summary = ProgressModel()
        for key in bridge.summary.phases:
            event(kind='phase', id=key, state='done')
        bridge._finish(0)
        capture('done')
    window.close()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    print('Representative native frames captured:', prefix)


if __name__ == '__main__':
    main()
