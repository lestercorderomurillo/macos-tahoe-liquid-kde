"""Maintenance must preserve even old, unreferenced recovery data."""

import os
from pathlib import Path
import subprocess

import pytest
import repository_maintenance as maintenance


def git(root, *args, input=None):
    return subprocess.check_output(["git", "-C", str(root), *args],
                                   input=input, text=True).strip()


def commit(root, text):
    (root / "tracked").write_text(text)
    git(root, "add", ".")
    git(root, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "commit", "-qm", text)
    return git(root, "rev-parse", "HEAD")


@pytest.mark.parametrize("automatic", [False, True])
def test_maintenance_preserves_refs_reflogs_loose_objects_and_user_files(tmp_path, automatic, monkeypatch):
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2020-01-01T00:00:00Z")
    git(tmp_path, "init", "-q")
    first = commit(tmp_path, "first")
    git(tmp_path, "tag", "v0.0.1")
    second = commit(tmp_path, "experiment")
    git(tmp_path, "branch", "experiment")
    git(tmp_path, "reset", "--hard", first)
    lost = git(tmp_path, "hash-object", "-w", "--stdin", input="recover me")
    obj = tmp_path / ".git/objects" / lost[:2] / lost[2:]
    os.utime(obj, (1, 1))
    (tmp_path / "tracked").write_text("stash")
    git(tmp_path, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "stash")
    (tmp_path / "tracked").write_text("staged")
    git(tmp_path, "add", "tracked")
    (tmp_path / "tracked").write_text("unstaged")
    (tmp_path / "personal").write_text("untracked")
    for key in ("gc.reflogExpire", "gc.reflogExpireUnreachable", "gc.pruneExpire"):
        git(tmp_path, "config", key, "now")
    git(tmp_path, "config", "gc.refs/*.reflogExpire", "now")
    git(tmp_path, "config", "gc.refs/*.reflogExpireUnreachable", "now")
    git(tmp_path, "config", "gc.rerereResolved", "0")
    git(tmp_path, "config", "gc.rerereUnresolved", "0")
    recovery = tmp_path / ".git/rr-cache" / ("a" * 40)
    recovery.mkdir(parents=True)
    (recovery / "preimage").write_text("conflict")
    (recovery / "postimage").write_text("resolution")
    os.utime(recovery / "preimage", (1, 1))
    os.utime(recovery / "postimage", (1, 1))
    os.utime(recovery, (1, 1))
    # Force both safe automatic tasks, while trying to enable destructive
    # tasks too. Explicit task selection must ignore these enabled defaults.
    git(tmp_path, "config", "maintenance.loose-objects.auto", "-1")
    git(tmp_path, "config", "maintenance.incremental-repack.auto", "-1")
    for task in ("gc", "reflog-expire", "rerere-gc", "prefetch"):
        git(tmp_path, "config", f"maintenance.{task}.enabled", "true")
    git(tmp_path, "repack", "-d")
    refs = git(tmp_path, "show-ref")
    reflogs = git(tmp_path, "reflog", "show", "--all", "--format=%H %gs")
    status = git(tmp_path, "status", "--porcelain", "--untracked-files=all")
    index = git(tmp_path, "show", ":tracked")
    config = (tmp_path / ".git/config").read_bytes()
    result = maintenance.compact_repository(tmp_path, automatic=automatic)
    assert result["status"] == "ok", result
    if automatic:
        # The second incremental run expires superseded packs; all of their
        # objects, including unreachable objects, must remain recoverable.
        assert maintenance.compact_repository(tmp_path, automatic=True)["status"] == "ok"
    assert git(tmp_path, "show-ref") == refs
    assert git(tmp_path, "reflog", "show", "--all", "--format=%H %gs") == reflogs
    assert git(tmp_path, "status", "--porcelain", "--untracked-files=all") == status
    assert git(tmp_path, "show", ":tracked") == index
    assert (tmp_path / "tracked").read_text() == "unstaged"
    assert (tmp_path / "personal").read_text() == "untracked"
    assert (tmp_path / ".git/config").read_bytes() == config
    assert (recovery / "preimage").read_text() == "conflict"
    assert (recovery / "postimage").read_text() == "resolution"
    assert git(tmp_path, "cat-file", "-p", lost) == "recover me"
    assert git(tmp_path, "cat-file", "-t", second) == "commit"
    git(tmp_path, "fsck", "--full")
    if not automatic:
        assert result["reclaimed_bytes"] == max(0, result["before_bytes"] - result["after_bytes"])


@pytest.mark.parametrize("kind", ["archive", "symlink", "linked", "alternates", "worktrees"])
def test_shared_and_non_git_sources_are_left_alone(tmp_path, monkeypatch, kind):
    marker = tmp_path / ".git"
    if kind == "linked":
        marker.write_text("gitdir: elsewhere")
    elif kind == "symlink":
        marker.symlink_to(tmp_path, target_is_directory=True)
    elif kind != "archive":
        marker.mkdir()
        if kind == "alternates":
            (marker / "objects/info").mkdir(parents=True)
            (marker / "objects/info/alternates").write_text("/elsewhere")
        else:
            (marker / "worktrees").mkdir()
    monkeypatch.setattr(maintenance.subprocess, "run", lambda *a, **k: pytest.fail("must skip"))
    assert maintenance.compact_repository(tmp_path)["status"] == "skipped"


def test_missing_git_is_reported_without_deleting_source(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / "personal").write_text("keep")
    def missing(*args, **kwargs):
        raise FileNotFoundError("git")
    monkeypatch.setattr(maintenance.subprocess, "run", missing)
    assert maintenance.compact_repository(tmp_path)["status"] == "failed"
    assert (tmp_path / "personal").read_text() == "keep"


def test_usage_does_not_follow_symlinks_or_double_count_hardlinks(tmp_path):
    source = tmp_path / "file"
    source.write_bytes(b"x" * 8192)
    external = tmp_path.with_name(tmp_path.name + "-external")
    external.mkdir()
    (external / "not-counted").write_bytes(b"y" * 8192)
    link = tmp_path / "link"
    link.symlink_to(external, target_is_directory=True)
    (tmp_path / "hardlink").hardlink_to(source)
    # Some filesystems allocate blocks for the link itself. Count those, but
    # never its target's contents or the hardlink's duplicate source data.
    assert maintenance.disk_usage(tmp_path) == (source.stat().st_blocks + link.lstat().st_blocks) * 512


def test_duplicate_roots_are_compacted_once(tmp_path, monkeypatch):
    import installer_ui
    monkeypatch.setattr(installer_ui, "drop_root_to_invoking_user", lambda: 0)
    calls = []
    def compact(root, **kw):
        calls.append(root)
        return {"status": "ok", "reclaimed_bytes": 0}
    monkeypatch.setattr(maintenance, "compact_repository", compact)
    assert maintenance.main(["--repository", str(tmp_path), "--repository", str(tmp_path / ".")]) == 0
    assert calls == [tmp_path]


def test_full_repack_recovers_duplicate_storage_without_removing_history(tmp_path):
    git(tmp_path, "init", "-q")
    commit(tmp_path, "initial")
    common = os.urandom(8192).hex()
    objects = [git(tmp_path, "hash-object", "-w", "--stdin", input=f"{i}\n{common}")
               for i in range(60)]
    # Retain these blobs in an actual historical tree; savings must come from
    # packing/deltas rather than deleting unreferenced objects.
    for i, object_id in enumerate(objects):
        git(tmp_path, "update-index", "--add", "--cacheinfo", "100644", object_id, str(i))
    tree = git(tmp_path, "write-tree")
    git(tmp_path, "update-ref", "refs/tags/saved-assets", tree)
    result = maintenance.compact_repository(tmp_path)
    assert result["status"] == "ok", result
    assert result["reclaimed_bytes"] > 0
    assert git(tmp_path, "rev-parse", "refs/tags/saved-assets") == tree
    for object_id in objects:
        assert git(tmp_path, "cat-file", "-t", object_id) == "blob"


@pytest.mark.parametrize("entry", ["install", "installer"])
def test_maintenance_entry_does_not_launch_wizard_or_query_releases(tmp_path, repo, entry):
    import shutil
    # Exercise the real entry point with an isolated shared-module boundary;
    # importing installer_ui would fail, so this also works without a GUI.
    shutil.copyfile(repo / entry, tmp_path / entry)
    scripts = tmp_path / "src/scripts"
    scripts.mkdir(parents=True)
    (scripts / "repository_maintenance.py").write_text(
        'def main(argv):\n    print("maintenance only")\n    return 0\n')
    result = subprocess.run([os.sys.executable, str(tmp_path / entry), "--free-space"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "maintenance only"


@pytest.mark.parametrize("entry", ["install", "installer"])
def test_reexec_from_old_updater_maintains_storage_and_continues_after_failure(tmp_path, repo, entry):
    import shutil
    shutil.copyfile(repo / entry, tmp_path / entry)
    scripts = tmp_path / "src/scripts"
    scripts.mkdir(parents=True)
    (scripts / "repository_maintenance.py").write_text(
        'def main(argv):\n    assert argv == ["--auto"]\n    print("maintenance failed")\n    return 1\n')
    ui = tmp_path / "src/installer"
    ui.mkdir()
    (ui / "installer_ui.py").write_text('def main(argv):\n    print("wizard opened")\n    return 0\n')
    # Older released updaters already set this flag before re-exec. They
    # cannot invoke our new helper before updating, so use the new entry point.
    result = subprocess.run([os.sys.executable, str(tmp_path / entry)],
                            env={**os.environ, "MAC_TAHOE_UPDATED": "1"},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["maintenance failed", "wizard opened"]
