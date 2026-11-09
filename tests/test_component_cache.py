"""Incremental payload installation must never conceal changed or missing data."""
import json
import shutil

import pytest
import component_manifest  # Bind real hashing before any per-test replacement.

from component_cache import Receipt, fingerprint, identical, identity


def test_content_not_timestamp_and_links(tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    (source / 'file').write_text('a')
    (source / 'alias').symlink_to('file')
    target = tmp_path / 'target'
    shutil.copytree(source, target, symlinks=True)
    assert identical(source, target)
    original = fingerprint(source)
    (source / 'file').touch()
    assert fingerprint(source) == original
    (source / 'alias').unlink(); (source / 'alias').symlink_to('elsewhere')
    assert not identical(source, target)
    (source / 'alias').unlink(); (source / 'alias').symlink_to('file')
    (source / 'file').chmod(0o700)
    assert not identical(source, target)


def test_receipt_requires_matching_inputs_and_complete_output(tmp_path):
    artifact = tmp_path / 'installed'; artifact.mkdir()
    (artifact / 'payload').write_text('one')
    receipt = Receipt('launcher', 'one', tmp_path / 'receipts')
    assert not receipt.current([artifact])
    receipt.save([artifact])
    assert receipt.current([artifact])
    assert not Receipt('launcher', 'two', tmp_path / 'receipts').current([artifact])
    assert not Receipt('dock', 'one', tmp_path / 'receipts').current([artifact])
    (artifact / 'payload').unlink()
    assert not receipt.current([artifact])
    receipt.path.write_text('{broken')
    assert not receipt.current([artifact])
    receipt.invalidate()
    assert not receipt.path.exists()


def test_component_changes_do_not_invalidate_other_payloads(tmp_path):
    launcher, dock = tmp_path / 'launcher', tmp_path / 'dock'
    launcher.write_text('one'); dock.write_text('one')
    first = identity([('dock', dock)], {'color': 'blue'})
    launcher.write_text('two')
    assert identity([('dock', dock)], {'color': 'blue'}) == first
    assert identity([('dock', dock)], {'color': 'red'}) != first


def test_unchanged_tree_preserves_inode_and_repairs_deletion(tmp_path, monkeypatch):
    from steps._helpers import install_tree
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    source = tmp_path / 'source'; source.mkdir()
    (source / 'payload').write_text('same')
    target = tmp_path / 'target'
    shutil.copytree(source, target)
    inode = (target / 'payload').stat().st_ino
    assert install_tree(source, target)
    assert (target / 'payload').stat().st_ino == inode
    (target / "payload").unlink()
    assert install_tree(source, target)
    assert (target / "payload").read_text() == "same"


def test_icon_reinstall_skips_generation_but_changed_choices_and_damage_repair(monkeypatch, tmp_path):
    import steps.icons as icons
    import installer_choices
    import component_cache
    import component_manifest  # Import before replacing its dependency in this test.
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
    monkeypatch.setattr(icons, 'DEST_DIR', tmp_path / 'icons')
    # Use the real recipe graph and identities with a tiny offline payload.
    import paths
    source = tmp_path / 'source'
    scripts = source / 'src/scripts'
    shutil.copytree(paths.REPO_ROOT / 'src/scripts', scripts,
                    ignore=shutil.ignore_patterns('__pycache__'))
    offline = source / 'src/offline/icons'
    offline.mkdir(parents=True)
    artwork = offline / 'base.svg'
    artwork.write_text('original artwork')
    monkeypatch.setattr(paths, 'REPO_ROOT', source)
    monkeypatch.setattr(icons, 'OFFLINE_DIR', offline)
    options = {'icons': 'regular', 'color': 'blue'}
    monkeypatch.setattr(installer_choices, 'selected', lambda: options)
    calls = []
    def generate():
        calls.append(1)
        names = [*icons._THEME_NAMES, 'MacTahoeLiquidKde-Icons-Regular-Light', 'MacTahoeLiquidKde-Icons-Regular-Dark']
        for name in names:
            path = icons.DEST_DIR / name
            path.mkdir(parents=True, exist_ok=True)
            (path / 'index.theme').write_text('generated')
    monkeypatch.setattr(icons, '_install_payload', generate)
    icons.install(); icons.install()
    assert len(calls) == 1
    options['color'] = 'red'
    icons.install()
    assert len(calls) == 2
    (icons.DEST_DIR / icons._THEME_NAMES[0] / 'index.theme').unlink()
    icons.install()
    assert len(calls) == 3
    native = scripts / 'steps/_native_build.py'
    native.write_text(native.read_text() + '\nNATIVE_RECIPE_REVISION = 2\n')
    icons.install()
    assert len(calls) == 3  # Compiler-only changes do not regenerate icons.
    shared = scripts / 'steps/_helpers.py'
    shared.write_text(shared.read_text() + '\nCOPY_RECIPE_REVISION = 2\n')
    icons.install()
    assert len(calls) == 4  # Installation recipe changes still invalidate.
    artwork.write_text('changed artwork')
    icons.install()
    assert len(calls) == 5
    generator = scripts / 'icon_toolset.py'
    generator.write_text(generator.read_text() + '\nRENDERER_REVISION = 2\n')
    icons.install()
    assert len(calls) == 6


def test_icon_failure_never_marks_success(monkeypatch, tmp_path):
    import steps.icons as icons
    import component_cache
    import log
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
    monkeypatch.setattr(component_cache, 'identity', lambda *args: 'key')
    monkeypatch.setattr(icons, 'DEST_DIR', tmp_path / 'icons')
    def fail():
        raise RuntimeError('generation interrupted')
    monkeypatch.setattr(icons, '_install_payload', fail)
    with pytest.raises(RuntimeError):
        icons.install()
    assert not list((tmp_path / 'state').rglob('*.json'))


def test_capture_rejects_focus_identity_or_geometry_change():
    from release_screenshots import verify_focused_frame
    window = dict(id='one', caption='Documents', type=0, resourceClass='org.gnome.Nautilus',
                  active=True, geometry=dict(x=10, y=10, width=100, height=100))
    assert verify_focused_frame([window], [window], 'org.gnome.Nautilus') == window
    for changed in (dict(active=False), dict(id='two'), dict(geometry={}), dict(resourceClass='org.kde.dolphin')):
        with pytest.raises(ValueError):
            verify_focused_frame([window], [window | changed], 'org.gnome.Nautilus')
    with pytest.raises(ValueError):
        verify_focused_frame([window], [window, window], 'org.gnome.Nautilus')


def test_committed_component_hashes_match_sources():
    from component_manifest import snapshot
    from paths import REPO_ROOT
    assert json.loads((REPO_ROOT / 'component-hashes.json').read_text()) == snapshot()


@pytest.mark.parametrize("launcher", ["absent", "auto", "explicit"])
def test_native_build_reuses_objects_and_rebuilds_changed_source(tmp_path, monkeypatch, launcher):
    import shutil
    import subprocess
    from steps._native_build import cmake_build
    if not all(shutil.which(tool) for tool in ('cmake', 'make', 'c++')):
        pytest.skip('Native build tools are unavailable')
    import shlex
    import steps._native_build as helpers
    find_tool = shutil.which
    wrappers = {}
    for name in ('auto', 'explicit'):
        wrapper = tmp_path / name
        log = tmp_path / (name + '.log')
        wrapper.write_text('#!/bin/sh\nprintf "called\\n" >> ' + shlex.quote(str(log)) + '\nexec "$@"\n')
        wrapper.chmod(0o755)
        wrappers[name] = wrapper
    monkeypatch.setattr(helpers.shutil, 'which', lambda tool: (
        str(wrappers['auto']) if launcher != 'absent' else None
    ) if tool == 'ccache' else find_tool(tool))
    monkeypatch.delenv('CMAKE_CXX_COMPILER_LAUNCHER', raising=False)
    if launcher == 'explicit':
        monkeypatch.setenv('CMAKE_CXX_COMPILER_LAUNCHER', str(wrappers['explicit']))
    source = tmp_path / 'source'; source.mkdir()
    (source / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.16)\nproject(probe LANGUAGES CXX)\nadd_executable(probe main.cpp)\n')
    code = source / 'main.cpp'
    code.write_text('int main() { return 0; }\n')
    build = tmp_path / 'build'
    assert cmake_build(source, build, 'probe')
    obj = next(build.rglob('main.cpp.o'))
    stamp = obj.stat().st_mtime_ns
    assert cmake_build(source, build, 'probe')
    assert obj.stat().st_mtime_ns == stamp
    code.write_text('int main() { return 3; }\n')
    import os
    os.utime(code, (1, 1))  # Archives can restore older mtimes despite changed bytes.
    assert cmake_build(source, build, 'probe')
    assert subprocess.run([str(build / 'probe')]).returncode == 3
    if launcher != 'absent':
        assert (tmp_path / (launcher + '.log')).read_text().count('called') >= 2
    if launcher == 'explicit':
        assert not (tmp_path / 'auto.log').exists()


def test_source_ledger_uses_git_modes_but_runtime_checks_real_permissions(tmp_path):
    source = tmp_path / 'source'; source.mkdir(mode=0o700)
    target = tmp_path / 'target'; target.mkdir(mode=0o755)
    assert fingerprint(source, portable=True) == fingerprint(target, portable=True)
    assert fingerprint(source) != fingerprint(target)


def test_installer_file_previews_keep_verified_focus_and_hashes():
    import hashlib
    from paths import REPO_ROOT
    from release_screenshots import verify_focused_frame
    folder = REPO_ROOT / 'src/installer/assets'
    sources = json.loads((folder / 'sources.json').read_text())
    for manager, resource in (('nautilus', 'org.gnome.Nautilus'), ('dolphin', 'org.kde.dolphin')):
        for mode in ('light', 'dark'):
            record = sources[f'{manager}-{mode}.jpg']
            assert record['reviewed'] and record['stable_frames']
            verify_focused_frame(record['before'], record['after'], resource)
            assert hashlib.sha256((folder / record['file']).read_bytes()).hexdigest() == record['sha256']


def test_icon_uninstall_invalidates_receipt_even_without_payload(monkeypatch, tmp_path):
    import steps.icons as icons
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
    monkeypatch.setattr(icons, 'DEST_DIR', tmp_path / 'icons')
    artifact = tmp_path / 'old'; artifact.write_text('old')
    receipt = Receipt('icons', 'old')
    receipt.save([artifact])
    icons.uninstall()
    assert not receipt.path.exists()
