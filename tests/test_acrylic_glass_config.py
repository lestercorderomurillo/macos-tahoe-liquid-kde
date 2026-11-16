"""Real KConfig CLI regression checks in private configuration directories."""

import configparser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.parametrize("first_edition", ["MacTahoe", "MacGoldenGate"])
def test_native_material_follows_source_edition_across_reinstalls(tmp_path, first_edition):
    if not all(shutil.which(tool) for tool in ("kreadconfig6", "kwriteconfig6")):
        pytest.skip("KConfig CLI tools required")
    repo = Path(__file__).resolve().parents[1]
    presets_path = Path("src/offline/kwin-effects/acrylic-glass/src/presets.json")
    presets = {preset["value"]: preset for preset in json.loads((repo / presets_path).read_text())}
    editions = {"MacTahoe": 1, "MacGoldenGate": 2}
    for edition in editions:
        checkout = tmp_path / edition
        shutil.copytree(repo / "src/scripts", checkout / "src/scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        (checkout / "src/scripts/defaults.json").write_text(json.dumps({"wallpaper": edition}))
        (checkout / presets_path).parent.mkdir(parents=True)
        shutil.copyfile(repo / presets_path, checkout / presets_path)

    config = tmp_path / "config"
    config.mkdir()
    config_file = config / "kwinrc"
    config_file.write_text(
        "[Plugins]\notherEffectEnabled=true\n"
        "[Effect-liquidglass]\nMaterialPreset=0\nBlurStrength=8.25\n"
        "GradientTopColor=#265a81\nDarkGradientOverlay=\n"
        "WindowCornerRadius=13.5\nDockCornerRadius=0\nPopupCornerRadius=\n"
        "WindowClasses=custom-app\nBlurMatching=true\nBlurNonMatching=false\n"
    )
    env = {key: val for key, val in os.environ.items() if key in ("PATH", "LANG", "LC_ALL")}
    env.update(HOME=str(tmp_path), XDG_CONFIG_HOME=str(config),
               XDG_CONFIG_DIRS=str(tmp_path / "system-config"))
    other_edition = next(edition for edition in editions if edition != first_edition)
    previous = None
    for edition in (first_edition, other_edition, first_edition, first_edition):
        env["PYTHONPATH"] = str(tmp_path / edition / "src/scripts")
        # The working directory must not override the executing source edition.
        other_checkout = "MacGoldenGate" if edition == "MacTahoe" else "MacTahoe"
        result = subprocess.run(
            [sys.executable, "-c", "from steps.acrylic_glass import _install_material_preset; "
             "assert _install_material_preset()"],
            cwd=tmp_path / other_checkout, env=env, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        saved = configparser.ConfigParser()
        saved.optionxform = str
        saved.read(config_file)
        expected = {key: str(value).lower() if isinstance(value, bool) else str(value)
                    for key, value in presets[editions[edition]]["values"].items()}
        material = dict(saved["Effect-liquidglass"])
        components = json.loads(material.pop("ComponentMaterials"))
        assert components["dock"]["BlurStrength"] == 5
        assert components["dock"]["DarkGradientOverlay"] is False
        assert components["apps"]["BlurStrength"] == float(expected["BlurStrength"])
        assert material == expected | {
            "MaterialPreset": str(editions[edition]), "WindowCornerRadius": "13.5",
            "DockCornerRadius": "0", "PopupCornerRadius": "", "WindowClasses": "custom-app",
            "BlurMatching": "true", "BlurNonMatching": "false",
        }
        assert saved["Plugins"]["otherEffectEnabled"] == "true"
        if previous is not None and previous[0] == edition:
            assert config_file.read_bytes() == previous[1]
        previous = (edition, config_file.read_bytes())


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
