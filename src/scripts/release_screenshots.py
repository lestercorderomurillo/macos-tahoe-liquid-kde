"""Release screenshot provenance and publication checks (no desktop access)."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / 'src/scripts/release_capture_profile.json'
EDITIONS = {'tahoe': ('MacTahoe', 1, 'v4'), 'golden-gate': ('MacGoldenGate', 2, 'v1')}
INSTALLER_PAGES = ('welcome', 'appearance', 'icons', 'wallpaper', 'launcher', 'layout',
                   'effects', 'window_controls', 'shadows', 'fonts', 'firefox', 'files', 'glass_style', 'boot', 'oled', 'summary')
MATERIAL_CASES = {'glass-tahoe-clear': (1, 0), 'glass-tahoe-frosted': (1, 1),
                  'glass-golden-gate-official': (2, 1)}
CASES = tuple(MATERIAL_CASES) + ('launcher', 'dock', 'menu', 'context', 'finder', 'showcase', 'about') + tuple(
    'installer-' + page for page in INSTALLER_PAGES)
MODES = ('light', 'dark')
RECIPE_FILES = ('release_capture.py', 'release_capture_guest.py', 'release_capture_profile.json',
                'release_screenshots.py', 'screenshot_checks.py', 'release_capture_wizard.py')
STATIC_ART = {'banner_v3.png', 'banner.png', 'macos-26.png', 'macos-27.png', 'macos-27-dark.png'}
SCREENSHOT_DOCS = ('README.md', 'TESTING.md', 'GLASS_PRESETS.md')
README_MAX_EDGE = 2560
AUXILIARY_MAX_EDGE = 1280
EXPORT_QUALITY = 92


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def commit_id(repo: Path, ref: str) -> str:
    return git(repo, 'rev-parse', '--verify', ref + '^{commit}')


def verify_recipe(repo: Path, ref: str) -> None:
    for name in RECIPE_FILES:
        path = 'src/scripts/' + name
        require((ROOT / path).read_bytes() == blob(repo, ref, path),
                f'Capture recipe differs from {ref}: {name}; commit it and run the matching checkout')


def runtime_tree(repo: Path, ref: str) -> str:
    # Screenshots must be committed after capture. Exclude only their outputs;
    # changes to code, assets, dependencies, VERSION or the recipe invalidate it.
    tree = subprocess.check_output(['git', '-C', str(repo), 'ls-tree', '-rz', ref])
    entries = [e for e in tree.split(b'\0') if e and not e.split(b'\t', 1)[1].startswith(b'src/screenshots/')]
    for index, entry in enumerate(entries):
        document = entry.split(b'\t', 1)[1].decode()
        if document in SCREENSHOT_DOCS:
            # Staging changes image URLs, but any other documentation edit still
            # invalidates the captured source.
            readme = re.sub(rb'(src/screenshots/[\w.-]+)-[0-9a-f]{12}\.(?:png|webp)',
                            rb'\1.png', blob(repo, ref, document)).replace(b'_2k.png', b'_4k.png')
            entries[index] = document.encode() + b'\t' + hashlib.sha256(readme).hexdigest().encode()
    return hashlib.sha256(b'\0'.join(entries)).hexdigest()


# Reviewed v0.63.0 packaging-only changes. Any later code edit invalidates
# this equivalence; payload bytes themselves remain in the visual fingerprint.
FONT_PACKAGING_EQUIVALENCE = {'src/scripts/steps/fonts.py': ('6f4912e04de79b1a56d11462badd3f90eadd4eaf', 'e7791550d140d5556939697041c92f197fb4e41d'), 'nix/packages.nix': ('5c0207d9554df4e414c9d4dcea9d99709a66ccf3', '1cd61cc57b9c3f2fdfa05bfaaaf8937ec2599e3b')}
FONT_BUNDLE_IMPLEMENTATION = 'eafb4b4909c933982b80360d07a72d3a27a3ee69'

def visual_tree(repo: Path, ref: str, *, ignore_paths: frozenset[str] = frozenset()) -> str:
    """Conservative visual inputs; unknown runtime changes require new evidence.

    Keep runtime_tree unchanged so historical manifest hashes remain verifiable.
    Console updater and repository maintenance commands have no rendered output.
    """
    console_messages = {
        'Dock preset update failed',
        'Update available: {current} → {latest}',
        'Keeping local source: changes present or not a clean git checkout',
        'Could not verify the published update — keeping the current checkout',
        'Keeping local commits: the release is not a fast-forward',
        'Compacting Git storage: {path}',
        'Recovered {size} MiB. Git ancestry and local recovery data were preserved.',
        'Published historical files may download again on demand; current source and local work stay available.',
        'Git maintenance disabled by local configuration.',
        'Recovered {size} MiB. Git history and recovery data were preserved.',
        'Files still referenced by Git history remain; cleanup does not remove older commits.',
        'Git maintenance could not finish: {reason}',
        'No independent Git checkout (archives need no Git cleanup).',
        'Shared object store or linked worktrees; leaving it unchanged.',
        'Not the root of a Git checkout.',
    }
    entries = []
    font_entries = {}
    for entry in subprocess.check_output(['git', '-C', str(repo), 'ls-tree', '-rz', ref]).split(b'\0'):
        if not entry:
            continue
        metadata, raw_path = entry.split(b'\t', 1)
        path = raw_path.decode()
        if (path in ignore_paths or path in ('VERSION', '.dockerignore') or path.endswith('.md') or path.startswith(('tests/', 'src/screenshots/', '.github/'))
                or path in ('src/scripts/release_screenshots.py', 'src/scripts/release_screenshots_cli.py',
                            'src/scripts/repository_maintenance.py', 'src/scripts/repository_history.py',
                            'src/scripts/repository_cache.py')):
            continue
        object_id = metadata.split()[-1].decode()
        if path == 'src/scripts/font_bundle.py' and object_id == FONT_BUNDLE_IMPLEMENTATION:
            continue
        equivalence = FONT_PACKAGING_EQUIVALENCE.get(path)
        if equivalence and object_id == equivalence[0]:
            entries.append(metadata.rsplit(b' ', 1)[0] + b' ' + equivalence[1].encode() + b'\t' + raw_path)
            continue
        if path.startswith('src/offline/fonts/'):
            if path.endswith(('.otf', '.ttf')):
                font_entries[path] = hashlib.sha256(blob(repo, ref, path)).hexdigest()
                continue
            if path.endswith('/fonts.json'):
                continue
            if path.endswith('/fonts.tar.xz'):
                from font_bundle import unpacked_fonts
                manifest = json.loads(blob(repo, ref, 'src/offline/fonts/fonts.json'))
                for name, data in unpacked_fonts(blob(repo, ref, path), manifest).items():
                    font_path = 'src/offline/fonts/' + name
                    require(font_path not in font_entries, 'Duplicate packed font')
                    font_entries[font_path] = hashlib.sha256(data).hexdigest()
                continue
        if path == 'src/scripts/cli.py':
            module = ast.parse(blob(repo, ref, path))
            module.body = [node for node in module.body if not (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and
                node.name in ('auto_update_and_reexec', '_update_published_checkout', '_repo_is_clean_git_checkout', '_git'))]
            content = ast.dump(module, include_attributes=False).encode()
        elif path == 'src/scripts/theme_switch.py':
            module = ast.parse(blob(repo, ref, path))
            # Clock readiness affects when a scheduled transition runs, not
            # the rendering of either mode. Keep the mode selection and every
            # apply/render function in the fingerprint.
            module.body = [node for node in module.body if not (
                isinstance(node, ast.FunctionDef) and node.name == 'wait_for_clock_sync')]
            readiness_guard = ast.dump(ast.parse(
                'if not wait_for_clock_sync():\n'
                '    print("theme apply: waiting for clock synchronization; "\n'
                '          "automatic service will retry", file=sys.stderr)\n'
                '    return 75').body[0])
            for node in ast.walk(module):
                if isinstance(node, ast.FunctionDef) and node.name == 'main':
                    for statement in ast.walk(node):
                        if isinstance(statement, ast.If):
                            statement.body = [child for child in statement.body
                                              if ast.dump(child) != readiness_guard]
            content = ast.dump(module, include_attributes=False).encode()
        elif path == 'src/offline/mac-tahoe-liquid-kde-theme.service':
            # Only the known clock-readiness retry policy is nonvisual. Changes
            # to ExecStart, ordering or other service behavior remain visible.
            retry_settings = {'RestartForceExitStatus=75', 'RestartSec=15s',
                              'TimeoutStartSec=3min'}
            content = '\n'.join(line.strip() for line in blob(repo, ref, path).decode().splitlines()
                                if line.strip() and not line.lstrip().startswith('#')
                                and line.strip() not in retry_settings).encode()
        elif path in ('install', 'installer'):
            module = ast.parse(blob(repo, ref, path))
            # These branches maintain storage before the wizard is loaded.
            # Keep every other entry-point statement in the visual fingerprint.
            maintenance_tests = {ast.dump(ast.parse(test, mode='eval').body) for test in (
                'sys.argv[1:] == ["--free-space"]',
                'os.environ.get("MAC_TAHOE_UPDATED") == "1"')}
            module.body = [node for node in module.body if not (
                isinstance(node, ast.If) and ast.dump(node.test) in maintenance_tests)]
            content = ast.dump(module, include_attributes=False).encode()
        elif path == 'src/scripts/localization.py':
            module = ast.parse(blob(repo, ref, path))
            for node in ast.walk(module):
                if isinstance(node, ast.Dict):
                    pairs = [(key, value) for key, value in zip(node.keys, node.values)
                             if not (isinstance(key, ast.Constant) and key.value in console_messages)]
                    node.keys = [key for key, value in pairs]
                    node.values = [value for key, value in pairs]
            content = ast.dump(module, include_attributes=False).encode()
        elif path.startswith('src/scripts/locales/') and path.endswith('.json'):
            catalog = json.loads(blob(repo, ref, path))
            content = json.dumps({k: v for k, v in catalog.items() if k not in console_messages},
                                 sort_keys=True, ensure_ascii=False).encode()
        else:
            entries.append(entry)
            continue
        entries.append(metadata.split(b' ', 1)[0] + b'\t' + raw_path + b'\t' +
                       hashlib.sha256(content).hexdigest().encode())
    entries.extend((path + '\t' + digest).encode() for path, digest in sorted(font_entries.items()))
    return hashlib.sha256(b'\0'.join(entries)).hexdigest()



def _scoped_python(repo: Path, ref: str, path: str) -> dict[str, str]:
    module = ast.parse(blob(repo, ref, path))
    functions = {}
    def strip(body, prefix=''):
        kept = []
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Adding an optional crop does not change existing uncropped calls.
                if node.name == 'picture':
                    pairs = [(arg, value) for arg, value in zip(node.args.kwonlyargs, node.args.kw_defaults)
                             if arg.arg != 'crop']
                    node.args.kwonlyargs = [pair[0] for pair in pairs]
                    node.args.kw_defaults = [pair[1] for pair in pairs]
                    for parent in ast.walk(node):
                        if isinstance(parent, (ast.For, ast.FunctionDef)):
                            parent.body = [child for child in parent.body if not (
                                isinstance(child, ast.If) and
                                ast.dump(child.test) == ast.dump(ast.parse('crop is not None', mode='eval').body))]
                functions[prefix + node.name] = ast.dump(node, include_attributes=False)
            else:
                if isinstance(node, ast.ClassDef):
                    node.body = strip(node.body, node.name + '.')
                kept.append(node)
        return kept
    module.body = strip(module.body)
    functions['<module>'] = ast.dump(module, include_attributes=False)
    return functions


# Dependency scope for the audited v0.63.4 Dock migration. These exact changes
# REQUIRE four new Dock frames, never visual equivalence or old Dock approval.
# Other components retain their own reviewed provenance. Any subsequent edit
# falls through to the conservative full-frame dependency check.
DOCK_MIGRATION_CAPTURE_DEPENDENCIES = {'src/offline/layouts/mac-tahoe.js': ('bb43a915eced126315f2b43144d09ce6d4751005', '40cc46eaaafa4a551287d536d7ce6f0663b07851'), 'src/offline/layouts/migrate-dock-preset.js': (None, '5f2775b105d98829f408e12965dfb918b33a850a'), 'src/offline/look-and-feel/MacTahoeLiquidKde-Dark/contents/layouts/org.kde.plasma.desktop-layout.js': ('3753a072afd83668c3b861678d9cb3f20425e204', 'e67912b73cd1395244d7f6e1c6f93e71a2ebbb83'), 'src/offline/look-and-feel/MacTahoeLiquidKde-Light/contents/layouts/org.kde.plasma.desktop-layout.js': ('3753a072afd83668c3b861678d9cb3f20425e204', 'e67912b73cd1395244d7f6e1c6f93e71a2ebbb83'), 'src/scripts/cli.py': ('54e5f5ef24867e746d992458f51e713d605222bf', '497dbdf4a75c8560435835b5419c6c072c88638b'), 'src/scripts/steps/layout.py': ('726d4a233c49e4faa313fe5f8c682294c690f5be', '92aa0d474bb77062728ced998edd591245a6c8c8')}

# The reviewed optional-apps transition changes the Dock and the wizard's
# Desktop/Summary surfaces only. These exact source blobs REQUIRE twelve new
# frames across both editions/modes; no affected frame may reuse old approval.
# Unknown or subsequent edits still invalidate the complete gallery.
DOCK_APPS_CAPTURE_DEPENDENCIES = {'src/installer/wizard_window.py': (('f0b682104a8f8c30af28c94ad954bb3b2535a5f7',),
                                    '6c14f892d4d5249d2f93373c7b6fc8c2488da1bc'),
 'src/offline/layouts/mac-tahoe.js': (('bb43a915eced126315f2b43144d09ce6d4751005',
                                       '40cc46eaaafa4a551287d536d7ce6f0663b07851'),
                                      'b59e603999e87e5a14e527be37591235a95e12eb'),
 'src/offline/layouts/migrate-dock-preset.js': ((None, '5f2775b105d98829f408e12965dfb918b33a850a'),
                                                '0abd3dde7947370e1a179ff2e6f14a9ca317c0d0'),
 'src/offline/look-and-feel/MacTahoeLiquidKde-Dark/contents/layouts/org.kde.plasma.desktop-layout.js': (('3753a072afd83668c3b861678d9cb3f20425e204',
                                                                                                         'e67912b73cd1395244d7f6e1c6f93e71a2ebbb83'),
                                                                                                        'a729045e55adc283bc39840e59b3a7633f396e0c'),
 'src/offline/look-and-feel/MacTahoeLiquidKde-Light/contents/layouts/org.kde.plasma.desktop-layout.js': (('3753a072afd83668c3b861678d9cb3f20425e204',
                                                                                                          'e67912b73cd1395244d7f6e1c6f93e71a2ebbb83'),
                                                                                                         'a729045e55adc283bc39840e59b3a7633f396e0c'),
 'src/scripts/cli.py': (('54e5f5ef24867e746d992458f51e713d605222bf',
                         '497dbdf4a75c8560435835b5419c6c072c88638b'),
                        '4875c6a5dc856a7febfc61024a285de5550c1b14'),
 'src/scripts/distro.py': (('625c03a418043256ef5eb6bc840f205293f7e1c4',),
                           'fb6f6910e9c8b1f3578b789907d10fbe14b0594b'),
 'src/scripts/dock_apps.py': ((None,), 'c8f10500f4a6a8037d419cd2d28cb173b939c7d1'),
 'src/scripts/installer_choices.py': (('f534f66933f6f25c5ff8da8323a2bc5228c0fe72',),
                                      '4b3c74bc178133463148849d2191022f42897f7f'),
 'src/scripts/locales/de.json': (('c90e4ea92abd6f34885def7cf711bdcc177338fb',
                                  '0b28916cd69f7c35069a1362568374da72e8c585'),
                                 'd2c9fa18f91830852967c4a79a37611209820ac5'),
 'src/scripts/locales/pt_BR.json': (('3b4495ba7ab23cd88275be51750aea0e3420e7cb',
                                     '27e7930142da4c128c15b57c9db876b94d295123'),
                                    '3dfb1b4827ae3d08aa7898e70a53dab2df75dd07'),
 'src/scripts/localization.py': (('652ea732bbcc6315ac4963e9251a034dd72e342c',
                                  'a92dd60bfdb4307b879c5c21be13d865a30fb6d7'),
                                 '161bccdf7b0e19ee9672b8acd089ff31c95d1162'),
 'src/scripts/steps/apps.py': (('18de9c3f402f7a8f74b2f32d2a838723bb867614',),
                               '779d5cb9a53d77e0b9b1ab096c0c020b72ac85de'),
 'src/scripts/steps/layout.py': (('726d4a233c49e4faa313fe5f8c682294c690f5be',
                                  '92aa0d474bb77062728ced998edd591245a6c8c8'),
                                 '6f5b66a3e295e1a2baa3fadaa52e9637b6cb8c9a')}

def affected_frames(repo: Path, source: str, target: str) -> set[str]:
    """Conservative dependencies: unknown changes invalidate every frame."""
    all_frames = expected_frames()
    if visual_tree(repo, source) == visual_tree(repo, target):
        return set()
    changed = set(git(repo, 'diff', '--name-only', source, target).splitlines())
    ignored = set()
    affected = set()
    def cases(names, editions=EDITIONS):
        affected.update(f'{e}-{m}-{c}' for e in editions for m in MODES for c in names)
    for path in changed:
        app_dependency = DOCK_APPS_CAPTURE_DEPENDENCIES.get(path)
        if app_dependency:
            def app_object_at(ref):
                entry = git(repo, 'ls-tree', ref, '--', path)
                return entry.split()[2] if entry else None
            previous, current = app_dependency
            if app_object_at(source) in previous and app_object_at(target) == current:
                cases(['dock', 'installer-layout', 'installer-summary'])
                ignored.add(path)
                continue
        dependency = DOCK_MIGRATION_CAPTURE_DEPENDENCIES.get(path)
        if dependency:
            def object_at(ref):
                entry = git(repo, 'ls-tree', ref, '--', path)
                return entry.split()[2] if entry else None
            if (object_at(source), object_at(target)) == dependency:
                cases(['dock'])
                ignored.add(path)
                continue
        if path == 'src/installer/wizard_window.py':
            before, after = (_scoped_python(repo, ref, path) for ref in (source, target))
            methods = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
            allowed = {'InstallerWindow.page_glass_style': 'installer-glass_style',
                       'InstallerWindow.page_summary': 'installer-summary'}
            if methods - allowed.keys():
                return all_frames
            cases([allowed[key] for key in methods])
        elif path == 'src/scripts/paths.py':
            normalized = []
            for ref in (source, target):
                module = ast.parse(blob(repo, ref, path))
                module.body = [node for node in module.body if not (
                    isinstance(node, ast.FunctionDef) and node.name == 'read_version'
                    or isinstance(node, ast.Import) and
                    all(alias.name == 're' and alias.asname is None for alias in node.names))]
                normalized.append(ast.dump(module, include_attributes=False))
            if normalized[0] != normalized[1]:
                return all_frames
            cases(['installer-welcome', 'about'])
        elif path == 'src/scripts/installer_choices.py':
            normalized = []
            for ref in (source, target):
                module = ast.parse(blob(repo, ref, path))
                for node in ast.walk(module):
                    if isinstance(node, ast.Dict):
                        pairs = [(k, v) for k, v in zip(node.keys, node.values)
                                 if not isinstance(k, ast.Constant) or k.value != 'glass_style']
                        node.keys = [k for k, _ in pairs]
                        node.values = [v for _, v in pairs]
                    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'dict':
                        node.keywords = [k for k in node.keywords if k.arg != 'glass_style']
                normalized.append(ast.dump(module, include_attributes=False))
            if normalized[0] != normalized[1]:
                return all_frames
            cases(['installer-glass_style', 'installer-summary'])
        elif path == 'src/scripts/steps/acrylic_glass.py':
            before, after = (_scoped_python(repo, ref, path) for ref in (source, target))
            methods = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
            if methods - {'_edition_preset', '_install_backing_tint'}:
                return all_frames
            cases([case for case in CASES if not case.startswith('installer-')])
        elif path == 'src/scripts/glass_surfaces.py':
            before, after = (_scoped_python(repo, ref, path) for ref in (source, target))
            methods = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
            if methods - {'apply_plasma_surface_defaults'}:
                return all_frames
            cases(['launcher', 'menu', 'context'], ['golden-gate'])
        elif path.startswith('src/installer/assets/glass-preset-'):
            cases(['installer-glass_style'])
        elif path == 'src/installer/assets/sources.json':
            before, after = (json.loads(blob(repo, ref, path)) for ref in (source, target))
            keys = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
            if any(not key.startswith('glass-preset-') for key in keys):
                return all_frames
            cases(['installer-glass_style'])
        elif path == 'src/scripts/release_capture.py':
            # Orchestration selects frames; each selected frame still uses the
            # pinned guest renderer, readback, stability and identity checks.
            pass
        else:
            continue
        ignored.add(path)
    if visual_tree(repo, source, ignore_paths=frozenset(ignored)) != visual_tree(
            repo, target, ignore_paths=frozenset(ignored)):
        return all_frames
    return affected


def frame_origin(manifest: dict, frame: dict) -> tuple[str, str, str]:
    return (frame.get('source_commit', manifest['source_commit']),
            frame.get('source_tree', manifest['source_tree']),
            frame.get('source_version', manifest['version']))


def verify_frame_origins(repo: Path, manifest: dict, target: str) -> None:
    require(runtime_tree(repo, manifest['source_commit']) == manifest['source_tree'],
            'Inconsistent capture source tree')
    cache = {}
    for name, frame in manifest['frames'].items():
        source, tree, version = frame_origin(manifest, frame)
        if source not in cache:
            require(runtime_tree(repo, source) == tree, 'Inconsistent frame source tree')
            require(git(repo, 'show', source + ':VERSION') == version, 'Frame source version mismatch')
            require(subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', source, target],
                                   capture_output=True).returncode == 0, 'Frame source is not an ancestor')
            cache[source] = (tree, version, affected_frames(repo, source, target))
        require(cache[source][:2] == (tree, version), 'Inconsistent frame origin')
        require(name not in cache[source][2], 'Affected frame needs recapture: ' + name)


def verify_visual_source(repo: Path, source: str, target: str, source_tree: str) -> None:
    require(runtime_tree(repo, source) == source_tree, 'Inconsistent capture source tree')
    require(subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', source, target],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0,
            'Capture source is not an ancestor of this release')
    require(visual_tree(repo, source) == visual_tree(repo, target),
            'Visual release source changed after capture; recapture required')


def material_values(presets: list[dict], case: str) -> dict:
    material, variant = MATERIAL_CASES[case]
    preset = next(p for p in presets if p['value'] == material)
    values = dict(preset['values'])
    if variant:
        values.update(preset.get('tinted_values', {}))
    return values | {'MaterialPreset': material, 'BackingTint': variant}


def expected_frames() -> set[str]:
    return {f'{edition}-{mode}-{case}' for edition in EDITIONS for mode in MODES for case in CASES} | {'boot', 'shutdown'}


def blob(repo: Path, ref: str, path: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(repo), 'show', f'{ref}:{path}'])


def effect_identity(repo: Path, ref: str) -> str:
    """Mirror the compiled effect's source identity, including embedded shaders."""
    prefix = 'src/offline/kwin-effects/acrylic-glass/src/'
    paths = git(repo, 'ls-tree', '-r', '--name-only', ref, '--', prefix).splitlines()
    selected = [p for p in paths if p.endswith(('.cpp', '.h', '.kcfg', '.kcfgc'))
                or p.startswith(prefix + 'shaders/') or p == prefix + 'metadata.json']
    require(bool(selected), 'Release has no Acrylic Glass sources')
    hashes = ''.join(hashlib.sha256(blob(repo, ref, p)).hexdigest() for p in sorted(selected))
    return hashlib.sha256(hashes.encode()).hexdigest()


def image_name(edition: str, mode: str, case: str) -> str:
    _, preset, suffix = EDITIONS[edition]
    if case == 'launcher':
        return f'launcher_preset_{preset}_{mode}.png'
    if case == 'showcase':
        return f'showcase_{mode}_4k.png'
    name = {'context': 'context_menu', 'dock': 'dock_1'}.get(case, case)
    return f"{name}{'_dark' if mode == 'dark' else ''}_{suffix}.png"


def original_image_name(name: str) -> str:
    return re.sub(r'-[0-9a-f]{12}(?=\.png$)', '', str(Path(name).with_suffix('.png'))).replace('_2k.png', '_4k.png')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify_desktop_window(case: str, windows: list[dict]) -> dict:
    """Desktop showcase frames contain one focused application, never two."""
    caption = 'About This Computer (preview)' if case == 'about' else 'Documents'
    clients = [window for window in windows if window.get('type') not in (1, 2)]
    require(len(clients) == 1, f'{case}: desktop capture must show exactly one application')
    window = clients[0]
    require(window.get('caption') == caption, f'{case}: unexpected desktop application')
    if case != 'about':
        require(window.get('resourceClass') == 'org.gnome.Nautilus', f'{case}: Files window is missing')
    require(window.get('active') is True, f'{case}: desktop application is not focused')
    return window


def verify_icon_appearance(name: str, record: dict) -> None:
    if name in ('boot', 'shutdown'):
        return
    mode = next(m for e in EDITIONS for m in MODES if name.startswith(f'{e}-{m}-'))
    expected = 'MacTahoeLiquidKde-Icons-Regular-' + mode.capitalize()
    require(record.get('appearance', {}).get('Icons') == expected, f'Wrong icon appearance: {name}')


def validate(repo: Path, ref: str, bundle: Path, *, reviewed: bool = True) -> dict:
    from PIL import Image
    manifest = json.loads((bundle / 'manifest.json').read_text())
    require(manifest.get('schema') in (1, 2), 'Unsupported screenshot manifest')
    source = commit_id(repo, manifest['source_commit'])
    target = commit_id(repo, ref)
    require(subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', source, target],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0,
            'Capture source is not an ancestor of this release')
    if manifest.get('schema') == 2:
        verify_frame_origins(repo, manifest, target)
    else:
        verify_visual_source(repo, source, target, manifest['source_tree'])
    require(manifest['version'] == git(repo, 'show', source + ':VERSION'),
            'Capture version differs from its original source')
    require(json.loads(blob(repo, target, 'src/scripts/defaults.json')) ==
            {'wallpaper': EDITIONS['tahoe'][0], 'launcher_preset': EDITIONS['tahoe'][1]},
            'Tahoe defaults differ from the capture recipe')
    profile = json.loads(PROFILE.read_text())
    require(manifest['profile_sha256'] == digest(PROFILE), 'Capture recipe changed; recapture required')
    require(manifest['vm_image_sha256'] == profile['vm_image_sha256'], 'Unpinned capture VM')
    require(set(manifest['frames']) == expected_frames(), 'Missing or unexpected release captures')
    require(re.fullmatch('[a-f0-9]{64}', manifest['effect_build']) is not None, 'Missing active effect identity')
    require(manifest['effect_build'] == effect_identity(repo, source), 'Loaded effect differs from the release source')
    for name, record in manifest['frames'].items():
        path = bundle / 'frames' / (name + '.png')
        require(not path.is_symlink() and path.is_file(), f'Missing capture: {name}')
        require(digest(path) == record['sha256'], f'Capture changed: {name}')
        with Image.open(path) as image:
            require(image.format == 'PNG' and list(image.size) == profile['resolution'], f'Wrong resolution: {name}')
        if name in ('boot', 'shutdown'):
            require(record.get('plymouth_verified') is True, f'Unverified Plymouth capture: {name}')
            continue
        edition, mode, case = next((e, m, c) for e in EDITIONS for m in MODES for c in CASES
                                   if name == f'{e}-{m}-{c}')
        require(record['effect_build'] == manifest['effect_build'], f'Stale effect: {name}')
        require(record['appearance']['Plasma'] == 'MacTahoeLiquidKde-' + mode.capitalize(), f'Wrong appearance: {name}')
        verify_icon_appearance(name, record)
        require(record['wallpaper'] == EDITIONS[edition][0], f'Wrong wallpaper: {name}')
        require(record['launcher_preset'] == EDITIONS[edition][1], f'Wrong launcher preset: {name}')
        require(record.get('stable_frames') is True, f'Unsettled capture: {name}')
        require(record.get('window_verified') is True, f'Unverified window: {name}')
        if case.startswith('installer-'):
            require(record.get('installer_page') == case.removeprefix('installer-'),
                    f'Wrong installer page: {name}')
            require(record.get('installer_edition') == EDITIONS[edition][0],
                    f'Wrong installer edition: {name}')
        if case in ('finder', 'showcase', 'about') or case in MATERIAL_CASES:
            verify_desktop_window(case, record['windows'])
        if case in MATERIAL_CASES:
            presets = json.loads(blob(repo, source, 'src/offline/kwin-effects/acrylic-glass/src/presets.json'))
            require(record.get('material_values') == material_values(presets, case), f'Wrong glass material: {name}')
        if case in ('finder', 'showcase') or case in MATERIAL_CASES:
            from screenshot_checks import check_files_pixels
            with Image.open(path) as image:
                check_files_pixels(image, mode, record['windows'], profile['scale'])
    if reviewed:
        review = json.loads((bundle / 'review.json').read_text())
        require(review.get('manifest_sha256') == digest(bundle / 'manifest.json'), 'Review belongs to another capture run')
        require(review.get('approved') == {n: r['sha256'] for n, r in manifest['frames'].items()},
                'Every fresh frame must be reviewed; old screenshots cannot fill gaps')
        require(not review.get('rejected'), 'Rejected screenshots block publication')
    return manifest


def stage(repo: Path, edition: str, bundle: Path, manifest: dict) -> None:
    """Replace the complete screenshot set only after validating the whole run."""
    from PIL import Image
    import shutil
    import tempfile
    with tempfile.TemporaryDirectory(prefix='mttkde-stage-') as directory:
        prepared = Path(directory)
        (prepared / 'src/screenshots').mkdir(parents=True)
        documents = [name for name in SCREENSHOT_DOCS if (repo / name).is_file()]
        for name in documents:
            shutil.copyfile(repo / name, prepared / name)
        _stage(prepared, edition, bundle, manifest)
        out = repo / 'src/screenshots'
        out.mkdir(parents=True, exist_ok=True)
        for path in (prepared / 'src/screenshots').iterdir():
            shutil.copyfile(path, out / path.name)
        for name in documents:
            shutil.copyfile(prepared / name, repo / name)
        staged = json.loads((out / 'release-capture.json').read_text())['images']
        replaced = {original_image_name(name) for name in staged}
        replaced.update(f"launcher{s}_{EDITIONS[edition][2]}.png" for s in ('', '_dark'))
        for path in out.iterdir():
            if path.suffix in ('.png', '.webp') and original_image_name(path.name) in replaced and path.name not in staged:
                path.unlink()
        for name in ('capture.json', 'launcher-presets.json', 'appearance-review.json'):
            (out / name).unlink(missing_ok=True)


def _stage(repo: Path, edition: str, bundle: Path, manifest: dict) -> None:
    from PIL import Image
    import shutil
    out = repo / 'src/screenshots'
    records = {}
    replacements = {}
    readme = repo / 'README.md'
    readme_images = {original_image_name(name) for name in re.findall(
        r'src/screenshots/([\w.-]+\.(?:png|webp))', readme.read_text() if readme.exists() else '')}
    for name, record in manifest['frames'].items():
        if name in ('boot', 'shutdown'):
            filename = f"boot{'_shutdown' if name == 'shutdown' else ''}_{EDITIONS[edition][2]}.png"
        elif name.startswith(edition + '-'):
            mode, case = name[len(edition) + 1:].split('-', 1)
            filename = image_name(edition, mode, case)
        else:
            continue
        source = bundle / 'frames' / (name + '.png')
        origin, _, origin_version = frame_origin(manifest, record)
        exports = [(filename, record.get('crop'))]
        if name.startswith(edition + '-') and case == 'about':
            exports.append((f'desktop_about_{mode}_4k.png', None))
        for filename, crop in exports:
            max_edge = README_MAX_EDGE if filename in readme_images else AUXILIARY_MAX_EDGE
            if '-installer-' in name:
                max_edge = None
            with Image.open(source) as image:
                if crop:
                    require(0 <= crop[0] < crop[2] <= image.width and 0 <= crop[1] < crop[3] <= image.height,
                            f'Invalid crop: {name}')
                    image = image.crop(crop)
                if max_edge:
                    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
                output = out / Path(filename.replace('_4k.png', '_2k.png')).with_suffix('.webp')
                image.save(output, format='WEBP', quality=EXPORT_QUALITY, method=6)
                export = dict(format='webp', size=list(image.size), quality=EXPORT_QUALITY,
                              max_edge=max_edge, source_sha256=record['sha256'])
            checksum = digest(output)
            hashed = output.stem + '-' + checksum[:12] + '.webp'
            output.rename(out / hashed)
            replacements[filename] = hashed
            records[hashed] = dict(record, crop=crop, frame_name=name, source_commit=origin,
                                   source_release='v' + origin_version, sha256=checksum, export=export)
    for name in SCREENSHOT_DOCS:
        document = repo / name
        if not document.is_file():
            continue
        content = re.sub(r'src/screenshots/([\w.-]+\.(?:png|webp))',
                         lambda match: 'src/screenshots/' + replacements.get(original_image_name(match[1]), match[1]),
                         document.read_text())
        required = set(re.findall(r'src/screenshots/([\w.-]+\.(?:png|webp))', content)) - STATIC_ART
        require(required <= records.keys(), f'Uncaptured {document.stem} images: {sorted(required - records.keys())}')
        document.write_text(content)
    (out / 'release-capture.json').write_text(json.dumps({
        'schema': manifest['schema'], 'version': manifest['version'], 'source_commit': manifest['source_commit'],
        'source_tree': manifest['source_tree'], 'profile_sha256': manifest['profile_sha256'],
        'vm_image_sha256': manifest['vm_image_sha256'], 'effect_build': manifest['effect_build'],
        'edition': edition, 'images': records, 'review': json.loads((bundle / 'review.json').read_text()),
        'capture_manifest': manifest,
    }, indent=2) + '\n')
    # Retired manifests must not continue to claim an older release was captured.
    for name in ('capture.json', 'launcher-presets.json', 'appearance-review.json'):
        (out / name).unlink(missing_ok=True)


def verify_committed(repo: Path, ref: str, *, tahoe: Path | None = None) -> dict:
    """Release gate: read Git objects, never unchecked working-tree images."""
    ref = commit_id(repo, ref)
    record = json.loads(blob(repo, ref, 'src/screenshots/release-capture.json'))
    version = git(repo, 'show', ref + ':VERSION')
    capture_version = record['version']
    edition = record['edition']
    require(edition in EDITIONS, 'Unknown screenshot edition')
    source_repo = tahoe or repo
    source = record['source_commit']
    target = ref
    if edition == 'golden-gate':
        require(tahoe is not None, 'Golden Gate validation requires the pinned Tahoe checkout')
        pin = json.loads(blob(repo, ref, 'upstream.json'))
        target = pin['commit']
        require(git(source_repo, 'show', target + ':VERSION') == version, 'Golden Gate pin/version mismatch')
        require(commit_id(source_repo, 'v' + version) == target, 'Golden Gate must pin the published Tahoe release tag')
        require(json.loads(blob(repo, ref, 'defaults.json')) ==
                {'wallpaper': EDITIONS[edition][0], 'launcher_preset': EDITIONS[edition][1]},
                'Golden Gate defaults differ from the capture recipe')
    if record.get('schema') == 2:
        verify_frame_origins(source_repo, record['capture_manifest'], target)
    else:
        verify_visual_source(source_repo, source, target, record['source_tree'])
    require(capture_version == git(source_repo, 'show', source + ':VERSION'),
            'Capture version differs from its original source')
    manifest = record['capture_manifest']
    require(set(manifest['frames']) == expected_frames(), 'Incomplete release capture')
    require(manifest['version'] == capture_version and manifest['source_commit'] == source and
            manifest['source_tree'] == record['source_tree'], 'Inconsistent capture provenance')
    profile_bytes = blob(source_repo, target, 'src/scripts/release_capture_profile.json')
    require(hashlib.sha256(profile_bytes).hexdigest() == record['profile_sha256'] == manifest['profile_sha256'],
            'Capture recipe changed; recapture required')
    require(json.loads(profile_bytes)['vm_image_sha256'] == record['vm_image_sha256'] == manifest['vm_image_sha256'],
            'Unpinned capture VM')
    require(effect_identity(source_repo, target) == record['effect_build'] == manifest['effect_build'],
            'Loaded effect differs from the release source')
    review = record['review']
    manifest_bytes = (json.dumps(manifest, indent=2) + '\n').encode()
    require(review['manifest_sha256'] == hashlib.sha256(manifest_bytes).hexdigest(), 'Review belongs to another capture run')
    require(not review.get('rejected') and review['approved'] == {n: r['sha256'] for n, r in manifest['frames'].items()},
            'Every release capture must be reviewed')
    for name, frame in manifest['frames'].items():
        verify_icon_appearance(name, frame)
        case = next((c for c in MATERIAL_CASES if name.endswith('-' + c)), None)
        if case:
            presets = json.loads(blob(source_repo, source, 'src/offline/kwin-effects/acrylic-glass/src/presets.json'))
            require(frame.get('material_values') == material_values(presets, case), f'Wrong glass material: {name}')
            verify_desktop_window(case, frame['windows'])
        if name.endswith(('-finder', '-showcase', '-about')):
            verify_desktop_window(name.rsplit('-', 1)[1], frame['windows'])
    committed_docs = set(git(repo, 'ls-tree', '--name-only', ref, '--', *SCREENSHOT_DOCS).splitlines())
    required = set()
    for name in committed_docs:
        required.update(re.findall(r'src/screenshots/([\w.-]+\.(?:png|webp))', blob(repo, ref, name).decode()))
    required -= STATIC_ART
    require(required <= record['images'].keys(), 'Missing release screenshots')
    expected = {image_name(edition, m, c) for m in MODES for c in CASES}
    expected.update(f'boot{s}_{EDITIONS[edition][2]}.png' for s in ('', '_shutdown'))
    expected.update(f'desktop_about_{mode}_4k.png' for mode in MODES)
    require(expected <= {original_image_name(name) for name in record['images']}, 'Missing release screenshots')
    readme_images = {original_image_name(name) for name in re.findall(
        r'src/screenshots/([\w.-]+\.(?:png|webp))', blob(repo, ref, 'README.md').decode())}
    for name, image in record['images'].items():
        require(re.fullmatch(r'[\w.-]+\.(?:png|webp)', name) is not None, 'Invalid screenshot filename')
        require(name.endswith('-' + image['sha256'][:12] + Path(name).suffix), 'Screenshot URL is missing its content hash: ' + name)
        require(hashlib.sha256(blob(repo, ref, 'src/screenshots/' + name)).hexdigest() == image['sha256'],
                'Screenshot changed after review: ' + name)
        if name.endswith('.webp'):
            from io import BytesIO
            from PIL import Image
            export = image.get('export', {})
            limit = README_MAX_EDGE if original_image_name(name) in readme_images else AUXILIARY_MAX_EDGE
            if '-installer-' in image['frame_name']:
                limit = None
            require(export.get('format') == 'webp' and export.get('quality') == EXPORT_QUALITY and
                    export.get('max_edge') == limit and
                    export.get('source_sha256') == manifest['frames'][image['frame_name']]['sha256'],
                    'Invalid screenshot export provenance: ' + name)
            with Image.open(BytesIO(blob(repo, ref, 'src/screenshots/' + name))) as exported:
                require(exported.format == 'WEBP' and list(exported.size) == export.get('size') and
                        (limit is None or max(exported.size) <= limit),
                        'Invalid screenshot export dimensions: ' + name)
        image_source, _, image_version = (frame_origin(manifest, manifest['frames'][image['frame_name']])
                                          if record.get('schema') == 2 else (source, '', capture_version))
        require(image['source_commit'] == image_source and image['source_release'] == 'v' + image_version,
                'Stale screenshot: ' + name)
    return record
