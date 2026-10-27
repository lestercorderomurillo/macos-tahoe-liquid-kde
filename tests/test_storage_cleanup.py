"""Reinstallation replaces managed data without accumulating copies."""
import os
from pathlib import Path

import pytest

import utils


@pytest.fixture
def copying(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(utils, "_staging_root", lambda: cache)
    source = tmp_path / "source"
    source.mkdir()
    (source / "asset").write_text("new")
    (source / "alias").symlink_to("asset")
    dest = tmp_path / "installed"
    dest.mkdir()
    (dest / "obsolete").write_text("old")
    return source, dest, cache


def test_reinstall_replaces_tree_and_reclaims_only_disposable_staging(copying, monkeypatch):
    source, dest, cache = copying
    interrupted = cache / ".copy-abcdefgh"
    interrupted.mkdir()
    (interrupted / "new").mkdir()
    recovery = cache / ".copy-12345678"
    (recovery / "backup").mkdir(parents=True)
    (recovery / "backup/original").write_text("keep")
    legacy = cache / "tmp_theme_999999"
    legacy.mkdir()
    active = cache / f"tmp_theme_{os.getpid()}"
    active.mkdir()
    backup = cache / "bak_theme_999999"
    backup.mkdir()
    external = source.parent / "outside"
    external.mkdir()
    (cache / ".copy-symlink1").symlink_to(external)
    real_kill = os.kill

    def kill(pid, sig):
        if pid == 999999:
            raise ProcessLookupError
        return real_kill(pid, sig)

    monkeypatch.setattr(utils.os, "kill", kill)
    for _ in range(3):
        assert utils.safe_copy(source, dest)
        assert (dest / "asset").read_text() == "new"
        assert (dest / "alias").is_symlink()
        assert not (dest / "obsolete").exists()
    assert not interrupted.exists()
    assert not legacy.exists()
    assert active.exists() and backup.exists() and external.exists()
    assert (recovery / "backup/original").read_text() == "keep"
    assert {p.name for p in cache.glob(".copy-*")} == {recovery.name, ".copy-symlink1"}


@pytest.mark.parametrize("failure", ["copy", "backup", "activate", "rollback"])
def test_copy_failure_retains_old_data_and_recovery(copying, monkeypatch, failure):
    source, dest, cache = copying
    rename = Path.rename
    if failure == "copy":
        def copy(*args, **kwargs):
            raise OSError("copy failed")
        monkeypatch.setattr(utils.shutil, "copytree", copy)

    def move(path, target):
        if ((failure == "backup" and path == dest)
                or (failure in ("activate", "rollback") and path.name == "new")
                or (failure == "rollback" and path.name == "backup")):
            raise OSError("move failed")
        return rename(path, target)

    monkeypatch.setattr(Path, "rename", move)
    assert not utils.safe_copy(source, dest)
    if failure == "rollback":
        backups = list(cache.glob(".copy-*/backup/obsolete"))
        assert len(backups) == 1
        assert backups[0].read_text() == "old"
        utils._prune_copy_staging(cache)
        assert backups[0].exists()
    else:
        assert (dest / "obsolete").read_text() == "old"
        assert not list(cache.glob(".copy-*"))
