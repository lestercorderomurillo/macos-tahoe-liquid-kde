"""Executable user-data preservation across install, update and removal."""
from contextlib import ExitStack
from pathlib import Path
import shutil
from unittest.mock import patch

import pytest

import cli
import owned_assets as assets
from steps import fonts, icons, wallpapers


@pytest.fixture(autouse=True)
def private_state(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))


def copy_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


def copy_tree(source, target):
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, symlinks=True)
    return True


@pytest.mark.parametrize('tree', [False, True])
def test_install_update_and_uninstall_restores_preexisting_user_data(tmp_path, tree):
    source = tmp_path / 'source'; target = tmp_path / 'installed/asset'
    target.parent.mkdir()
    if tree:
        source.mkdir(); target.mkdir()
        (source / 'payload').write_text('project v1')
        (target / 'personal-photo').write_text('user data')
        copier = copy_tree
    else:
        source.write_text('project v1'); target.write_text('user font')
        copier = copy_file
    assets.install('test', source, target, copier)
    payload = source / 'payload' if tree else source
    payload.write_text('project v2')
    assets.install('test', source, target, copier)
    assert assets.remove_owned('test', target.parent) == 1
    assert (target / 'personal-photo' if tree else target).read_text() == ('user data' if tree else 'user font')
    if tree:
        assert not (target / 'payload').exists()


def test_uninstall_preserves_user_additions_and_modified_files(tmp_path):
    source = tmp_path / 'source'; source.mkdir(); (source / 'payload').write_text('project')
    target = tmp_path / 'installed/theme'
    target.parent.mkdir()
    assets.install('test', source, target, copy_tree)
    (target / 'personal').write_text('keep me')
    assert assets.remove_owned('test', target.parent) == 0
    assert (target / 'personal').read_text() == 'keep me'
    assets.install('test', source, target, copy_tree)
    assert assets.remove_owned('test', target.parent) == 1
    assert (target / 'personal').read_text() == 'keep me'


def test_unrecorded_prefix_matches_are_not_deleted(tmp_path, monkeypatch):
    for component, name in [(fonts, 'SFPro-UserPurchased.otf'),
                            (icons, 'MacTahoeLiquidKde-Icons-MyTheme/personal.svg'),
                            (wallpapers, 'MacTahoe-Landscape-99/personal.jpg')]:
        base = tmp_path / component.__name__; path = base / name
        path.parent.mkdir(parents=True); path.write_text('personal')
        monkeypatch.setattr(component, 'DEST_DIR', base)
        component.uninstall()
        assert path.read_text() == 'personal'


def test_failed_copy_does_not_claim_or_remove_original(tmp_path):
    source = tmp_path / 'source'; source.write_text('project')
    target = tmp_path / 'installed/font'; target.parent.mkdir(); target.write_text('user')
    with pytest.raises(OSError):
        assets.install('test', source, target, lambda *_: False)
    assert assets.remove_owned('test', target.parent) == 0
    assert target.read_text() == 'user'


def test_symlinked_parent_is_never_traversed(tmp_path):
    source = tmp_path / 'source'; source.write_text('project')
    external = tmp_path / 'external'; external.mkdir(); (external / 'font').write_text('user')
    base = tmp_path / 'installed'; base.symlink_to(external, target_is_directory=True)
    with pytest.raises(OSError):
        assets.install('test', source, base / 'font', copy_file)
    assert (external / 'font').read_text() == 'user'


def test_new_asset_removed_and_replaced_symlink_preserved(tmp_path):
    source = tmp_path / 'source'; source.write_text('project')
    base = tmp_path / 'installed';base.mkdir()
    for name in ['owned', 'modified']:
        assets.install('test', source, base / name, copy_file)
    (base / 'modified').unlink(); (base / 'modified').symlink_to(source)
    assert assets.remove_owned('test', base) == 1
    assert not (base / 'owned').exists()
    assert (base / 'modified').is_symlink() and source.read_text() == 'project'


@pytest.mark.parametrize('failure', ['apply', 'theme_switch', None])
def test_uninstall_stops_before_payload_removal_on_restore_failure(failure):
    calls = []
    def phase(feature, operation):
        calls.append((feature, operation))
        if feature == failure and operation == 'uninstall':
            cli.errors.append('injected restore failure')
            return False
        return True
    with ExitStack() as stack:
        replacements = dict(run_phase=phase, run_preflight=lambda *_: True,
            verify_plasma=lambda: True, check_cancelled=lambda: None,
            step_exists=lambda _: True, should_process=lambda *_: True,
            step=lambda *a, **k: None, note=lambda *_: None,
            progress_event=lambda *a, **k: None, _print_done=lambda *_: None,
            INSTALL_ORDER=['fonts'])
        for name, value in replacements.items():
            stack.enter_context(patch.object(cli, name, value))
        stack.enter_context(patch.object(cli, 'errors', []))
        assert cli._run_uninstall_steps({}) == int(failure is not None)
    assert (('fonts', 'uninstall') in calls) == (failure is None)


def test_multiple_user_versions_remain_identifiable_after_restore(tmp_path):
    import json
    source = tmp_path / 'source'; source.write_text('project')
    target = tmp_path / 'installed/font';target.parent.mkdir();target.write_text('original user font')
    assets.install('test', source, target, copy_file)
    target.write_text('later user edit')
    assets.install('test', source, target, copy_file)
    assert assets.remove_owned('test', target.parent) == 1
    assert target.read_text() == 'later user edit'
    _, root, record = assets._entry('test', target)
    recovery = json.loads(record.with_suffix('.recovery').read_text())
    assert recovery['target'] == str(target)
    assert (root / recovery['backups'][0]).read_text() == 'original user font'


def test_corrupt_record_cannot_escape_destination(tmp_path):
    import json
    base = tmp_path / 'installed';base.mkdir()
    victim = tmp_path / 'user-file';victim.write_text('personal')
    _, root, record = assets._entry('test', base / 'owned')
    root.mkdir(parents=True)
    record.write_text(json.dumps({'target':str(base / '..' / 'user-file'),
                                 'fingerprint':assets.fingerprint(victim)}))
    with pytest.raises(ValueError, match='escapes'):
        assets.remove_owned('test', base)
    assert victim.read_text() == 'personal'
