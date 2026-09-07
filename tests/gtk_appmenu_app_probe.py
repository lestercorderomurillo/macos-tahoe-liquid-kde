"""Opt-in startup A/B test using an extracted official ChatGPT Linux package.

Usage: python tests/gtk_appmenu_app_probe.py /path/to/usr/lib/chatgpt --output /tmp/results
No package download or installation. Bubblewrap isolates the network, processes,
home, display, and D-Bus session. The application keeps its own Chromium sandbox.
"""

import argparse
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def _inside(mode: str, seconds: int) -> dict:
    """Run only inside the namespace assembled by main()."""
    if not Path('/probe-hook.sh').is_file() or not Path('/results').is_dir():
        raise RuntimeError('This helper requires the probe namespace')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    home = Path('/home/test')
    home.mkdir(parents=True)
    runtime = home / 'runtime'
    runtime.mkdir(mode=0o700)
    config = home / '.config/gtk-3.0'
    config.mkdir(parents=True)
    (config / 'settings.ini').write_text('[Settings]\ngtk-modules=appmenu-gtk-module\n')
    env = dict(os.environ, HOME=str(home), XDG_RUNTIME_DIR=str(runtime),
               XDG_CONFIG_HOME=str(home / '.config'), XDG_CACHE_HOME=str(home / '.cache'),
               XDG_DATA_HOME=str(home / '.local/share'), DISPLAY=':42',
               XDG_CURRENT_DESKTOP='KDE', DESKTOP_SESSION='plasma',
               GIO_USE_VFS='local', GIO_USE_VOLUME_MONITOR='unix', NO_AT_BRIDGE='1',
               QT_QPA_PLATFORM='xcb', GDK_BACKEND='x11')
    if mode == 'protected':
        env['GTK3_MODULES'] = subprocess.check_output(
            ['sh', '-c', '. /probe-hook.sh; printf "%s" "$GTK3_MODULES"'],
            env=env, text=True, timeout=5)
    server = subprocess.Popen(
        ['Xvfb', ':42', '-screen', '0', '1280x800x24', '-nolisten', 'tcp'],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            if server.poll() is not None:
                raise RuntimeError('Private Xvfb failed to start')
            if subprocess.run(['xdpyinfo'], env=env, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=2).returncode == 0:
                break
            time.sleep(.05)
        else:
            raise RuntimeError('Private Xvfb startup timed out')
        with Path('/results/application.log').open('w') as log:
            app = subprocess.Popen(
                ['dbus-run-session', '--', '/opt/chatgpt/ChatGPT',
                 '--disable-breakpad', '--disable-crash-reporter',
                 '--user-data-dir=/home/test/profile'],
                env=env, stdout=log, stderr=log, start_new_session=True)
            try:
                started = time.monotonic()
                module_seen = False
                visible_window = False
                windows = ''
                while time.monotonic() - started < seconds and app.poll() is None:
                    for proc in Path('/proc').glob('[0-9]*'):
                        try:
                            if (proc / 'comm').read_text().strip() == 'ChatGPT':
                                module_seen |= 'libappmenu-gtk-module.so' in (proc / 'maps').read_text()
                        except OSError:
                            pass
                    windows = subprocess.check_output(
                        ['xwininfo', '-root', '-tree'], env=env, text=True, timeout=2)
                    visible_window = False
                    for match in re.finditer(
                            r'(0x[0-9a-f]+) "ChatGPT":[^\n]*?\s(\d+)x(\d+)[+-]', windows):
                        if int(match[2]) >= 300 and int(match[3]) >= 200:
                            details = subprocess.check_output(
                                ['xwininfo', '-id', match[1]], env=env, text=True, timeout=2)
                            visible_window |= 'Map State: IsViewable' in details
                    time.sleep(.2)
                return {'mode': mode, 'seconds': round(time.monotonic() - started, 2),
                        'exit': app.poll(), 'visible_window': visible_window,
                        'appmenu_observed': module_seen, 'windows': windows}
            finally:
                if app.poll() is None:
                    os.killpg(app.pid, signal.SIGTERM)
                    try:
                        app.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(app.pid, signal.SIGKILL)
                        app.wait(timeout=3)
    finally:
        server.terminate()
        try:
            server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app_dir', type=Path, help='Extracted directory containing ChatGPT')
    parser.add_argument('--output', required=True, type=Path, help='New directory for logs and JSON')
    parser.add_argument('--seconds', type=int, default=15)
    parser.add_argument('--runs', type=int, default=3)
    args = parser.parse_args()
    if not 12 <= args.seconds <= 300 or not 1 <= args.runs <= 10:
        parser.error('Use 12–300 seconds and 1–10 runs')
    application = args.app_dir.resolve()
    if not (application / 'ChatGPT').is_file():
        parser.error('The extracted ChatGPT binary is missing')
    for tool in ('bwrap', 'Xvfb', 'xdpyinfo', 'xwininfo', 'dbus-run-session', 'sh'):
        if not shutil.which(tool):
            parser.error(f'Missing required tool: {tool}')
    python = Path('/usr/bin/python3')
    if not python.is_file():
        parser.error('The isolated probe requires /usr/bin/python3')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/scripts'))
    from distro import gtk3_appmenu_module
    from steps.globalmenu import _gtk_appmenu_environment

    module = gtk3_appmenu_module()
    if module is None:
        parser.error('No native GTK3 appmenu module found')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    results = []
    with tempfile.TemporaryDirectory(prefix='mttkde-app-probe-') as tmp:
        staging = Path(tmp)
        (staging / 'hook.sh').write_text(_gtk_appmenu_environment(module))
        (staging / 'passwd').write_text(f'test:x:{os.getuid()}:{os.getgid()}:Test:/home/test:/bin/sh\n')
        (staging / 'group').write_text(f'test:x:{os.getgid()}:\n')
        command = ['bwrap', '--unshare-all', '--die-with-parent', '--new-session',
                   '--ro-bind', '/usr', '/usr', '--proc', '/proc', '--dev', '/dev',
                   '--tmpfs', '/tmp', '--tmpfs', '/home', '--dir', '/run', '--dir', '/etc']
        for item in ('/bin', '/sbin', '/lib', '/lib64'):
            path = Path(item)
            if path.is_symlink():
                command += ['--symlink', os.readlink(path), item]
            elif path.is_dir():
                command += ['--ro-bind', item, item]
        for item in ('fonts', 'ld.so.cache', 'os-release'):
            if Path('/etc', item).exists():
                command += ['--ro-bind', '/etc/' + item, '/etc/' + item]
        for item in ('passwd', 'group'):
            command += ['--ro-bind', str(staging / item), '/etc/' + item]
        command += ['--ro-bind', str(application), '/opt/chatgpt',
                    '--ro-bind', str(Path(__file__).resolve()), '/probe.py',
                    '--ro-bind', str(staging / 'hook.sh'), '/probe-hook.sh',
                    '--clearenv', '--setenv', 'PATH', '/usr/bin', '--setenv', 'LANG', 'C.UTF-8']
        for attempt in range(1, args.runs + 1):
            for mode in ('control', 'protected'):
                folder = output / f'{attempt}-{mode}'
                folder.mkdir()
                result = subprocess.run(
                    command + ['--bind', str(folder), '/results', '--', str(python),
                               '/probe.py', '--inside', mode, str(args.seconds)],
                    capture_output=True, text=True, timeout=args.seconds + 20, check=True)
                data = json.loads(result.stdout)
                data['attempt'] = attempt
                (folder / 'result.json').write_text(json.dumps(data, indent=2) + '\n')
                results.append(data)
                print(f"{attempt} {mode}: exit={data['exit']}, seconds={data['seconds']}, "
                      f"visible_window={data['visible_window']}, appmenu={data['appmenu_observed']}", flush=True)
    (output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    for data in results:
        if data['mode'] == 'control':
            if data['exit'] != 139 or data['visible_window']:
                print('Control did not reproduce the startup SIGSEGV; inspect the logs.')
                return 2
        elif data['exit'] is not None or not data['visible_window'] or not data['appmenu_observed']:
            print('Protected launch failed validation; inspect the logs.')
            return 1
    print(f'PASS: {args.runs} crashes versus {args.runs} protected visible launches. Logs: {output}')
    return 0


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--inside':
        print(json.dumps(_inside(sys.argv[2], int(sys.argv[3]))))
    else:
        raise SystemExit(main())
