"""Exercise SDK cache hit, miss and fork behavior without a registry or Docker daemon."""
import os
from pathlib import Path
import subprocess
import textwrap

import pytest


@pytest.mark.parametrize('hit,event,push_result,expected', [
    (True, 'push', '0', ['pull']),
    (False, 'push', '0', ['pull', 'build', 'push']),
    (False, 'pull_request', '0', ['pull', 'build']),
    (False, 'push', '1', ['pull', 'build', 'push', 'push']),
])
def test_sdk_cache_does_not_skip_build_on_miss(repo, tmp_path, hit, event, push_result, expected):
    recipe = tmp_path / 'tests/containers/Dockerfile.arch'
    recipe.parent.mkdir(parents=True)
    recipe.write_text('FROM archlinux:latest AS sdk\nRUN echo deps\n')
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    docker = bin_dir / 'docker'
    docker.write_text('#!/bin/sh\necho "$1" >> "$CALLS"\nif [ "$1" = pull ]; then exit "$PULL_RESULT"; fi\nif [ "$1" = push ]; then exit "$PUSH_RESULT"; fi\n')
    docker.chmod(0o755)
    action = (repo / '.github/actions/sdk/action.yml').read_text()
    script = textwrap.dedent(action.split('      run: |\n', 1)[1])
    env = os.environ | {'PATH': str(bin_dir) + ':' + os.environ['PATH'],
        'CALLS': str(tmp_path / 'calls'), 'PULL_RESULT': '0' if hit else '1',
        'PUSH_RESULT': push_result, 'DISTRO': 'arch', 'REPOSITORY': 'Owner/Project', 'EVENT': event,
        'GITHUB_OUTPUT': str(tmp_path / 'output')}
    subprocess.run(['bash', '-eu', '-c', script], cwd=tmp_path, env=env, check=True)
    assert (tmp_path / 'calls').read_text().splitlines() == expected
    first = (tmp_path / 'output').read_text()
    assert 'image=ghcr.io/owner/project/sdk-arch:' in first
    recipe.write_text(recipe.read_text() + 'RUN echo new-dependency\n')
    (tmp_path / 'output').unlink()
    subprocess.run(['bash', '-eu', '-c', script], cwd=tmp_path, env=env, check=True)
    assert (tmp_path / 'output').read_text() != first
