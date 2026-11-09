"""Conflict handoff uses real KConfig in a private HOME; never touches live KWin."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


def test_common_competitor_ids_match_upstream_plugin_names():
    from steps import acrylic_glass as g
    assert {"blur", "glass", "glass_x11", "forceblur", "forceblur_x11",
            "better_blur_dx", "better_blur_dx_woapi"} <= set(g.CONFLICTING_BLURS)
    assert "liquidglass" not in g.CONFLICTING_BLURS
    assert "kwin4_effect_shapecorners" not in g.CONFLICTING_BLURS


def probe(tmp_path, script):
    if not all(shutil.which(tool) for tool in ('kwriteconfig6', 'kreadconfig6')):
        pytest.skip('KConfig CLI required')
    config = tmp_path / 'config'
    config.mkdir()
    (config / 'kwinrc').write_text('[Plugins]\nblurEnabled=true\nglassEnabled=false\notherEffectEnabled=true\n')
    env = {key: value for key, value in os.environ.items() if key in ('PATH', 'LANG')}
    env.update(HOME=str(tmp_path), XDG_CONFIG_HOME=str(config),
               XDG_CONFIG_DIRS=str(tmp_path / 'system'), XDG_STATE_HOME=str(tmp_path / 'state'),
               PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src/scripts'))
    result = subprocess.run([sys.executable, '-c', '''
from steps import acrylic_glass as g
from pathlib import Path
import json
g.qdbus_call = lambda *args: True
g._loaded_effects = lambda: set()
''' + script], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_disable_reinstall_and_restore_original_values(tmp_path):
    probe(tmp_path, '''
assert g._disable_conflicting_blurs()
assert all(g._plugin_setting(effect) == 'false' for effect in g.CONFLICTING_BLURS)
saved = g._conflict_state_path().read_bytes()
assert g._disable_conflicting_blurs()
assert g._conflict_state_path().read_bytes() == saved
# Preserve an unrelated effect and a subsequent explicit user edit.
assert g._plugin_setting('otherEffect') == 'true'
assert g.kw_write('--file', 'kwinrc', '--group', 'Plugins', '--key', 'betterblurEnabled', 'true')
g._restore_conflicting_blurs()
assert g._plugin_setting('blur') == 'true'
assert g._plugin_setting('glass') == 'false'
assert g._plugin_setting('forceblur') is None
assert g._plugin_setting('betterblur') == 'true'
assert not g._conflict_state_path().exists()
''')


@pytest.mark.parametrize('effect', ['glass', 'glass_x11', 'forceblur', 'forceblur_x11',
                                   'better_blur_dx', 'better_blur_dx_woapi'])
def test_enabled_common_competitor_is_disabled_and_restored(tmp_path, effect):
    probe(tmp_path, f'''
effect = {effect!r}
assert g.kw_write('--file', 'kwinrc', '--group', 'Plugins', '--key', effect + 'Enabled', 'true')
assert g._disable_conflicting_blurs()
assert g._plugin_setting(effect) == 'false'
assert g._read_conflict_state(g._conflict_state_path())[effect] == 'true'
g._restore_conflicting_blurs()
assert g._plugin_setting(effect) == 'true'
''')


def test_still_loaded_competitor_rolls_back(tmp_path):
    probe(tmp_path, '''
g._loaded_effects = lambda: {'blur', 'unrelated-effect'}
assert not g._disable_conflicting_blurs()
assert g._plugin_setting('blur') == 'true'
assert g._plugin_setting('glass') == 'false'
assert g._plugin_setting('forceblur') is None
''')


def test_failed_disable_rolls_back_completed_writes(tmp_path):
    probe(tmp_path, '''
write = g.kw_write
failed = False
def fail_once(*args):
    global failed
    if 'betterblurEnabled' in args and not failed:
        failed = True
        return False
    return write(*args)
g.kw_write = fail_once
assert not g._disable_conflicting_blurs()
assert g._plugin_setting('blur') == 'true'
assert g._plugin_setting('glass') == 'false'
assert g._plugin_setting('forceblur') is None
''')


def test_failed_build_does_not_disable_any_effect(monkeypatch):
    from steps import acrylic_glass as g
    monkeypatch.setattr(g, 'kw_write', lambda *args: pytest.fail('Build changed KWin configuration'))
    monkeypatch.setattr(g, 'qdbus_call', lambda *args: pytest.fail('Build changed live KWin'))
    def failed_build(*args):
        raise RuntimeError('Compiler failed')
    monkeypatch.setattr(g, 'cmake_build', failed_build)
    with pytest.raises(RuntimeError, match='Compiler failed'):
        g.build()


@pytest.mark.parametrize('files,style,expected', [('nautilus', 'classic', '0'),
                                               ('nautilus', 'tinted', '1'),
                                               ('dolphin', 'tinted', None),
                                               ('keep', 'tinted', None)])
def test_backing_choice_is_scoped_to_nautilus_install(monkeypatch, files, style, expected):
    from steps import acrylic_glass as g
    from installer_choices import defaults
    monkeypatch.setattr(g, 'selected', lambda: defaults() | dict(files=files, glass_style=style))
    writes = []
    monkeypatch.setattr(g, 'kw_write', lambda *args: writes.append(args) or True)
    assert g._install_backing_tint()
    assert [args[-1] for args in writes] == ([] if expected is None else [expected])


def test_corrupt_recovery_state_stops_before_changing_settings(tmp_path):
    probe(tmp_path, '''
path = g._conflict_state_path()
path.parent.mkdir(parents=True)
path.write_text('[]')
assert not g._disable_conflicting_blurs()
assert g._plugin_setting('blur') == 'true'
assert g._plugin_setting('glass') == 'false'
assert g._plugin_setting('forceblur') is None
''')


def test_restore_does_not_enable_competitors_while_glass_remains_loaded(tmp_path):
    probe(tmp_path, '''
assert g._disable_conflicting_blurs()
saved = g._conflict_state_path().read_bytes()
g._loaded_effects = lambda: {'liquidglass'}
g._restore_conflicting_blurs()
assert g._plugin_setting('blur') == 'false'
assert g._conflict_state_path().read_bytes() == saved
''')


def test_unverifiable_live_handoff_stops_and_preserves_recovery(tmp_path):
    probe(tmp_path, '''
g._loaded_effects = lambda: None
assert not g._disable_conflicting_blurs()
saved = g._conflict_state_path().read_bytes()
assert g._plugin_setting('blur') == 'false'
g._restore_conflicting_blurs()
assert g._conflict_state_path().read_bytes() == saved
assert g._plugin_setting('blur') == 'false'
g._loaded_effects = lambda: set()
g._restore_conflicting_blurs()
assert g._plugin_setting('blur') == 'true'
assert not g._conflict_state_path().exists()
''')
