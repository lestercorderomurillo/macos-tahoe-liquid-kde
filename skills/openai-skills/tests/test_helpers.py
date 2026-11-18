"""Offline regressions for the project adaptations of GitHub skill helpers."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checks = load('skill_checks', 'gh-fix-ci/scripts/inspect_pr_checks.py')
comments = load('skill_comments', 'gh-address-comments/scripts/fetch_comments.py')


class HelperTests(unittest.TestCase):
    def test_failed_check_json_is_usable_and_job_log_is_specific(self):
        payload = '[{"name":"sdk", "state":"FAILURE"}]'
        with patch.object(checks, 'run_gh_command', return_value=checks.GhResult(1, payload, '')):
            rows = checks.fetch_checks('12', ROOT)
        self.assertTrue(checks.is_failing(rows[0]))
        with patch.object(checks, 'fetch_job_log', return_value=('specific failure', '')) as job:
            with patch.object(checks, 'fetch_run_log', side_effect=AssertionError('mixed run log')):
                self.assertEqual(checks.fetch_check_log('10', '20', ROOT), ('specific failure', '', 'ok'))
        job.assert_called_once_with('20', ROOT)

    def test_unavailable_job_log_does_not_substitute_another_job(self):
        with patch.object(checks, 'fetch_job_log', return_value=('', 'permission denied')):
            with patch.object(checks, 'fetch_run_log', side_effect=AssertionError('wrong log')):
                self.assertEqual(checks.fetch_check_log('10', '20', ROOT)[2], 'error')

    def test_fork_pr_uses_base_repository(self):
        with patch.object(comments, 'gh_pr_view_json', return_value={
                'number': 12, 'url': 'https://github.com/base/project/pull/12'}):
            self.assertEqual(comments.get_current_pr_ref(), ('base', 'project', 12))

    def test_different_page_counts_do_not_duplicate_completed_connections(self):
        def connection(nodes, more=False):
            return {'nodes': nodes, 'pageInfo': {'hasNextPage': more, 'endCursor': 'next' if more else None}}

        def page(review_id, more):
            return {'data': {'repository': {'pullRequest': {
                'number': 12, 'url': 'url', 'title': 'title', 'state': 'OPEN',
                'comments': connection([{'id': 'one-comment'}]),
                'reviews': connection([{'id': review_id}], more),
                'reviewThreads': connection([]),
            }}}}

        with patch.object(comments, 'gh_api_graphql', side_effect=[page('r1', True), page('r2', False)]):
            result = comments.fetch_all('base', 'project', 12)
        self.assertEqual(len(result['conversation_comments']), 1)
        self.assertEqual([r['id'] for r in result['reviews']], ['r1', 'r2'])

    def test_truncated_thread_comments_fail_clearly(self):
        connection = {'nodes': [], 'pageInfo': {'hasNextPage': False, 'endCursor': None}}
        thread = {'comments': {'pageInfo': {'hasNextPage': True}}}
        payload = {'data': {'repository': {'pullRequest': {
            'number': 12, 'url': 'url', 'title': 'title', 'state': 'OPEN',
            'comments': connection, 'reviews': connection,
            'reviewThreads': {**connection, 'nodes': [thread]},
        }}}}
        with patch.object(comments, 'gh_api_graphql', return_value=payload):
            with self.assertRaisesRegex(RuntimeError, 'exceeds 100'):
                comments.fetch_all('base', 'project', 12)


if __name__ == '__main__':
    unittest.main()
