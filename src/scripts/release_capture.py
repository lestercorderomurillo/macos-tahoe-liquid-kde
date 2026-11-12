"""Capture a complete release in fresh overlays of the pinned reference VM."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import tempfile
import time
import uuid

from release_screenshots import (ROOT, PROFILE, EDITIONS, MODES, INSTALLER_PAGES, commit_id, digest,
                                 git, runtime_tree, require, validate)


class Guest:
    def __init__(self, root, profile, image, source, edition, *, resume=False):
        self.root, self.profile, self.source, self.edition = root, profile, source, edition
        self.name = 'mttkde-capture-' + uuid.uuid4().hex[:12]
        self.stream = None
        self.process = None
        self.log = None
        self.image = image
        self.resume = resume
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            self.port = probe.getsockname()[1]
        self.ssh = ['sshpass', '-p', 'tester', 'ssh', '-p', str(self.port),
                    '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=5',
                    '-o', 'UserKnownHostsFile=' + str(root / 'known_hosts'), 'tester@127.0.0.1']
        self.scp = ['sshpass', '-p', 'tester', 'scp', '-q', '-P', str(self.port),
                    '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=5',
                    '-o', 'UserKnownHostsFile=' + str(root / 'known_hosts')]

    def __enter__(self):
        try:
            disk = self.root / 'disk.qcow2'
            if self.resume:
                info = json.loads(subprocess.check_output(['qemu-img', 'info', '--output=json', str(disk)], text=True))
                require(Path(info.get('full-backing-filename', '')).resolve() == self.image.resolve(), 'Wrong resume image')
            else:
                subprocess.run(['qemu-img', 'create', '-q', '-f', 'qcow2', '-F', 'qcow2', '-b', str(self.image), str(disk)], check=True)
            self.log = (self.root / 'qemu.log').open('w')
            self.process = subprocess.Popen([
                'qemu-system-x86_64', '-name', self.name, '-enable-kvm', '-cpu', 'host',
                '-smp', str(self.profile['cpus']), '-m', str(self.profile['memory_mib']),
                '-smbios', 'type=1,product=MTTKDE release capture',
                '-drive', f'file={disk},if=virtio,format=qcow2',
                '-device', 'virtio-vga-gl,xres=3840,yres=2160', '-display', 'egl-headless',
                '-device', 'usb-ehci', '-device', 'usb-tablet',
                '-netdev', f'user,id=net0,hostfwd=tcp:127.0.0.1:{self.port}-:22',
                '-device', 'virtio-net-pci,netdev=net0', '-rtc', 'base=2026-01-01T10:00:00,clock=vm',
                '-serial', f'file:{self.root / "console.log"}', '-qmp', f'unix:{self.root / "qmp.sock"},server=on,wait=off',
            ], stdout=self.log, stderr=self.log)
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError((self.root / 'qemu.log').read_text())
                try:
                    if self.remote('pgrep', '-u', 'tester', '-x', 'plasmashell', timeout=10):
                        break
                except subprocess.SubprocessError:
                    pass
                time.sleep(2)
            else:
                raise RuntimeError('Capture VM did not reach Plasma')
            self.socket = socket.socket(socket.AF_UNIX)
            self.socket.settimeout(15)
            self.socket.connect(str(self.root / 'qmp.sock'))
            self.stream = self.socket.makefile('rwb', buffering=0)
            self.stream.readline()
            self.qmp('qmp_capabilities')
            require(self.qmp('query-name')['name'] == self.name, 'Wrong capture VM')
            self.remote('mkdir', '-p', '/home/tester/release-capture/source')
            for source in (self.source, PROFILE, ROOT / 'src/scripts/release_capture_guest.py',
                           ROOT / 'src/scripts/release_screenshots.py', ROOT / 'src/scripts/screenshot_checks.py'):
                self.put(source, '/home/tester/release-capture/' + source.name)
            self.remote('tar', '-xf', '/home/tester/release-capture/source.tar', '-C', '/home/tester/release-capture/source')
            self.key('esc')
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *unused):
        if self.stream and self.process and self.process.poll() is None:
            for name in ('install.log', 'plymouth.log', 'finder.log', 'about.log', 'frame.png'):
                try:
                    self.get('/home/tester/release-capture/' + name, self.root / name)
                except subprocess.SubprocessError:
                    pass
        if self.stream:
            try:
                self.qmp('quit')
            except (OSError, ValueError, RuntimeError):
                pass
            self.stream.close()
            self.socket.close()
        if self.process:
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
        if self.log:
            self.log.close()

    def remote(self, *args, timeout=1900):
        return subprocess.check_output(self.ssh + [shlex.join(args)], text=True, stderr=subprocess.STDOUT, timeout=timeout).strip()

    def put(self, source, dest):
        subprocess.run(self.scp + [str(source), 'tester@127.0.0.1:' + dest], check=True, timeout=120)

    def get(self, source, dest):
        subprocess.run(self.scp + ['tester@127.0.0.1:' + source, str(dest)], check=True, timeout=120)

    def action(self, action, *args):
        try:
            output = self.remote('python3', '/home/tester/release-capture/release_capture_guest.py',
                                 '--repo', '/home/tester/release-capture/source', '--profile',
                                 '/home/tester/release-capture/release_capture_profile.json', action, *args)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f'Guest {action} failed:\n{exc.output}') from exc
        results = [line.removeprefix('MTTKDE_RESULT=') for line in output.splitlines() if line.startswith('MTTKDE_RESULT=')]
        require(len(results) == 1, 'Guest did not return capture evidence: ' + output[-2000:])
        return json.loads(results[0])

    def qmp(self, command, arguments=None):
        self.stream.write((json.dumps({'execute': command, 'arguments': arguments or {}}) + '\n').encode())
        while True:
            line = self.stream.readline()
            if not line:
                raise RuntimeError('Capture VM closed QMP')
            response = json.loads(line)
            if 'return' in response:
                return response['return']
            if 'error' in response:
                raise RuntimeError(str(response['error']))

    def key(self, code):
        for down in (True, False):
            self.qmp('input-send-event', {'events': [{'type': 'key', 'data': {'down': down, 'key': {'type': 'qcode', 'data': code}}}]})

    def move(self, x, y):
        self.qmp('input-send-event', {'events': [{'type': 'abs', 'data': {'axis': axis, 'value': round(value / size * 32767)}}
                 for axis, value, size in [('x', x, 3840), ('y', y, 2160)]]})

    def click(self, x, y, button='left'):
        self.move(x, y)
        time.sleep(.15)
        for down in (True, False):
            self.qmp('input-send-event', {'events': [{'type': 'btn', 'data': {'button': button, 'down': down}}]})
            time.sleep(.1)


@contextmanager
def capture_lock():
    directory = Path(tempfile.gettempdir()) / f'mttkde-release-{os.getuid()}'
    directory.mkdir(mode=0o700, exist_ok=True)
    with (directory / 'capture.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def capture(repo: Path, ref: str, image: Path, output: Path, reuse: Path | None = None, *, system_menu_only=False) -> dict:
    require(not (system_menu_only and reuse), 'Focused system-menu capture does not reuse a full gallery')
    profile = json.loads(PROFILE.read_text())
    image = image.resolve()
    require(digest(image) == profile['vm_image_sha256'], 'VM image checksum differs from the pinned recipe')
    info = json.loads(subprocess.check_output(['qemu-img', 'info', '--output=json', str(image)], text=True))
    require(not info.get('backing-filename') and not info.get('dirty-flag'), 'Use a sealed, standalone VM image')
    for tool in ('qemu-system-x86_64', 'qemu-img', 'sshpass', 'ssh', 'scp'):
        require(shutil.which(tool) is not None, f'Missing capture dependency: {tool}')
    source = commit_id(repo, ref)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / 'frames').mkdir()
    archive = output / 'source.tar'
    subprocess.run(['git', '-C', str(repo), 'archive', '--format=tar', '--output=' + str(archive), source], check=True)
    manifest = dict(schema=1, version=git(repo, 'show', source + ':VERSION'), source_commit=source,
                    source_tree=runtime_tree(repo, source), profile_sha256=digest(PROFILE),
                    vm_image_sha256=profile['vm_image_sha256'], frames={}, environments={},
                    host={'qemu': subprocess.check_output(['qemu-system-x86_64', '--version'], text=True).strip(),
                          'kernel': os.uname().release, 'machine': os.uname().machine})
    from release_screenshots import affected_frames, frame_origin, expected_frames, CASES
    pending = expected_frames()
    if system_menu_only:
        manifest['scope'] = 'system-menu'
        pending = {f'{edition}-{mode}-menu' for edition in EDITIONS for mode in MODES}
    approvals = {}
    if reuse is not None:
        old = json.loads((reuse / 'manifest.json').read_text())
        validate(repo, old['source_commit'], reuse)
        old_review = json.loads((reuse / 'review.json').read_text())
        manifest['schema'] = 2
        invalidated = {}
        for name, frame in old['frames'].items():
            origin, tree, version = frame_origin(old, frame)
            if origin not in invalidated:
                invalidated[origin] = affected_frames(repo, origin, source)
            if name in invalidated[origin]:
                continue
            shutil.copyfile(reuse / 'frames' / (name + '.png'), output / 'frames' / (name + '.png'))
            manifest['frames'][name] = dict(frame, source_commit=origin, source_tree=tree, source_version=version)
            approvals[name] = old_review['approved'][name]
            pending.remove(name)
        from release_screenshots import effect_identity
        manifest['effect_build'] = effect_identity(repo, source)
        print(f'Reusing {len(approvals)} reviewed frames; capturing {len(pending)} affected frames', flush=True)
    with capture_lock():
        for edition in EDITIONS:
            if not any(n.startswith(edition + '-') or (edition == 'tahoe' and n in ('boot', 'shutdown'))
                       for n in pending):
                continue
            with tempfile.TemporaryDirectory(prefix='mttkde-cap-') as temp:
                guest_dir = Path(temp)
                try:
                    with Guest(guest_dir, profile, image, archive, edition) as vm:
                        print(f'Installing {edition} from {source}', flush=True)
                        dock_only = pending <= {f'{e}-{m}-dock' for e in EDITIONS for m in MODES}
                        menu_only = pending <= {f'{e}-{m}-{c}' for e in EDITIONS for m in MODES for c in ('menu', 'context')}
                        installer_only = all('-installer-' in name for name in pending)
                        scope = ['dock'] if dock_only else ['menu'] if menu_only else ['installer'] if installer_only else []
                        manifest['environments'][edition] = vm.action('setup', edition, *scope)
                        for mode in MODES:
                            vm.action('clean-desktop')
                            vm.key('esc')
                            vm.action('mode', mode, *scope)
                            def shot(case):
                                name = f'{edition}-{mode}-{case}'
                                if name not in pending:
                                    return
                                if case not in ('menu', 'context'):
                                    vm.move(*profile['pointer'])
                                if case == 'dock':
                                    state = vm.action('plasma', 'var states=[]; panels().forEach(p=>p.widgets().forEach(w=>{'
                                        'if(w.type.includes("icontasks")){w.currentConfigGroup=["General"];'
                                        'states.push(w.readConfig("macOSDockIcons"));}}));'
                                        'print(JSON.stringify(states));')
                                    require(json.loads(state) in ([True], ['true']), 'Installer did not apply default Dock artwork')
                                record = vm.action('capture', edition, mode, case)
                                if case == 'dock':
                                    record['dock_appearance'] = 'macos'
                                name = f'{edition}-{mode}-{case}'
                                vm.get('/home/tester/release-capture/frame.png', output / 'frames' / (name + '.png'))
                                manifest['frames'][name] = record
                                manifest.setdefault('effect_build', record['effect_build'])
                                print('Captured ' + name, flush=True)
                            mode_pending = {case for case in CASES
                                            if f'{edition}-{mode}-{case}' in pending}
                            if mode_pending and mode_pending <= {'menu', 'context'}:
                                vm.action('launch', 'finder')
                                vm.action('arrange', json.dumps({'Documents': profile['windows']['Documents']}))
                                vm.move(140, 30)
                                time.sleep(1)
                                if not system_menu_only:
                                    preview = vm.action('capture', edition, mode, 'topbar')
                                    preview_name = f'{edition}-{mode}-topbar'
                                    (output / 'previews').mkdir(exist_ok=True)
                                    vm.get('/home/tester/release-capture/frame.png', output / 'previews' / (preview_name + '.png'))
                                    manifest.setdefault('component_previews', {})[preview_name] = preview
                                vm.click(40, 30)
                                vm.move(*profile['pointer'])
                                vm.key('down')
                                shot('menu')
                                vm.key('esc')
                                vm.action('close')
                                vm.click(2100, 1000, 'right')
                                vm.move(*profile['pointer'])
                                vm.key('down')
                                shot('context')
                                vm.key('esc')
                            elif mode_pending - {case for case in mode_pending if case.startswith('installer-')} == {'dock'}:
                                vm.action('plasma', 'panels().forEach(p=>{if(p.location==="bottom")p.hiding="none";});')
                                vm.move(1920, 2159)
                                time.sleep(1)
                                shot('dock')
                                vm.action('clean-desktop')
                            elif any(f'{edition}-{mode}-{case}' in pending for case in CASES
                                   if not case.startswith('installer-')):
                                vm.action('plasma', 'panels().forEach(p=>p.widgets().forEach(w=>{if(w.type==="org.kde.mac-tahoe-liquid-kde.launcher")'
                                          '{w.currentConfigGroup=["General"];w.writeConfig("launcherPreset",' + str(EDITIONS[edition][1]) + ');}}));')
                                vm.action('launcher')
                                shot('launcher')
                                vm.key('esc')
                                vm.action('plasma', 'panels().forEach(p=>{if(p.location==="bottom")p.hiding="none";});')
                                # Reveal the panel before moving the pointer back to
                                # the neutral capture position.
                                vm.move(1920, 2159)
                                time.sleep(1)
                                shot('dock')
                                for case, x, y, button in [('menu', 40, 30, 'left'), ('context', 2100, 1000, 'right')]:
                                    vm.key('esc')
                                    vm.click(1900, 1000)
                                    vm.click(x, y, button)
                                    shot(case)
                                vm.key('esc')
                                vm.action('launch', 'finder')
                                vm.action('arrange', json.dumps({'Documents': profile['windows']['Documents']}))
                                shot('finder')
                                vm.action('arrange', json.dumps({'Documents':
                                          dict(profile['windows']['Documents'], x=460)}))
                                shot('showcase')
                                from release_screenshots import MATERIAL_CASES
                                for material_case in MATERIAL_CASES:
                                    vm.action('material', material_case)
                                    shot(material_case)
                                vm.action('material', 'restore')
                                vm.action('close')
                                vm.action('launch', 'about')
                                vm.action('arrange', json.dumps({'About This Computer (preview)':
                                          dict(profile['windows']['About This Computer (preview)'], x=780)}))
                                shot('about')
                                vm.action('close')
                            for page in INSTALLER_PAGES:
                                if f'{edition}-{mode}-installer-{page}' not in pending:
                                    continue
                                vm.action('wizard', page)
                                shot('installer-' + page)
                            vm.action('clean-desktop')
                        if edition == 'tahoe' and pending & {'boot', 'shutdown'}:
                            vm.action('boot')
                            for case in ('boot', 'shutdown'):
                                path = output / 'frames' / (case + '.png')
                                vm.get(f'/home/tester/release-capture/source/tests/vm/output/plymouth-{case}-splash.png', path)
                                manifest['frames'][case] = dict(sha256=digest(path), plymouth_verified=True)
                        vm.get('/home/tester/release-capture/install.log', output / (edition + '-install.log'))
                finally:
                    for name in ('qemu.log', 'console.log', 'install.log', 'plymouth.log', 'finder.log', 'about.log', 'frame.png'):
                        if (guest_dir / name).exists():
                            shutil.copyfile(guest_dir / name, output / (edition + '-' + name))
                    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'review.json').write_text(json.dumps({
        'manifest_sha256': digest(output / 'manifest.json'), 'approved': approvals, 'rejected': {},
    }, indent=2) + '\n')
    return validate(repo, source, output, reviewed=False)


def capture_file_previews(repo: Path, ref: str, image: Path, output: Path, *, resume=False):
    """Four focused file-manager photographs, without refreshing the gallery."""
    profile = json.loads(PROFILE.read_text())
    image = image.resolve()
    require(digest(image) == profile['vm_image_sha256'], 'VM image checksum differs from the pinned recipe')
    info = json.loads(subprocess.check_output(['qemu-img', 'info', '--output=json', str(image)], text=True))
    require(not info.get('backing-filename') and not info.get('dirty-flag'), 'Use a sealed standalone VM')
    source = commit_id(repo, ref)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=resume)
    archive = output / 'source.tar'
    fresh = output / 'source-next.tar'
    subprocess.run(['git', '-C', str(repo), 'archive', '--format=tar', '--output=' + str(fresh), source], check=True)
    if resume:
        require(archive.is_file() and digest(archive) == digest(fresh), 'Resume source differs from original capture')
    fresh.replace(archive)
    manifest = dict(source_commit=source, vm_image_sha256=profile['vm_image_sha256'], frames={})
    with capture_lock(), Guest(output, profile, image, archive, 'tahoe', resume=resume) as vm:
        manifest['environment'] = vm.action('setup', 'tahoe')
        manifest['capture_tools'] = {name: digest(ROOT / 'src/scripts' / name) for name in ('release_capture.py', 'release_capture_guest.py')}
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        for mode in MODES:
            vm.action('mode', mode)
            vm.move(*profile['pointer'])
            for manager in ('nautilus', 'dolphin'):
                name = f'{manager}-{mode}'
                record = vm.action('file-preview', manager)
                vm.get('/home/tester/release-capture/frame.png', output / (name + '.png'))
                manifest['frames'][name] = record
                (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def stage_file_previews(repo: Path, bundle: Path):
    """Stage the four individually reviewed photographs with focus evidence."""
    from io import BytesIO
    from PIL import Image
    from release_screenshots import verify_focused_frame
    manifest = json.loads((bundle / 'manifest.json').read_text())
    profile = json.loads(PROFILE.read_text())
    require(manifest['vm_image_sha256'] == profile['vm_image_sha256'], 'Unpinned preview VM')
    expected = {f'{manager}-{mode}' for manager in ('nautilus', 'dolphin') for mode in MODES}
    require(set(manifest['frames']) == expected, 'Incomplete file-manager previews')
    destination = repo / 'src/installer/assets'
    sources = json.loads((destination / 'sources.json').read_text())
    updates = {}
    for name in sorted(expected):
        record = manifest['frames'][name]
        source = bundle / (name + '.png')
        require(digest(source) == record['sha256'], 'Changed preview: ' + name)
        manager = name.split('-')[0]
        resource = {'nautilus': 'org.gnome.Nautilus', 'dolphin': 'org.kde.dolphin'}[manager]
        verify_focused_frame(record['before'], record['after'], resource)
        require(record['stable_frames'] is True, 'Unsettled preview: ' + name)
        with Image.open(source) as image:
            require(list(image.size) == profile['resolution'], 'Unexpected preview resolution')
            crop = record['crop']
            require(0 <= crop[0] < crop[2] <= image.width and 0 <= crop[1] < crop[3] <= image.height,
                    'Invalid preview crop')
            buffer = BytesIO()
            image.crop(crop).convert('RGB').save(buffer, format='JPEG', quality=95, subsampling=0)
        import hashlib
        payload = buffer.getvalue()
        checksum = hashlib.sha256(payload).hexdigest()
        filename = f'{name}-{checksum[:12]}.jpg'
        updates[name + '.jpg'] = (payload, dict(
            source=str(source.relative_to(repo)), source_sha256=record['sha256'],
            source_commit=manifest['source_commit'], vm_image_sha256=manifest['vm_image_sha256'],
            crop=crop, sha256=checksum, file=filename, kind='focused-vm-file-preview',
            before=record['before'], after=record['after'], stable_frames=True, reviewed=True))
    for key, (payload, record) in updates.items():
        old = sources[key]['file']
        (destination / record['file']).write_bytes(payload)
        if old != record['file']:
            require(Path(old).name == old, 'Invalid old preview filename')
            (destination / old).unlink(missing_ok=True)
        sources[key] = record
    (destination / 'sources.json').write_text(json.dumps(sources, indent=2) + '\n')
    (bundle / 'review.json').write_text(json.dumps(dict(
        manifest_sha256=digest(bundle / 'manifest.json'),
        approved={name: manifest['frames'][name]['sha256'] for name in sorted(expected)}), indent=2) + '\n')
