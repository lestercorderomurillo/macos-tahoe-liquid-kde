"""Release capture operations; executable only in the disposable QEMU guest."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid


def run(*args, timeout=60):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, timeout=timeout).strip()
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f'{args[0]} failed:\n{exc.output}') from exc


def session():
    from screenshot_checks import require_virtual_machine
    require_virtual_machine()
    if run('cat', '/sys/class/dmi/id/product_name') != 'MTTKDE release capture':
        raise RuntimeError('This is not the release capture VM')
    pid = run('pgrep', '-u', str(os.getuid()), '-x', 'plasmashell').split()[0]
    os.environ.update(dict(p.decode().split('=', 1) for p in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0') if b'=' in p))
    os.environ.update(LANG='en_US.UTF-8', LANGUAGE='en', LC_ALL='en_US.UTF-8', TZ='UTC')


def plasma(script):
    return run('qdbus6', 'org.kde.plasmashell', '/PlasmaShell', 'org.kde.PlasmaShell.evaluateScript', script)


def windows(script=''):
    from PyQt6.QtCore import QCoreApplication, QObject, QTimer, pyqtClassInfo, pyqtSlot
    from PyQt6.QtDBus import QDBusConnection, QDBusInterface
    app = QCoreApplication.instance() or QCoreApplication([])
    bus = QDBusConnection.sessionBus()
    service = f'org.mttkde.ReleaseCapture.p{os.getpid()}'
    @pyqtClassInfo('D-Bus Interface', 'org.mttkde.ReleaseCapture')
    class Recorder(QObject):
        result = None
        @pyqtSlot(str)
        def record(self, text):
            self.result = json.loads(text)
            app.quit()
    recorder = Recorder()
    assert bus.registerService(service)
    assert bus.registerObject('/Probe', recorder, QDBusConnection.RegisterOption.ExportAllSlots)
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'capture.js'
        path.write_text(script + 'callDBus(' + json.dumps(service) + ',"/Probe","org.mttkde.ReleaseCapture","record",'
                        'JSON.stringify(workspace.windowList().filter(w=>!w.minimized).map(w=>({'
                        'caption:w.caption,resourceClass:String(w.resourceClass),type:w.windowType,'
                        'appletPopup:w.appletPopup,active:w===workspace.activeWindow,geometry:w.frameGeometry}))));')
        api = QDBusInterface('org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting', bus)
        loaded = api.call('loadScript', str(path), service).arguments()
        assert loaded and isinstance(loaded[0], int)
        try:
            QDBusInterface('org.kde.KWin', f'/Scripting/Script{loaded[0]}', 'org.kde.kwin.Script', bus).call('run')
            QTimer.singleShot(5000, app.quit)
            app.exec()
        finally:
            api.call('unloadScript', service)
            bus.unregisterObject('/Probe')
            bus.unregisterService(service)
    if recorder.result is None:
        raise RuntimeError('KWin did not report capture windows')
    return recorder.result


def close():
    windows('workspace.windowList().filter(w=>w.caption.includes("About This Computer (preview)") || '
            'String(w.resourceClass).toLowerCase().includes("nautilus")).forEach(w=>w.closeWindow());')


def clean_desktop():
    """Keep running test applications out of the documentation Dock."""
    session()
    windows('workspace.windowList().filter(w=>w.windowType===0).forEach(w=>w.closeWindow());')
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        # Include minimized windows: their applications still appear in the Dock.
        open_apps = windows('workspace.windowList().filter(w=>w.windowType===0).forEach(w=>w.minimized=false);')
        if not any(w['type'] == 0 for w in open_apps):
            return
        time.sleep(.3)
    raise RuntimeError('Applications remain open; refusing a Dock capture with extra icons')


def setup(repo, profile, edition):
    from release_screenshots import EDITIONS
    session()
    packages = run('dpkg-query', '-W', '-f=${Package}=${Version}\n')
    run('sudo', 'timedatectl', 'set-ntp', 'false')
    run('sudo', 'timedatectl', 'set-timezone', profile['timezone'])
    package, preset, _ = EDITIONS[edition]
    (repo / 'src/scripts/defaults.json').write_text(json.dumps({'wallpaper': package, 'launcher_preset': preset}) + '\n')
    from steps import rounded_corners
    cached_archive = Path('/opt/mttkde-capture') / rounded_corners.ARCHIVE.name
    if cached_archive.is_file():
        if not rounded_corners._archive_is_valid(cached_archive):
            raise RuntimeError('The reference VM contains an invalid Rounded Corners archive')
        rounded_corners.ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cached_archive, rounded_corners.ARCHIVE)
    # Every edition starts from the same read-only VM image, then installs the
    # exact exported release sources. No package upgrade or host install occurs.
    from installer_choices import defaults
    # The fixed profile explicitly recreates its layout even if the sealed VM
    # contains an earlier installation. Normal reinstalls preserve it by default.
    choices = defaults() | {'appearance': 'light', 'reset_layout': True}
    command = ['sudo', 'env', 'MAC_TAHOE_NO_UPDATE_CHECK=true', 'MTTKDE_NO_CONFIRM=1',
               str(repo / 'src/scripts/installer_backend.py'), 'install',
               '--wizard-options', json.dumps(choices)]
    with (repo.parent / 'install.log').open('w') as log:
        subprocess.run(command, cwd=repo, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=1800)
    if not all(path.is_file() for path in rounded_corners.build_artifacts()):
        raise RuntimeError('Rounded Corners was not built from this release; capture cannot use the old VM plugin')
    session()
    if run('dpkg-query', '-W', '-f=${Package}=${Version}\n') != packages:
        raise RuntimeError('Installation changed the pinned package inventory; prepare a new reference VM')
    # Use a mode by dimensions, never an unstable display-mode numeric index.
    run('kscreen-doctor', 'output.Virtual-1.mode.3840x2160@60', 'output.Virtual-1.scale.2')
    run('kwriteconfig6', '--file', 'kscreenlockerrc', '--group', 'Daemon', '--key', 'Autolock', 'false')
    run('kwriteconfig6', '--file', 'kdeglobals', '--group', 'KDE', '--key', 'AnimationDurationFactor', '0')
    pins = plasma('var saved=[]; panels().forEach(p=>p.widgets().forEach(w=>{if(w.type.includes("icontasks")) {'
                  'w.currentConfigGroup=["General"];w.writeConfig("launchers",' + json.dumps(profile['pins']) + ');'
                  'saved.push(w.readConfig("launchers"));}})); print(JSON.stringify(saved));')
    # Plasma's scripting readConfig serializes its QStringList as CSV.
    if json.loads(pins) != [','.join(profile['pins'])]:
        raise RuntimeError('Capture Dock did not retain the requested application pins')
    folder = Path.home() / 'Documents'
    folder.mkdir(exist_ok=True)
    # Refuse unexpected fixture data rather than including private guest files.
    for path in folder.iterdir():
        if path.name not in profile['documents'] or not path.is_dir() or any(path.iterdir()):
            raise RuntimeError(f'Unexpected Documents fixture: {path.name}')
    for name in profile['documents']:
        (folder / name).mkdir(exist_ok=True)
    run('sudo', 'date', '--set', profile['clock'])
    return {'packages': packages, 'kwin': run('kwin_wayland', '--version'),
            'plasma': run('plasmashell', '--version'),
            'compositor': run('qdbus6', 'org.kde.KWin', '/KWin', 'org.kde.KWin.supportInformation')}


def mode(repo, requested):
    from screenshot_checks import wait_for_session
    close()
    # The installed command carries the edition and the user's icon choices;
    # importing the source module would silently fall back to the base icons.
    run(str(Path.home() / '.local/bin/mac-tahoe-theme-switch'), requested, timeout=180)
    return wait_for_session(requested)


def launch(repo, name):
    from distro import user_service_manager_command
    commands = {'finder': ['nautilus', '--new-window', str(Path.home() / 'Documents')],
                'about': ['qml6', str(repo / 'src/scripts/preview_about.qml')]}
    log = repo.parent / (name + '.log')
    env = dict(os.environ, QT_FORCE_STDERR_LOGGING='1', MAC_TAHOE_ABOUT_MOCK='1')
    unit = 'mttkde-release-capture-' + name
    stop = user_service_manager_command('stop', unit + '.service')
    if stop is None:
        raise RuntimeError('The pinned capture guest must provide the reference user service manager')
    subprocess.run(stop, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    if name == 'finder':
        probe = ['pgrep', '-u', str(os.getuid()), '-x', 'nautilus']
        if subprocess.run(probe, stdout=subprocess.DEVNULL).returncode == 0:
            subprocess.run(['nautilus', '--quit'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            deadline = time.monotonic() + 5
            while subprocess.run(probe, stdout=subprocess.DEVNULL).returncode == 0:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Previous Files process did not close')
                time.sleep(.2)
    log.write_text('')
    # SSH logind scopes can terminate even detached children. A transient
    # guest service keeps the application alive across capture commands.
    command = ['systemd-run', '--user', '--collect', '--unit=' + unit,
               '-p', 'StandardOutput=append:' + str(log), '-p', 'StandardError=append:' + str(log)]
    for key in ('WAYLAND_DISPLAY', 'DISPLAY', 'DBUS_SESSION_BUS_ADDRESS', 'XDG_RUNTIME_DIR',
                'QT_QPA_PLATFORMTHEME', 'QT_FORCE_STDERR_LOGGING', 'LANG', 'LC_ALL', 'TZ'):
        if key in env:
            command.append('--setenv=' + key + '=' + env[key])
    run(*command, *commands[name])
    caption = 'Documents' if name == 'finder' else 'About This Computer (preview)'
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if any(w['caption'] == caption for w in windows()):
            if name != 'about' or 'MTTKDE_ABOUT_READY' in log.read_text():
                return
        time.sleep(.3)
    raise RuntimeError(f'{name} never became ready')


def arrange(placements):
    script = ''
    for caption, geometry in placements.items():
        script += ('workspace.windowList().filter(w=>w.caption===' + json.dumps(caption) + ').forEach(w=>{'
                   'w.minimized=false;const geometry=' + json.dumps(geometry) + ';'
                   'const bounds=workspace.clientArea(KWin.FullArea,w);'
                   'bounds.x=geometry.x;bounds.y=geometry.y;'
                   'bounds.width=geometry.width;bounds.height=geometry.height;'
                   'w.frameGeometry=bounds;workspace.activeWindow=w;});')
    windows(script)


def wizard(repo, page):
    from release_screenshots import INSTALLER_PAGES
    if page not in INSTALLER_PAGES:
        raise ValueError(page)
    folder = repo.parent / 'wizard-capture'
    folder.mkdir(exist_ok=True)
    state = folder / 'state.json'
    current = json.loads(state.read_text()) if state.exists() else {}
    pid = current.get('pid')
    live = False
    if isinstance(pid, int):
        try:
            live = str(repo / 'src/scripts/release_capture_wizard.py').encode() in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        except OSError:
            pass
    if not live:
        state.unlink(missing_ok=True)
        command = ['systemd-run', '--user', '--collect', '--unit=mttkde-wizard-' + uuid.uuid4().hex[:8],
                   '-p', 'StandardOutput=append:' + str(folder / 'wizard.log'),
                   '-p', 'StandardError=append:' + str(folder / 'wizard.log')]
        for key in ('WAYLAND_DISPLAY', 'DISPLAY', 'DBUS_SESSION_BUS_ADDRESS', 'XDG_RUNTIME_DIR',
                    'XDG_CONFIG_DIRS', 'QT_QPA_PLATFORMTHEME', 'LANG', 'LC_ALL', 'TZ'):
            if key in os.environ:
                command.append('--setenv=' + key + '=' + os.environ[key])
        run(*command, 'python3', str(repo / 'src/scripts/release_capture_wizard.py'), str(repo))
    request = uuid.uuid4().hex
    pending = folder / 'page.tmp'
    pending.write_text(json.dumps({'page': page, 'request': request}))
    pending.replace(folder / 'page.json')
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        current = json.loads(state.read_text()) if state.exists() else {}
        if current.get('request') == request:
            arrange({current['title']: {'x': 550, 'y': 225, 'width': 820, 'height': 600}})
            return current
        time.sleep(.2)
    raise RuntimeError('Installer capture page did not become ready: ' + page)


def capture(repo, profile, edition, requested, case):
    from PIL import Image
    from release_screenshots import EDITIONS, digest, verify_desktop_window, verify_icon_appearance
    from screenshot_checks import wait_for_session, check_files_pixels
    state = wait_for_session(requested)
    state['Icons'] = run('kreadconfig6', '--file', 'kdeglobals', '--group', 'Icons', '--key', 'Theme')
    verify_icon_appearance(f'{edition}-{requested}-{case}', {'appearance': state})
    wallpaper = json.loads(plasma('print(JSON.stringify(desktops().map(d=>{'
        'd.currentConfigGroup=["Wallpaper","org.kde.image","General"];return d.readConfig("Image");})));'))
    expected_wallpaper = (Path.home() / '.local/share/wallpapers' / EDITIONS[edition][0]).as_uri()
    if len(wallpaper) != 1 or not (wallpaper[0] == expected_wallpaper or wallpaper[0].startswith(expected_wallpaper + '/')):
        raise RuntimeError(f'Wrong edition wallpaper: {wallpaper}')
    presets = json.loads(plasma('var presets=[];panels().forEach(p=>p.widgets().forEach(w=>{'
        'if(w.type==="org.kde.mac-tahoe-liquid-kde.launcher"){'
        'w.currentConfigGroup=["General"];presets.push(Number(w.readConfig("launcherPreset")));}}));'
        'print(JSON.stringify(presets));'))
    if presets != [EDITIONS[edition][1]]:
        raise RuntimeError(f'Wrong launcher preset: {presets}')
    run('sudo', 'date', '--set', profile['clock'])
    target = repo.parent / 'frame.png'
    if case in ('finder', 'showcase', 'about'):
        verify_desktop_window(case, windows())
    previous = None
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        run('spectacle', '-b', '-n', '-f', '-o', str(target))
        with Image.open(target) as image:
            if list(image.size) != profile['resolution']:
                raise RuntimeError(f'Unexpected capture dimensions: {image.size}')
            current = image.convert('RGB').tobytes()
        if previous == current:
            break
        previous = current
        time.sleep(.3)
    else:
        raise RuntimeError('Capture did not settle to identical consecutive frames')
    observed = windows()
    shell = [w for w in observed if 'plasmashell' in w['resourceClass']]
    installer_state = None
    if case.startswith('installer-'):
        installer_state = json.loads((repo.parent / 'wizard-capture/state.json').read_text())
        if installer_state['page'] != case.removeprefix('installer-'):
            raise RuntimeError('Installer page changed before capture')
        chosen = [w for w in observed if w['type'] == 0 and w['active']
                  and w['caption'] == installer_state['title']]
        expected = 1
    elif case == 'launcher':
        chosen = [w for w in shell if w['appletPopup']]
        expected = EDITIONS[edition][1]
    elif case == 'dock':
        chosen = [w for w in shell if w['type'] == 2 and w['geometry']['y'] > 100]
        expected = 1
    elif case in ('menu', 'context'):
        chosen = [w for w in shell if w['type'] not in (1, 2)]
        expected = 1
    else:
        chosen = [verify_desktop_window(case, observed)]
        expected = 1
    if len(chosen) != expected:
        raise RuntimeError(f'{case}: expected {expected} windows, found {chosen}; observed {observed}')
    crop = None
    if case not in ('launcher', 'showcase'):
        g = chosen[0]['geometry']
        scale = profile['scale']
        crop = [max(0, round(g['x'] * scale) - 28), max(0, round(g['y'] * scale) - 28),
                min(3840, round((g['x'] + g['width']) * scale) + 28),
                min(2160, round((g['y'] + g['height']) * scale) + 28)]
    pixels = None
    if case in ('finder', 'showcase'):
        with Image.open(target) as image:
            pixels = check_files_pixels(image, requested, observed, profile['scale'])
    identity = run('qdbus6', 'org.kde.KWin', '/Effects', 'org.kde.kwin.Effects.debug', 'liquidglass', '')
    return dict(sha256=digest(target), appearance=state, effect_build=identity, crop=crop,
                wallpaper=EDITIONS[edition][0], wallpaper_uri=wallpaper[0], launcher_preset=presets[0], windows=observed,
                files_pixels=pixels, stable_frames=True, window_verified=True,
                installer_page=installer_state['page'] if installer_state else None,
                installer_edition=installer_state['edition'] if installer_state else None)


def boot(repo):
    # Use the existing Plymouth pixel probe. Its temporary 4K wrapper remains
    # inside the disposable guest and never changes shipped theme sources.
    folder = repo.parent / 'bin'
    folder.mkdir(exist_ok=True)
    shim = folder / 'magick'
    shim.write_text('#!/bin/sh\nif [ "$1" = identify ]; then shift; exec /usr/bin/identify "$@"; fi\nexec /usr/bin/convert "$@"\n')
    shim.chmod(0o755)
    for command in ('plymouthd', 'identify', 'convert', 'xwininfo', 'scrot', 'Xvfb'):
        if not shutil.which(command):
            raise RuntimeError(f'Capture VM is missing {command}')
    script = repo / 'tests/vm/render-release.sh'
    script.write_text((repo / 'tests/vm/render.sh').read_text().replace('1920x1080', '3840x2160')
                      .replace('splash plymouth.theme=', 'splash plymouth.ignore-serial-consoles plymouth.theme='))
    config = repo.parent / 'plymouthd.conf'
    config.write_text('[Daemon]\nTheme=MacTahoeLiquidKde\nShowDelay=0\n')
    run('sudo', 'install', '-m', '644', str(config), '/etc/plymouth/plymouthd.conf')
    with (repo.parent / 'plymouth.log').open('w') as log:
        subprocess.run(['sudo', 'env', 'PATH=' + str(folder) + ':' + os.environ['PATH'], 'bash', str(script)],
                       cwd=repo, stdout=log, stderr=subprocess.STDOUT, timeout=180, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('action', choices=('setup', 'mode', 'launch', 'launcher', 'arrange', 'close', 'clean-desktop', 'wizard', 'plasma', 'capture', 'boot'))
    parser.add_argument('args', nargs='*')
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo / 'src/scripts'))
    session()
    profile = json.loads(args.profile.read_text())
    result = None
    if args.action == 'setup': result = setup(args.repo, profile, args.args[0])
    elif args.action == 'mode': result = mode(args.repo, args.args[0])
    elif args.action == 'launch': launch(args.repo, args.args[0])
    elif args.action == 'launcher': run('qdbus6', 'org.kde.plasmashell', '/PlasmaShell', 'org.kde.PlasmaShell.activateLauncherMenu')
    elif args.action == 'arrange': arrange(json.loads(args.args[0]))
    elif args.action == 'close': close()
    elif args.action == 'clean-desktop': clean_desktop()
    elif args.action == 'wizard': result = wizard(args.repo, args.args[0])
    elif args.action == 'plasma': result = plasma(args.args[0])
    elif args.action == 'capture': result = capture(args.repo, profile, *args.args)
    elif args.action == 'boot': boot(args.repo)
    print('MTTKDE_RESULT=' + json.dumps(result))


if __name__ == '__main__':
    main()
