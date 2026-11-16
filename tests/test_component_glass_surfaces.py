"""Background edits operate on real installed SVGs and remain transactional."""
import copy
import gzip
import json
from pathlib import Path
import shutil
import pytest
import glass_surface_settings as surfaces

REPO = Path(__file__).resolve().parents[1]

@pytest.fixture
def installed(tmp_path):
    data, config, state = (tmp_path / p for p in ('data', 'config', 'state'))
    shutil.copytree(REPO / 'src/offline/plasma-theme', data / 'plasma/desktoptheme')
    source = REPO / 'src/offline/kvantum/mac-tahoe-liquid-kde'
    for name in ('mac-tahoe-liquid-kde', 'mac-tahoe-liquid-kdeDark'):
        dest = config / 'Kvantum' / name
        dest.mkdir(parents=True)
        for ext in ('svg', 'kvconfig'):
            shutil.copy2(source / (name + '.' + ext), dest / (name + '.' + ext))
    (config / 'Kvantum/kvantum.kvconfig').write_text('[General]\ntheme=mac-tahoe-liquid-kde\n[Applications]\nOther=other-app\n')
    preset = json.loads((REPO / 'src/offline/kwin-effects/acrylic-glass/src/presets.json').read_text())[0]
    materials = {name: preset['values'] | preset.get('components', {}).get(name, {}) for name in surfaces.COMPONENTS}
    return data, config, state, materials


def test_component_apply_is_independent_repeatable_and_reversible(installed):
    data, config, state, materials = installed
    plasma = data / 'plasma/desktoptheme/MacTahoeLiquidKde-Light'
    dock = plasma / 'widgets/panel-background.svgz'
    original = dock.read_bytes()
    surfaces.apply(materials, data, config, state)
    assert dock.read_bytes() == original  # exact historical default, no SVG serialization
    assert surfaces.apply(materials, data, config, state) == []
    unrelated = (plasma / 'dialogs/background.svgz').read_bytes()
    changed = copy.deepcopy(materials)
    changed['dock']['SurfaceTransparencyLight'] = 65
    surfaces.apply(changed, data, config, state)
    dock_surface = plasma / "widgets/glass-dock.svgz"
    assert dock_surface.read_bytes() != original
    assert dock.read_bytes() == original  # The menu bar remains independent.
    assert (plasma / 'dialogs/background.svgz').read_bytes() == unrelated
    root = surfaces._read_svg(dock_surface.read_bytes())
    node = next(n for n in root.iter() if n.get('id') == 'center')
    assert any('0.35' in n.get('style', '') or n.get('opacity') == '0.35' for n in node.iter())
    assert surfaces.apply(changed, data, config, state) == []
    surfaces.apply(materials, data, config, state)
    assert dock.read_bytes() == original
    assert 'Other=other-app' in (config / 'Kvantum/kvantum.kvconfig').read_text()


def test_svg_clone_keeps_use_position_and_shared_border():
    source = b'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><defs><rect id="paint" width="30" height="30" fill="#fff" opacity="0.55"/></defs><use id="center" x="40" y="50" transform="scale(2)" xlink:href="#paint"/><use id="border" xlink:href="#paint"/></svg>'''
    root = surfaces._read_svg(surfaces.patch_svg(source, ('center',), 80))
    indexed = {n.get('id'): n for n in root.iter()}
    assert indexed['paint'].get('opacity') == '0.55'
    assert indexed['center'].get('transform') == 'scale(2) translate(40,50)'
    assert list(indexed['center'])[0].get('opacity') == '0.2'
    assert indexed['border'].tag.endswith('use')


def test_invalid_settings_and_write_failure_leave_assets_intact(installed, monkeypatch):
    data, config, state, materials = installed
    snapshots = {p: p.read_bytes() for root in (data, config) for p in root.rglob('*') if p.is_file()}
    invalid = copy.deepcopy(materials)
    invalid['dock']['SurfaceTransparencyLight'] = float('nan')
    with pytest.raises(ValueError):
        surfaces.apply(invalid, data, config, state)
    original_write = surfaces.atomic_write
    failures = []
    def fail_once(path, content):
        if path.name == 'assets.json' and not failures:
            failures.append(path)
            raise OSError('disk failure')
        original_write(path, content)
    monkeypatch.setattr(surfaces, 'atomic_write', fail_once)
    with pytest.raises(OSError):
        surfaces.apply(materials, data, config, state)
    assert all(p.read_bytes() == content for p, content in snapshots.items())
    assert {p for root in (data, config) for p in root.rglob('*') if p.is_file()} == set(snapshots)


def test_symlink_output_does_not_write_outside_owned_trees(installed, tmp_path):
    data, config, state, materials = installed
    outside = tmp_path / 'outside'
    outside.mkdir()
    (data / 'mac-tahoe-liquid-kde').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        surfaces.apply(materials, data, config, state)
    assert list(outside.iterdir()) == []


def test_uninstall_restores_owned_fills_but_keeps_external_edits(installed):
    data, config, state, materials = installed
    dock = data / "plasma/desktoptheme/MacTahoeLiquidKde-Light/widgets/panel-background.svgz"
    original = dock.read_bytes()
    materials["dock"]["SurfaceTransparencyLight"] = 65
    surfaces.apply(materials, data, config, state)
    external = config / "Kvantum/mac-tahoe-liquid-kdeDark/mac-tahoe-liquid-kdeDark.svg"
    external.write_bytes(external.read_bytes() + b"\n<!-- external edit -->")
    edited = external.read_bytes()
    surfaces.restore(data, config, state)
    assert dock.read_bytes() == original
    assert external.read_bytes() == edited
    assert json.loads((data / "mac-tahoe-liquid-kde/glass-surfaces/assets.json").read_text()) == {}
    assert "mac-tahoe-liquid-kdeFinder=" not in (config / "Kvantum/kvantum.kvconfig").read_text()


def test_live_component_apply_reloads_background_without_restart(installed, tmp_path, repo, launcher_popup_module):
    import os
    import subprocess
    import sys
    data, config, state, materials = installed
    (tmp_path / "materials.json").write_text(json.dumps(materials))
    (config / "plasmarc").write_text("[Theme]\nname=MacTahoeLiquidKde-Light\n")
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    env = {key: value for key, value in os.environ.items() if key in ("PATH", "LANG")}
    env.update(HOME=str(tmp_path), XDG_CONFIG_HOME=str(config), XDG_DATA_HOME=str(data),
               XDG_STATE_HOME=str(state), XDG_CACHE_HOME=str(tmp_path / "cache"),
               XDG_RUNTIME_DIR=str(runtime), QML_IMPORT_PATH=str(launcher_popup_module),
               QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
    result = subprocess.run(["dbus-run-session", "--", sys.executable,
                             str(repo / "tests/glass_live_probe.py"), str(repo)],
                            env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "LIVE_COMPONENT_SURFACE_OK" in result.stdout


@pytest.mark.parametrize("style,cycles", [("MacTahoe", True), ("kvantum-dark", True), ("Breeze", False)])
def test_qt_reload_uses_installed_style_under_transition_lock(tmp_path, style, cycles):
    switcher = tmp_path / "installed-switcher"
    marker = tmp_path / "reload.json"
    switcher.write_text("""from contextlib import contextmanager
import json
from pathlib import Path
locked = False
@contextmanager
def _theme_transition_lock():
    global locked
    locked = True
    try: yield
    finally: locked = False
def _kread(*args):
    assert locked, 'read before transition lock'
    return STYLE
def cycle_widget_style_live(value):
    assert locked, 'reload outside transition lock'
    Path(MARKER).write_text(json.dumps(value))
    return True
""".replace("STYLE", repr(style)).replace("MARKER", repr(str(marker))))
    assert surfaces.reload_qt_surfaces(switcher)
    assert marker.exists() == cycles
    if cycles:
        assert json.loads(marker.read_text()) == style


@pytest.mark.parametrize("layout", ["standalone", "nix"])
def test_reload_cli_resolves_installed_python_module(tmp_path, layout):
    import os
    import shutil
    import subprocess
    import sys
    helper = tmp_path / "libexec/glass_surface_settings.py"
    helper.parent.mkdir()
    shutil.copy2(Path(surfaces.__file__), helper)
    switcher = (helper.with_name("theme_switch.py") if layout == "nix"
                else tmp_path / ".local/bin/mac-tahoe-theme-switch")
    switcher.parent.mkdir(parents=True, exist_ok=True)
    marker = tmp_path / "reloaded"
    switcher.write_text("from contextlib import nullcontext\nfrom pathlib import Path\n"
        "_theme_transition_lock = nullcontext\n"
        "def _kread(*args): return 'MacTahoe'\n"
        "def cycle_widget_style_live(style):\n"
        "    Path(" + repr(str(marker)) + ").write_text(style)\n    return True\n")
    result = subprocess.run([sys.executable, str(helper), "--reload"],
                            env={**os.environ, "HOME": str(tmp_path)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert marker.read_text() == "MacTahoe"
