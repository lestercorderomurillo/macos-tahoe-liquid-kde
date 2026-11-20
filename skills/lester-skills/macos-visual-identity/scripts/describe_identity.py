#!/usr/bin/env python3
"""Locate current identity sources and references without changing the desktop."""

import argparse
import hashlib
import json
from pathlib import Path


def describe(tahoe, component):
    routes = json.loads((Path(__file__).resolve().parents[1] /
                         'references/components.json').read_text())
    if component not in routes:
        raise ValueError('Unknown identity component: ' + component)
    result = {'component': component, 'checkout': str(tahoe),
              'sources': [], 'references': [], 'missing': [],
              'limits': 'Source inventory only. Current runtime appearance, reference truth '
                        'and user approval have not been established.'}
    for category in ('sources', 'references'):
        for name in routes[component][category]:
            path = tahoe / name
            if not path.is_file():
                result['missing'].append(name)
            else:
                result[category].append({'path': str(path),
                                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return result


def main():
    routes = json.loads((Path(__file__).resolve().parents[1] /
                         'references/components.json').read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tahoe', type=Path, required=True)
    parser.add_argument('--component', choices=sorted(routes), required=True)
    args = parser.parse_args()
    try:
        result = describe(args.tahoe.resolve(), args.component)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Cannot inspect identity: {exc}\n')
    print(json.dumps(result, indent=2))
    return 1 if result['missing'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
