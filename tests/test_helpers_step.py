"""Security-sensitive step helper tests."""

from __future__ import annotations

import os
from contextlib import contextmanager

import pytest

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
    source.chmod(0o600)
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
    assert destination.stat().st_mode & 0o777 == 0o600
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


def test_system_payload_repairs_restrictive_modes_and_reuses_bytes(tmp_path, monkeypatch):
    from contextlib import nullcontext
    monkeypatch.setattr(_helpers, "_as_root", nullcontext)
    # Ownership is independently exercised by the disposable VM qualification.
    monkeypatch.setattr(_helpers.os, "geteuid", lambda: 0)
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.qml").write_text("import QtQuick\nItem {}\n")
    (source / "plugin.so").write_bytes(b"plugin")
    (source / "main.qml").chmod(0o660)
    (source / "plugin.so").chmod(0o750)
    source.chmod(0o750)
    outside = tmp_path / "private"
    outside.write_text("private")
    outside.chmod(0o600)
    (source / "alias").symlink_to(outside)
    root = tmp_path / "system"
    root.mkdir()
    destination = root / "org/kde/module"
    old_umask = os.umask(0o007)
    try:
        assert _helpers.sudo_install_tree(source, destination, directory_root=root)
        assert _helpers.sudo_install_file(source / "plugin.so", root / "plugins/plugin.so", "plugin",
                                          directory_root=root)
    finally:
        os.umask(old_umask)
    assert (destination / "main.qml").stat().st_mode & 0o777 == 0o644
    assert (destination / "plugin.so").stat().st_mode & 0o777 == 0o755
    assert (root / "plugins/plugin.so").stat().st_mode & 0o777 == 0o755
    assert (root / "plugins").stat().st_mode & 0o777 == 0o755
    assert outside.stat().st_mode & 0o777 == 0o600
    assert destination.stat().st_mode & 0o777 == 0o755
    # Reproduce an old installation with identical content and private parents.
    for path in (destination, destination.parent, destination.parent.parent):
        path.chmod(0o750)
    (destination / "main.qml").chmod(0o660)
    (destination / "plugin.so").chmod(0o750)
    (root / "plugins/plugin.so").chmod(0o750)
    monkeypatch.setattr(_helpers.shutil, "copy2", lambda *a, **k: pytest.fail("unchanged file copied"))
    monkeypatch.setattr(_helpers.shutil, "copytree", lambda *a, **k: pytest.fail("unchanged tree copied"))
    # On a non-root runner, emulate root ownership only for the reuse predicate.
    original_stat = type(destination).stat
    def root_stat(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        values = list(result)
        values[4] = 0
        return os.stat_result(values)
    monkeypatch.setattr(type(destination), "stat", root_stat)
    assert _helpers.sudo_install_tree(source, destination, directory_root=root)
    assert _helpers.sudo_install_file(source / "plugin.so", root / "plugins/plugin.so", "plugin",
                                      directory_root=root)
    assert (destination / "main.qml").stat().st_mode & 0o777 == 0o644
    for path in (destination, destination.parent, destination.parent.parent):
        assert path.stat().st_mode & 0o777 == 0o755
    assert (root / "plugins/plugin.so").stat().st_mode & 0o777 == 0o755
    assert outside.stat().st_mode & 0o777 == 0o600


def test_system_permission_failure_is_reported(tmp_path, monkeypatch):
    from contextlib import nullcontext
    monkeypatch.setattr(_helpers, "_as_root", nullcontext)
    source = tmp_path / "source"
    source.write_text("payload")
    target = tmp_path / "installed"
    target.write_text("previous")
    def denied(*args):
        raise PermissionError("chmod denied")
    monkeypatch.setattr(_helpers, "_public_payload", denied)
    assert not _helpers.sudo_install_file(source, target, "payload")
    assert target.read_text() == "previous"


@pytest.mark.parametrize("escape", ["outside", "symlink"])
def test_public_namespace_rejects_escape_before_writing(tmp_path, monkeypatch, escape):
    from contextlib import nullcontext
    monkeypatch.setattr(_helpers, "_as_root", nullcontext)
    source = tmp_path / "source"
    source.write_text("payload")
    root = tmp_path / "system"
    root.mkdir()
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    if escape == "symlink":
        (root / "alias").symlink_to(private, target_is_directory=True)
        target = root / "alias/new/payload"
    else:
        target = private / "new/payload"
    assert not _helpers.sudo_install_file(source, target, "payload", directory_root=root)
    assert not (private / "new").exists()
    assert private.stat().st_mode & 0o777 == 0o700
