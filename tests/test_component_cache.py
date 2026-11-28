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
    for name in component_manifest.ICON_NOTICES:
        (source / name).write_text(name)
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
    switcher = scripts / 'theme_switch.py'
    switcher.write_text(switcher.read_text() + '\n# scheduled login fix\n')
    icons.install()
    assert len(calls) == 6
    (source / 'NOTICE').write_text('revised notice')
    icons.install()
    assert len(calls) == 7


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
    shared = tmp_path / 'shared'; shared.mkdir()
    header = shared / 'result.h'; header.write_text('#define RESULT 0\n')
    code.write_text('#include "' + str(header) + '"\nint main() { return RESULT; }\n')
    def build_probe():
        return cmake_build(source, build, 'probe', extra_sources=(shared,))
    assert build_probe()
    obj = next(build.rglob('main.cpp.o'))
    stamp = obj.stat().st_mtime_ns
    assert build_probe()
    assert obj.stat().st_mtime_ns == stamp
    header.write_text('#define RESULT 2\n')
    import os
    os.utime(header, (1, 1))
    assert build_probe()
    assert subprocess.run([str(build / 'probe')]).returncode == 2
    code.write_text('int main() { return 3; }\n')
    import os
    os.utime(code, (1, 1))  # Archives can restore older mtimes despite changed bytes.
    assert build_probe()
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


def test_desktop_control_shared_views_and_native_regions_invalidate_satellites(tmp_path):
    scripts = tmp_path / 'src/scripts/steps'; scripts.mkdir(parents=True)
    (scripts / 'plasmoids.py').write_text('')
    (scripts / 'globalmenu.py').write_text('')
    packages = tmp_path / 'src/offline/plasmoids'; packages.mkdir(parents=True)
    names = ['org.kde.mac-tahoe-liquid-kde.' + suffix for suffix in
             ('controlcenter', 'battery', 'wifi', 'notifications', 'unrelated')]
    for name in names:
        path = packages / name; path.mkdir(); (path / 'view.qml').write_text('original')
    native = packages / 'org.kde.mac.tahoe.liquid.taskmanager/launcher'
    native.mkdir(parents=True); (native / 'controlglass.cpp').write_text('original')
    menu = packages / 'org.kde.mac.tahoe.liquid.globalmenu'
    menu.mkdir(); (menu / 'AboutWindow.qml').write_text('original')
    first = component_manifest.snapshot(tmp_path)["components"]
    (packages / names[0] / 'view.qml').write_text('updated shared view')
    second = component_manifest.snapshot(tmp_path)["components"]
    for name in names[:4]:
        assert first['plasmoids/' + name] != second['plasmoids/' + name]
    assert first['plasmoids/' + names[-1]] == second['plasmoids/' + names[-1]]
    (native / 'controlglass.cpp').write_text('updated native region')
    third = component_manifest.snapshot(tmp_path)["components"]
    assert second['plasmoids/' + menu.name] != third['plasmoids/' + menu.name]
    for name in names[:4]:
        assert second['plasmoids/' + name] != third['plasmoids/' + name]
    assert second['plasmoids/' + names[-1]] == third['plasmoids/' + names[-1]]


def test_shared_launcher_sources_invalidate_launcher_and_controls_only(tmp_path):
    root = tmp_path / 'source'
    widgets = root / 'src/offline/plasmoids'
    controls = widgets / 'org.kde.mac-tahoe-liquid-kde.controlcenter'
    menu = controls / 'contents/ui/MacOptionsMenu.qml'
    menu.parent.mkdir(parents=True)
    menu.write_text('import QtQuick\nItem {}\n')
    for name in ('launcher', 'notifications', 'wifi', 'battery', 'trashcan'):
        folder = widgets / ('org.kde.mac-tahoe-liquid-kde.' + name)
        folder.mkdir(parents=True)
        (folder / 'metadata.json').write_text('{}')
    (widgets / 'org.kde.mac.tahoe.liquid.taskmanager/launcher').mkdir(parents=True)
    scripts = root / 'src/scripts'
    scripts.mkdir(parents=True)
    before = component_manifest.snapshot(root)['components']
    menu.write_text(menu.read_text() + '\n// Updated shared source\n')
    after = component_manifest.snapshot(root)['components']
    for name in ('launcher', 'controlcenter', 'notifications', 'wifi', 'battery'):
        key = 'plasmoids/org.kde.mac-tahoe-liquid-kde.' + name
        assert before[key] != after[key]
    key = 'plasmoids/org.kde.mac-tahoe-liquid-kde.trashcan'
    assert before[key] == after[key]


def test_every_component_detects_changed_and_unchanged_inputs(tmp_path):
    from paths import REPO_ROOT
    from component_manifest import component_inputs, snapshot

    # Mirror the shipped component topology with small editable payloads.
    # Run the production discovery and hashing code after every edit.
    recorded = json.loads((REPO_ROOT / 'component-hashes.json').read_text())['components']
    for _, inputs in component_inputs(REPO_ROOT):
        for _, path in inputs:
            local = tmp_path / path.relative_to(REPO_ROOT)
            if path.is_dir():
                local.mkdir(parents=True, exist_ok=True)
            else:
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_text('value = 1\n')

    def hashes():
        return snapshot(tmp_path)['components']

    baseline = hashes()
    assert baseline.keys() == recorded.keys()
    assert hashes() == baseline
    for name in baseline:
        if name.startswith('recipe/'):
            primary = tmp_path / 'src/scripts/steps' / (name.split('/')[1] + '.py')
        else:
            primary = tmp_path / 'src/offline' / name
        file = primary / 'changed-asset' if primary.is_dir() else primary
        previous = file.read_bytes() if file.exists() else None
        file.write_bytes(b'value = 2\n')
        changed = hashes()
        assert changed[name] != baseline[name], name
        independent = 'clipboard' if name in ('fonts', 'recipe/fonts') else 'fonts'
        assert changed[independent] == baseline[independent], name
        if previous is None:
            file.unlink()
        else:
            file.write_bytes(previous)
    assert hashes() == baseline


def test_cursor_archive_failure_preserves_live_theme(tmp_path, monkeypatch):
    from steps import cursors
    monkeypatch.setattr(cursors, "OFFLINE_DIR", tmp_path)
    monkeypatch.setattr(cursors, "DEST_DIR", tmp_path / "installed")
    monkeypatch.setattr(cursors, "fail", lambda message: errors.append(message))
    errors = []
    tarball = tmp_path / "MacTahoeLiquidKde-Cursors.tar.zst"
    tarball.write_bytes(b"incomplete")
    theme = cursors.DEST_DIR / cursors.THEMES[0]
    theme.mkdir(parents=True)
    (theme / "index.theme").write_text("previous")
    cursors.install()
    assert errors and (theme / "index.theme").read_text() == "previous"
    personal = cursors.DEST_DIR / "MacTahoeLiquidKde-personal"
    personal.mkdir()
    cursors.uninstall()
    assert personal.is_dir() and not theme.exists()
