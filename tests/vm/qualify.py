#!/usr/bin/env python3
"""Exercise install, live mode switches, reboot and uninstall in a disposable VM.

Start the guest with ./vm first. SSH must accept tester/tester on its loopback
port, with passwordless sudo and the repository mounted read-only at ~/repo.
Artifacts are retained even when a phase fails. A failed phase never qualifies
that distribution. This harness never installs the theme on the host.
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

PORTS = dict(arch=2221, cachyos=2222, manjaro=2223, endeavouros=2224,
             garuda=2225, fedora=2226, nobara=2227, opensuse=2228,
             neon=2231, debian=2232, artix=2233, kubuntu=2234)
WORKTREE = '/home/tester/macos-tahoe-liquid-kde'


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
    def __init__(self, distro: str, output: Path):
        self.distro = distro
        self.output = output
        self.output.mkdir(parents=True, exist_ok=True)
        self.ssh = ['sshpass', '-e', 'ssh', '-o', 'StrictHostKeyChecking=no',
                    '-o', 'UserKnownHostsFile=/dev/null', '-o', 'ConnectTimeout=5',
                    '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3',
                    '-p', str(PORTS[distro]), 'tester@127.0.0.1']
        self.env = {**os.environ, 'SSHPASS': os.environ.get('VM_PASSWORD', 'tester')}
        self.report = {'distro': distro, 'started': now(), 'status': 'running', 'phases': []}

    def run(self, command: str, *, timeout: int = 120, check: bool = True):
        # SSH/PAM may export a different bus from the logged-in Plasma session
        # (notably OpenRC). Let the desktop recovery code discover that session.
        command = 'unset DBUS_SESSION_BUS_ADDRESS DISPLAY WAYLAND_DISPLAY XDG_SESSION_TYPE; ' + command
        result = subprocess.run([*self.ssh, 'bash -c ' + shlex.quote(command)], env=self.env,
                                capture_output=True, timeout=timeout)
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
        wrapped = (f'( {command} ) > {guest_log} 2>&1; '
                   f'result=$?; cat {guest_log}; exit "$result"')
        result = self.run(wrapped, timeout=timeout, check=False)
        (self.output / f'{name}.log').write_bytes(result.stdout + result.stderr)
        self.report['phases'].append(dict(name=name, started=started, finished=now(),
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

    def qualify(self):
        self.assert_identity()
        self.phase('prepare', f'mkdir -p {WORKTREE} && '
                   f'rsync -a --delete --exclude=.git --exclude=.vm --exclude=build '
                   f'/home/tester/repo/ {WORKTREE}/')
        self.probe('baseline', 'baseline')
        self.phase('screen-unlocked', self.desktop_command(
            'kwriteconfig6 --file kscreenlockerrc --group Daemon --key Autolock false && '
            'kwriteconfig6 --file kscreenlockerrc --group Daemon --key LockOnResume false && '
            'sudo loginctl unlock-sessions'))
        self.phase('apps-profile', self.desktop_command('python3 tests/vm/desktop_apps.py --prepare'))
        self.phase('resolution', self.desktop_command('kscreen-doctor output.1.mode.3840x2160@60 output.1.scale.2'))
        self.phase('install', f'cd {WORKTREE} && sudo env MTTKDE_NO_CONFIRM=1 '
                   'MAC_TAHOE_NO_UPDATE_CHECK=true ./src/scripts/installer_backend.py install --dark', timeout=3600)
        dark = self.probe('dark', 'dark')
        if self.distro == 'kubuntu':
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


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('distro', choices=PORTS)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--poweroff', action='store_true', help='Stop the guest after a passing run')
    args = parser.parse_args()
    guest = Guest(args.distro, args.output.resolve())
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
