"""Refresh/check the maintainer's per-component source fingerprint ledger.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import ast
import json
from pathlib import Path

from component_cache import identity
from paths import REPO_ROOT


def dependencies(entry, scripts):
    """Follow repository-local Python imports, including function-local imports."""
    pending, seen = [Path(entry)], set()
    while pending:
        path = pending.pop()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module] + [node.module + '.' + alias.name for alias in node.names]
            for name in names:
                candidate = scripts / (name.replace('.', '/') + '.py')
                if candidate.is_file():
                    pending.append(candidate)
    return sorted(seen)


def snapshot(root=REPO_ROOT):
    scripts = root / 'src/scripts'
    offline = root / 'src/offline'
    components = {}
    mapping = {'aurorae': 'window_decorations', 'plasma-theme': 'plasma_theme',
               'look-and-feel': 'global_theme', 'layouts': 'layout',
               'menu-style': 'kvantum', 'kvantum-engine': 'kvantum', 'plasma-env': 'globalmenu'}
    for path in sorted(offline.iterdir()):
        entries = sorted(path.iterdir()) if path.name in ('plasmoids', 'kwin-effects') else [path]
        for payload in entries:
            name = str(payload.relative_to(offline))
            step = mapping.get(path.name, path.name.replace('-', '_'))
            if path.name == 'plasmoids':
                step = 'globalmenu' if payload.name.endswith('globalmenu') else 'plasmoids'
            elif path.name == 'kwin-effects':
                step = 'acrylic_glass'
            recipe = dependencies(scripts / 'steps' / (step + '.py'), scripts)
            inputs = [(name, payload)] + [(str(p.relative_to(root)), p) for p in recipe]
            components[name] = identity(inputs, portable=True)
    # Components with no offline payload still have independently audited recipes.
    for entry in sorted((scripts / 'steps').glob('*.py')):
        if entry.name.startswith('_'):
            continue
        components['recipe/' + entry.stem] = identity([
            (str(p.relative_to(root)), p) for p in dependencies(entry, scripts)], portable=True)
    return dict(schema=1, components=components)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    path = REPO_ROOT / 'component-hashes.json'
    rendered = json.dumps(snapshot(), indent=2, sort_keys=True) + '\n'
    if args.write:
        path.write_text(rendered)
    elif not path.is_file() or path.read_text() != rendered:
        parser.exit(1, 'Stale component hashes: run python src/scripts/component_manifest.py --write\n')


if __name__ == '__main__':
    main()
