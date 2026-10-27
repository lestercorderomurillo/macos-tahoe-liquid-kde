"""Static guards for the Acrylic Glass CMake fallback paths."""

import re
import json
import shutil
import subprocess

import pytest
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "src/offline/kwin-effects/acrylic-glass"


def test_acrylic_glass_fails_cleanly_without_kwin_dev_support():
    top = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "if(NOT GLASS_WAYLAND AND NOT GLASS_X11)" in top
    assert "Acrylic Glass requires KWin development files for Wayland or X11." in top


def test_acrylic_glass_only_configures_kcm_when_a_kwin_backend_is_available():
    src = (ROOT / "src/CMakeLists.txt").read_text(encoding="utf-8")
    assert "if(GLASS_WAYLAND OR GLASS_X11)" in src
    assert "add_subdirectory(kcm)" in src


def test_acrylic_glass_enables_optional_x11_backend():
    top = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    src = (ROOT / "src/CMakeLists.txt").read_text(encoding="utf-8")
    assert 'option(GLASS_X11 "Whether to build Acrylic Glass for X11 if present." ON)' in top
    assert "add_library(liquidglass_x11 MODULE ${liquidglass_SOURCES})" in src
    assert "target_compile_definitions(liquidglass_x11 PRIVATE GLASS_X11 KWIN_BUILD_X11)" in src
    assert "kwin-x11/effects/plugins" in src
    compat = (ROOT / "src/kwin_version_compat.h").read_text(encoding="utf-8")
    assert "ACRYLIC_GLASS_WAYLAND_BACKGROUND_EFFECT_V1" in compat


def test_acrylic_glass_requests_only_present_backend_sdks(monkeypatch):
    from steps import acrylic_glass
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)

    for binaries, expected in (
        ({"kwin_wayland"}, {"kwin-cmake:kwin"}),
        ({"kwin_x11"}, {"kwin-x11-cmake:kwin-x11"}),
        ({"kwin_wayland", "kwin_x11"},
         {"kwin-cmake:kwin"}),
        (set(), {"kwin-cmake:kwin"}),
    ):
        monkeypatch.setattr(acrylic_glass, "have", lambda binary: binary in binaries)
        kwin_dependencies = {dependency for dependency in acrylic_glass.deps()
                             if dependency.startswith(("kwin-cmake:", "kwin-x11-cmake:"))}
        assert kwin_dependencies == expected


@pytest.mark.parametrize("session,dependency,module", [
    ("wayland", "kwin-cmake:kwin", "liquidglass.so"),
    ("x11", "kwin-x11-cmake:kwin-x11", "liquidglass_x11.so"),
])
def test_active_session_requires_its_sdk_and_module(monkeypatch, tmp_path, session, dependency, module):
    from steps import acrylic_glass
    monkeypatch.setenv("XDG_SESSION_TYPE", session)
    monkeypatch.setattr(acrylic_glass, "have", lambda binary: True)
    monkeypatch.setattr(acrylic_glass, "BUILD", tmp_path)
    assert {item for item in acrylic_glass.deps()
            if item.startswith(("kwin-cmake:", "kwin-x11-cmake:"))} == {dependency}
    other = "liquidglass_x11.so" if session == "wayland" else "liquidglass.so"
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / other).touch()
    assert tmp_path / "src" / module in acrylic_glass.build_artifacts()
    assert not (tmp_path / "src" / module).exists()


def test_acrylic_glass_reports_the_optional_x11_artifact(monkeypatch, tmp_path):
    from steps import acrylic_glass
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)

    build = tmp_path / "build"
    monkeypatch.setattr(acrylic_glass, "BUILD", build)
    wayland = build / "src/liquidglass.so"
    x11 = build / "src/liquidglass_x11.so"
    config = build / "src/kcm/kwin_liquidglass_config.so"
    wayland.parent.mkdir(parents=True)
    wayland.touch()
    config.parent.mkdir(parents=True)
    config.touch()

    assert acrylic_glass.build_artifacts() == [config, wayland]
    x11.touch()
    assert acrylic_glass.build_artifacts() == [config, wayland, x11]
    wayland.unlink()
    assert acrylic_glass.build_artifacts() == [config, x11]
    x11.unlink()
    assert any(not path.exists() for path in acrylic_glass.build_artifacts())


def test_acrylic_glass_version_floor_matches_preflight():
    """The effect's CMake floor, the preflight runtime floor, and the
    README must all agree on 6.6 — they drifted once (CMake said 6.4
    while preflight blocked <6.6), which is exactly the inconsistency
    this test exists to prevent."""
    sys.path.insert(0, str(REPO / "src/scripts"))
    import preflight

    assert preflight._MIN_PLASMA == (6, 6)

    top = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "VERSION_LESS 6.6" in top
    assert "requires KDE Plasma 6.6+" in top
    # The retired 6.4 floor must not creep back.
    assert "VERSION_LESS 6.4" not in top


def test_acrylic_glass_preset_fits_kcm_ranges():
    """Installer tuning must remain representable in the effect KCM."""
    from steps import acrylic_glass

    presets = json.loads((ROOT / "src/presets.json").read_text())
    assert [p["id"] for p in presets] == ["tahoe", "golden-gate"]
    assert [p["value"] for p in presets] == [1, 2]
    root = ET.parse(ROOT / "src/kcm/config.ui").getroot()
    schema = ET.parse(ROOT / "src/glass.kcfg").getroot()
    assert schema.find(".//{*}entry[@name='AcrylicGlassType']") is None
    for preset in presets:
        for key, value in preset["values"].items():
            widget = root.find(f".//widget[@name='kcfg_{key}']")
            assert widget is not None, key
            assert schema.find(f".//{{*}}entry[@name='{key}']") is not None
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                maximum = widget.find("./property[@name='maximum']")[0]
                assert 0 <= value <= float(maximum.text), key
    for key, value in presets[0]["values"].items():
        default = schema.find(f".//{{*}}entry[@name='{key}']/{{*}}default").text
        assert default == (str(value).lower() if isinstance(value, bool) else str(value)), key


@pytest.mark.parametrize("active,returncode,identity,confirmed", [
    ("liquidglass\n", 0, True, True),
    ("liquidglass\n", 0, False, False),
    ("liquidglass\n", 0, None, False),
    ("other-liquidglass\n", 0, True, False),
    ("liquidglass\n", 1, True, False),
    ("", 0, True, False),
])
@pytest.mark.parametrize("edition", ["MacTahoe", "MacGoldenGate"])
def test_acrylic_glass_installs_the_effect_default_blur(monkeypatch, tmp_path, capsys,
                                                       active, returncode, identity, confirmed, edition):
    """Fresh installs apply the edition material and preserve radius overrides."""
    import contextlib
    from steps import acrylic_glass
    from subprocess import CompletedProcess
    monkeypatch.setattr(acrylic_glass, "_as_root", contextlib.nullcontext)
    monkeypatch.setattr(acrylic_glass, "default_wallpaper", lambda: edition)

    build = tmp_path / "build"
    for name in ("src/liquidglass.so", "src/liquidglass_x11.so",
                 "src/kcm/kwin_liquidglass_config.so"):
        artifact = build / name
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.touch()
    monkeypatch.setattr(acrylic_glass, "BUILD", build)
    monkeypatch.setattr(acrylic_glass, "_plugin_dir", lambda: tmp_path / "plugins")
    monkeypatch.setattr(acrylic_glass, "LEGACY_USER_PLUGIN_DIR", tmp_path / "legacy")
    installed_files = []
    activated_links = []
    monkeypatch.setattr(acrylic_glass, "sudo_install_file",
                        lambda source, destination, *args, **kwargs:
                        installed_files.append(destination) or True)
    monkeypatch.setattr(acrylic_glass, "_activate_effect_binary",
                        lambda source, destination: activated_links.append(destination) or True)
    monkeypatch.setattr(acrylic_glass, "_running_build_matches", lambda: identity)
    monkeypatch.setattr(acrylic_glass, "_running_plugin_matches", lambda path: None)
    monkeypatch.setattr(acrylic_glass, "qdbus_call", lambda *args: True)
    monkeypatch.setattr(acrylic_glass, "qdbus_cmd", lambda: "probe-qdbus")
    monkeypatch.setattr(acrylic_glass, "have", lambda command: True)
    monkeypatch.setattr(acrylic_glass, "run_user",
                        lambda command, **kwargs: CompletedProcess(command, returncode, active)
                        if command[0] == "probe-qdbus" else CompletedProcess(command, 0, ("28" if command[6].endswith("CornerRadius") else command[-1]) + "\n"))
    monkeypatch.setattr(acrylic_glass.time, "sleep", lambda seconds: None)
    writes = []
    monkeypatch.setattr(acrylic_glass, "kw_write",
                        lambda *args: writes.append(args) or True)

    acrylic_glass.install()
    output = capsys.readouterr().out
    assert tmp_path / "plugins/kwin-x11/effects/plugins/liquidglass.so" in activated_links
    assert tmp_path / "plugins/kwin-x11/effects/configs/kwin_liquidglass_config.so" in installed_files
    assert ("Acrylic Glass loaded" in output) == confirmed
    if returncode != 0 or "liquidglass" not in active.splitlines():
        assert "activation was not confirmed" in output
    elif identity is False:
        assert "previous plugin loaded" in output
    elif identity is None:
        assert "running build could not be verified" in output

    config = ET.parse(ROOT / "src/glass.kcfg").getroot()
    entry = config.find(".//{*}entry[@name='BlurStrength']/{*}default")
    assert entry is not None
    default = entry.text
    assert default == "5.0"
    blur_writes = [args for args in writes if "BlurStrength" in args]
    assert blur_writes == [("--file", "kwinrc", "--group", "Effect-liquidglass",
                           "--key", "BlurStrength", default)]
    # The complete install must preserve the #89 workaround, including
    # avoiding the obsolete Menu/Dialog/Tooltip/Bottom radius keys.
    assert not any(args[-2].endswith("CornerRadius") for args in writes)


def test_golden_gate_shares_tahoe_optics_with_its_own_gradient(monkeypatch):
    from steps import acrylic_glass as glass
    monkeypatch.setattr(glass, "default_wallpaper", lambda: "MacGoldenGate")
    golden = glass._edition_preset()
    monkeypatch.setattr(glass, "default_wallpaper", lambda: "MacTahoe")
    tahoe = glass._edition_preset()
    assert tahoe["MaterialPreset"] == "1"
    assert golden["MaterialPreset"] == "2"
    assert tahoe.keys() == golden.keys()
    differences = {key for key in tahoe if tahoe[key] != golden[key]}
    assert differences == {"MaterialPreset", "DarkGradientOverlay",
                           "GradientTopOpacity", "GradientBottomOpacity"}
    schema = ET.parse(ROOT / "src/glass.kcfg").getroot()
    rgb_default = schema.find(".//{*}entry[@name='RgbDriftStrength']/{*}default").text
    assert float(golden["RgbDriftStrength"]) == float(rgb_default)


@pytest.mark.parametrize("saved", [None, "true", "false", ""])
def test_gradient_default_preserves_saved_toggle(monkeypatch, saved):
    from subprocess import CompletedProcess
    from steps import acrylic_glass as glass
    monkeypatch.setattr(glass, "have", lambda command: True)
    monkeypatch.setattr(glass, "run_user", lambda command, **kwargs:
                        CompletedProcess(command, 0, (command[-1] if saved is None else saved) + "\n"))
    writes = []
    monkeypatch.setattr(glass, "kw_write", lambda *args: writes.append(args) or True)
    glass._install_missing_defaults((("DarkGradientOverlay", "true"),))
    assert [args[-2:] for args in writes] == ([("DarkGradientOverlay", "true")] if saved is None else [])


def test_corner_defaults_only_seed_missing_keys(monkeypatch):
    from subprocess import CompletedProcess
    from steps import acrylic_glass

    values = {"WindowCornerRadius": "28", "DockCornerRadius": ""}
    writes = []
    monkeypatch.setattr(acrylic_glass, "have", lambda command: True)

    def read(command, **kwargs):
        assert command[:5] == ["kreadconfig6", "--file", "kwinrc", "--group",
                               "Effect-liquidglass"]
        key = command[command.index("--key") + 1]
        return CompletedProcess(command, 0, values.get(key, command[-1]) + "\n")

    monkeypatch.setattr(acrylic_glass, "run_user", read)
    monkeypatch.setattr(acrylic_glass, "kw_write", lambda *args: writes.append(args) or True)
    acrylic_glass._install_corner_defaults()
    assert [args[-2:] for args in writes] == [("PopupCornerRadius", "6")]


def test_corner_defaults_do_not_replace_custom_values(monkeypatch):
    from subprocess import CompletedProcess
    from steps import acrylic_glass

    monkeypatch.setattr(acrylic_glass, "have", lambda command: True)
    monkeypatch.setattr(acrylic_glass, "run_user",
                        lambda command, **kwargs: CompletedProcess(command, 0, "28\n"))
    writes = []
    monkeypatch.setattr(acrylic_glass, "kw_write", lambda *args: writes.append(args) or True)
    acrylic_glass._install_corner_defaults()
    acrylic_glass._install_corner_defaults()
    assert writes == []


def test_corner_defaults_fail_closed_on_missing_reader(monkeypatch, capsys):
    from steps import acrylic_glass

    monkeypatch.setattr(acrylic_glass, "have", lambda command: False)
    writes = []
    monkeypatch.setattr(acrylic_glass, "kw_write", lambda *args: writes.append(args) or True)
    acrylic_glass._install_corner_defaults()
    assert writes == []
    assert "kreadconfig6" in capsys.readouterr().out


def test_corner_defaults_fail_closed_on_read_errors(monkeypatch, capsys):
    import subprocess
    from steps import acrylic_glass

    def read(command, **kwargs):
        key = command[command.index("--key") + 1]
        if key == "WindowCornerRadius":
            raise OSError("reader unavailable")
        if key == "DockCornerRadius":
            raise subprocess.TimeoutExpired(command, 5)
        return subprocess.CompletedProcess(command, 1, command[-1] + "\n")

    monkeypatch.setattr(acrylic_glass, "have", lambda command: True)
    monkeypatch.setattr(acrylic_glass, "run_user", read)
    writes = []
    monkeypatch.setattr(acrylic_glass, "kw_write", lambda *args: writes.append(args) or True)
    acrylic_glass._install_corner_defaults()
    assert writes == []
    output = capsys.readouterr().out
    assert all(key in output for key, _ in acrylic_glass._CORNER_DEFAULTS)


def test_corner_defaults_warn_on_failed_write(monkeypatch, capsys):
    from subprocess import CompletedProcess
    from steps import acrylic_glass

    monkeypatch.setattr(acrylic_glass, "have", lambda command: True)
    monkeypatch.setattr(acrylic_glass, "run_user",
                        lambda command, **kwargs: CompletedProcess(command, 0, command[-1] + "\n"))
    monkeypatch.setattr(acrylic_glass, "kw_write", lambda *args: False)
    acrylic_glass._install_corner_defaults()
    assert "kwriteconfig6" in capsys.readouterr().out


def test_acrylic_glass_gates_kwin_68_draw_window_api():
    """KWin 6.8 (6.7.90 beta onwards) made Effect::drawWindow() return
    bool and dropped snapToPixelGrid/snapToPixelGridF. The effect must
    switch its override signature on GLASS_KWIN_68 and keep its own pixel
    snapping helpers so it builds on 6.6, 6.7 and 6.8."""
    top = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "VERSION_GREATER_EQUAL 6.7.90" in top
    src = (ROOT / "src/CMakeLists.txt").read_text(encoding="utf-8")
    assert "target_compile_definitions(liquidglass PRIVATE GLASS_KWIN_68)" in src
    assert "target_compile_definitions(liquidglass_x11 PRIVATE GLASS_KWIN_68)" in src

    compat = (ROOT / "src/kwin_version_compat.h").read_text(encoding="utf-8")
    assert "#ifdef GLASS_KWIN_68" in compat
    assert "using AcrylicGlassDrawWindowResult = bool;" in compat
    assert "using AcrylicGlassDrawWindowResult = void;" in compat

    header = (ROOT / "src/effect.h").read_text(encoding="utf-8")
    assert "AcrylicGlassDrawWindowResult drawWindow(" in header

    effect = (ROOT / "src/effect.cpp").read_text(encoding="utf-8")
    assert "AcrylicGlassDrawWindowResult BlurEffect::drawWindow(" in effect
    # KWin's helpers are gone on 6.8; only the local copies may be called.
    assert re.search(r"(?<![A-Za-z_])snapToPixelGridF?\(", effect) is None
    assert "inline QRect agSnapToPixelGrid(" in effect
    assert "inline QRectF agSnapToPixelGridF(" in effect


def test_acrylic_glass_selects_abi_per_backend(tmp_path):
    if not shutil.which("cmake"):
        pytest.skip("cmake not available")
    source = (ROOT / "CMakeLists.txt").read_text()
    start = source.index("if(GLASS_WAYLAND)\n    find_package(KWin")
    end = source.index("find_package(KDecoration3 REQUIRED)", start)
    # Run the actual discovery/version logic with synthetic SDK versions.
    for wayland, x11, expected in [
        ("6.6.5", "", "OFF;OFF;OFF"),
        ("6.7.4", "", "ON;OFF;OFF"),
        ("6.7.90", "", "ON;ON;OFF"),
        ("6.8.0", "6.7.4", "ON;ON;OFF"),
        ("", "6.8.0", "OFF;OFF;ON"),
    ]:
        script = tmp_path / "versions.cmake"
        result = tmp_path / "result"
        script.write_text(
            # Match the project's policy baseline: older CMake otherwise
            # treats TRUE as a variable name rather than a boolean (CMP0012).
            "cmake_minimum_required(VERSION 3.16.0)\n"
            "macro(find_package)\nendmacro()\n"
            f"set(GLASS_WAYLAND {'ON' if wayland else 'OFF'})\n"
            f"set(GLASS_X11 {'ON' if x11 else 'OFF'})\n"
            "set(KWin_FOUND TRUE)\nset(KWinX11_FOUND TRUE)\n"
            f'set(KWin_VERSION "{wayland}")\n'
            f'set(KWinX11_VERSION "{x11}")\n'
            + source[start:end]
            + f'file(WRITE "{result}" "${{GLASS_KWIN_67_WAYLAND}};'
              '${GLASS_KWIN_68_WAYLAND};'
              '${GLASS_KWIN_68_X11}")\n')
        proc = subprocess.run(["cmake", "-P", str(script)],
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert result.read_text() == expected


def test_detects_mapped_plugin_retained_after_atomic_replacement(tmp_path):
    import mmap
    from pathlib import Path
    from steps.acrylic_glass import _plugin_mapping_matches

    plugin = tmp_path / "liquidglass.so"
    plugin.write_bytes(bytes(4096))
    with plugin.open("rb") as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ):
        assert _plugin_mapping_matches(Path("/proc/self/maps").read_text(), plugin) is True
        replacement = tmp_path / "replacement.so"
        replacement.write_bytes(bytes(4096))
        replacement.replace(plugin)
        assert _plugin_mapping_matches(Path("/proc/self/maps").read_text(), plugin) is False
    assert _plugin_mapping_matches(Path("/proc/self/maps").read_text(), plugin) is None


def test_versioned_plugin_upgrade_and_identical_reinstall(tmp_path, monkeypatch):
    import contextlib
    import os
    import stat
    from steps import acrylic_glass as glass

    monkeypatch.setattr(glass, "_as_root", contextlib.nullcontext)

    def install(source, destination, label):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        return True

    monkeypatch.setattr(glass, "sudo_install_file", install)
    source = tmp_path / "build.so"
    directory = tmp_path / "plugins"
    source.write_bytes(b"first build")
    first = glass._versioned_effect_path(source, directory)
    original_umask = os.umask(0o027)
    try:
        assert glass._install_effect_binary(source, first)
    finally:
        os.umask(original_umask)
    assert stat.S_IMODE(first.parent.parent.stat().st_mode) == 0o755
    assert stat.S_IMODE(first.parent.stat().st_mode) == 0o755
    assert stat.S_IMODE(first.stat().st_mode) == 0o644
    first.parent.parent.chmod(0o750)
    first.parent.chmod(0o750)
    first.chmod(0o666)
    assert glass._install_effect_binary(source, first)
    assert stat.S_IMODE(first.parent.parent.stat().st_mode) == 0o755
    assert stat.S_IMODE(first.parent.stat().st_mode) == 0o755
    assert stat.S_IMODE(first.stat().st_mode) == 0o644
    link = directory / "liquidglass.so"
    assert glass._activate_effect_binary(first, link)
    assert link.resolve() == first
    inode = first.stat().st_ino
    assert glass._install_effect_binary(source, first)
    assert first.stat().st_ino == inode

    source.write_bytes(b"updated build")
    second = glass._versioned_effect_path(source, directory)
    assert second != first
    assert glass._install_effect_binary(source, second)
    assert glass._activate_effect_binary(second, link)
    assert link.resolve() == second
    assert first.read_bytes() == b"first build"
    assert second.name == "liquidglass.so"
    foreign = directory / ".mttkde-liquidglass/custom/liquidglass.so"
    foreign.parent.mkdir()
    foreign.write_bytes(b"unowned")
    assert set(glass._owned_effect_paths(directory)) == {link, first, second}
    assert not glass._install_effect_binary(source, first)
