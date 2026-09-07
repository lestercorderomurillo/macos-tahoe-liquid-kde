"""Security-sensitive step helper tests."""

from __future__ import annotations

import os
from contextlib import contextmanager

from steps import _helpers


def test_temp_dir_is_private_unique_and_self_cleaning(tmp_path, monkeypatch):
    """A planted predictable path must never control staging contents."""
    monkeypatch.setattr(_helpers.tempfile, "tempdir", str(tmp_path))
    victim = tmp_path / "victim"
    victim.mkdir()
    planted = tmp_path / f"mttkde-test-{os.getpid()}"
    planted.symlink_to(victim, target_is_directory=True)

    with _helpers.temp_dir("mttkde-test") as staging:
        assert staging.parent == tmp_path
        assert staging != planted
        assert staging.stat().st_mode & 0o777 == 0o700
        (staging / "owned").write_text("safe\n")

    assert not staging.exists()
    assert planted.is_symlink()
    assert victim.is_dir()


def test_user_config_install_keeps_directories_and_file_owned_by_invoker(tmp_path, monkeypatch):
    source = tmp_path / "source.sh"
    source.write_text("export GTK3_MODULES=appmenu-gtk-module\n")
    destination = tmp_path / "config/plasma-workspace/env/hook.sh"
    owner = (os.geteuid(), os.getegid())
    ownership_changes = []

    @contextmanager
    def elevation():
        assert destination.parent.is_dir()
        assert destination.parent.stat().st_uid == owner[0]
        yield

    monkeypatch.setattr(_helpers, "_as_root", elevation)
    monkeypatch.setattr(_helpers.os, "chown", lambda path, uid, gid, **kwargs:
                        ownership_changes.append((path, uid, gid, kwargs)))
    assert _helpers.sudo_install_file(source, destination, "hook", user_owned=True)
    assert destination.read_text() == source.read_text()
    assert ownership_changes == [(destination.with_name("hook.sh.mttkde-tmp"),
                                  *owner, {"follow_symlinks": False})]


def test_failed_user_ownership_preserves_previous_config(tmp_path, monkeypatch):
    source = tmp_path / "source.sh"
    source.write_text("new\n")
    destination = tmp_path / "hook.sh"
    destination.write_text("previous\n")

    @contextmanager
    def elevation():
        yield

    def denied(*args, **kwargs):
        raise PermissionError("test")

    monkeypatch.setattr(_helpers, "_as_root", elevation)
    monkeypatch.setattr(_helpers.os, "chown", denied)
    assert not _helpers.sudo_install_file(source, destination, "hook", user_owned=True)
    assert destination.read_text() == "previous\n"
