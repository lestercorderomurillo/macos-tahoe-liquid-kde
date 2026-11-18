#!/usr/bin/env python3
"""Read-only local release version, pin, tag and optional archive check."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def check(tahoe, golden, archive=None):
    version = (tahoe / 'VERSION').read_text().strip()
    if not re.fullmatch(r'\d+\.\d+(?:\.\d+|rc[1-9]\d*)', version):
        raise ValueError('Invalid project version')
    pin = json.loads((golden / 'upstream.json').read_text())
    if (golden / 'VERSION').read_text().strip() != version or pin.get('version') != version:
        raise ValueError('Edition versions and pin version differ')
    if pin.get('repository') != 'lestercorderomurillo/macos-tahoe-liquid-kde':
        raise ValueError('Unexpected pinned repository')
    if not re.fullmatch('[0-9a-f]{40}', pin.get('commit', '')):
        raise ValueError('Pin is not an immutable commit')
    if not re.fullmatch('[0-9a-f]{64}', pin.get('sha256', '')):
        raise ValueError('Invalid archive digest')
    commit = pin['commit']
    if git(tahoe, 'rev-parse', 'v' + version + '^{commit}') != commit:
        raise ValueError('Local Tahoe release tag does not match Golden Gate pin')
    if git(tahoe, 'show', commit + ':VERSION') != version:
        raise ValueError('Pinned source version differs')
    if archive is not None:
        with archive.open('rb') as stream:
            digest = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != pin['sha256']:
            raise ValueError('Published archive checksum mismatch')
    return {'version': version, 'tahoe_commit': commit,
            'local_consistency': 'passed',
            'archive_checksum': 'passed' if archive is not None else 'not checked: provide --archive',
            'publication': 'not queried', 'visual_approval': 'not established',
            'limits': 'Local consistency only. Qualification, component hashes, edition support, '
                      'publication and user approval remain separate requirements.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tahoe', type=Path, required=True)
    parser.add_argument('--golden', type=Path, required=True)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    try:
        result = check(args.tahoe.resolve(), args.golden.resolve(), args.archive)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Pair check failed: {exc}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
