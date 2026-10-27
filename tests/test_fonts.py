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
