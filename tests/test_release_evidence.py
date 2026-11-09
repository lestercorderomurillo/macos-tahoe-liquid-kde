"""Publishing early still rejects stale local evidence and altered photographs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


@pytest.fixture
def evidence_repo(repo, tmp_path):
    spec = importlib.util.spec_from_file_location('release_evidence', repo / '.github/scripts/release_evidence.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    (tmp_path / 'VERSION').write_text('1.2.3\n')
    (tmp_path / 'installer.py').write_text('print("ready")\n')
    subprocess.run(['git', '-C', str(tmp_path), 'add', '.'], check=True)
    data = {'version': '1.2.3', 'source_sha256': module.source_fingerprint(tmp_path),
            'checks': [{'command': 'pytest affected-tests', 'result': 'passed'}]}
    (tmp_path / 'release-evidence.json').write_text(json.dumps(data))
    return module, tmp_path, data


def test_verified_local_evidence_does_not_require_remote_ci(evidence_repo):
    module, root, data = evidence_repo
    assert module.verify(root) == data


@pytest.mark.parametrize('change', ['source', 'version', 'mode', 'failed-check', 'missing-checks'])
def test_changed_or_failed_local_evidence_blocks_publication(evidence_repo, change):
    module, root, data = evidence_repo
    if change == 'source':
        (root / 'installer.py').write_text('raise RuntimeError()\n')
    elif change == 'version':
        (root / 'VERSION').write_text('1.2.4\n')
    elif change == 'mode':
        (root / 'installer.py').chmod(0o755)
    else:
        data['checks'] = [] if change == 'missing-checks' else [{'command': 'pytest', 'result': 'failed'}]
        (root / 'release-evidence.json').write_text(json.dumps(data))
    with pytest.raises(ValueError):
        module.verify(root)


def test_reviewed_capture_must_match_its_hash(evidence_repo):
    module, root, data = evidence_repo
    image = root / 'focused.png'
    image.write_bytes(b'reviewed frame')
    data['captures'] = [{'path': 'focused.png', 'reviewed': True,
                         'sha256': hashlib.sha256(image.read_bytes()).hexdigest()}]
    (root / 'release-evidence.json').write_text(json.dumps(data))
    module.verify(root)
    image.write_bytes(b'changed frame')
    with pytest.raises(ValueError, match='Capture'):
        module.verify(root)


@pytest.mark.parametrize('changed', ['image', 'provenance'])
def test_historical_gallery_is_preserved_byte_for_byte(evidence_repo, changed):
    module, root, data = evidence_repo
    gallery = root / 'src/screenshots'
    gallery.mkdir(parents=True)
    image = gallery / 'reviewed.png'
    image.write_bytes(b'original reviewed image')
    manifest = gallery / 'release-capture.json'
    manifest.write_text(json.dumps({'images': {'reviewed.png': {
        'sha256': hashlib.sha256(image.read_bytes()).hexdigest()}}}))
    subprocess.run(['git', '-C', str(root), 'add', 'src'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c',
                    'user.email=test@example.invalid', 'commit', '-qm', 'Reviewed gallery'], check=True)
    data['gallery_commit'] = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    (root / 'release-evidence.json').write_text(json.dumps(data))
    module.verify(root)
    (image if changed == 'image' else manifest).write_bytes(b'changed')
    with pytest.raises(ValueError, match='Historical gallery'):
        module.verify(root)
