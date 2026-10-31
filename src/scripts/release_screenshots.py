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
                   'effects', 'window_controls', 'shadows', 'fonts', 'firefox', 'files', 'boot', 'oled', 'summary')
CASES = ('launcher', 'dock', 'menu', 'context', 'finder', 'showcase', 'about') + tuple(
    'installer-' + page for page in INSTALLER_PAGES)
MODES = ('light', 'dark')
RECIPE_FILES = ('release_capture.py', 'release_capture_guest.py', 'release_capture_profile.json',
                'release_screenshots.py', 'screenshot_checks.py', 'release_capture_wizard.py')
STATIC_ART = {'banner_v3.png', 'banner.png', 'macos-26.png', 'macos-27.png', 'macos-27-dark.png'}
SCREENSHOT_DOCS = ('README.md', 'TESTING.md')


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
            readme = re.sub(rb'(src/screenshots/[\w.-]+)-[0-9a-f]{12}(\.png)',
                            rb'\1\2', blob(repo, ref, document))
            entries[index] = document.encode() + b'\t' + hashlib.sha256(readme).hexdigest().encode()
    return hashlib.sha256(b'\0'.join(entries)).hexdigest()


def visual_tree(repo: Path, ref: str) -> str:
    """Conservative visual inputs; unknown runtime changes require new evidence.

    Keep runtime_tree unchanged so historical manifest hashes remain verifiable.
    Console updater and repository maintenance commands have no rendered output.
    """
    console_messages = {
        'Update available: {current} → {latest}',
        'Keeping local source: changes present or not a clean git checkout',
        'Could not verify the published update — keeping the current checkout',
        'Keeping local commits: the release is not a fast-forward',
        'Compacting Git storage: {path}',
        'Recovered {size} MiB. Git history and recovery data were preserved.',
        'Files still referenced by Git history remain; cleanup does not remove older commits.',
        'Git maintenance could not finish: {reason}',
        'No independent Git checkout (archives need no Git cleanup).',
        'Shared object store or linked worktrees; leaving it unchanged.',
        'Not the root of a Git checkout.',
    }
    entries = []
    for entry in subprocess.check_output(['git', '-C', str(repo), 'ls-tree', '-rz', ref]).split(b'\0'):
        if not entry:
            continue
        metadata, raw_path = entry.split(b'\t', 1)
        path = raw_path.decode()
        if (path == 'VERSION' or path.endswith('.md') or path.startswith(('tests/', 'src/screenshots/', '.github/'))
                or path in ('src/scripts/release_screenshots.py', 'src/scripts/release_screenshots_cli.py',
                            'src/scripts/repository_maintenance.py')):
            continue
        if path == 'src/scripts/cli.py':
            module = ast.parse(blob(repo, ref, path))
            module.body = [node for node in module.body if not (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and
                node.name in ('auto_update_and_reexec', '_repo_is_clean_git_checkout'))]
            content = ast.dump(module, include_attributes=False).encode()
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
    return hashlib.sha256(b'\0'.join(entries)).hexdigest()


def verify_visual_source(repo: Path, source: str, target: str, source_tree: str) -> None:
    require(runtime_tree(repo, source) == source_tree, 'Inconsistent capture source tree')
    require(subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', source, target],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0,
            'Capture source is not an ancestor of this release')
    require(visual_tree(repo, source) == visual_tree(repo, target),
            'Visual release source changed after capture; recapture required')


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
    return re.sub(r'-[0-9a-f]{12}(?=\.png$)', '', name)


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
    require(manifest.get('schema') == 1, 'Unsupported screenshot manifest')
    source = commit_id(repo, manifest['source_commit'])
    target = commit_id(repo, ref)
    require(subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', source, target],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0,
            'Capture source is not an ancestor of this release')
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
        if case in ('finder', 'showcase', 'about'):
            verify_desktop_window(case, record['windows'])
        if case in ('finder', 'showcase'):
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
        for path in out.glob('*.png'):
            if original_image_name(path.name) in replaced and path.name not in staged:
                path.unlink()
        for name in ('capture.json', 'launcher-presets.json', 'appearance-review.json'):
            (out / name).unlink(missing_ok=True)


def _stage(repo: Path, edition: str, bundle: Path, manifest: dict) -> None:
    from PIL import Image
    import shutil
    out = repo / 'src/screenshots'
    records = {}
    replacements = {}
    for name, record in manifest['frames'].items():
        if name in ('boot', 'shutdown'):
            filename = f"boot{'_shutdown' if name == 'shutdown' else ''}_{EDITIONS[edition][2]}.png"
        elif name.startswith(edition + '-'):
            mode, case = name[len(edition) + 1:].split('-', 1)
            filename = image_name(edition, mode, case)
        else:
            continue
        source = bundle / 'frames' / (name + '.png')
        crop = record.get('crop')
        if crop:
            with Image.open(source) as image:
                require(0 <= crop[0] < crop[2] <= image.width and 0 <= crop[1] < crop[3] <= image.height,
                        f'Invalid crop: {name}')
                image.crop(crop).save(out / filename)
        else:
            shutil.copyfile(source, out / filename)
        checksum = digest(out / filename)
        hashed = str(Path(filename).with_suffix('')) + '-' + checksum[:12] + '.png'
        (out / filename).rename(out / hashed)
        replacements[filename] = hashed
        records[hashed] = dict(record, source_commit=manifest['source_commit'], source_release='v' + manifest['version'],
                               sha256=checksum)
        if name.startswith(edition + '-') and case == 'about':
            full_name = f'desktop_about_{mode}_4k.png'
            full_hash = digest(source)
            full_hashed = str(Path(full_name).with_suffix('')) + '-' + full_hash[:12] + '.png'
            shutil.copyfile(source, out / full_hashed)
            replacements[full_name] = full_hashed
            records[full_hashed] = dict(record, crop=None, source_commit=manifest['source_commit'],
                                       source_release='v' + manifest['version'], sha256=full_hash)
    for name in SCREENSHOT_DOCS:
        document = repo / name
        if not document.is_file():
            continue
        content = re.sub(r'src/screenshots/([\w.-]+\.png)',
                         lambda match: 'src/screenshots/' + replacements.get(original_image_name(match[1]), match[1]),
                         document.read_text())
        required = set(re.findall(r'src/screenshots/([\w.-]+\.png)', content)) - STATIC_ART
        require(required <= records.keys(), f'Uncaptured {document.stem} images: {sorted(required - records.keys())}')
        document.write_text(content)
    (out / 'release-capture.json').write_text(json.dumps({
        'schema': 1, 'version': manifest['version'], 'source_commit': manifest['source_commit'],
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
        if name.endswith(('-finder', '-showcase', '-about')):
            verify_desktop_window(name.rsplit('-', 1)[1], frame['windows'])
    committed_docs = set(git(repo, 'ls-tree', '--name-only', ref, '--', *SCREENSHOT_DOCS).splitlines())
    required = set()
    for name in committed_docs:
        required.update(re.findall(r'src/screenshots/([\w.-]+\.png)', blob(repo, ref, name).decode()))
    required -= STATIC_ART
    require(required <= record['images'].keys(), 'Missing release screenshots')
    expected = {image_name(edition, m, c) for m in MODES for c in CASES}
    expected.update(f'boot{s}_{EDITIONS[edition][2]}.png' for s in ('', '_shutdown'))
    expected.update(f'desktop_about_{mode}_4k.png' for mode in MODES)
    require(expected <= {original_image_name(name) for name in record['images']}, 'Missing release screenshots')
    for name, image in record['images'].items():
        require(re.fullmatch(r'[\w.-]+\.png', name) is not None, 'Invalid screenshot filename')
        require(name.endswith('-' + image['sha256'][:12] + '.png'), 'Screenshot URL is missing its content hash: ' + name)
        require(hashlib.sha256(blob(repo, ref, 'src/screenshots/' + name)).hexdigest() == image['sha256'],
                'Screenshot changed after review: ' + name)
        require(image['source_commit'] == source and image['source_release'] == 'v' + capture_version,
                'Stale screenshot: ' + name)
    return record
