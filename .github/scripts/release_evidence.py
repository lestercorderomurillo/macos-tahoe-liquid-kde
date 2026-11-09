"""Verify maintainer-recorded local evidence; full CI remains asynchronous."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def source_fingerprint(repo):
    digest = hashlib.sha256()
    entries = subprocess.check_output(['git', '-C', str(repo), 'ls-files', '-z']).split(b'\0')
    for raw in sorted(filter(None, entries)):
        name = raw.decode()
        if name == 'release-evidence.json' or name.endswith('.md') or name.startswith('src/screenshots/'):
            continue
        path = repo / name
        digest.update(raw + b'\0')
        if path.is_symlink():
            digest.update(b'link\0' + str(path.readlink()).encode())
        else:
            digest.update(b'exec\0' if path.stat().st_mode & 0o111 else b'file\0')
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def verify(repo):
    evidence = json.loads((repo / 'release-evidence.json').read_text())
    if evidence['version'] != (repo / 'VERSION').read_text().strip():
        raise ValueError('Local evidence belongs to another version')
    if evidence['source_sha256'] != source_fingerprint(repo):
        raise ValueError('Sources changed after local validation')
    if not evidence['checks'] or any(c['result'] != 'passed' or not c['command'] for c in evidence['checks']):
        raise ValueError('Passing focused local checks are required')
    gallery = repo / 'src/screenshots/release-capture.json'
    if gallery.exists():
        original = subprocess.check_output(['git', '-C', str(repo), 'show',
            evidence['gallery_commit'] + ':src/screenshots/release-capture.json'])
        if gallery.read_bytes() != original:
            raise ValueError('Historical gallery provenance changed; review and record the new gallery')
        for name, record in json.loads(original)['images'].items():
            image = gallery.parent / name
            if not image.resolve().is_relative_to(gallery.parent.resolve()):
                raise ValueError('Gallery image escapes screenshot directory')
            if hashlib.sha256(image.read_bytes()).hexdigest() != record['sha256']:
                raise ValueError('Historical gallery image changed')
    for capture in evidence.get('captures', []):
        path = repo / capture['path']
        if not path.resolve().is_relative_to(repo.resolve()):
            raise ValueError('Capture path escapes repository')
        if not capture['reviewed'] or hashlib.sha256(path.read_bytes()).hexdigest() != capture['sha256']:
            raise ValueError('Capture is unreviewed or changed')
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    args = parser.parse_args()
    verify(args.repo.resolve())
    print('Focused local evidence verified. Full remote CI is tracked separately.')


if __name__ == '__main__':
    main()
