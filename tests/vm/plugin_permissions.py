#!/usr/bin/env python3
"""Focused issue #129 install/reinstall qualification in a disposable Plasma VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src/scripts"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("install", "reinstall", "verify"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from screenshot_checks import require_virtual_machine
    require_virtual_machine()
    assert Path('/sys/class/dmi/id/product_name').read_text().strip() == 'MTTKDE release capture'
    if args.phase != "verify":
        assert os.getuid() == 0 and os.environ.get("SUDO_USER") == "tester"
        user = pwd.getpwnam("tester")
        os.environ["HOME"] = user.pw_dir
        os.initgroups(user.pw_name, user.pw_gid)
        os.setegid(user.pw_gid)
        os.seteuid(user.pw_uid)
        os.umask(0o007)
    from utils import restore_desktop_session_env
    restore_desktop_session_env()
    from distro import qt6_plugins_dir, qt6_qml_dir
    from steps import plasmoids, globalmenu, kvantum
    from steps._helpers import _as_root
    import log
    files = [
        qt6_plugins_dir() / plasmoids._TASKMANAGER_SO_RELPATH,
        qt6_plugins_dir() / globalmenu._SO_RELPATH,
        kvantum.menu_style_destination(),
    ]
    trees = [
        qt6_qml_dir() / plasmoids._TASKMANAGER_QML_RELPATH,
        qt6_qml_dir() / plasmoids._LAUNCHER_QML_RELPATH,
        qt6_qml_dir() / globalmenu._QML_RELPATH,
    ]
    if args.phase == "install":
        for step in (plasmoids, globalmenu, kvantum):
            step.build()
            assert not log.errors, log.errors
    if args.phase == "reinstall":
        # Reproduce already-installed root-owned restrictive files and QML parents.
        with _as_root():
            for path in files:
                path.chmod(0o750)
            for tree in trees:
                for path in [tree, *tree.rglob('*')]:
                    if not path.is_symlink():
                        path.chmod(0o750 if path.is_dir() or path.stat().st_mode & 0o111 else 0o660)
                parent = tree.parent
                while parent != qt6_qml_dir():
                    parent.chmod(0o750)
                    parent = parent.parent
    if args.phase != "verify":
        for step in (plasmoids, globalmenu, kvantum):
            step.install()
            assert not log.errors, log.errors
    records = {}
    for path in [*files, *(p for tree in trees for p in [tree, *tree.rglob('*')])]:
        if path.is_symlink():
            continue
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == (0o755 if path.is_dir() or mode & 0o111 else 0o644), (path, oct(mode))
        assert os.access(path, os.R_OK | (os.X_OK if path.is_dir() else 0), effective_ids=True), path
        records[str(path)] = {"mode": oct(mode), "uid": path.stat().st_uid}
        if path.is_file():
            records[str(path)]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    if args.phase == "verify":
        assert os.getuid() != 0
        from PyQt6.QtCore import QPluginLoader, QUrl
        from PyQt6 import QtQuick  # Register Python QtQuick types before the QML loader thread.
        from PyQt6.QtGui import QGuiApplication
        from PyQt6.QtQml import QQmlComponent, QQmlEngine
        app = QGuiApplication([])
        loaders = [QPluginLoader(str(path)) for path in files]
        for loader in loaders:
            assert loader.load(), loader.errorString()
        engine = QQmlEngine()
        component = QQmlComponent(engine)
        probe = args.output.with_suffix(".qml")
        probe.write_text('import QtQuick\nimport org.kde.mac.tahoe.launcher\nItem {}')
        component.loadUrl(QUrl.fromLocalFile(str(probe)), QQmlComponent.CompilationMode.Asynchronous)
        deadline = time.monotonic() + 15
        while component.isLoading() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert not component.isLoading(), "QML import timed out"
        assert not component.isError(), [error.toString() for error in component.errors()]
        item = component.create()
        assert item is not None, [error.toString() for error in component.errors()]
    args.output.write_text(json.dumps({"phase": args.phase, "umask": "0007", "files": records}, indent=2) + '\n')


if __name__ == '__main__':
    main()
