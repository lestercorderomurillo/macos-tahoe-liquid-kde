"""Reinstalling fonts must not invalidate files mapped by the running desktop."""

import mmap

import pytest

from steps import fonts


def test_reinstall_preserves_mapped_font_and_skips_identical_copy(tmp_path):
    source = tmp_path / "source.ttf"
    target = tmp_path / "installed.ttf"
    old = b"old font" * 1024
    new = b"new font" * 2048
    source.write_bytes(new)
    target.write_bytes(old)
    with target.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
        old_inode = target.stat().st_ino
        assert fonts._copy_font(source, target)
        assert target.stat().st_ino != old_inode
        assert mapped[:] == old
        assert target.read_bytes() == new
        installed = target.stat()
        assert not fonts._copy_font(source, target)
        assert target.stat().st_ino == installed.st_ino
        assert target.stat().st_mtime_ns == installed.st_mtime_ns
    assert sorted(path.name for path in tmp_path.iterdir()) == ["installed.ttf", "source.ttf"]


@pytest.mark.parametrize("operation", ["copy", "replace"])
def test_failed_font_update_keeps_previous_file(tmp_path, monkeypatch, operation):
    source = tmp_path / "source.ttf"
    target = tmp_path / "installed.ttf"
    source.write_bytes(b"new font")
    target.write_bytes(b"old font")
    def fail(*args, **kwargs):
        if operation == "copy":
            args[1].write_bytes(b"partial")
        raise OSError("injected failure")
    if operation == "copy":
        monkeypatch.setattr(fonts.shutil, "copy2", fail)
    else:
        monkeypatch.setattr(fonts.os, "replace", fail)
    with pytest.raises(OSError, match="injected failure"):
        fonts._copy_font(source, target)
    assert target.read_bytes() == b"old font"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["installed.ttf", "source.ttf"]


def test_bundled_fonts_preserve_original_bytes_and_reinstall(tmp_path):
    import hashlib
    import json
    from font_bundle import font_sources
    manifest = json.loads((fonts.OFFLINE_DIR / 'fonts.json').read_text())
    with font_sources(fonts.OFFLINE_DIR, tmp_path) as sources:
        assert len(sources) == len(manifest['files']) + 1
        for source in sources:
            if source.name in manifest['files']:
                assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest['files'][source.name]['sha256']
            fonts._copy_font(source, tmp_path / source.name)
    before = {p.name: p.stat().st_ino for p in tmp_path.iterdir()}
    with font_sources(fonts.OFFLINE_DIR, tmp_path) as sources:
        assert all(not fonts._copy_font(p, tmp_path / p.name) for p in sources)
    assert before == {p.name: p.stat().st_ino for p in tmp_path.iterdir()}


@pytest.mark.parametrize('name', ['../escape.ttf', '/escape.ttf', 'valid.ttf'])
def test_font_bundle_rejects_invalid_members(name):
    import hashlib
    import io
    import tarfile
    from font_bundle import unpacked_fonts
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:xz') as archive:
        member = tarfile.TarInfo(name)
        member.size = 4
        archive.addfile(member, io.BytesIO(b'font'))
    data = stream.getvalue()
    manifest = {'archive_sha256': hashlib.sha256(data).hexdigest(),
                'files': {name: {'size': 4, 'sha256': 'corrupt'}}}
    with pytest.raises(ValueError):
        unpacked_fonts(data, manifest)
