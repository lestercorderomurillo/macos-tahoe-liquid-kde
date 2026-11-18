#!/usr/bin/env python3
"""Read-only edition, path and content-address checks of a screenshot manifest."""

import argparse
import hashlib
import json
from pathlib import Path
import re


def audit(repo, edition):
    directory = (repo / 'src/screenshots').resolve()
    manifest = json.loads((directory / 'release-capture.json').read_text())
    if manifest.get('edition') != edition:
        raise ValueError('Screenshot edition does not match requested edition')
    images = manifest.get('images')
    if not isinstance(images, dict) or not images:
        raise ValueError('Manifest has no image records')
    sources = set()
    for name, record in images.items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory) or path == directory:
            raise ValueError('Image path escapes screenshot directory')
        expected = record.get('sha256', '')
        if not re.fullmatch('[a-f0-9]{64}', expected):
            raise ValueError('Invalid image hash: ' + name)
        if not re.search('-' + expected[:12] + r'\.(png|webp|jpe?g)$', name):
            raise ValueError('Filename does not carry its content hash: ' + name)
        with path.open('rb') as stream:
            actual = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                actual.update(chunk)
        if actual.hexdigest() != expected:
            raise ValueError('Image content changed: ' + name)
        source = record.get('source_commit', manifest.get('source_commit'))
        if not isinstance(source, str) or not re.fullmatch('[a-f0-9]{40}', source):
            raise ValueError('Missing immutable capture source: ' + name)
        sources.add(source)
    return {'edition': edition, 'images_checked': len(images),
            'recorded_source_commits': sorted(sources), 'integrity': 'passed',
            'visual_review': 'not performed', 'user_approval': 'not established',
            'limits': 'Integrity against the recorded manifest only; provenance truth and visible behavior need independent evidence.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--edition', choices=('tahoe', 'golden-gate'), required=True)
    args = parser.parse_args()
    try:
        result = audit(args.repo.resolve(), args.edition)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        parser.exit(1, f'Screenshot audit failed: {exc}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
