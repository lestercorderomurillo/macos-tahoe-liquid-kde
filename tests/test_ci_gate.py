"""Execute the release gate with synthetic GitHub workflow responses."""
import json
import shutil
import subprocess
import textwrap

import pytest

SHA = 'a' * 40


def run(branch, conclusion='success', *, sha=SHA, status='completed', id=1, event='push'):
    return dict(id=id, head_sha=sha, head_branch=branch, event=event,
                status=status, conclusion=conclusion, html_url='https://example.test/run')


@pytest.mark.parametrize('responses,success', [
    ([[run('main'), run('dev')]], True),
    ([[run('main')]], False),
    ([[run('main'), run('dev', 'failure')]], False),
    ([[run('main', 'cancelled'), run('dev')]], False),
    ([[run('main', 'skipped'), run('dev')]], False),
    ([[run('main'), run('dev', sha='b' * 40)]], False),
    ([[run('main'), run('dev', event='pull_request')]], False),
    ([[run('main', 'failure', id=2), run('main', id=1), run('dev')]], False),
    ([[run('main', 'failure', id=1), run('main', id=2), run('dev')]], True),
    ([[run('main', status='in_progress'), run('dev')], [run('main'), run('dev')]], True),
    ([[]], False),
])
def test_gate_requires_latest_success_on_both_branches(repo, responses, success, branches=None):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required to execute the GitHub Actions gate')
    workflow = (repo / '.github/workflows/require-ci.yml').read_text()
    script = textwrap.dedent(workflow.split('          script: |\n', 1)[1])
    harness = '''
const responses = RESPONSES;
let requests = 0;
const core = { info() {} };
const github = { rest: { actions: { async listWorkflowRuns(args) {
  if (args.workflow_id !== 'test.yml' || args.head_sha !== '__COMMIT__' || args.event !== 'push') {
    throw new Error('Wrong workflow query');
  }
  return {data: {workflow_runs: responses[Math.min(requests++, responses.length - 1)]}};
}}}};
process.env.CI_REPOSITORY = 'owner/repo';
process.env.CI_SHA = '__COMMIT__';
process.env.CI_BRANCHES = JSON.stringify(SELECTED_BRANCHES);
const setTimeout = resolve => resolve();
(async () => { SCRIPT })().then(() => console.log('success')).catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
'''.replace('RESPONSES', json.dumps(responses)).replace('__COMMIT__', SHA).replace('SCRIPT', script).replace('SELECTED_BRANCHES', json.dumps(branches or ['main', 'dev']))
    result = subprocess.run([node, '-e', harness], capture_output=True, text=True, timeout=10)
    assert (result.returncode == 0) == success, result.stdout + result.stderr


def test_release_checks_local_evidence_without_waiting_for_matrix(repo):
    text = (repo / '.github/workflows/release.yml').read_text()
    assert 'require-ci.yml' not in text
    assert 'needs: ci' not in text
    assert 'python3 .github/scripts/release_evidence.py' in text
    assert 'python3 src/scripts/component_manifest.py' in text
    assert '--verify-tag --title' in text
    matrix = (repo / '.github/workflows/test.yml').read_text()
    assert 'branches: [main, dev]' in matrix
    assert 'shard: [0, 1]' in matrix and 'cross-distro:' in matrix and '  nix:' in matrix


@pytest.mark.parametrize('responses,success', [
    ([[run('dev')]], True),
    ([[run('main')]], False),
    ([[run('dev', sha='b' * 40)]], False),
    ([[run('dev', 'failure')]], False),
    ([[run('dev', 'cancelled')]], False),
    ([[run('dev', 'skipped')]], False),
    ([[run('dev', event='pull_request')]], False),
    ([[run('dev', status='in_progress')], [run('dev')]], True),
])
def test_main_promotion_reuses_only_successful_exact_dev_commit(repo, responses, success):
    test_gate_requires_latest_success_on_both_branches(repo, responses, success, ['dev'])
