"""Expose wizard pages for documentation only inside the disposable capture VM."""
from pathlib import Path
import json
import os
import runpy
import sys


def main():
    repo = Path(sys.argv[1]).resolve()
    sys.path[:0] = [str(repo / 'src/scripts'), str(repo / 'src/installer')]
    from release_capture_guest import session
    session()
    os.environ['MAC_TAHOE_NO_UPDATE_CHECK'] = 'true'
    from PyQt6.QtCore import QTimer
    from wizard_window import InstallerWindow, STEPS

    folder = repo.parent / 'wizard-capture'
    folder.mkdir(exist_ok=True)
    command = folder / 'page.json'
    state = folder / 'state.json'
    state.unlink(missing_ok=True)
    original_show = InstallerWindow.show

    def show(window):
        original_show(window)
        previous = None

        def poll():
            nonlocal previous
            try:
                requested = json.loads(command.read_text())
            except (OSError, ValueError):
                return
            if requested == previous:
                return
            page = requested['page']
            if page not in dict(STEPS):
                raise ValueError('Not a selectable installer page: ' + page)
            # Render the real native page with the edition's actual defaults.
            # Never click Install: the capture guest is already installed.
            window.page = page
            window.render()
            previous = requested

            def ready():
                pending = state.with_suffix('.tmp')
                pending.write_text(json.dumps({'page': page, 'request': requested['request'],
                                               'pid': os.getpid(), 'edition': window.bridge.editionName,
                                               'title': window.windowTitle()}))
                pending.replace(state)
            QTimer.singleShot(500, ready)

        timer = QTimer(window)
        timer.timeout.connect(poll)
        timer.start(100)

    InstallerWindow.show = show
    os.chdir(repo)
    sys.argv = [str(repo / 'installer')]
    runpy.run_path(str(repo / 'installer'), run_name='__main__')


if __name__ == '__main__':
    main()
