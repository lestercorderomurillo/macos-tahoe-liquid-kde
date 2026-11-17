"""Successful installation reclaims only its own disposable compiler intermediates."""
import hashlib
from pathlib import Path
import shutil
import subprocess

import pytest

import cli
from steps import _native_build as native


@pytest.mark.parametrize('outcome', ['success', 'failure', 'cancel'])
def test_real_build_install_cleanup_and_reinstall(tmp_path, monkeypatch, outcome):
    if not all(shutil.which(tool) for tool in ('cmake', 'make', 'c++')):
        pytest.skip('Native build tools unavailable')
    source = tmp_path / 'source'; source.mkdir()
    (source / 'CMakeLists.txt').write_text(
        'cmake_minimum_required(VERSION 3.16)\nproject(probe LANGUAGES CXX)\n'
        'add_executable(probe main.cpp)\n')
    (source / 'main.cpp').write_text('int main() { return 0; }\n')
    build = tmp_path / 'build'
    installed = tmp_path / 'installed'
    hashes = []

    def install(_):
        assert native.cmake_build(source, build, 'probe')
        assert list(build.rglob('main.cpp.o'))
        (build / 'make-build.log').write_text('diagnostic evidence')
        shutil.copy2(build / 'probe', installed)
        hashes.append(hashlib.sha256(installed.read_bytes()).hexdigest())
        if outcome == 'cancel':
            raise KeyboardInterrupt
        return int(outcome == 'failure')

    monkeypatch.setattr(cli, '_run_install_steps', install)
    if outcome == 'cancel':
        with pytest.raises(KeyboardInterrupt):
            cli._run_install_body({})
    else:
        assert cli._run_install_body({}) == int(outcome == 'failure')
    assert bool(list(build.rglob('main.cpp.o'))) == (outcome != 'success')
    assert (build / 'make-build.log').read_text() == 'diagnostic evidence'
    assert (build / 'CMakeCache.txt').is_file()
    assert subprocess.run([str(installed)]).returncode == 0
    assert hashlib.sha256((build / 'probe').read_bytes()).hexdigest() == hashes[0]
    if outcome == 'success':
        assert cli._run_install_body({}) == 0
        assert hashes[0] == hashes[1]
        assert not list(build.rglob('main.cpp.o'))
    assert native._install_builds.get() is None


def test_cleanup_preserves_changed_foreign_and_linked_files(tmp_path):
    build = tmp_path / 'build'; objects = build / 'CMakeFiles/probe.dir'
    objects.mkdir(parents=True)
    stamp = build / '.mttkde-source-sha256'; stamp.write_text('ours')
    for name in ('remove.o', 'changed.o', 'linked.o', 'keep.so', 'build.log'):
        (objects / name).write_text('evidence')
    (build / 'unmanaged.o').write_text('user data')
    outside = tmp_path / 'outside'; outside.mkdir()
    (outside / 'foreign.o').write_text('foreign')
    (objects / 'symlink.o').symlink_to(outside / 'foreign.o')
    import os
    os.link(objects / 'linked.o', outside / 'hardlink')
    (objects / 'foreign-dir').symlink_to(outside, target_is_directory=True)
    with native.installation_build_cleanup() as cleanup:
        native._record_build_objects(build, 'ours')
        (objects / 'changed.o').write_text('new build output')
        assert cleanup() > 0
    assert not (objects / 'remove.o').exists()
    for name in ('changed.o', 'linked.o', 'keep.so', 'build.log', 'symlink.o'):
        assert (objects / name).exists()
    assert (build / 'unmanaged.o').read_text() == 'user data'
    assert (outside / 'foreign.o').read_text() == 'foreign'
    with native.installation_build_cleanup() as cleanup:
        native._record_build_objects(build, 'ours')
        stamp.unlink()  # Another build has started and invalidated the success marker.
        assert cleanup() == 0
    assert (objects / 'changed.o').exists()


@pytest.mark.parametrize('outcome', [0, 1])
def test_previous_successful_build_cleaned_when_component_reused(tmp_path, monkeypatch, outcome):
    if not all(shutil.which(tool) for tool in ('cmake', 'make', 'c++')):
        pytest.skip('Native build tools unavailable')
    monkeypatch.setenv('BUILD', str(tmp_path / 'build'))
    monkeypatch.setenv('OFFLINE', str(tmp_path / 'offline'))
    source = tmp_path / 'offline/menu-style'; source.mkdir(parents=True)
    (source / 'CMakeLists.txt').write_text(
        'cmake_minimum_required(VERSION 3.16)\nproject(probe LANGUAGES CXX)\n'
        'add_executable(probe main.cpp)\n')
    (source / 'main.cpp').write_text('int main() { return 0; }\n')
    build = tmp_path / 'build/menu-style'
    assert native.cmake_build(source, build, 'previous installation')
    assert list(build.rglob('*.o'))
    before = hashlib.sha256((build / 'probe').read_bytes()).hexdigest()
    # The current transaction reuses installed payloads, never calling cmake_build.
    monkeypatch.setattr(cli, '_run_install_steps', lambda _: outcome)
    assert cli._run_install_body({}) == outcome
    assert bool(list(build.rglob('*.o'))) == bool(outcome)
    assert hashlib.sha256((build / 'probe').read_bytes()).hexdigest() == before
    assert (build / 'CMakeCache.txt').is_file()


@pytest.mark.parametrize('guard', ['foreign-source', 'incomplete', 'symlink', 'changed-stamp'])
def test_previous_build_ownership_and_success_guards(tmp_path, monkeypatch, guard):
    monkeypatch.setenv('BUILD', str(tmp_path / 'build'))
    monkeypatch.setenv('OFFLINE', str(tmp_path / 'offline'))
    source = tmp_path / 'offline/menu-style'
    build = tmp_path / 'build/menu-style'
    obj = build / 'CMakeFiles/probe.dir/old.o'; obj.parent.mkdir(parents=True)
    obj.write_bytes(b'old compiler output')
    marker = build / '.mttkde-source-sha256'; marker.write_text('a' * 64)
    (build / 'CMakeCache.txt').write_text(f'CMAKE_HOME_DIRECTORY:INTERNAL={source}\n')
    if guard == 'foreign-source':
        (build / 'CMakeCache.txt').write_text('CMAKE_HOME_DIRECTORY:INTERNAL=/foreign/project\n')
    elif guard == 'incomplete':
        marker.unlink()
    elif guard == 'symlink':
        other = tmp_path / 'other'; build.rename(other); build.symlink_to(other, target_is_directory=True)
    with native.installation_build_cleanup() as cleanup:
        if guard == 'changed-stamp':
            marker.write_text('b' * 64)
        assert cleanup() == 0
    assert obj.read_bytes() == b'old compiler output'


def test_cleanup_preserves_active_legacy_build(tmp_path):
    build = tmp_path / 'build'; objects = build / 'CMakeFiles/probe.dir'
    objects.mkdir(parents=True)
    obj = objects / 'active.o'; obj.write_bytes(b'compiler output')
    (build / '.mttkde-source-sha256').write_text('ours')
    process = subprocess.Popen(['sleep', '60'], cwd=build)
    try:
        with native.installation_build_cleanup() as cleanup:
            native._record_build_objects(build, 'ours')
            assert cleanup() == 0
        assert obj.exists()
    finally:
        process.terminate(); process.wait()
