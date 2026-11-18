#!/usr/bin/env python3
"""Summarize recorded gh run view JSON without network or workflow changes."""

import argparse
from datetime import datetime
import json
from pathlib import Path


def summarize(run):
    if not isinstance(run, dict) or not isinstance(run.get('jobs'), list):
        raise ValueError('Expected a gh run view object with a jobs list')
    completed, incomplete = [], []
    for job in run['jobs']:
        if not isinstance(job, dict) or not job.get('name'):
            raise ValueError('Each job needs a name')
        row = {key: job.get(key) for key in ('name', 'status', 'conclusion', 'databaseId')}
        if job.get('status') != 'completed':
            incomplete.append(row)
            continue
        start, end = (datetime.fromisoformat(job[key].replace('Z', '+00:00'))
                      for key in ('startedAt', 'completedAt'))
        if start.tzinfo is None or end.tzinfo is None or end < start:
            raise ValueError('Job times must have zones and nonnegative duration')
        row['elapsed_seconds'] = (end - start).total_seconds()
        completed.append(row)
    return {
        'source': {key: run.get(key) for key in ('headSha', 'status', 'conclusion', 'url')},
        'completed_jobs_by_duration': sorted(completed, key=lambda j: -j['elapsed_seconds']),
        'incomplete_jobs': incomplete,
        'limits': 'Elapsed job times include setup and teardown, not queue time. '
                  'Concurrent durations are not the workflow critical path or billed minutes. '
                  'No savings or coverage equivalence has been established.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_json', type=Path)
    args = parser.parse_args()
    try:
        result = summarize(json.loads(args.run_json.read_text()))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        parser.exit(1, f'Invalid run data: {exc}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
