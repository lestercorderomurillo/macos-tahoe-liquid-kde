"""Behavior checks for read-only project helpers using disposable fixtures."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


COLLECTION = Path(__file__).resolve().parents[1]
GRAPH = COLLECTION.parents[1] / 'tools/repo_graph.py'
if not GRAPH.is_file():
    GRAPH = COLLECTION.parents[2] / 'macos-golden-gate-liquid-kde/tools/repo_graph.py'


def load(name, skill, script):
    spec = importlib.util.spec_from_file_location(name, COLLECTION / skill / 'scripts' / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


impact = load('project_impact', 'project-impact', 'inspect_impact.py')
pair = load('paired_release', 'paired-release', 'check_pair.py')
screenshots = load('screenshot_provenance', 'screenshot-provenance', 'audit.py')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE).decode().strip()


class ProjectHelpers(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def repository(self, name):
        root = self.root / name
        root.mkdir()
        git(root, 'init', '-q')
        (root / 'VERSION').write_text('0.99rc1\n')
        git(root, 'add', '.')
        git(root, '-c', 'user.name=Skill Fixture', '-c', 'user.email=fixture@example.invalid',
            'commit', '-qm', 'fixture')
        return root

    def test_impact_includes_callers_deletions_and_untracked_paths_without_writes(self):
        root = self.repository('impact')
        (root / 'a.py').write_text('VALUE = 1\n')
        (root / 'tests').mkdir()
        (root / 'tests/test_a.py').write_text('import a\n')
        git(root, 'add', '.')
        git(root, '-c', 'user.name=Skill Fixture', '-c', 'user.email=fixture@example.invalid',
            'commit', '-qm', 'source')
        (root / 'a.py').unlink()
        name = 'untracked $(never run).py'
        (root / name).write_text('pass\n')
        before = git(root, 'status', '--porcelain')
        report = impact.report(root, GRAPH)
        self.assertEqual(report['changed'], ['a.py', name])
        self.assertIn('tests/test_a.py', report['tests'])
        self.assertIn(name, report['unindexed'])
        self.assertEqual(git(root, 'status', '--porcelain'), before)

    def test_impact_rejects_outside_paths_and_missing_graph(self):
        root = self.repository('impact')
        with self.assertRaisesRegex(ValueError, 'repository-relative'):
            impact.report(root, GRAPH, ['../outside.py'])
        with self.assertRaisesRegex(ValueError, 'graph not found'):
            impact.report(root, self.root / 'missing.py')

    def test_impact_cli_starts_without_shadowing_standard_library(self):
        root = self.repository('cli')
        command = [sys.executable, str(COLLECTION / 'project-impact/scripts/inspect_impact.py'),
                   '--repo', str(root), '--graph', str(GRAPH), 'VERSION']
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)['changed'], ['VERSION'])

    def pair_fixture(self):
        tahoe = self.repository('tahoe')
        golden = self.root / 'golden'
        golden.mkdir()
        (golden / 'VERSION').write_text('0.99rc1\n')
        commit = git(tahoe, 'rev-parse', 'HEAD')
        git(tahoe, 'tag', 'v0.99rc1')
        archive = self.root / 'archive.tar.gz'
        archive.write_bytes(b'fixture archive bytes')
        pin = {'repository': 'lestercorderomurillo/macos-tahoe-liquid-kde',
               'commit': commit, 'version': '0.99rc1',
               'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
        (golden / 'upstream.json').write_text(json.dumps(pin))
        return tahoe, golden, archive

    def test_pair_verifies_archive_and_marks_unchecked_claims(self):
        tahoe, golden, archive = self.pair_fixture()
        result = pair.check(tahoe, golden, archive)
        self.assertEqual(result['archive_checksum'], 'passed')
        self.assertEqual(result['publication'], 'not queried')
        self.assertIn('not checked', pair.check(tahoe, golden)['archive_checksum'])

    def test_pair_rejects_archive_mismatch(self):
        tahoe, golden, archive = self.pair_fixture()
        archive.write_bytes(b'wrong archive')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            pair.check(tahoe, golden, archive)

    def test_pair_rejects_version_and_tag_mismatches(self):
        tahoe, golden, _ = self.pair_fixture()
        (golden / 'VERSION').write_text('0.98.0')
        with self.assertRaisesRegex(ValueError, 'versions'):
            pair.check(tahoe, golden)
        (golden / 'VERSION').write_text('0.99rc1')
        path = golden / 'upstream.json'
        pin = json.loads(path.read_text())
        pin['commit'] = '1' * 40
        path.write_text(json.dumps(pin))
        with self.assertRaisesRegex(ValueError, 'tag'):
            pair.check(tahoe, golden)

    def gallery(self):
        directory = self.root / 'src/screenshots'
        directory.mkdir(parents=True)
        data = b'image fixture; no rendering claim'
        digest = hashlib.sha256(data).hexdigest()
        name = 'dock-' + digest[:12] + '.png'
        (directory / name).write_bytes(data)
        manifest = {'edition': 'tahoe', 'source_commit': '1' * 40,
                    'images': {name: {'sha256': digest}}}
        (directory / 'release-capture.json').write_text(json.dumps(manifest))
        return directory, name, manifest

    def test_gallery_preserves_historical_source_and_detects_tampering(self):
        directory, name, _ = self.gallery()
        result = screenshots.audit(self.root, 'tahoe')
        self.assertEqual(result['recorded_source_commits'], ['1' * 40])
        self.assertEqual(result['visual_review'], 'not performed')
        (directory / name).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'content changed'):
            screenshots.audit(self.root, 'tahoe')

    def test_gallery_rejects_wrong_edition_and_path_escape(self):
        directory, name, manifest = self.gallery()
        with self.assertRaisesRegex(ValueError, 'edition'):
            screenshots.audit(self.root, 'golden-gate')
        manifest['images'] = {'../' + name: manifest['images'][name]}
        (directory / 'release-capture.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'escapes'):
            screenshots.audit(self.root, 'tahoe')


if __name__ == '__main__':
    unittest.main()
