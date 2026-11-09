"""CI covers runtime changes without promotion polling or duplicate main runs."""


def test_full_ci_runs_on_dev_prs_and_manual_dispatch(repo):
    text = (repo / '.github/workflows/test.yml').read_text()
    push, remainder = text.split('  push:\n', 1)[1].split('  pull_request:\n', 1)
    assert 'branches: [dev]' in push
    assert 'branches: [main, dev]' in remainder
    assert "paths-ignore: ['**/*.md', 'src/screenshots/**']" in push
    assert '  workflow_dispatch:' in text
    assert 'promotion:' not in text and 'require-ci.yml' not in text
    assert 'shard: [0, 1]' in text
    assert 'cross-distro:' in text and '  nix:' in text
    for distro in ['cachyos', 'arch', 'manjaro', 'endeavouros', 'garuda', 'fedora',
                   'nobara', 'opensuse', 'debian', 'neon', 'arch-kdeunstable']:
        assert '- ' + distro in text


def test_release_uses_local_evidence_without_waiting_for_matrix(repo):
    text = (repo / '.github/workflows/release.yml').read_text()
    assert 'require-ci.yml' not in text and 'needs: ci' not in text
    assert 'python3 .github/scripts/release_evidence.py' in text
    assert 'python3 src/scripts/component_manifest.py' in text
    assert '--verify-tag --title' in text
    assert 'gh release view' not in text
    assert not (repo / '.github/workflows/require-ci.yml').exists()
