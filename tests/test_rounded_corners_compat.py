"""Fail-closed, repeatable backport application to the pinned online source."""
import os
import shutil
import tarfile
from pathlib import Path

import pytest
from rounded_corners_compat import apply
from steps import rounded_corners as rounded


def test_unexpected_source_aborts_before_any_write(tmp_path):
    source = tmp_path / 'src'
    source.mkdir()
    shader = source / 'Shader.cpp'
    shader.write_text('// An incompatible future upstream source.\n')
    before = shader.read_bytes()
    with pytest.raises(ValueError, match='does not match'):
        apply(tmp_path)
    assert shader.read_bytes() == before


def test_build_does_not_compile_an_unpatched_source(tmp_path, monkeypatch):
    (tmp_path / 'CMakeLists.txt').touch()
    monkeypatch.setattr(rounded, 'SOURCE', tmp_path)
    failures = []
    monkeypatch.setattr(rounded, 'fail', failures.append)
    monkeypatch.setattr(rounded, 'cmake_build', lambda *a: pytest.fail('unsafe build'))
    rounded.build()
    assert len(failures) == 1
    assert 'compatibility patch failed' in failures[0]


@pytest.mark.skipif(not os.environ.get('MTTKDE_ROUNDED_CORNERS_ARCHIVE'),
                    reason='requires the verified upstream release archive')
def test_patch_applies_to_pinned_release_and_is_idempotent(tmp_path):
    archive = Path(os.environ['MTTKDE_ROUNDED_CORNERS_ARCHIVE'])
    assert rounded._archive_is_valid(archive)
    with tarfile.open(archive) as tar:
        tar.extractall(tmp_path, filter='data')
    source = tmp_path / f'KDE-Rounded-Corners-{rounded.UPSTREAM_VERSION}'
    apply(source)
    first = {p: p.read_bytes() for p in source.rglob('*') if p.is_file()}
    apply(source)
    assert all(p.read_bytes() == data for p, data in first.items())
    # Uninstall removes exactly the locales the pinned release installs.
    assert {p.parent.name for p in source.glob('po/*/kcmcorners.po')} == set(rounded.LOCALES)
    # The 6.8 orientation detection now comes from upstream itself (#103).
    assert 'ShaderTrait::RoundedCorners' in (source / 'src/Shader.cpp').read_text()
    assert 'dFdy(position0.y)' in (source / 'src/shaders/variables.glsl').read_text()
    effect = (source / 'src/Effect.cpp').read_text()
    assert effect.count('_mttkde_corner_shape_v1') == 3
    assert 'kwindow->isDesktop()' in (source / 'src/WindowManager.cpp').read_text()
    assert '!w->isDesktop() && !w->isDock()' in (source / 'src/Window.cpp').read_text()
    # A damaged later file must not partially patch an earlier one.
    shutil.rmtree(source)
    with tarfile.open(archive) as tar:
        tar.extractall(tmp_path, filter='data')
    (source / 'src/Effect.cpp').write_text('unexpected')
    original = (source / 'src/WindowManager.cpp').read_bytes()
    with pytest.raises(ValueError):
        apply(source)
    assert (source / 'src/WindowManager.cpp').read_bytes() == original
