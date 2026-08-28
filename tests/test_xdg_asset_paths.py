"""User theme payloads must follow XDG_DATA_HOME when it is customized."""

import os
import subprocess
import sys
from pathlib import Path


def test_theme_asset_destinations_follow_xdg_data_home(tmp_path):
    repo = Path(__file__).resolve().parent.parent
    data_home = tmp_path / "user-data"
    env = os.environ.copy()
    env["XDG_DATA_HOME"] = str(data_home)
    env["PYTHONPATH"] = str(repo / "src/scripts")
    code = """
from steps import color_schemes, cursors, fonts, global_theme, icons
from steps import plasma_theme, plasmoids, wallpapers, window_decorations
paths = (
    color_schemes.DEST_DIR, cursors.DEST_DIR, fonts.DEST_DIR,
    global_theme.DEST_DIR, icons.DEST_DIR, plasma_theme.DEST_DIR,
    plasmoids.DEST_DIR, wallpapers.DEST_DIR, window_decorations.DEST_DIR,
)
print('\\n'.join(map(str, paths)))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd=repo,
    )
    destinations = [Path(line) for line in result.stdout.splitlines()]
    assert destinations
    assert all(path.is_relative_to(data_home) for path in destinations)
