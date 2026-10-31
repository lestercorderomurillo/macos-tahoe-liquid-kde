"""Published updates and developer work use real git histories in temporary folders."""
import subprocess
from pathlib import Path

import pytest
import cli
import installer_ui


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def commit(root, message):
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Update test', '-c', 'user.email=update@example.invalid',
        'commit', '-qm', message)
    return git(root, 'rev-parse', 'HEAD')


@pytest.fixture
def releases(tmp_path, monkeypatch):
    for key in ('MAC_TAHOE_NO_UPDATE_CHECK', 'MAC_TAHOE_UPDATED'):
        monkeypatch.delenv(key, raising=False)
    remote = tmp_path / 'published'
    remote.mkdir()
    git(remote, 'init', '-q')
    (remote / 'VERSION').write_text('0.61.9\n')
    (remote / 'installer').write_text('# old installer\n')
    old = commit(remote, 'old release')
    local = tmp_path / 'local'
    subprocess.run(['git', 'clone', '-q', str(remote), str(local)], check=True)
    (remote / 'VERSION').write_text('0.61.10\n')
    (remote / 'installer').write_text('# new installer\n')
    new = commit(remote, 'new release')
    git(remote, 'tag', 'v0.61.10')
    monkeypatch.setattr(cli, 'REPO_ROOT', local)
    monkeypatch.setattr(cli, 'read_version', lambda: (local / 'VERSION').read_text().strip())
    monkeypatch.setattr(cli, 'fetch_latest_release', lambda: '0.61.10')
    fetches = []
    def local_git(*args, **kwargs):
        if args[0] == 'fetch':
            fetches.append(args)
            args = ('fetch', '--no-tags', str(remote), args[-1])
        return subprocess.run(['git', '-C', str(local), *args], text=True,
                              capture_output=True, check=False)
    monkeypatch.setattr(cli, '_git', local_git)
    restarts = []
    monkeypatch.setattr(cli.os, 'execv', lambda *args: restarts.append(args))
    return local, remote, old, new, fetches, restarts


@pytest.mark.parametrize('state', ['clean', 'modified', 'staged', 'untracked', 'deleted',
                                  'local-commit', 'equal', 'newer', 'invalid', 'offline',
                                  'mismatch', 'fetch-failed', 'disabled'])
def test_version_update_preserves_development_work(releases, monkeypatch, state):
    local, remote, old, new, fetches, restarts = releases
    if state in ('modified', 'staged'):
        (local / 'installer').write_text('# local test\n')
        if state == 'staged':
            git(local, 'add', 'installer')
    elif state == 'untracked':
        (local / 'experiment.py').write_text('# local test\n')
        git(local, 'config', 'status.showUntrackedFiles', 'no')
    elif state == 'deleted':
        (local / 'installer').unlink()
    elif state == 'local-commit':
        (local / 'experiment.py').write_text('# committed test\n')
        commit(local, 'local experiment')
    elif state in ('equal', 'newer', 'invalid'):
        (local / 'VERSION').write_text({'equal': '0.61.10', 'newer': '0.62.0', 'invalid': 'testing'}[state])
        commit(local, 'testing version')
    elif state == 'offline':
        monkeypatch.setattr(cli, 'fetch_latest_release', lambda: None)
    elif state == 'mismatch':
        git(remote, 'tag', '-f', 'v0.61.10', old)
    elif state == 'fetch-failed':
        git(remote, 'tag', '-d', 'v0.61.10')
    elif state == 'disabled':
        monkeypatch.setenv('MAC_TAHOE_NO_UPDATE_CHECK', 'true')
        monkeypatch.setattr(cli, 'fetch_latest_release', lambda: pytest.fail('network check'))
    before = git(local, 'rev-parse', 'HEAD')
    status = git(local, 'status', '--porcelain', '--untracked-files=all')
    files = {p.name: p.read_bytes() for p in local.iterdir() if p.is_file()}
    cli.auto_update_and_reexec([], prog='installer')
    if state == 'clean':
        assert git(local, 'rev-parse', 'HEAD') == new
        assert (local / 'VERSION').read_text().strip() == '0.61.10'
        assert restarts == [(str(local / 'installer'), [str(local / 'installer')])]
    else:
        assert git(local, 'rev-parse', 'HEAD') == before
        assert git(local, 'status', '--porcelain', '--untracked-files=all') == status
        assert all((local / name).read_bytes() == value for name, value in files.items())
        assert not restarts


def test_edit_during_fetch_prevents_update(releases, monkeypatch):
    local, remote, old, new, fetches, restarts = releases
    previous = cli._git
    def edit(*args, **kwargs):
        result = previous(*args, **kwargs)
        if args[0] == 'fetch':
            (local / 'installer').write_text('# concurrent edit\n')
        return result
    monkeypatch.setattr(cli, '_git', edit)
    cli.auto_update_and_reexec([], prog='installer')
    assert git(local, 'rev-parse', 'HEAD') == old
    assert (local / 'installer').read_text() == '# concurrent edit\n'
    assert not restarts


def test_maintenance_failure_still_restarts_verified_update(releases, monkeypatch):
    import repository_maintenance
    local, remote, old, new, fetches, restarts = releases
    calls = []
    def maintenance(root, **kw):
        calls.append((root, kw))
        return {"status": "failed", "reason": "disk full"}
    monkeypatch.setattr(repository_maintenance, "compact_repository", maintenance)
    cli.auto_update_and_reexec([], prog='installer')
    assert calls == [(local, {"automatic": True})]
    assert git(local, 'rev-parse', 'HEAD') == new
    assert restarts


@pytest.mark.parametrize('args,updates', [([], True), (['--uninstall'], False), (['--check-update'], False)])
def test_gui_entry_checks_update_before_opening(monkeypatch, args, updates):
    calls = []
    monkeypatch.setattr(installer_ui, 'drop_root_to_invoking_user', lambda: 0)
    monkeypatch.setattr(cli, 'auto_update_and_reexec', lambda argv, prog: calls.append('update'))
    monkeypatch.setattr(installer_ui, 'launch_preview', lambda *a: calls.append('window') or 0)
    monkeypatch.setattr(installer_ui, 'update_status', lambda: {})
    assert installer_ui.main(args) == 0
    assert ('update' in calls) == updates
    if updates:
        assert calls == ['update', 'window']
