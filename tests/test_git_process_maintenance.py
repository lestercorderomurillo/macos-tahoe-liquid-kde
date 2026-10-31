"""Updater Git commands must not run independent garbage collection."""
import json
import subprocess

import cli


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def automatic_children(trace):
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    return [event['argv'] for event in events if event.get('event') == 'child_start'
            and any(part in ('maintenance', 'gc') for part in event.get('argv', []))]


def test_fetch_and_fast_forward_leave_maintenance_to_the_installer(tmp_path, monkeypatch):
    remote = tmp_path / 'remote'
    remote.mkdir()
    git(remote, 'init', '-q', '-b', 'main')
    git(remote, 'config', 'user.name', 'Update fixture')
    git(remote, 'config', 'user.email', 'fixture@example.invalid')
    def release(number):
        (remote / 'VERSION').write_text(f'1.0.{number}\n')
        git(remote, 'add', '.')
        git(remote, 'commit', '-qm', str(number))
        git(remote, 'tag', f'v1.0.{number}')
    release(1)
    local = tmp_path / 'local'
    subprocess.run(['git', 'clone', '-q', '--no-local', str(remote), str(local)], check=True)
    git(local, 'config', 'maintenance.auto', 'true')
    git(local, 'config', 'gc.auto', '1')
    configuration = (local / '.git/config').read_bytes()
    release(2)
    control = tmp_path / 'control.json'
    monkeypatch.setenv('GIT_TRACE2_EVENT', str(control))
    git(local, 'fetch', '--no-tags', str(remote), 'refs/tags/v1.0.2')
    assert automatic_children(control), 'Control must exercise Git auto-maintenance.'
    release(3)
    subject = tmp_path / 'subject.json'
    monkeypatch.setenv('GIT_TRACE2_EVENT', str(subject))
    monkeypatch.setattr(cli, 'REPO_ROOT', local)
    fetched = cli._git('fetch', '--no-tags', str(remote), 'refs/tags/v1.0.3', capture=True)
    assert fetched is not None and fetched.returncode == 0
    merged = cli._git('merge', '--ff-only', 'FETCH_HEAD', capture=True)
    assert merged is not None and merged.returncode == 0
    assert (local / 'VERSION').read_text().strip() == '1.0.3'
    assert automatic_children(subject) == []
    assert (local / '.git/config').read_bytes() == configuration
