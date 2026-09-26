"""Real KConfig CLI regression checks in private configuration directories."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.parametrize("value", [None, "28", "0", "13.5", "", "not-a-number"])
def test_native_corner_defaults_preserve_present_values(tmp_path, value):
    if not all(shutil.which(tool) for tool in ("kreadconfig6", "kwriteconfig6")):
        pytest.skip("KConfig CLI tools required")
    config = tmp_path / "config"
    config.mkdir()
    config_file = config / "kwinrc"
    original = "[Effect-liquidglass]\nCustomSetting=untouched\n"
    if value is not None:
        original += f"WindowCornerRadius={value}\n"
    config_file.write_text(original)
    scripts = Path(__file__).resolve().parents[1] / "src/scripts"
    env = {key: val for key, val in os.environ.items()
           if key in ("PATH", "LANG", "LC_ALL")}
    env.update(HOME=str(tmp_path), XDG_CONFIG_HOME=str(config),
               XDG_CONFIG_DIRS=str(tmp_path / "system-config"), PYTHONPATH=str(scripts))
    script = "from steps.acrylic_glass import _install_corner_defaults; _install_corner_defaults()"
    subprocess.run([sys.executable, "-c", script], env=env, check=True, timeout=20)
    after_first = config_file.read_bytes()
    subprocess.run([sys.executable, "-c", script], env=env, check=True, timeout=20)
    assert config_file.read_bytes() == after_first
    for key, expected in (("WindowCornerRadius", "22" if value is None else value),
                          ("DockCornerRadius", "20"), ("PopupCornerRadius", "6"),
                          ("CustomSetting", "untouched")):
        result = subprocess.run(["kreadconfig6", "--file", "kwinrc", "--group",
                                 "Effect-liquidglass", "--key", key], env=env,
                                capture_output=True, text=True, check=True, timeout=5)
        assert result.stdout.removesuffix("\n") == expected


def test_native_corner_defaults_preserve_system_cascade(tmp_path):
    if not all(shutil.which(tool) for tool in ("kreadconfig6", "kwriteconfig6")):
        pytest.skip("KConfig CLI tools required")
    config = tmp_path / "config"
    system_config = tmp_path / "system-config"
    config.mkdir()
    system_config.mkdir()
    (system_config / "kwinrc").write_text("[Effect-liquidglass]\nWindowCornerRadius=35\n")
    scripts = Path(__file__).resolve().parents[1] / "src/scripts"
    env = {key: val for key, val in os.environ.items()
           if key in ("PATH", "LANG", "LC_ALL")}
    env.update(HOME=str(tmp_path), XDG_CONFIG_HOME=str(config),
               XDG_CONFIG_DIRS=str(system_config), PYTHONPATH=str(scripts))
    subprocess.run([sys.executable, "-c",
                    "from steps.acrylic_glass import _install_corner_defaults; _install_corner_defaults()"],
                   env=env, check=True, timeout=20)
    assert "WindowCornerRadius" not in (config / "kwinrc").read_text()
    assert (system_config / "kwinrc").read_text() == "[Effect-liquidglass]\nWindowCornerRadius=35\n"
