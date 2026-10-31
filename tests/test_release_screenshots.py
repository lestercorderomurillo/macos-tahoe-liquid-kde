"""Release gates must reject stale pictures before any publication occurs."""
import json
import subprocess

import pytest

import release_screenshots as shots
from release_screenshots_cli import publish


def commit(repo, message='fixture'):
    subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                    'commit', '-qm', message], check=True, capture_output=True)
    return shots.commit_id(repo, 'HEAD')


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def test_console_maintenance_preserves_visual_fingerprint_but_ui_changes_do_not(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    installer = tmp_path / 'installer'
    baseline = 'import sys\nfrom installer_ui import main\nmain(sys.argv[1:])\n'
    installer.write_text(baseline)
    (tmp_path / 'install').write_text(baseline)
    before = commit(tmp_path)
    branch = ('if sys.argv[1:] == ["--free-space"]:\n'
              '    from repository_maintenance import main\n'
              '    raise SystemExit(main([]))\n')
    scripts = tmp_path / 'src/scripts'
    scripts.mkdir(parents=True)
    (scripts / 'repository_maintenance.py').write_text('# console-only Git maintenance\n')
    installer.write_text(branch + baseline)
    after = commit(tmp_path)
    assert shots.visual_tree(tmp_path, before) == shots.visual_tree(tmp_path, after)
    installer.write_text(branch + baseline.replace('main(sys.argv[1:])', 'main(["--uninstall"])'))
    changed = commit(tmp_path)
    assert shots.visual_tree(tmp_path, before) != shots.visual_tree(tmp_path, changed)


@pytest.fixture
def capture(tmp_path, monkeypatch):
    Image = pytest.importorskip('PIL.Image')
    repo = tmp_path / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    (repo / 'VERSION').write_text('1.2.3\n')
    (repo / 'README.md').write_text('![Files](src/screenshots/finder_v4.png)\n'
                                  '![Emblem](src/screenshots/macos-26.png)\n')
    (repo / 'TESTING.md').write_text('![Installer](src/screenshots/installer-welcome_v4.png)\n')
    source = repo / 'src/offline/kwin-effects/acrylic-glass/src'
    source.mkdir(parents=True)
    (source / 'effect.cpp').write_text('release source\n')
    profile = repo / 'src/scripts/release_capture_profile.json'
    profile.parent.mkdir(parents=True)
    write_json(profile.parent / 'defaults.json', {'wallpaper': 'MacTahoe', 'launcher_preset': 1})
    write_json(profile, {'resolution': [32, 32], 'scale': 1, 'vm_image_sha256': 'a' * 64})
    monkeypatch.setattr(shots, 'PROFILE', profile)
    ref = commit(repo)
    bundle = tmp_path / 'bundle'
    (bundle / 'frames').mkdir(parents=True)
    manifest = dict(schema=1, version='1.2.3', source_commit=ref, source_tree=shots.runtime_tree(repo, ref),
                    profile_sha256=shots.digest(profile), vm_image_sha256='a' * 64,
                    effect_build=shots.effect_identity(repo, ref), frames={})
    for name in sorted(shots.expected_frames()):
        path = bundle / 'frames' / (name + '.png')
        Image.new('RGB', (32, 32), 'black' if '-dark-' in name else 'white').save(path)
        record = {'sha256': shots.digest(path)}
        if name in ('boot', 'shutdown'):
            record['plymouth_verified'] = True
        else:
            edition, mode, case = next((e, m, c) for e in shots.EDITIONS for m in shots.MODES for c in shots.CASES
                                       if name == f'{e}-{m}-{c}')
            record.update(effect_build=manifest['effect_build'], appearance={
                              'Plasma': 'MacTahoeLiquidKde-' + mode.capitalize(),
                              'Icons': 'MacTahoeLiquidKde-Icons-Regular-' + mode.capitalize()},
                          wallpaper=shots.EDITIONS[edition][0], launcher_preset=shots.EDITIONS[edition][1],
                          stable_frames=True, window_verified=True, windows=[{
                              'caption': 'About This Computer (preview)' if case == 'about' else 'Documents',
                              'resourceClass': 'qml6' if case == 'about' else 'org.gnome.Nautilus',
                              'type': 0, 'active': True,
                              'geometry': dict(x=0, y=0, width=32, height=32)}])
            if case.startswith('installer-'):
                record.update(installer_page=case.removeprefix('installer-'),
                              installer_edition=shots.EDITIONS[edition][0])
        manifest['frames'][name] = record
    write_json(bundle / 'manifest.json', manifest)
    write_json(bundle / 'review.json', {'manifest_sha256': shots.digest(bundle / 'manifest.json'),
                                      'approved': {n: r['sha256'] for n, r in manifest['frames'].items()}, 'rejected': {}})
    return repo, ref, bundle, manifest


def test_capture_can_be_committed_without_invalidating_source(capture):
    repo, ref, bundle, manifest = capture
    shots.validate(repo, ref, bundle)
    shots.stage(repo, 'tahoe', bundle, manifest)
    final = commit(repo, 'reviewed screenshots')
    assert ref != final
    assert shots.runtime_tree(repo, ref) == shots.runtime_tree(repo, final)
    assert shots.verify_committed(repo, final)['version'] == '1.2.3'
    assert 'installer-welcome_v4-' in (repo / 'TESTING.md').read_text()


@pytest.mark.parametrize('mode', shots.MODES)
def test_base_icons_cannot_replace_the_installed_regular_appearance(capture, mode):
    repo, ref, bundle, manifest = capture
    manifest['frames'][f'tahoe-{mode}-dock']['appearance']['Icons'] = 'MacTahoeLiquidKde-Icons'
    write_json(bundle / 'manifest.json', manifest)
    with pytest.raises(ValueError, match='Wrong icon appearance'):
        shots.validate(repo, ref, bundle, reviewed=False)
    # A matching review hash must not make the same bad provenance publishable.
    review = json.loads((bundle / 'review.json').read_text())
    review['manifest_sha256'] = shots.digest(bundle / 'manifest.json')
    write_json(bundle / 'review.json', review)
    shots.stage(repo, 'tahoe', bundle, manifest)
    final = commit(repo)
    with pytest.raises(ValueError, match='Wrong icon appearance'):
        shots.verify_committed(repo, final)


@pytest.mark.parametrize('path,content', [('src/new-code.py', 'changed code\n')])
def test_unknown_runtime_code_requires_recapture(capture, path, content):
    repo, ref, bundle, _ = capture
    (repo / path).write_text(content)
    final = commit(repo)
    with pytest.raises(ValueError, match='changed after capture'):
        shots.validate(repo, final, bundle)


def test_old_loaded_effect_is_rejected_even_when_every_frame_agrees(capture):
    repo, ref, bundle, manifest = capture
    manifest['effect_build'] = 'b' * 64
    for frame in manifest['frames'].values():
        if 'effect_build' in frame:
            frame['effect_build'] = 'b' * 64
    write_json(bundle / 'manifest.json', manifest)
    with pytest.raises(ValueError, match='Loaded effect differs'):
        shots.validate(repo, ref, bundle, reviewed=False)


@pytest.mark.parametrize('failure', ['missing', 'changed', 'incomplete-review', 'wrong-review', 'rejected', 'wrong-vm', 'wrong-preset'])
def test_incomplete_or_changed_captures_block(capture, failure):
    repo, ref, bundle, manifest = capture
    name = 'golden-gate-light-launcher'
    if failure == 'missing':
        (bundle / 'frames' / (name + '.png')).unlink()
    elif failure == 'changed':
        with (bundle / 'frames' / (name + '.png')).open('ab') as stream:
            stream.write(b'changed')
    elif failure in ('wrong-vm', 'wrong-preset'):
        if failure == 'wrong-vm': manifest['vm_image_sha256'] = 'c' * 64
        else: manifest['frames'][name]['launcher_preset'] = 1
        write_json(bundle / 'manifest.json', manifest)
    else:
        review = json.loads((bundle / 'review.json').read_text())
        if failure == 'incomplete-review': review['approved'].pop(name)
        elif failure == 'wrong-review': review['manifest_sha256'] = 'c' * 64
        else: review['rejected'][name] = manifest['frames'][name]['sha256']
        write_json(bundle / 'review.json', review)
    with pytest.raises(ValueError):
        shots.validate(repo, ref, bundle)


def test_staging_failure_preserves_existing_images(capture):
    repo, _, bundle, manifest = capture
    out = repo / 'src/screenshots'
    out.mkdir()
    (out / 'finder_v4.png').write_bytes(b'original')
    (repo / 'README.md').write_text('![Missing](src/screenshots/uncaptured.png)\n')
    with pytest.raises(ValueError, match='Uncaptured README'):
        shots.stage(repo, 'tahoe', bundle, manifest)
    assert list(out.iterdir()) == [out / 'finder_v4.png']
    assert (out / 'finder_v4.png').read_bytes() == b'original'


def test_committed_picture_change_blocks_publication(capture, monkeypatch):
    repo, ref, bundle, manifest = capture
    shots.stage(repo, 'tahoe', bundle, manifest)
    commit(repo)
    next((repo / 'src/screenshots').glob('finder_v4-*.png')).write_bytes(b'replaced after review')
    final = commit(repo)
    calls = []
    import release_screenshots_cli
    # Keep Git verification real while ensuring no gh invocation can escape.
    original = subprocess.run
    def run(command, **kwargs):
        if command[0] == 'gh':
            calls.append(command)
            raise AssertionError('Publication ran before screenshot verification')
        return original(command, **kwargs)
    monkeypatch.setattr(release_screenshots_cli.subprocess, 'run', run)
    with pytest.raises(ValueError, match='Screenshot changed after review'):
        publish(repo, final)
    assert calls == []


def test_effect_identity_includes_nested_headers_and_shaders(capture):
    repo, ref, _, _ = capture
    shader = repo / 'src/offline/kwin-effects/acrylic-glass/src/shaders/final.frag'
    shader.parent.mkdir()
    shader.write_text('changed shader')
    final = commit(repo)
    assert shots.effect_identity(repo, final) != shots.effect_identity(repo, ref)


@pytest.mark.parametrize('case', ['finder', 'showcase', 'about'])
@pytest.mark.parametrize('failure', ['inactive', 'focus-missing', 'combined'])
def test_desktop_capture_rejects_unfocused_or_combined_apps(capture, case, failure):
    repo, ref, bundle, manifest = capture
    frame = manifest['frames']['tahoe-light-' + case]
    if failure == 'combined':
        frame['windows'].append({'caption': 'Other application', 'type': 0, 'active': True})
    elif failure == 'inactive':
        frame['windows'][0]['active'] = False
    else:
        del frame['windows'][0]['active']
    write_json(bundle / 'manifest.json', manifest)
    with pytest.raises(ValueError, match='exactly one application|not focused'):
        shots.validate(repo, ref, bundle, reviewed=False)


def test_staging_adds_a_separate_full_desktop_about_image(capture):
    repo, _, bundle, manifest = capture
    with (repo / 'README.md').open('a') as stream:
        stream.write('![About desktop](src/screenshots/desktop_about_light_4k.png)\n')
    shots.stage(repo, 'tahoe', bundle, manifest)
    out = repo / 'src/screenshots'
    records = json.loads((out / 'release-capture.json').read_text())['images']
    name = next(name for name in records if name.startswith('desktop_about_light_4k-'))
    assert (out / name).read_bytes() == (bundle / 'frames/tahoe-light-about.png').read_bytes()
    assert records[name]['crop'] is None
    assert name in (repo / 'README.md').read_text()


def test_staging_changes_urls_and_removes_only_replaced_images(capture):
    repo, _, bundle, manifest = capture
    out = repo / 'src/screenshots'
    out.mkdir()
    old = 'finder_v4-' + 'a' * 12 + '.png'
    for name in (old, 'finder_v4.png', 'launcher_v4.png', 'unrelated.png'):
        (out / name).write_bytes(b'old')
    (repo / 'README.md').write_text(f'![Files](src/screenshots/{old})\n')
    shots.stage(repo, 'tahoe', bundle, manifest)
    records = json.loads((out / 'release-capture.json').read_text())['images']
    finder = next(name for name in records if name.startswith('finder_v4-'))
    assert finder in (repo / 'README.md').read_text()
    assert not (out / old).exists()
    assert not (out / 'finder_v4.png').exists()
    assert not (out / 'launcher_v4.png').exists()
    assert (out / 'unrelated.png').read_bytes() == b'old'
    assert all(name.endswith('-' + shots.digest(out / name)[:12] + '.png') for name in records)
    shots.stage(repo, 'tahoe', bundle, manifest)
    assert finder in (repo / 'README.md').read_text()


@pytest.mark.parametrize('document', shots.SCREENSHOT_DOCS)
def test_documentation_changes_beyond_image_hashes_invalidate_capture(capture, document):
    repo, ref, bundle, manifest = capture
    shots.stage(repo, 'tahoe', bundle, manifest)
    staged = commit(repo)
    assert shots.runtime_tree(repo, ref) == shots.runtime_tree(repo, staged)
    with (repo / document).open('a') as stream:
        stream.write('Changed description\n')
    changed = commit(repo)
    assert shots.runtime_tree(repo, ref) != shots.runtime_tree(repo, changed)


def test_testing_gallery_rejects_uncaptured_images_without_modifying_readme(capture):
    repo, _, bundle, manifest = capture
    before = (repo / 'README.md').read_bytes()
    (repo / 'TESTING.md').write_text('![Missing](src/screenshots/missing-installer.png)\n')
    with pytest.raises(ValueError, match='Uncaptured TESTING images'):
        shots.stage(repo, 'tahoe', bundle, manifest)
    assert (repo / 'README.md').read_bytes() == before
    assert not (repo / 'src/screenshots').exists()


def test_capture_tool_changes_require_a_committed_recipe(capture, monkeypatch):
    repo, ref, _, _ = capture
    monkeypatch.setattr(shots, 'ROOT', repo)
    monkeypatch.setattr(shots, 'RECIPE_FILES', ('release_capture_profile.json',))
    shots.verify_recipe(repo, ref)
    with (repo / 'src/scripts/release_capture_profile.json').open('a') as stream:
        stream.write('\n')
    with pytest.raises(ValueError, match='Capture recipe differs'):
        shots.verify_recipe(repo, ref)


def test_wrong_tag_never_publishes(capture):
    repo, _, bundle, manifest = capture
    subprocess.run(['git', '-C', str(repo), 'tag', 'v1.2.3'], check=True)
    shots.stage(repo, 'tahoe', bundle, manifest)
    final = commit(repo)
    with pytest.raises(ValueError, match='tag does not point'):
        publish(repo, final)


def test_golden_gate_requires_the_matching_tahoe_pin(capture, tmp_path):
    repo, _, bundle, manifest = capture
    shots.stage(repo, 'tahoe', bundle, manifest)
    final = commit(repo)
    subprocess.run(['git', '-C', str(repo), 'tag', 'v1.2.3'], check=True)
    golden = tmp_path / 'golden'
    golden.mkdir()
    subprocess.run(['git', 'init', '-q', str(golden)], check=True)
    (golden / 'VERSION').write_text('1.2.3\n')
    (golden / 'README.md').write_text('![Files](src/screenshots/finder_v1.png)\n![Emblem](src/screenshots/macos-27.png)\n')
    write_json(golden / 'defaults.json', {'wallpaper': 'MacGoldenGate', 'launcher_preset': 2})
    write_json(golden / 'upstream.json', {'commit': final})
    shots.stage(golden, 'golden-gate', bundle, manifest)
    target = commit(golden)
    assert shots.verify_committed(golden, target, tahoe=repo)['edition'] == 'golden-gate'
    write_json(golden / 'upstream.json', {'commit': manifest['source_commit']})
    target = commit(golden)
    with pytest.raises(ValueError, match='must pin the published Tahoe release tag'):
        shots.verify_committed(golden, target, tahoe=repo)


@pytest.mark.parametrize('key,value', [('installer_page', 'welcome'), ('installer_edition', 'MacGoldenGate')])
def test_installer_gallery_rejects_wrong_page_or_edition(capture, key, value):
    repo, ref, bundle, manifest = capture
    manifest['frames']['tahoe-light-installer-icons'][key] = value
    write_json(bundle / 'manifest.json', manifest)
    with pytest.raises(ValueError, match='Wrong installer'):
        shots.validate(repo, ref, bundle, reviewed=False)


@pytest.mark.parametrize('path,content', [
    ('VERSION', '1.2.4\n'), ('AGENTS.md', 'Only test changed visual behavior.\n'),
    ('TESTING.md', '![Installer](src/screenshots/installer-welcome_v4.png)\nNew console tests passed.\n'),
    ('tests/new_test.py', '# nonvisual regression coverage\n'),
    ('.github/workflows/test.yml', '# CI runtime setup does not render the desktop\n'),
])
def test_nonvisual_release_reuses_original_reviewed_evidence(capture, path, content):
    repo, ref, bundle, manifest = capture
    shots.stage(repo, 'tahoe', bundle, manifest)
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if path == "TESTING.md":
        target.write_text(target.read_text() + "New console tests passed.\n")
    else:
        target.write_text(content)
    final = commit(repo)
    shots.validate(repo, final, bundle)
    record = shots.verify_committed(repo, final)
    assert record['version'] == '1.2.3'
    assert record['source_commit'] == ref
    assert all(image['source_release'] == 'v1.2.3' for image in record['images'].values())


def test_updater_exclusion_does_not_hide_other_cli_changes(capture):
    repo, _, bundle, manifest = capture
    cli = repo / 'src/scripts/cli.py'
    cli.write_text('def auto_update_and_reexec():\n    return 1\n\ndef install():\n    return "same UI"\n')
    source = commit(repo)
    manifest['source_commit'] = source
    manifest['source_tree'] = shots.runtime_tree(repo, source)
    write_json(bundle / 'manifest.json', manifest)
    cli.write_text(cli.read_text().replace('return 1', 'return 2'))
    updated = commit(repo)
    shots.validate(repo, updated, bundle, reviewed=False)
    cli.write_text(cli.read_text().replace('same UI', 'changed UI'))
    changed = commit(repo)
    with pytest.raises(ValueError, match='changed after capture'):
        shots.validate(repo, changed, bundle, reviewed=False)


def test_ui_translation_changes_still_require_recapture(capture):
    repo, _, bundle, manifest = capture
    catalog = repo / 'src/scripts/locales/de.json'
    catalog.parent.mkdir(parents=True)
    write_json(catalog, {'Welcome': 'Willkommen', 'Update available: {current} → {latest}': 'Alt'})
    source = commit(repo)
    manifest['source_commit'] = source
    manifest['source_tree'] = shots.runtime_tree(repo, source)
    write_json(bundle / 'manifest.json', manifest)
    write_json(catalog, {'Welcome': 'Willkommen', 'Update available: {current} → {latest}': 'Neu'})
    updated = commit(repo)
    shots.validate(repo, updated, bundle, reviewed=False)
    write_json(catalog, {'Welcome': 'Changed visible text'})
    changed = commit(repo)
    with pytest.raises(ValueError, match='changed after capture'):
        shots.validate(repo, changed, bundle, reviewed=False)


def test_nonvisual_release_publishes_current_version_without_relabeling_images(capture, monkeypatch):
    repo, _, bundle, manifest = capture
    shots.stage(repo, 'tahoe', bundle, manifest)
    (repo / 'VERSION').write_text('1.2.4\n')
    final = commit(repo)
    subprocess.run(['git', '-C', str(repo), 'tag', 'v1.2.4'], check=True)
    original = subprocess.run
    calls = []
    def run(command, **kwargs):
        if command[0] == 'gh':
            calls.append(command)
            return subprocess.CompletedProcess(command, 0)
        return original(command, **kwargs)
    monkeypatch.setattr(subprocess, 'run', run)
    publish(repo, final)
    assert calls == [['gh', 'release', 'create', 'v1.2.4', '--verify-tag',
                      '--title', 'v1.2.4', '--generate-notes']]
    assert shots.verify_committed(repo, final)['version'] == '1.2.3'
