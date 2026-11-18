#!/usr/bin/env python3
"""Inspect changes using Golden Gate's existing read-only offline graph."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def report(repo, graph=None, paths=()):
    repo = Path(git(repo, 'rev-parse', '--show-toplevel').decode().strip())
    candidates = [repo / 'tools/repo_graph.py',
                  repo.parent / 'macos-golden-gate-liquid-kde/tools/repo_graph.py']
    graph = Path(graph).resolve() if graph else next((p for p in candidates if p.is_file()), None)
    if graph is None or not graph.is_file():
        raise ValueError('Offline graph not found; provide --graph <path>')
    changed = list(paths)
    if not changed:
        for args in [('diff', '--name-only', '-z', 'HEAD'),
                     ('ls-files', '--others', '--exclude-standard', '-z')]:
            changed.extend(p.decode() for p in git(repo, *args).split(b'\0') if p)
    changed = sorted(set(changed))
    for name in changed:
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Paths must be repository-relative without parent traversal')
    raw = subprocess.check_output([sys.executable, str(graph), '--repo', str(repo),
                                   '--limit', '0', '--', *changed])
    result = json.loads(raw)
    result.update(repository=str(repo), head=git(repo, 'rev-parse', 'HEAD').decode().strip(),
                  graph=str(graph), tests_are_suggestions=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--graph', type=Path)
    parser.add_argument('paths', nargs='*')
    args = parser.parse_args()
    try:
        result = report(args.repo.resolve(), args.graph, args.paths)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Cannot inspect impact: {exc}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
