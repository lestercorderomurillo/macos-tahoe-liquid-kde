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
    def __init__(self, root, profile, image, source, edition):
        self.root, self.profile, self.source, self.edition = root, profile, source, edition
        self.name = 'mttkde-capture-' + uuid.uuid4().hex[:12]
        self.stream = None
        self.process = None
        self.log = None
        self.image = image
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


def capture(repo: Path, ref: str, image: Path, output: Path) -> dict:
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
    with capture_lock():
        for edition in EDITIONS:
            with tempfile.TemporaryDirectory(prefix='mttkde-cap-') as temp:
                guest_dir = Path(temp)
                try:
                    with Guest(guest_dir, profile, image, archive, edition) as vm:
                        print(f'Installing {edition} from {source}', flush=True)
                        manifest['environments'][edition] = vm.action('setup', edition)
                        for mode in MODES:
                            vm.action('clean-desktop')
                            vm.key('esc')
                            vm.action('mode', mode)
                            def shot(case):
                                vm.move(*profile['pointer'])
                                record = vm.action('capture', edition, mode, case)
                                name = f'{edition}-{mode}-{case}'
                                vm.get('/home/tester/release-capture/frame.png', output / 'frames' / (name + '.png'))
                                manifest['frames'][name] = record
                                manifest.setdefault('effect_build', record['effect_build'])
                                print('Captured ' + name, flush=True)
                            vm.action('plasma', 'panels().forEach(p=>p.widgets().forEach(w=>{if(w.type==="org.kde.mac-tahoe-liquid-kde.launcher")'
                                      '{w.currentConfigGroup=["General"];w.writeConfig("launcherPreset",' + str(EDITIONS[edition][1]) + ');}}));')
                            vm.action('launcher')
                            shot('launcher')
                            vm.key('esc')
                            vm.action('plasma', 'panels().forEach(p=>{if(p.location==="bottom")p.hiding="none";});')
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
                            vm.action('close')
                            vm.action('launch', 'about')
                            vm.action('arrange', json.dumps({'About This Computer (preview)':
                                      dict(profile['windows']['About This Computer (preview)'], x=780)}))
                            shot('about')
                            vm.action('close')
                            for page in INSTALLER_PAGES:
                                vm.action('wizard', page)
                                shot('installer-' + page)
                            vm.action('clean-desktop')
                        if edition == 'tahoe':
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
    return validate(repo, source, output, reviewed=False)
