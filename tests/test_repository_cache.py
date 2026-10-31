"""Exercise the production cache against real repositories and subsequent pulls."""
import json
import os
from pathlib import Path
import subprocess

import pytest
import repository_cache as cache
from repository_history import PublishedSnapshot, inspect_history
from repository_maintenance import disk_usage


def git(root, *args, input=None):
    return subprocess.check_output(['git', '-c', 'maintenance.auto=false', '-c', 'gc.auto=0',
             '-C', str(root), *args], input=input, text=True, stderr=subprocess.PIPE).strip()


def available(root):
    return set(git(root, 'cat-file', '--batch-all-objects', '--batch-check=%(objectname)').splitlines())


@pytest.fixture
def history(tmp_path, monkeypatch):
    monkeypatch.delenv('MAC_TAHOE_NO_UPDATE_CHECK', raising=False)
    monkeypatch.delenv('GOLDEN_GATE_TAHOE_SOURCE', raising=False)
    remote = tmp_path / 'remote'
    remote.mkdir()
    git(remote, 'init', '-q', '-b', 'main')
    git(remote, 'config', 'user.name', 'Cache fixture')
    git(remote, 'config', 'user.email', 'test@example.invalid')
    git(remote, 'config', 'uploadpack.allowFilter', 'true')
    def release(number):
        (remote / 'VERSION').write_text(f'1.0.{number}\n')
        (remote / 'asset').write_bytes(os.urandom(256 * 1024))
        git(remote, 'add', '.')
        git(remote, 'commit', '-qm', f'release {number}')
        git(remote, 'tag', f'v1.0.{number}')
        git(remote, 'branch', '-f', 'dev', 'HEAD')
        return git(remote, 'rev-parse', 'HEAD')
    for number in range(1, 9):
        release(number)
    root = tmp_path / 'user'
    subprocess.run(['git', 'clone', '-q', '--no-local', str(remote), str(root)], check=True)
    project = 'lestercorderomurillo/macos-tahoe-liquid-kde'
    git(root, 'remote', 'set-url', 'origin', f'https://github.com/{project}.git')
    # Redirect only the fixture's canonical transport, not the proof checks.
    git(root, 'config', f'url.file://{remote}.insteadOf', f'https://github.com/{project}.git')
    def proof(root, project):
        refs = dict(line.split('\t')[::-1] for line in git(remote, 'ls-remote', '.').splitlines()
                    if '\trefs/' in line)
        number = (remote / 'VERSION').read_text().strip()
        return PublishedSnapshot(project, number, git(remote, 'rev-parse', 'HEAD'), refs)
    monkeypatch.setattr(cache, 'published_snapshot', proof)
    # Git expands insteadOf in remote get-url too; canonical identity remains
    # exercised in separate proof-resolver tests, while this fixture uses file://.
    monkeypatch.setattr(cache, 'canonical_project', lambda root: project)
    import repository_history
    original = repository_history._canonical_origin
    monkeypatch.setattr(repository_history, '_canonical_origin', lambda url, repo:
                        url == f'file://{remote}' or original(url, repo))
    return root, remote, release


def test_reclaims_history_and_preserves_main_dev_old_base_merges_and_recovery(history):
    root, remote, release = history
    old_blob = git(remote, 'rev-parse', 'v1.0.1:asset')
    git(root, 'branch', 'finished-old-work', 'v1.0.1')
    before = disk_usage(root / '.git')
    refs = git(root, 'show-ref')
    logs = (root / '.git/logs/HEAD').read_bytes()
    result = cache.trim_published_cache(root)
    assert result['status'] == 'ok', result
    assert result['evicted_blobs'] == 7
    assert disk_usage(root / '.git') < before * .4
    assert old_blob not in available(root)
    assert git(root, 'rev-list', '--count', 'HEAD') == '8'
    assert git(root, 'show-ref', '--tags') in refs
    assert (root / '.git/logs/HEAD').read_bytes() == logs
    assert not git(root, 'branch', '--list', 'finished-old-work')
    journal = json.loads((root / '.git/tahoe-maintenance-journal.json').read_text())
    assert journal['retired_refs'][0]['reflog']
    release(9)
    git(root, 'pull', '--ff-only')
    git(remote, 'switch', '-c', 'agent-feature', 'v1.0.2')
    (remote / 'feature').write_text('other AI work')
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'agent feature')
    git(remote, 'switch', 'main')
    git(remote, 'merge', '--no-ff', 'agent-feature', '-m', 'merge old-base work')
    release(10)
    git(root, 'pull', '--ff-only')
    assert old_blob not in available(root)
    git(root, 'switch', '--track', 'origin/dev')
    release(11)
    git(root, 'pull', '--ff-only')
    git(root, 'switch', 'main')
    git(root, 'pull', '--ff-only')
    old9 = git(remote, 'rev-parse', 'v1.0.9:asset')
    assert old9 in available(root)
    result = cache.trim_published_cache(root)
    assert result['status'] == 'ok', result
    assert old9 not in available(root)
    assert (root / 'feature').read_text() == 'other AI work'
    git(root, 'fsck', '--full')
    assert cache.trim_published_cache(root, automatic=True)['reason'] == 'unchanged-object-cache'
    # An explicit historical lookup hydrates only the requested old blob.
    assert subprocess.check_output(['git', '-C', str(root), 'cat-file', 'blob', old_blob]) == (
        subprocess.check_output(['git', '-C', str(remote), 'cat-file', 'blob', old_blob]))


@pytest.mark.parametrize('kind', ['modified', 'staged', 'untracked', 'deleted', 'local-commit',
                                 'private-blob', 'private-tag', 'worktree', 'index-lock'])
def test_developer_and_active_git_states_are_never_converted(history, kind):
    root, remote, release = history
    if kind == 'modified':
        (root / 'VERSION').write_text('local work')
    elif kind == 'staged':
        (root / 'local').write_text('work')
        git(root, 'add', 'local')
    elif kind == 'untracked':
        (root / 'local').write_text('work')
    elif kind == 'deleted':
        (root / 'asset').unlink()
    elif kind == 'local-commit':
        git(root, '-c', 'user.name=Test', '-c', 'user.email=t@example.invalid',
            'commit', '--allow-empty', '-qm', 'unpublished')
    elif kind == 'private-blob':
        git(root, 'hash-object', '-w', '--stdin', input='private recovery data')
    elif kind == 'private-tag':
        git(root, 'tag', 'personal')
    elif kind == 'worktree':
        git(root, 'worktree', 'add', '-b', 'other-agent', str(root.parent / 'other'))
    else:
        (root / '.git/index.lock').write_text('other process')
    objects = available(root)
    config = (root / '.git/config').read_bytes()
    refs = git(root, 'show-ref')
    result = cache.trim_published_cache(root)
    assert result['status'] == 'skipped', result
    assert available(root) == objects
    assert (root / '.git/config').read_bytes() == config
    assert git(root, 'show-ref') == refs


def test_new_agent_branch_during_packing_aborts_before_eviction(history, monkeypatch):
    root, remote, release = history
    original = cache._checked
    modified = False
    def concurrent(root, *args, **kw):
        nonlocal modified
        result = original(root, *args, **kw)
        if args[0] == 'pack-objects' and not modified:
            modified = True
            git(root, 'branch', 'new-agent-work')
            (root / 'agent-file').write_text('in progress')
        return result
    monkeypatch.setattr(cache, '_checked', concurrent)
    objects = available(root)
    config = (root / '.git/config').read_bytes()
    assert cache.trim_published_cache(root)['reason'] == 'concurrent-source-change'
    assert objects <= available(root)
    assert (root / '.git/config').read_bytes() == config
    assert (root / 'agent-file').read_text() == 'in progress'
    assert git(root, 'rev-parse', 'new-agent-work') == git(root, 'rev-parse', 'HEAD')
    assert not (root / '.git/index.lock').exists()
    assert not (root / '.git/config.lock').exists()


@pytest.mark.parametrize('phase', ['preparing', 'remote-backed'])
def test_interruption_preserves_git_and_next_cleanup_can_resume(history, monkeypatch, phase):
    root, remote, release = history
    original = cache._write_json
    def interrupt(path, value):
        original(path, value)
        if value.get('phase') == phase:
            raise OSError('simulated interruption')
    monkeypatch.setattr(cache, '_write_json', interrupt)
    objects = available(root)
    assert cache.trim_published_cache(root)['status'] == 'skipped'
    assert objects <= available(root)
    assert git(root, 'status', '--porcelain') == ''
    assert (root / 'VERSION').read_text().strip() == '1.0.8'
    assert not (root / '.git/index.lock').exists()
    assert not (root / '.git/config.lock').exists()
    monkeypatch.setattr(cache, '_write_json', original)
    result = cache.trim_published_cache(root)
    assert result['status'] == 'ok', result
    git(root, 'fsck', '--full')


def test_midx_cache_is_retired_before_old_packs(history):
    root, remote, release = history
    git(root, 'multi-pack-index', 'write')
    assert (root / '.git/objects/pack/multi-pack-index').exists()
    result = cache.trim_published_cache(root)
    assert result['status'] == 'ok', result
    assert not (root / '.git/objects/pack/multi-pack-index').exists()
    git(root, 'fsck', '--full')


def test_recovery_journal_accumulates_across_cleanups(history):
    root, remote, release = history
    git(root, 'branch', 'old-first', 'v1.0.1')
    assert cache.trim_published_cache(root)['status'] == 'ok'
    release(9)
    git(root, 'pull', '--ff-only')
    git(root, 'branch', 'old-second', 'v1.0.2')
    assert cache.trim_published_cache(root)['status'] == 'ok'
    journal = json.loads((root / '.git/tahoe-maintenance-journal.json').read_text())
    assert {entry['name'] for entry in journal['retired_refs']} >= {'refs/heads/old-first', 'refs/heads/old-second'}
    assert all(entry['reflog'] for entry in journal['retired_refs'] if entry['name'].startswith('refs/heads/'))


@pytest.mark.parametrize('policy', ['off', 'compact'])
def test_local_policy_disables_eviction_without_network(history, monkeypatch, policy):
    root, remote, release = history
    git(root, 'config', 'tahoe.maintenance', policy)
    monkeypatch.setattr(cache, 'published_snapshot', lambda *a: pytest.fail('network proof'))
    assert cache.trim_published_cache(root)['reason'] == 'user-maintenance-policy'


@pytest.mark.parametrize('guard', ['disabled', 'development', 'failed-hint'])
def test_resolver_never_retries_disabled_or_already_failed_network(tmp_path, monkeypatch, guard):
    # Call the real resolver, not the fixture's release transport.
    if guard == 'disabled':
        monkeypatch.setenv('MAC_TAHOE_NO_UPDATE_CHECK', 'true')
    elif guard == 'development':
        monkeypatch.setenv('GOLDEN_GATE_TAHOE_SOURCE', str(tmp_path))
    else:
        monkeypatch.delenv('MAC_TAHOE_NO_UPDATE_CHECK', raising=False)
        monkeypatch.delenv('GOLDEN_GATE_TAHOE_SOURCE', raising=False)
        monkeypatch.setenv(cache.HINTS, json.dumps({'example/project': None}))
    monkeypatch.setattr(cache.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('network'))
    monkeypatch.setattr(cache, '_checked', lambda *a, **k: pytest.fail('git transport'))
    assert cache.published_snapshot(tmp_path, 'example/project') is None


def test_real_resolver_requires_public_tag_head_and_version_agreement(tmp_path, monkeypatch):
    monkeypatch.delenv('MAC_TAHOE_NO_UPDATE_CHECK', raising=False)
    monkeypatch.delenv('GOLDEN_GATE_TAHOE_SOURCE', raising=False)
    project = 'lestercorderomurillo/macos-tahoe-liquid-kde'
    monkeypatch.setenv(cache.HINTS, json.dumps({project: '1.2.3'}))
    (tmp_path / 'VERSION').write_text('1.2.3\n')
    commit = 'a' * 40
    calls = []
    def checked(root, *args, **kw):
        calls.append(args)
        return f'{commit}\trefs/tags/v1.2.3' if args[0] == 'ls-remote' else commit
    monkeypatch.setattr(cache, '_checked', checked)
    monkeypatch.setattr(cache.urllib.request, 'urlopen', lambda *a, **kw: pytest.fail('duplicate API query'))
    proof = cache.published_snapshot(tmp_path, project)
    assert proof.commit == commit
    assert calls[0][0] == 'ls-remote'
    (tmp_path / 'VERSION').write_text('1.2.4\n')
    assert cache.published_snapshot(tmp_path, project) is None
    (tmp_path / 'VERSION').write_text('1.2.3\n')
    monkeypatch.setattr(cache, '_checked', lambda root, *a, **kw:
                        f'{commit}\trefs/tags/v1.2.3' if a[0] == 'ls-remote' else 'b' * 40)
    assert cache.published_snapshot(tmp_path, project) is None


def test_unchanged_automatic_launch_does_not_repeat_proof_or_packing(history, monkeypatch):
    root, remote, release = history
    assert cache.trim_published_cache(root)['status'] == 'ok'
    monkeypatch.setattr(cache, 'published_snapshot', lambda *a: pytest.fail('duplicate proof query'))
    assert cache.trim_published_cache(root, automatic=True)['reason'] == 'unchanged-object-cache'


def test_real_installer_update_uses_partial_transport_without_reloading_old_assets(history, monkeypatch):
    import cli
    root, remote, release = history
    assert cache.trim_published_cache(root)['status'] == 'ok'
    old = git(remote, 'rev-parse', 'v1.0.1:asset')
    release(9)
    monkeypatch.delenv('MAC_TAHOE_UPDATED', raising=False)
    monkeypatch.setattr(cli, 'REPO_ROOT', root)
    monkeypatch.setattr(cli, 'read_version', lambda: (root / 'VERSION').read_text().strip())
    monkeypatch.setattr(cli, 'fetch_latest_release', lambda: '1.0.9')
    commands = []
    def run(command, **kw):
        commands.append(command)
        return subprocess.run(command, **kw)
    monkeypatch.setattr(cli, 'run_user', run)
    restarts = []
    monkeypatch.setattr(cli.os, 'execv', lambda *a: restarts.append(a))
    cli.auto_update_and_reexec([], 'installer')
    assert any('fetch' in args and '--filter=blob:none' in args for args in commands)
    assert (root / 'VERSION').read_text().strip() == '1.0.9'
    assert (root / 'asset').read_bytes() == (remote / 'asset').read_bytes()
    assert old not in available(root)
    assert len(restarts) == 1


def test_process_death_recovers_only_our_marked_standard_git_locks(history):
    import sys
    root, remote, release = history
    code = '''import os,sys
from pathlib import Path
from repository_cache import _lease
with _lease(Path(sys.argv[1]) / '.git', 'main'):
    os._exit(77)
'''
    env = dict(os.environ, PYTHONPATH=str(Path(cache.__file__).parent))
    crashed = subprocess.run([sys.executable, '-c', code, str(root)], env=env)
    assert crashed.returncode == 77
    assert (root / '.git/index.lock').exists()
    assert (root / '.git/refs/heads/main.lock').exists()
    result = cache.trim_published_cache(root)
    assert result['status'] == 'ok', result
    assert not (root / '.git/index.lock').exists()
    assert not (root / '.git/refs/heads/main.lock').exists()
    assert not (root / '.git/tahoe-maintenance-owner.json').exists()
    git(root, 'fsck', '--full')


@pytest.mark.parametrize('contents', ['interrupted malformed JSON', '{"retired_refs":[{}]}'])
def test_unrecognized_recovery_journal_is_preserved_without_eviction(history, contents):
    root, remote, release = history
    journal = root / '.git/tahoe-maintenance-journal.json'
    journal.write_text(contents)
    objects = available(root)
    config = (root / '.git/config').read_bytes()
    result = cache.trim_published_cache(root)
    assert result['reason'] == 'unrecognized-maintenance-journal', result
    assert journal.read_text() == contents
    assert available(root) == objects
    assert (root / '.git/config').read_bytes() == config


def test_packing_a_converted_development_clone_preserves_private_recovery(history, monkeypatch):
    from repository_maintenance import compact_repository
    root, remote, release = history
    assert cache.trim_published_cache(root)['status'] == 'ok'
    old_public = git(remote, 'rev-parse', 'v1.0.1:asset')
    git(root, 'config', 'user.name', 'Development fixture')
    git(root, 'config', 'user.email', 'test@example.invalid')
    git(root, 'switch', '-c', 'agent-work')
    private = os.urandom(128 * 1024)
    (root / 'private-work').write_bytes(private)
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'private unpublished work')
    commit = git(root, 'rev-parse', 'HEAD')
    (root / 'private-work').write_text('stashed work')
    git(root, 'stash')
    git(root, 'switch', 'main')
    lost = git(root, 'hash-object', '-w', '--stdin', input='private dangling data')
    refs, logs = git(root, 'show-ref'), git(root, 'reflog', '--all')
    config = (root / '.git/config').read_bytes()
    monkeypatch.setenv('MAC_TAHOE_NO_UPDATE_CHECK', 'true')
    result = compact_repository(root)
    assert result['status'] == 'ok', result
    assert git(root, 'show-ref') == refs
    assert git(root, 'reflog', '--all') == logs
    assert (root / '.git/config').read_bytes() == config
    assert subprocess.check_output(['git', '-C', str(root), 'show', commit + ':private-work']) == private
    assert git(root, 'cat-file', '-p', lost) == 'private dangling data'
    assert old_public not in available(root)
    git(root, 'fsck', '--full')
