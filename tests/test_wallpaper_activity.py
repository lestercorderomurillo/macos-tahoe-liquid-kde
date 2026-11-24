"""Isolated KDE session, with actual wallpaper, tray and widget consumers."""
import os
import shutil
import subprocess
import sys

import pytest


def test_contrast_across_activities_and_outputs(repo, tmp_path, launcher_popup_module):
    for command in ("kwin_wayland", "plasmashell", "qdbus6", "dbus-run-session"):
        if not shutil.which(command):
            pytest.skip(f"{command} required for the Plasma Activity regression")
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY", "SESSION_MANAGER")}
    env.update(XDG_CONFIG_DIRS="/etc/xdg", XDG_DATA_DIRS="/usr/local/share:/usr/share", HOME=str(tmp_path), XDG_RUNTIME_DIR=str(runtime), XDG_SESSION_TYPE="wayland",
               QT_FORCE_STDERR_LOGGING="1", QT_LOGGING_TO_CONSOLE="1", QT_QPA_PLATFORM="offscreen", QML_IMPORT_PATH=str(launcher_popup_module),
               XDG_CONFIG_HOME=str(tmp_path / "config"), XDG_DATA_HOME=str(tmp_path / "data"),
               XDG_STATE_HOME=str(tmp_path / "state"), XDG_CACHE_HOME=str(tmp_path / "cache"))
    subprocess.run(["dbus-run-session", "--", sys.executable, str(repo / "tests/wallpaper_activity_probe.py")],
                   env=env, check=True, timeout=100)
