"""Exercise material controls and installation of each edition's preset."""
import configparser
import json
import os
import select
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from steps import acrylic_glass as glass

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def kcm_probe(tmp_path_factory):
    if not shutil.which("cmake"):
        pytest.skip("CMake required for the native KCM")
    build = tmp_path_factory.mktemp("glass-kcm-build")
    result = subprocess.run(["cmake", "-S", str(REPO / "tests/glass"), "-B", str(build),
                             f"-DGLASS_SOURCE={glass.SRC}"], capture_output=True, text=True, timeout=60)
    if "GLASS_KCM_SDK_MISSING" in result.stdout:
        pytest.skip("KWin D-Bus development interface required")
    assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run(["cmake", "--build", str(build), "-j2"],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return build


@pytest.mark.parametrize("saved_tint", ["0", "1"])
@pytest.mark.parametrize("saved_preset", ["absent", "0", "1", "2"])
def test_native_material_preset_controls(kcm_probe, tmp_path, saved_preset, saved_tint):
    if not shutil.which("dbus-run-session"):
        pytest.skip("private D-Bus session required")
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG")}
    env.update(HOME=str(tmp_path), XDG_CONFIG_HOME=str(tmp_path / "config"),
               XDG_CONFIG_DIRS=str(tmp_path / "system"), QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(["dbus-run-session", "--", str(kcm_probe / "glass-kcm-probe"),
                             str(kcm_probe / "kcm/kwin_liquidglass_config.so"),
                             str(glass.SRC / "src/presets.json"), saved_preset, saved_tint],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "save/reopen, cancel and restore verified" in result.stderr
    # The KCM ends with Tahoe selected, omitting keys equal to schema defaults.
    # Installing another edition must replace this sparse KCM configuration.
    config = tmp_path / "config/kwinrc"
    env["PYTHONPATH"] = str(REPO / "src/scripts")
    for edition, index in (("MacGoldenGate", 2), ("MacTahoe", 1)):
        result = subprocess.run([sys.executable, "-c",
                                 "from steps import acrylic_glass as g; "
                                 f"g.default_wallpaper = lambda: {edition!r}; "
                                 "assert g._install_material_preset()"],
                                env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        saved = configparser.ConfigParser()
        saved.optionxform = str
        saved.read(config)
        material = saved["Effect-liquidglass"]
        assert material.items() >= _preset_values(index).items()
        assert material["WindowCornerRadius"] == "13.5"
        assert material["WindowClasses"] == "preserved-app"


def _preset_values(preset_value):
    presets = json.loads((glass.SRC / "src/presets.json").read_text())
    preset = next(preset for preset in presets if preset["value"] == preset_value)
    return {key: str(value).lower() if isinstance(value, bool) else str(value)
            for key, value in preset["values"].items()} | {"MaterialPreset": str(preset_value)}


@pytest.mark.parametrize("edition", ["MacTahoe", "MacGoldenGate"])
@pytest.mark.parametrize("existing", ["fresh", "legacy", "custom", "clear", "tahoe", "golden-gate", "empty"])
def test_installation_reapplies_complete_edition_material(monkeypatch, edition, existing):
    monkeypatch.setattr(glass, "default_wallpaper", lambda: edition)
    golden = edition == "MacGoldenGate"
    saved = {}
    if existing != "fresh":
        saved = dict(BlurStrength="4.0" if golden else "3.5", Brightness="1.0", Contrast="1.0",
                     Saturation="1.0", HighlightStrength="0.30", HighlightWidth="24",
                     MagnifyGlassStrength="0.015" if golden else "0.03", NoiseStrength="2",
                     RefractionWidth="72" if golden else "96", DarkGradientOverlay="false")
    if existing == "custom":
        saved["BlurStrength"] = "8.25"
        saved["GradientTopColor"] = "#263a51"
    elif existing == "clear":
        saved |= {"MaterialPreset": "0", "BlurStrength": "1.5", "MaterialOpacity": "0.55"}
    elif existing in ("tahoe", "golden-gate"):
        saved = _preset_values(1 if existing == "tahoe" else 2)
    elif existing == "empty":
        saved["MagnifyGlassStrength"] = ""
    independent = {"WindowCornerRadius": "13.5", "DockCornerRadius": "0",
                   "PopupCornerRadius": "", "WindowClasses": "custom-app",
                   "BlurMatching": "true", "BlurNonMatching": "false"}
    saved |= independent
    writes = []
    def write(*args):
        writes.append(args[-2])
        saved[args[-2]] = args[-1]
        return True
    monkeypatch.setattr(glass, "kw_write", write)
    assert glass._install_material_preset()
    expected = _preset_values(2 if golden else 1) | independent
    if existing == "clear":
        expected["MaterialOpacity"] = "0.55"  # Retired key is ignored, not rewritten.
    assert "MaterialOpacity" not in writes
    assert saved == expected
    assert writes[-1] == "MaterialPreset"
    writes.clear()
    assert glass._install_material_preset()
    assert saved == expected


@pytest.mark.parametrize("failed_key", ["BlurStrength", "GradientBottomOpacity", "MaterialPreset"])
def test_material_write_failure_does_not_report_success(monkeypatch, capsys, failed_key):
    writes = []
    def write(*args):
        writes.append(args[-2])
        return args[-2] != failed_key
    monkeypatch.setattr(glass, "kw_write", write)
    assert not glass._install_material_preset()
    assert writes[-1] == failed_key
    if failed_key != "MaterialPreset":
        assert "MaterialPreset" not in writes
    assert f"{failed_key} preset not applied" in capsys.readouterr().out


def test_native_glass_shader_pixels(kcm_probe, tmp_path, monkeypatch):
    import glass_surfaces
    if not shutil.which("Xvfb"):
        pytest.skip("Xvfb required for isolated software OpenGL")
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG")}
    env.update(HOME=str(tmp_path), XDG_CONFIG_HOME=str(tmp_path / "config"),
               XDG_CONFIG_DIRS=str(tmp_path / "system"), QT_QPA_PLATFORM="xcb",
               LIBGL_ALWAYS_SOFTWARE="1")
    themes = tmp_path / "themes"
    monkeypatch.setattr(glass_surfaces, "default_wallpaper", lambda: "MacGoldenGate")
    for mode in ("Light", "Dark"):
        name = "MacTahoeLiquidKde-" + mode
        shutil.copytree(REPO / "src/offline/plasma-theme" / name, themes / name)
        glass_surfaces.apply_plasma_surface_defaults(themes / name)
    with (tmp_path / "xvfb.log").open("w") as log:
        server = subprocess.Popen(["Xvfb", "-displayfd", "1", "-screen", "0", "640x480x24", "-nolisten", "tcp"],
                                  stdout=subprocess.PIPE, stderr=log, text=True, env=env)
        try:
            assert select.select([server.stdout], [], [], 15)[0], "Xvfb did not start"
            display = server.stdout.readline().strip()
            assert display.isdigit(), (tmp_path / "xvfb.log").read_text()
            env["DISPLAY"] = ":" + display
            result = subprocess.run([str(kcm_probe / "glass-shader-probe"), str(glass.SRC / "src/shaders"), str(themes)],
                                    env=env, capture_output=True, text=True, timeout=30)
            assert result.returncode == 0, result.stdout + result.stderr
            assert "both profiles verified" in result.stderr
        finally:
            server.terminate()
            server.wait(timeout=5)


@pytest.mark.parametrize("edition", ["MacTahoe", "MacGoldenGate"])
@pytest.mark.parametrize("style", ["classic", "tinted", "official"])
def test_installer_frost_glass_values(monkeypatch, edition, style):
    monkeypatch.setattr(glass, "default_wallpaper", lambda: edition)
    monkeypatch.setattr(glass, "selected", lambda: {"files": "nautilus", "glass_style": style})
    saved = {}
    monkeypatch.setattr(glass, "kw_write", lambda *args: saved.update({args[-2]: args[-1]}) or True)
    assert glass._install_material_preset()
    expected = _preset_values(2 if style == "official" else 1)
    if style == "tinted":
        expected.update(BlurStrength="12.0", MagnifyGlassStrength="0.02", RgbDriftStrength="10.0",
                        RefractionWidth="38.0", HighlightWidth="16.0", HighlightStrength="0.1",
                        Brightness="1.0", Contrast="1.0", Saturation="1.33",
                        NoiseStrength="0", BlurDecorations="true")
    assert saved == expected
