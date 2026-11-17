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
