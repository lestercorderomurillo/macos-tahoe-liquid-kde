"""Refresh/check the maintainer's per-component source fingerprint ledger.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import ast
import json
from pathlib import Path

from component_cache import identity
from paths import REPO_ROOT


def _imports(path, scripts):
    result = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module] + [node.module + '.' + alias.name for alias in node.names]
        else:
            continue
        for name in names:
            candidate = scripts / (name.replace('.', '/') + '.py')
            if candidate.is_file():
                result.add(candidate)
    return result


def dependencies(entry, scripts, *, resolved_inputs=(), imports=None):
    """Follow local imports. Reuse parsed modules only within one snapshot."""
    if imports is None:
        imports = {}
    pending, seen = [Path(entry)], set()
    while pending:
        path = pending.pop()
        if path in seen or path in resolved_inputs or not path.is_file():
            continue
        seen.add(path)
        if path not in imports:
            imports[path] = _imports(path, scripts)
        pending.extend(imports[path] - seen)
    return sorted(seen)


ICON_NOTICES = ("NOTICE", "LICENSING.md", "THIRD_PARTY_NOTICES.md")


def icon_recipe_inputs(root):
    # The installer passes the resolved style and tint to the generator.
    # Other wizard choices, including the scheduler, do not affect its output.
    scripts = root / "src/scripts"
    recipe = dependencies(scripts / "steps/icons.py", scripts,
                          resolved_inputs=(scripts / "installer_choices.py",))
    return [(str(path.relative_to(root)), path) for path in recipe] + [
        (name, root / name) for name in ICON_NOTICES]


def component_inputs(root):
    scripts = root / 'src/scripts'
    offline = root / 'src/offline'
    imports = {}
    mapping = {'aurorae': 'window_decorations', 'plasma-theme': 'plasma_theme',
               'look-and-feel': 'global_theme', 'layouts': 'layout',
               'desktop-widgets': 'plasmoids', 'kwin-scripts': 'layout',
               'mac-tahoe-liquid-kde-theme.service': 'theme_switch',
               'mac-tahoe-liquid-kde-theme.timer': 'theme_switch',
               'mac-tahoe-liquid-kde-oled.service': 'oled_care',
               'mac-tahoe-liquid-kde-oled.timer': 'oled_care',
               'menu-style': 'kvantum', 'kvantum-engine': 'kvantum', 'plasma-env': 'globalmenu'}
    for path in sorted(offline.iterdir()):
        entries = sorted(path.iterdir()) if path.name in ('plasmoids', 'kwin-effects') else [path]
        for payload in entries:
            name = str(payload.relative_to(offline))
            step = mapping.get(path.name, path.name.replace('-', '_'))
            if path.name == 'plasmoids':
                step = 'globalmenu' if payload.name.endswith('globalmenu') else 'plasmoids'
            elif path.name == 'kwin-effects':
                step = 'layout' if payload.name == 'dock-flush' else 'acrylic_glass'
            inputs = [(name, payload)]
            if path.name == 'icons':
                inputs.extend(icon_recipe_inputs(root))
            else:
                recipe = dependencies(scripts / 'steps' / (step + '.py'), scripts, imports=imports)
                inputs.extend((str(p.relative_to(root)), p) for p in recipe)
            if name == 'kwin-effects/acrylic-glass':
                launcher = offline / 'plasmoids/org.kde.mac.tahoe.liquid.taskmanager/launcher'
                for header in ('glassink.h', 'contrastpreset.h'):
                    inputs.append(('adaptive-contrast/' + header, launcher / header))
            if path.name == 'desktop-widgets':
                for filename in ('desktop_widget_settings.py', 'weather_panel_settings.py'):
                    source = scripts / filename
                    inputs.append((str(source.relative_to(root)), source))
            # Launcher and notification options share the Control Center menu.
            if path.name == 'plasmoids' and payload.name == 'org.kde.mac-tahoe-liquid-kde.launcher':
                controls = path / 'org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui'
                inputs.append(('shared-options-menu', controls / 'MacOptionsMenu.qml'))
            # Satellite status applets import the Control Center's shared views.
            if path.name == 'plasmoids' and payload.name in (
                'org.kde.mac-tahoe-liquid-kde.acrylicglass',
                'org.kde.mac-tahoe-liquid-kde.battery',
                'org.kde.mac-tahoe-liquid-kde.bluetooth',
                'org.kde.mac-tahoe-liquid-kde.wifi',
                'org.kde.mac-tahoe-liquid-kde.notifications',
            ):
                shared = path / 'org.kde.mac-tahoe-liquid-kde.controlcenter'
                inputs.append(('desktop-controls', shared))
            if path.name == 'plasmoids' and payload.name in (
                'org.kde.mac.tahoe.liquid.globalmenu',
                'org.kde.mac-tahoe-liquid-kde.launcher',
                'org.kde.mac-tahoe-liquid-kde.controlcenter',
                'org.kde.mac-tahoe-liquid-kde.battery',
                'org.kde.mac-tahoe-liquid-kde.bluetooth',
                'org.kde.mac-tahoe-liquid-kde.wifi',
                'org.kde.mac-tahoe-liquid-kde.notifications',
            ):
                inputs.append(('desktop-controls-native',
                               path / 'org.kde.mac.tahoe.liquid.taskmanager' / 'launcher'))
            yield name, inputs
    # Components with no offline payload still have independently audited recipes.
    for entry in sorted((scripts / 'steps').glob('*.py')):
        if entry.name.startswith('_'):
            continue
        if entry.stem == 'icons':
            yield 'recipe/icons', icon_recipe_inputs(root)
        else:
            yield 'recipe/' + entry.stem, [
                (str(p.relative_to(root)), p) for p in dependencies(entry, scripts, imports=imports)]


def snapshot(root=REPO_ROOT):
    return dict(schema=1, components={
        name: identity(inputs, portable=True) for name, inputs in component_inputs(root)
    })


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
