"""Real Git states must distinguish an installation from unpublished work."""
import os
from pathlib import Path
import subprocess

import pytest
from repository_history import PublishedSnapshot, inspect_history


def git(root, *args, input=None):
    return subprocess.check_output(['git', '-C', str(root), *args],
                                   input=input, text=True).strip()


@pytest.fixture
def released(tmp_path, monkeypatch):
    monkeypatch.delenv('GOLDEN_GATE_TAHOE_SOURCE', raising=False)
    root = tmp_path / 'checkout'
    root.mkdir()
    git(root, 'init', '-q', '-b', 'main')
    git(root, 'config', 'user.name', 'History fixture')
    git(root, 'config', 'user.email', 'fixture@example.invalid')
    commits = []
    for number in (1, 2):
        (root / 'VERSION').write_text(f'1.0.{number}\n')
        (root / 'installer').write_text(f'# release {number}\n')
        git(root, 'add', '.')
        git(root, 'commit', '-qm', f'release {number}')
        git(root, 'tag', f'v1.0.{number}')
        commits.append(git(root, 'rev-parse', 'HEAD'))
    repository = 'lestercorderomurillo/macos-tahoe-liquid-kde'
    git(root, 'remote', 'add', 'origin', 'https://github.com/' + repository + '.git')
    canonical = {'refs/heads/main': commits[1], 'refs/heads/dev': commits[1],
                 'refs/heads/retired-cache': commits[0],
                 'refs/tags/v1.0.1': commits[0], 'refs/tags/v1.0.2': commits[1]}
    for branch in ('main', 'dev', 'retired-cache'):
        git(root, 'update-ref', 'refs/remotes/origin/' + branch, canonical['refs/heads/' + branch])
    git(root, 'branch', '--set-upstream-to=origin/main', 'main')
    git(root, 'symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/main')
    return root, PublishedSnapshot(repository, '1.0.2', commits[1], canonical), commits[0]


def commit(root, message):
    git(root, 'add', '.')
    git(root, 'commit', '-qm', message)
    return git(root, 'rev-parse', 'HEAD')


def state(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob('*') if path.is_file() and not path.is_symlink()}


def test_clean_release_plan_is_versioned_and_read_only(released):
    root, proof, old = released
    git(root, 'branch', 'dev', old)
    git(root, 'branch', '--set-upstream-to=origin/dev', 'dev')
    git(root, 'branch', 'old-finished-work', old)
    before = state(root)
    plan = inspect_history(root, proof)
    assert plan.mode == 'installation', plan
    retired = {change.name for change in plan.changes if change.after is None}
    assert retired == {'refs/heads/old-finished-work',
                       'refs/remotes/origin/retired-cache'}
    advanced = {change.name: change.after for change in plan.changes if change.after}
    assert advanced == {}
    assert plan.frontiers == []
    assert state(root) == before


@pytest.mark.parametrize('change', ['modified', 'staged', 'untracked', 'deleted', 'version-deleted'])
def test_local_files_are_development_even_when_version_was_not_bumped(released, change):
    root, proof, old = released
    if change == 'version-deleted':
        (root / 'VERSION').unlink()
    elif change == 'deleted':
        (root / 'installer').unlink()
    elif change == 'untracked':
        (root / 'new-feature.py').write_text('# human or agent work\n')
        git(root, 'config', 'status.showUntrackedFiles', 'no')
    else:
        (root / 'installer').write_text('# work in progress\n')
        if change == 'staged':
            git(root, 'add', 'installer')
    before = state(root)
    plan = inspect_history(root, proof)
    assert plan.mode == 'development', plan
    assert plan.reason == 'local-files-in-progress'
    assert plan.changes == []
    assert state(root) == before


@pytest.mark.parametrize('new_version', ['1.0.2', '1.0.3'])
def test_clean_unpublished_commits_are_development(released, new_version):
    root, proof, old = released
    (root / 'VERSION').write_text(new_version + '\n')
    (root / 'installer').write_text('# unpublished implementation\n')
    unpublished = commit(root, 'agent work')
    plan = inspect_history(root, proof)
    assert plan.mode == 'development'
    assert plan.changes == []
    assert git(root, 'rev-parse', 'HEAD') == unpublished


@pytest.mark.parametrize('kind', ['branch', 'reflog-only', 'stash', 'dangling-blob', 'private-tag'])
def test_private_recovery_and_divergent_work_block_history_retirement(released, kind):
    root, proof, old = released
    if kind in ('branch', 'reflog-only'):
        git(root, 'switch', '-c', 'unfinished', old)
        (root / 'personal').write_text('unique work')
        unpublished = commit(root, 'private work')
        git(root, 'switch', 'main')
        if kind == 'reflog-only':
            git(root, 'branch', '-D', 'unfinished')
    elif kind == 'stash':
        (root / 'installer').write_text('stash me')
        git(root, 'stash', 'push')
    elif kind == 'dangling-blob':
        unpublished = git(root, 'hash-object', '-w', '--stdin', input='unreferenced private content')
        path = root / '.git/objects' / unpublished[:2] / unpublished[2:]
        os.utime(path, (1, 1))
    else:
        git(root, 'tag', '-a', '-m', 'private annotation', 'personal-baseline', old)
    before = state(root)
    plan = inspect_history(root, proof)
    assert plan.mode == 'development', plan
    assert plan.changes == []
    assert state(root) == before


def test_active_remote_tracking_intent_preserves_an_old_local_branch(released):
    root, proof, old = released
    future = git(root, 'commit-tree', git(root, 'rev-parse', 'HEAD^{tree}'),
                 '-p', proof.commit, input='future agent work\n')
    proof.refs['refs/heads/active-feature'] = future
    git(root, 'update-ref', 'refs/remotes/origin/active-feature', future)
    git(root, 'branch', 'active-feature', old)
    git(root, 'branch', '--set-upstream-to=origin/active-feature', 'active-feature')
    plan = inspect_history(root, proof)
    assert plan.mode == 'development', plan
    assert plan.changes == []


def test_remote_only_cache_is_not_confused_with_local_agent_work(released):
    root, proof, old = released
    future = git(root, 'commit-tree', git(root, 'rev-parse', 'HEAD^{tree}'),
                 '-p', proof.commit, input='canonical remote agent work\n')
    proof.refs['refs/heads/active-feature'] = future
    git(root, 'update-ref', 'refs/remotes/origin/active-feature', future)
    before = state(root)
    plan = inspect_history(root, proof)
    assert plan.mode == 'installation', plan
    assert not any(change.name == 'refs/remotes/origin/active-feature' for change in plan.changes)
    assert state(root) == before


@pytest.mark.parametrize('marker', ['index.lock', 'MERGE_HEAD', 'rebase-merge', 'sequencer'])
def test_git_operation_in_progress_blocks_retirement(released, marker):
    root, proof, old = released
    (root / '.git' / marker).write_text('in progress')
    before = state(root)
    plan = inspect_history(root, proof)
    assert plan.mode == 'busy', plan
    assert plan.changes == []
    assert state(root) == before


def test_other_worktree_and_its_branch_are_preserved(released, tmp_path):
    root, proof, old = released
    worktree = tmp_path / 'agent-worktree'
    git(root, 'worktree', 'add', '-b', 'agent-work', str(worktree), old)
    (worktree / 'personal').write_text('not committed yet')
    plan = inspect_history(root, proof)
    assert plan.mode == 'unsupported'
    assert (worktree / 'personal').read_text() == 'not committed yet'
    assert git(root, 'rev-parse', 'refs/heads/agent-work') == old


def test_explicit_source_never_enters_installation_history_mode(released, monkeypatch):
    root, proof, old = released
    monkeypatch.setenv('GOLDEN_GATE_TAHOE_SOURCE', str(root))
    assert inspect_history(root, proof).mode == 'development'


def test_local_version_and_tag_names_are_not_publication_proof(released):
    root, proof, old = released
    assert inspect_history(root, None).mode == 'unverified'
    forged = PublishedSnapshot(proof.repository, proof.version, proof.commit,
                               {'refs/tags/v1.0.2': old})
    assert inspect_history(root, forged).mode == 'unverified'


def test_missing_remote_ancestry_requires_proof_instead_of_discarding_data(released):
    root, proof, old = released
    unknown = 'a' * 40
    proof.refs['refs/heads/dev'] = unknown
    assert inspect_history(root, proof).mode == 'unverified'
    verified = PublishedSnapshot(proof.repository, proof.version, proof.commit,
                                 proof.refs, frozenset({unknown}))
    assert inspect_history(root, verified).mode == 'installation'
