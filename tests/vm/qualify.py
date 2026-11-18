#!/usr/bin/env python3
"""Run either prepared captures or a full VM lifecycle qualification.

For lifecycle qualification, start the guest with ./vm first. SSH must accept tester/tester on its loopback
port, with passwordless sudo and the repository mounted read-only at ~/repo.
Artifacts are retained even when a phase fails. A failed phase never qualifies
that distribution. This harness never installs the theme on the host.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET

PORTS = dict(arch=2221, cachyos=2222, manjaro=2223, endeavouros=2224,
             garuda=2225, fedora=2226, nobara=2227, opensuse=2228,
             neon=2231, debian=2232, artix=2233, kubuntu=2234)
WORKTREE = '/home/tester/macos-tahoe-liquid-kde'
REPO = Path(__file__).resolve().parents[2]
VM = REPO / 'vm'


def verify_capture(data: bytes):
    from PIL import Image, ImageStat

    with Image.open(io.BytesIO(data)) as capture:
        if capture.format != 'PNG' or min(capture.size) < 480:
            raise RuntimeError('Guest capture is not a desktop PNG')
        if 'A' in capture.getbands() and capture.getchannel('A').getextrema()[1] == 0:
            raise RuntimeError('Guest capture is fully transparent')
        if max(ImageStat.Stat(capture.convert('RGB')).stddev) < 2:
            raise RuntimeError('Guest capture is blank')


class Guest:
    def __init__(self, distro: str, output: Path, *, port=None, identity=None, deadline=None):
        self.distro = distro
        self.identity = identity
        self.deadline = deadline
        self.output = output
        self.output.mkdir(parents=True, exist_ok=True)
        self.ssh = ['sshpass', '-e', 'ssh', '-o', 'StrictHostKeyChecking=no',
                    '-o', 'UserKnownHostsFile=/dev/null', '-o', 'ConnectTimeout=5',
                    '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3',
                    '-p', str(port or PORTS[distro]), 'tester@127.0.0.1']
        self.env = {**os.environ, 'SSHPASS': os.environ.get('VM_PASSWORD', 'tester')}
        self.report = {'distro': distro, 'started': now(), 'status': 'running', 'phases': []}

    def remaining(self, timeout):
        if self.deadline is None:
            return timeout
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError('Capture batch time budget exhausted')
        return min(timeout, remaining)

    def run(self, command: str, *, timeout: int = 120, check: bool = True):
        # SSH/PAM may export a different bus from the logged-in Plasma session
        # (notably OpenRC). Let the desktop recovery code discover that session.
        command = 'unset DBUS_SESSION_BUS_ADDRESS DISPLAY WAYLAND_DISPLAY XDG_SESSION_TYPE; ' + command
        result = subprocess.run([*self.ssh, 'bash -c ' + shlex.quote(command)], env=self.env,
                                capture_output=True, timeout=self.remaining(timeout))
        if check and result.returncode:
            raise RuntimeError(f'Guest command exited {result.returncode}: {command}\n'
                               + result.stderr.decode(errors='replace')[-2000:])
        return result

    def assert_identity(self):
        wanted = {'opensuse': 'opensuse-tumbleweed', 'kubuntu': 'ubuntu'}.get(self.distro, self.distro)
        flavor_check = ''
        if self.distro == 'kubuntu':
            flavor_check = ('test "$VERSION_ID" = 26.04 && '
                            'test "$(dpkg-query -W -f=\'${Status}\' kubuntu-desktop)" '
                            '= "install ok installed" && ')
        # This guard runs before copying files or invoking install/uninstall.
        result = self.run("test \"$(cat /sys/class/dmi/id/sys_vendor)\" = QEMU && "
                          "test \"$(id -un)\" = tester && "
                          ". /etc/os-release && " + flavor_check + "printf '%s' \"$ID\"")
        if result.stdout.decode().strip() != wanted:
            raise RuntimeError('Guest identity does not match the selected distribution')
        if self.identity is not None:
            result = self.run('sudo -n cat /sys/class/dmi/id/product_uuid', timeout=10)
            if result.stdout.decode().strip().lower() != self.identity:
                raise RuntimeError('SSH does not reach the guest created for this capture')

    def save(self):
        (self.output / 'result.json').write_text(json.dumps(self.report, indent=2) + '\n')

    def launcher(self, name: str):
        # Widget IDs in appletsrc do not prove that the QML can be instantiated.
        self.phase(name, f'cd {WORKTREE} && python3 -m pytest -q '
                   'tests/test_launcher_presets.py -k test_native_launcher_popup_presets '
                   '--junitxml=/tmp/mttkde-launcher.xml', timeout=600)
        data = self.run('cat /tmp/mttkde-launcher.xml').stdout
        (self.output / f'{name}.xml').write_bytes(data)
        cases = ET.fromstring(data).findall('.//testcase')
        if len(cases) != 8 or any(case.find(tag) is not None
                                 for case in cases for tag in ('skipped', 'failure', 'error')):
            raise RuntimeError('All eight native launcher cases must pass without skips')

    def phase(self, name: str, command: str, timeout: int = 120):
        print(f'{self.distro}: {name}', flush=True)
        started = now()
        guest_log = f'/tmp/mttkde-qa-{name}.log'
        wrapped = f'set -o pipefail; ( {command} ) 2>&1 | tee {guest_log}'
        begin = time.monotonic()
        try:
            result = self.run(wrapped, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as error:
            if self.deadline is not None:
                (self.output / f'{name}.log').write_bytes((error.stdout or b'') + (error.stderr or b''))
                self.report['phases'].append(dict(name=name, started=started, finished=now(),
                                                  seconds=round(time.monotonic() - begin, 2),
                                                  exit_code=None, timed_out=True))
                self.save()
            raise
        (self.output / f'{name}.log').write_bytes(result.stdout + result.stderr)
        self.report['phases'].append(dict(name=name, started=started, finished=now(),
                                         seconds=round(time.monotonic() - begin, 2),
                                         exit_code=result.returncode))
        self.save()
        if result.returncode:
            raise RuntimeError(f'{name} failed; see {self.output / (name + ".log")}')

    def probe(self, name: str, mode: str):
        command = (f'cd {WORKTREE} && python3 tests/vm/desktop_probe.py '
                   f'--distro {self.distro} --mode {mode} --output /tmp/mttkde-probe.json')
        self.phase(name, command)
        report = json.loads(self.run('cat /tmp/mttkde-probe.json').stdout)
        (self.output / f'{name}.json').write_text(json.dumps(report, indent=2) + '\n')
        return report

    def desktop_command(self, command: str) -> str:
        # Recover the actual session, including non-default Wayland socket names.
        source = ('import sys,subprocess; sys.path.insert(0,"src/scripts"); '
                  'from utils import restore_desktop_session_env; '
                  'restore_desktop_session_env(); '
                  f'raise SystemExit(subprocess.call({command!r}, shell=True))')
        return f'cd {WORKTREE} && python3 -c {shlex.quote(source)}'

    def screenshot(self, name: str, *, mode: str | None = None, apps: dict | None = None):
        self.phase(name + '-capture', self.desktop_command(
            'sudo loginctl unlock-sessions && kscreen-doctor --dpms on && sleep 2 && '
            'rm -f /tmp/mttkde-desktop.png && '
            'spectacle --background --nonotify --fullscreen --output /tmp/mttkde-desktop.png'))
        result = self.run('cat /tmp/mttkde-desktop.png')
        if not result.stdout.startswith(b'\x89PNG\r\n\x1a\n'):
            raise RuntimeError('Guest capture did not produce a PNG')
        (self.output / f'{name}.png').write_bytes(result.stdout)
        verify_capture(result.stdout)
        if mode is not None and apps is not None:
            from PIL import Image
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/scripts'))
            from screenshot_checks import check_files_pixels
            files = [w for w in apps['windows'] if w['resourceClass'] == 'org.gnome.Nautilus']
            if len(files) != 1:
                raise RuntimeError(f'Expected one Files window, found {len(files)}')
            with Image.open(io.BytesIO(result.stdout)) as capture:
                pixels = check_files_pixels(capture, mode, apps['windows'], 2, caption=files[0]['caption'])
            (self.output / f'{name}-pixels.json').write_text(json.dumps(pixels, indent=2) + '\n')

    def apps(self, name: str, mode: str):
        self.run('sudo loginctl unlock-sessions')
        self.phase(name, self.desktop_command(
            f'python3 tests/vm/desktop_apps.py --mode {mode} --output /tmp/mttkde-apps.json'), timeout=180)
        report = json.loads(self.run('cat /tmp/mttkde-apps.json').stdout)
        (self.output / f'{name}.json').write_text(json.dumps(report, indent=2) + '\n')
        return report

    def wait_desktop(self, previous_boot: str):
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            result = self.run('cat /proc/sys/kernel/random/boot_id; '
                              'pgrep -u "$(id -u)" -x plasmashell', timeout=15, check=False)
            if result.returncode == 0 and result.stdout.decode().splitlines()[0] != previous_boot:
                self.assert_identity()
                time.sleep(12)
                return
            time.sleep(5)
        raise RuntimeError('Guest did not reboot into Plasma within five minutes')

    def installed_captures(self, *, capture_only):
        self.assert_identity()
        if capture_only:
            self.phase('mount-source', 'mkdir -p /home/tester/repo && '
                       '(mountpoint -q /home/tester/repo || '
                       'sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro repo /home/tester/repo) && '
                       'findmnt --mountpoint /home/tester/repo --types 9p --options ro >/dev/null')
        self.phase('prepare', f'mkdir -p {WORKTREE} && '
                   f'rsync -a --delete --exclude=.git --exclude=.vm --exclude=build '
                   f'/home/tester/repo/ {WORKTREE}/')
        if not capture_only:
            self.probe('baseline', 'baseline')
        self.phase('screen-unlocked', self.desktop_command(
            'kwriteconfig6 --file kscreenlockerrc --group Daemon --key Autolock false && '
            'kwriteconfig6 --file kscreenlockerrc --group Daemon --key LockOnResume false && '
            'sudo loginctl unlock-sessions'))
        self.phase('apps-profile', self.desktop_command('python3 tests/vm/desktop_apps.py --prepare'))
        self.phase('resolution', self.desktop_command('kscreen-doctor output.1.mode.3840x2160@60 output.1.scale.2'))
        if capture_only:
            self.phase('source-identity', f'cd {WORKTREE} && sha256sum VERSION src/scripts/installer_backend.py '
                       'src/scripts/defaults.json')

        self.phase('install', f'cd {WORKTREE} && sudo env MTTKDE_NO_CONFIRM=1 '
                   'MAC_TAHOE_NO_UPDATE_CHECK=true ./src/scripts/installer_backend.py install --dark', timeout=3600)
        dark = self.probe('dark', 'dark')
        if not capture_only and self.distro == 'kubuntu':
            self.launcher('launcher-installed')
        dark_apps = self.apps('apps-dark', 'dark')
        self.screenshot('dark', mode='dark', apps=dark_apps)
        self.phase('switch-light', self.desktop_command('~/.local/bin/mac-tahoe-theme-switch light'))
        light = self.probe('light', 'light')
        light_apps = self.apps('apps-light', 'light')
        if dark_apps['processes'] != light_apps['processes']:
            raise RuntimeError('Live theme switch restarted a tested application')
        if light['shell_pid'] != dark['shell_pid'] or light['compositor_pid'] != dark['compositor_pid']:
            raise RuntimeError('Live switch restarted Plasma or KWin')
        self.screenshot('light', mode='light', apps=light_apps)
        return dark

    def qualify(self):
        dark = self.installed_captures(capture_only=False)
        self.phase('switch-dark', self.desktop_command('~/.local/bin/mac-tahoe-theme-switch dark'))
        self.probe('dark-again', 'dark')
        self.apps('apps-dark-again', 'dark')
        self.run('sudo reboot', check=False)
        self.wait_desktop(dark['boot_id'])
        self.probe('reboot', 'dark')
        if self.distro == 'kubuntu':
            self.launcher('launcher-reboot')
        reboot_apps = self.apps('apps-reboot', 'dark')
        self.screenshot('reboot', mode='dark', apps=reboot_apps)
        self.phase('uninstall', f'cd {WORKTREE} && sudo env MTTKDE_NO_CONFIRM=1 '
                   'MAC_TAHOE_NO_UPDATE_CHECK=true ./src/scripts/installer_backend.py uninstall', timeout=900)
        self.probe('uninstalled', 'uninstalled')
        self.phase('firefox-after-uninstall', self.desktop_command(
            'python3 tests/vm/desktop_apps.py --check-browser'), timeout=90)
        self.screenshot('uninstalled')
        self.report.update(status='pass', finished=now())
        self.save()


def prepared_capture(distro, output, deadline, source):
    identity = str(uuid.uuid4())
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    guest = Guest(distro, output, port=port, identity=identity, deadline=deadline)
    env = os.environ | {
        'VM_SSH_PORT': str(port), 'VM_GUEST_UUID': identity,
        'VM_SOURCE_DIR': str(source),
        'VM_DISPLAY': os.environ.get('VM_DISPLAY', 'egl-headless'),
        'VM_CPUS': os.environ.get('VM_CPUS', '2'),
        'VM_MEM_MIB': os.environ.get('VM_MEM_MIB', '4096'),
        'VM_XRES': '3840', 'VM_YRES': '2160',
        'VM_CONSOLE_LOG': str(output / 'console.log'),
    }
    started = time.monotonic()
    process = None
    try:
        guest.remaining(1)
        with (output / 'boot.log').open('wb') as log:
            process = subprocess.Popen([str(VM), distro, '--prepared'], env=env,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            boot_limit = min(deadline, time.monotonic() + 90)
            while time.monotonic() < boot_limit:
                if process.poll() is not None:
                    raise RuntimeError('Prepared guest exited during boot; see boot.log')
                try:
                    result = guest.run('pgrep -u tester -x plasmashell', check=False, timeout=8)
                except subprocess.TimeoutExpired:
                    continue
                if result.returncode == 0:
                    guest.report['boot_seconds'] = round(time.monotonic() - started, 2)
                    break
                time.sleep(1)
            else:
                raise RuntimeError('Prepared guest did not reach Plasma within the boot budget')
        guest.installed_captures(capture_only=True)
        guest.report['status'] = 'pass'
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        guest.report.update(status='fail', error=str(error))
        print(f'{distro}: FAIL: {error}', flush=True)
    finally:
        if process is not None and process.poll() is None:
            # The launcher owns the disposable overlay and cleans it on SIGTERM.
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        guest.report.update(finished=now(), seconds=round(time.monotonic() - started, 2))
        guest.save()
    return guest.report


def capture_batch(targets, output, jobs, budget):
    listed = subprocess.check_output([str(VM), 'inventory'], text=True)
    inventory = dict((distro, state) for distro, state, _ in
                     (line.split('\t', 2) for line in listed.splitlines()))
    targets = list(PORTS) if targets == ['all'] else list(dict.fromkeys(targets))
    missing = [distro for distro in targets if inventory[distro] != 'prepared']
    ready = [distro for distro in targets if inventory[distro] == 'prepared']
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise RuntimeError(f'Capture batch output must be empty: {output}')
    print(f'Prepared: {len(ready)}/{len(targets)}; {jobs} concurrent; {budget}s wall budget', flush=True)
    if missing:
        print('Missing prepared images: ' + ', '.join(missing), flush=True)
    started = time.monotonic()
    deadline = started + budget
    results = []
    source_digest = None
    if ready:
        # Freeze the working tree once, including local edits, before any VM
        # can read it. Ignore display artifacts and unrelated build caches.
        scratch = Path(os.environ.get('VM_RUN_DIR', REPO / '.vm/run')).resolve()
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='capture-source.', dir=scratch) as staged:
            source = Path(staged)
            excludes = ['--exclude=/.git', '--exclude=/.vm', '--exclude=/build',
                        '--exclude=/src/screenshots']
            if scratch.is_relative_to(REPO) and scratch != REPO:
                excludes.append('--exclude=/' + str(scratch.relative_to(REPO)))
            elif source.is_relative_to(REPO):
                excludes.append('--exclude=/' + source.name)
            subprocess.run(
                ['rsync', '-a', *excludes, str(REPO) + '/', str(source) + '/'],
                check=True, timeout=max(0.01, deadline - time.monotonic()),
            )
            digest = hashlib.sha256()
            for path in sorted(source.rglob('*')):
                if path.is_symlink():
                    payload = b'link:' + os.fsencode(path.readlink())
                elif path.is_file():
                    with path.open('rb') as stream:
                        payload = hashlib.file_digest(stream, 'sha256').digest()
                else:
                    continue
                digest.update(os.fsencode(path.relative_to(source)) + b'\0' + payload)
            source_digest = digest.hexdigest()
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                futures = [pool.submit(prepared_capture, distro, output / distro, deadline, source)
                           for distro in ready]
                results = [future.result() for future in futures]
    passed = sum(result['status'] == 'pass' for result in results)
    elapsed = round(time.monotonic() - started, 2)
    report = dict(status='pass' if passed == len(targets) else 'incomplete',
                  seconds=elapsed, budget_seconds=budget,
                  passed=passed, requested=len(targets), missing=missing, results=results,
                  source_sha256=source_digest)
    (output / 'batch.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{passed}/{len(targets)} passed in {elapsed:.1f}s ({output / "batch.json"})', flush=True)
    return int(passed != len(targets))


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('distro', nargs='+', choices=(*PORTS, 'all'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--poweroff', action='store_true', help='Stop the guest after a passing run')
    parser.add_argument('--prepared', action='store_true', help='Boot prepared guests and run the capture batch')
    parser.add_argument('--jobs', type=int, default=4, help='Concurrent prepared guests (default: 4)')
    parser.add_argument('--budget', type=int, default=600, help='Batch wall budget in seconds (default: 600)')
    args = parser.parse_args()
    if args.prepared:
        if args.jobs < 1 or args.budget < 1 or ('all' in args.distro and args.distro != ['all']) or args.poweroff:
            parser.error('invalid capture batch options')
        try:
            return capture_batch(args.distro, args.output.resolve(), args.jobs, args.budget)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            print(f'Capture batch: {error}', file=sys.stderr)
            return 1
    if len(args.distro) != 1 or args.distro == ['all']:
        parser.error('lifecycle qualification requires one already running distro; use ./vm capture for batches')
    guest = Guest(args.distro[0], args.output.resolve())
    try:
        guest.qualify()
        if args.poweroff:
            guest.run('sudo poweroff', check=False)
    except (OSError, ValueError, RuntimeError, ET.ParseError, subprocess.SubprocessError) as error:
        guest.report.update(status='fail', error=str(error), finished=now())
        guest.save()
        print(f'{args.distro}: FAIL: {error}', flush=True)
        return 1
    print(f'{args.distro}: PASS ({guest.output})', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
